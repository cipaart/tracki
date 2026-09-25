"""Stahovani na pozadi.

Vlakno mluvi s UI vyhradne pres frontu udalosti - zadne volani tkinteru z
jineho vlakna, jinak by aplikace nahodne padala. UI si frontu vybira v
pravidelnem tiku (viz ui/main_window.py).
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yt_dlp
from yt_dlp.utils import DownloadCancelled

from .. import paths
from . import naming, tagging
from .config import DEFAULT_QUALITY, Settings
from .errors import TrackiError, clean_message, from_exception
from .urls import ParsedUrl


# --- udalosti ---------------------------------------------------------------
@dataclass
class Resolving:
    url: str


@dataclass
class PlaylistResolved:
    title: str
    total: int


@dataclass
class ItemStarted:
    index: int          # 1-based
    total: int
    title: str


@dataclass
class Progress:
    index: int
    total: int
    percent: float      # 0..100 pro aktualni polozku
    downloaded: int = 0
    total_bytes: int = 0
    speed: float | None = None
    eta: int | None = None


@dataclass
class Converting:
    index: int
    total: int
    title: str


@dataclass
class ItemFinished:
    index: int
    total: int
    title: str
    path: Path
    size: int


@dataclass
class ItemSkipped:
    index: int
    total: int
    title: str
    path: Path


@dataclass
class ItemFailed:
    index: int
    total: int
    title: str
    error: TrackiError


@dataclass
class JobFinished:
    downloaded: list[ItemFinished] = field(default_factory=list)
    skipped: list[ItemSkipped] = field(default_factory=list)
    failed: list[ItemFailed] = field(default_factory=list)
    cancelled: bool = False

    @property
    def total(self) -> int:
        return len(self.downloaded) + len(self.skipped) + len(self.failed)


@dataclass
class JobFailed:
    error: TrackiError


Event = (
    Resolving | PlaylistResolved | ItemStarted | Progress | Converting
    | ItemFinished | ItemSkipped | ItemFailed | JobFinished | JobFailed
)


@dataclass
class DownloadRequest:
    parsed: ParsedUrl
    dest_dir: Path
    quality: str = DEFAULT_QUALITY
    write_tags: bool = True
    embed_cover: bool = True
    clean_titles: bool = True
    existing_policy: str = "rename"

    @classmethod
    def from_settings(
        cls, parsed: ParsedUrl, settings: Settings, quality: str | None = None
    ) -> "DownloadRequest":
        return cls(
            parsed=parsed,
            dest_dir=settings.download_dir,
            quality=quality or settings.quality,
            write_tags=settings.write_tags,
            embed_cover=settings.embed_cover,
            clean_titles=settings.clean_titles,
            existing_policy=settings.existing_policy,
        )


class _Log:
    """Sbira hlaseni yt-dlp, aby se daly ukazat jako technicky detail."""

    def __init__(self, limit: int = 60) -> None:
        self.lines: list[str] = []
        self.limit = limit

    def _add(self, message: str) -> None:
        text = clean_message(str(message))
        if text:
            self.lines.append(text)
            if len(self.lines) > self.limit:
                del self.lines[0]

    # yt-dlp logger interface
    def debug(self, msg: str) -> None:
        if not str(msg).startswith("[debug] "):
            self._add(msg)

    def info(self, msg: str) -> None:
        self._add(msg)

    def warning(self, msg: str) -> None:
        self._add(msg)

    def error(self, msg: str) -> None:
        self._add(msg)

    def tail(self, count: int = 8) -> str:
        return "\n".join(self.lines[-count:])


class DownloadJob(threading.Thread):
    """Jedno stahovani (video nebo cely playlist) v samostatnem vlakne."""

    PROGRESS_INTERVAL = 0.12   # s; castejsi updaty UI nestihne a k nicemu nejsou

    def __init__(self, request: DownloadRequest, events: "queue.Queue[Event]") -> None:
        super().__init__(name="tracki-download", daemon=True)
        self.request = request
        self.events = events
        self._cancel = threading.Event()
        self._log = _Log()
        self._last_progress = 0.0
        self._index = 0
        self._total = 1
        self._current_title = ""

    # --- rizeni -----------------------------------------------------------
    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    # --- beh --------------------------------------------------------------
    def run(self) -> None:
        try:
            self._run()
        except DownloadCancelled:
            self._emit(JobFinished(cancelled=True))
        except BaseException as exc:  # noqa: BLE001 - vlakno nesmi nikdy propadnout
            error = from_exception(exc)
            if not error.detail:
                error.detail = self._log.tail()
            self._emit(JobFailed(error))

    def _run(self) -> None:
        ffmpeg = paths.ffmpeg_path()
        if not ffmpeg:
            raise TrackiError("FFMPEG_MISSING")

        dest = self.request.dest_dir
        try:
            dest.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise TrackiError("DEST_NOT_WRITABLE", str(exc),
                              params={"path": str(dest)}) from exc
        if not _writable(dest):
            raise TrackiError("DEST_NOT_WRITABLE", params={"path": str(dest)})

        self._emit(Resolving(self.request.parsed.url))
        entries = self._resolve_entries(ffmpeg)
        self._total = len(entries)

        result = JobFinished()
        for position, entry in enumerate(entries, start=1):
            self._index = position
            try:
                self._check_cancel()
                outcome = self._download_one(entry, position, ffmpeg)
            except DownloadCancelled:
                # Zruseni uprostred playlistu: uz stazene polozky si ponechame
                # a nahlasime je, at je uzivatel vidi v historii.
                result.cancelled = True
                break
            if isinstance(outcome, ItemFinished):
                result.downloaded.append(outcome)
            elif isinstance(outcome, ItemSkipped):
                result.skipped.append(outcome)
            elif isinstance(outcome, ItemFailed):
                result.failed.append(outcome)

        result.cancelled = result.cancelled or self.cancelled
        self._emit(result)

    # --- kroky ------------------------------------------------------------
    def _resolve_entries(self, ffmpeg: str) -> list[dict[str, Any]]:
        """U videa vrati jeden zaznam, u playlistu seznam jeho polozek."""
        parsed = self.request.parsed
        if not parsed.is_playlist:
            return [{"url": parsed.url, "title": ""}]

        options = self._base_options(ffmpeg) | {
            "extract_flat": "in_playlist",
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            try:
                info = ydl.extract_info(parsed.url, download=False)
            except Exception as exc:  # noqa: BLE001
                raise self._translate(exc) from exc

        if not info:
            raise TrackiError("PLAYLIST_EMPTY", self._log.tail())

        raw_entries = [e for e in (info.get("entries") or []) if e]
        entries = []
        for entry in raw_entries:
            url = entry.get("url") or entry.get("webpage_url")
            video_id = entry.get("id")
            if not url and video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
            if not url:
                continue
            # Nedostupne polozky maji v flat vypisu nulovou delku a titulek
            # "[Private video]" / "[Deleted video]" - poznam je az pri stahovani.
            entries.append({"url": url, "title": entry.get("title") or ""})

        if not entries:
            raise TrackiError("PLAYLIST_EMPTY", self._log.tail())

        self._emit(PlaylistResolved(title=info.get("title") or "", total=len(entries)))
        return entries

    def _download_one(
        self, entry: dict[str, Any], position: int, ffmpeg: str
    ) -> ItemFinished | ItemSkipped | ItemFailed | None:
        total = self._total
        title = entry.get("title") or ""
        self._current_title = title
        self._emit(ItemStarted(position, total, title))

        try:
            info = self._probe(entry["url"], ffmpeg)
            title = info.get("title") or title or "audio"
            if self.request.clean_titles:
                # Vycisteny nazev se pouzije i pro soubor, tagy a historii,
                # aby vsude sedelo totez.
                title = tagging.strip_noise(title) or title
            self._current_title = title

            stem = naming.safe_stem(title)
            target = naming.resolve_target(
                self.request.dest_dir, stem, self.request.existing_policy
            )
            if target is None:
                skipped = ItemSkipped(
                    position, total, title, self.request.dest_dir / f"{stem}.mp3"
                )
                self._emit(skipped)
                return skipped

            if self.request.existing_policy == "overwrite" and target.exists():
                try:
                    target.unlink()
                except OSError as exc:
                    raise TrackiError("PERMISSION_DENIED", str(exc),
                                      params={"path": str(target)}) from exc

            path = self._fetch(entry["url"], target, ffmpeg)
            if self.request.write_tags:
                # Selhani tagovani neni duvod zahodit hotove MP3 - jen se
                # poznamena do logu pro pripadnou diagnostiku.
                tags = tagging.derive(info, clean=self.request.clean_titles)
                if not tagging.write(path, tags):
                    self._log.warning(f"tagy se nepodarilo zapsat: {path.name}")
            size = path.stat().st_size if path.is_file() else 0
            finished = ItemFinished(position, total, title, path, size)
            self._emit(finished)
            return finished

        except DownloadCancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            error = self._translate(exc)
            if total == 1:
                # Jedno video: chyba je vysledek celeho stahovani.
                raise error from exc
            failed = ItemFailed(position, total, title, error)
            self._emit(failed)
            return failed

    def _probe(self, url: str, ffmpeg: str) -> dict[str, Any]:
        """Zjisti nazev videa jeste pred stahovanim, at umime pojmenovat soubor."""
        options = self._base_options(ffmpeg) | {"skip_download": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise TrackiError("VIDEO_UNAVAILABLE", self._log.tail())
        if info.get("is_live"):
            raise TrackiError("VIDEO_LIVE")
        if info.get("live_status") in ("is_upcoming", "post_live"):
            raise TrackiError("VIDEO_NOT_STARTED")
        return info

    def _fetch(self, url: str, target: Path, ffmpeg: str) -> Path:
        """Stahne a prekonvertuje jednu polozku, vrati vyslednou cestu."""
        stem = target.stem
        outtmpl = str(target.parent / f"{naming.escape_outtmpl(stem)}.%(ext)s")
        produced: list[str] = []

        def postprocessor_hook(data: dict[str, Any]) -> None:
            if data.get("status") == "started" and data.get("postprocessor") == "ExtractAudio":
                self._emit(Converting(self._index, self._total, self._current_title))
            if data.get("status") == "finished":
                filepath = (data.get("info_dict") or {}).get("filepath")
                if filepath:
                    produced.append(filepath)

        options = self._base_options(ffmpeg) | {
            "format": "bestaudio/best",
            "outtmpl": {"default": outtmpl},
            "noplaylist": True,
            "overwrites": True,
            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
            "postprocessors": self._postprocessors(),
            "writethumbnail": self.request.embed_cover,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        self._check_cancel()

        if target.is_file():
            return target
        # Zalozni varianta: vezmeme, co postprocessor ohlasil jako vysledek.
        for candidate in reversed(produced):
            path = Path(candidate)
            if path.is_file():
                return path
        matches = sorted(target.parent.glob(f"{glob_escape(stem)}.*"))
        for path in matches:
            if path.suffix.lower() == ".mp3":
                return path
        raise TrackiError("OUTPUT_MISSING", self._log.tail(),
                          params={"path": str(target)})

    def _postprocessors(self) -> list[dict[str, Any]]:
        quality = "0" if self.request.quality == DEFAULT_QUALITY else self.request.quality
        steps: list[dict[str, Any]] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": quality,
        }]
        if self.request.embed_cover:
            steps.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})
        return steps

    def _base_options(self, ffmpeg: str) -> dict[str, Any]:
        return {
            "ffmpeg_location": ffmpeg,
            "logger": self._log,
            "quiet": True,
            "no_warnings": False,
            "noprogress": True,
            "consoletitle": False,
            "color": "no_color",
            # Zadne volani mimo YouTube: bez kontroly novych verzi, bez
            # nacitani uzivatelskych konfiguracnich souboru a pluginu.
            "check_formats": False,
            "ignoreerrors": False,
            "noplaylist": False,
            "retries": 5,
            "fragment_retries": 5,
            "socket_timeout": 30,
            "restrictfilenames": False,
            "windowsfilenames": True,
            "nopart": False,
            "clean_infojson": True,
            "writeinfojson": False,
            "writedescription": False,
            "writesubtitles": False,
        }

    # --- hooky ------------------------------------------------------------
    def _progress_hook(self, data: dict[str, Any]) -> None:
        self._check_cancel()
        status = data.get("status")
        if status != "downloading":
            return

        now = time.monotonic()
        downloaded = int(data.get("downloaded_bytes") or 0)
        total_bytes = int(
            data.get("total_bytes") or data.get("total_bytes_estimate") or 0
        )
        percent = (downloaded / total_bytes * 100) if total_bytes else 0.0
        # Throttling: posledni procento poslat vzdy, at bar nezustane na 97 %.
        if now - self._last_progress < self.PROGRESS_INTERVAL and percent < 99.5:
            return
        self._last_progress = now

        self._emit(Progress(
            index=self._index,
            total=self._total,
            percent=min(percent, 100.0),
            downloaded=downloaded,
            total_bytes=total_bytes,
            speed=data.get("speed"),
            eta=data.get("eta"),
        ))

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise DownloadCancelled("zruseno uzivatelem")

    def _emit(self, event: Event) -> None:
        self.events.put(event)

    def _translate(self, exc: BaseException) -> TrackiError:
        error = from_exception(exc)
        if error.code == "UNKNOWN" or not error.detail:
            tail = self._log.tail()
            if tail:
                # Hlaska z yt-dlp byva v logu podrobnejsi nez v samotne vyjimce.
                error = TrackiError(
                    error.code if error.code != "UNKNOWN" else _classify_tail(tail),
                    error.detail or tail,
                    error.params,
                )
        return error


def _classify_tail(tail: str) -> str:
    from .errors import classify

    return classify(tail)


def glob_escape(text: str) -> str:
    """Escapuje znaky, ktere glob bere jako vzor ([, ], ?, *)."""
    return "".join("[" + ch + "]" if ch in "*?[]" else ch for ch in text)


def _writable(directory: Path) -> bool:
    import tempfile

    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".tracki-", delete=True):
            return True
    except OSError:
        return False


def run_job(
    request: DownloadRequest, on_event: Callable[[Event], None]
) -> DownloadJob:
    """Pomocnik pro testy a skripty: spusti job a synchronne preda udalosti."""
    events: "queue.Queue[Event]" = queue.Queue()
    job = DownloadJob(request, events)
    job.start()
    while job.is_alive() or not events.empty():
        try:
            on_event(events.get(timeout=0.1))
        except queue.Empty:
            continue
    return job
