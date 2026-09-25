"""Nahrada za yt_dlp pro testy - zadna sit, ale stejne rozhrani.

Testy si skriptuji chovani pres Script: co ktera URL vrati, ktera selze a co
se ma stat v prubehu stahovani.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from yt_dlp.utils import DownloadError


@dataclass
class Script:
    # url -> info dict vraceny z extract_info
    infos: dict[str, dict[str, Any]] = field(default_factory=dict)
    # url -> zprava chyby, kterou ma extract_info vyhodit
    errors: dict[str, str] = field(default_factory=dict)
    # url -> chyba vyhozena az pri download()
    download_errors: dict[str, str] = field(default_factory=dict)
    # volano pred kazdym download(url) - testy tim treba rusi job
    before_download: Callable[[str], None] | None = None
    downloaded: list[str] = field(default_factory=list)
    emit_progress: bool = True


class FakeYoutubeDL:
    script = Script()

    def __init__(self, options: dict[str, Any]) -> None:
        self.options = options

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    # --- rozhrani, ktere downloader pouziva ---
    def extract_info(self, url: str, download: bool = False) -> dict[str, Any] | None:
        message = self.script.errors.get(url)
        if message:
            raise DownloadError(message)
        return self.script.infos.get(url)

    def download(self, urls: list[str]) -> None:
        for url in urls:
            if self.script.before_download:
                self.script.before_download(url)

            message = self.script.download_errors.get(url)
            if message:
                raise DownloadError(message)

            if self.script.emit_progress:
                for hook in self.options.get("progress_hooks", []):
                    hook({"status": "downloading", "downloaded_bytes": 500_000,
                          "total_bytes": 1_000_000, "speed": 250_000.0, "eta": 2})
                    hook({"status": "downloading", "downloaded_bytes": 1_000_000,
                          "total_bytes": 1_000_000, "speed": 250_000.0, "eta": 0})

            target = self._output_path()
            for hook in self.options.get("postprocessor_hooks", []):
                hook({"status": "started", "postprocessor": "ExtractAudio",
                      "info_dict": {}})

            target.parent.mkdir(parents=True, exist_ok=True)
            # Zacatek platneho MP3 ramce, ne "ID3" - jinak by mutagen soubor
            # cetl jako ID3 hlavicku verze 0 a odmitl ho.
            target.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 4096)
            self.script.downloaded.append(url)

            for hook in self.options.get("postprocessor_hooks", []):
                hook({"status": "finished", "postprocessor": "ExtractAudio",
                      "info_dict": {"filepath": str(target)}})

    def _output_path(self) -> Path:
        template = self.options["outtmpl"]["default"]
        # napodobi yt-dlp: %(ext)s -> mp3 a %% -> %
        return Path(template.replace("%(ext)s", "mp3").replace("%%", "%"))


def info(video_id: str, title: str, **extra: Any) -> dict[str, Any]:
    data = {"id": video_id, "title": title, "ext": "webm"}
    data.update(extra)
    return data


def playlist(title: str, entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"_type": "playlist", "title": title, "entries": entries}
