"""Nastaveni a historie v jednom JSON souboru.

Zapisuje se atomicky (tmp + os.replace), aby padek nebo vypnuti PC uprostred
zapisu nezanechalo rozbity soubor. Nacteni je zamerne odolne: cokoli
nepouzitelneho se zahodi a nahradi vychozi hodnotou, aplikace nikdy nespadne
kvuli poskozenemu configu.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from .. import paths

THEMES = ("system", "dark", "light")
LANGUAGES = ("cs", "en")
SCREENS = ("download", "history", "settings")
EXISTING_POLICIES = ("rename", "overwrite", "skip")

# Hodnota pro yt-dlp preferredquality: "0" = nejlepsi dostupna (VBR)
QUALITY_PRESETS: tuple[str, ...] = ("best", "320", "256", "192", "128")
DEFAULT_QUALITY = "best"

MAX_HISTORY_LIMIT = 500


@dataclass
class HistoryEntry:
    title: str
    path: str
    url: str = ""
    timestamp: float = field(default_factory=time.time)
    size: int = 0
    quality: str = DEFAULT_QUALITY

    @property
    def file(self) -> Path:
        return Path(self.path)

    def exists(self) -> bool:
        try:
            return self.file.is_file()
        except OSError:
            return False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEntry | None":
        if not isinstance(data, dict):
            return None
        title = str(data.get("title") or "").strip()
        path = str(data.get("path") or "").strip()
        if not title or not path:
            return None
        return cls(
            title=title,
            path=path,
            url=str(data.get("url") or ""),
            timestamp=_as_float(data.get("timestamp"), time.time()),
            size=int(_as_float(data.get("size"), 0)),
            quality=str(data.get("quality") or DEFAULT_QUALITY),
        )


@dataclass
class Settings:
    # vzhled a jazyk
    theme: str = "system"
    language: str = "cs"
    # stahovani
    output_dir: str = ""
    quality: str = DEFAULT_QUALITY
    ask_quality: bool = False
    existing_policy: str = "rename"
    # metadata
    write_tags: bool = True
    embed_cover: bool = True
    clean_titles: bool = True
    # chovani
    open_folder_after: bool = False
    last_screen: str = "download"
    max_history: int = 100
    confirm_playlist_over: int = 20

    def normalized(self) -> "Settings":
        """Opravi hodnoty mimo povoleny rozsah na vychozi."""
        default = Settings()
        if self.theme not in THEMES:
            self.theme = default.theme
        if self.language not in LANGUAGES:
            self.language = default.language
        if self.last_screen not in SCREENS:
            self.last_screen = default.last_screen
        if self.quality not in QUALITY_PRESETS:
            self.quality = default.quality
        if self.existing_policy not in EXISTING_POLICIES:
            self.existing_policy = default.existing_policy
        if not isinstance(self.max_history, int) or not 0 <= self.max_history <= MAX_HISTORY_LIMIT:
            self.max_history = default.max_history
        if not isinstance(self.confirm_playlist_over, int) or self.confirm_playlist_over < 0:
            self.confirm_playlist_over = default.confirm_playlist_over
        for name in ("ask_quality", "write_tags", "embed_cover", "clean_titles",
                     "open_folder_after"):
            if not isinstance(getattr(self, name), bool):
                setattr(self, name, getattr(default, name))

        if not self.output_dir or not _looks_like_path(self.output_dir):
            self.output_dir = str(paths.default_download_dir())
        return self

    @property
    def download_dir(self) -> Path:
        return Path(self.output_dir) if self.output_dir else paths.default_download_dir()


class Store:
    """Nastaveni + historie nad jednim souborem na disku."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else paths.config_path()
        self.settings = Settings()
        self.history: list[HistoryEntry] = []
        self.load_error: str | None = None

    # --- cteni a zapis ----------------------------------------------------
    def load(self) -> "Store":
        self.load_error = None
        raw: dict[str, Any] = {}
        try:
            if self.path.is_file():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Poskozeny config nesmi zabranit spusteni - jen si to poznamename.
            self.load_error = str(exc)
            raw = {}

        if not isinstance(raw, dict):
            self.load_error = "config neni objekt JSON"
            raw = {}

        self.settings = _settings_from_dict(raw.get("settings"))
        self.history = _history_from_list(raw.get("history"))
        self._trim_history()
        return self

    def save(self) -> bool:
        """Zapise atomicky. Vraci False, kdyz to neslo (read-only disk apod.)."""
        payload = {
            "version": 1,
            "settings": asdict(self.settings),
            "history": [asdict(entry) for entry in self.history],
        }
        tmp = self.path.with_suffix(".json.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(tmp, self.path)
            return True
        except OSError:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    # --- historie ---------------------------------------------------------
    def add_history(self, entry: HistoryEntry) -> None:
        """Prida zaznam nahoru; stejny soubor se neduplikuje."""
        self.history = [item for item in self.history if item.path != entry.path]
        self.history.insert(0, entry)
        self._trim_history()

    def remove_history(self, entry: HistoryEntry) -> None:
        self.history = [item for item in self.history if item.path != entry.path]

    def clear_history(self) -> None:
        self.history = []

    def _trim_history(self) -> None:
        limit = max(0, min(self.settings.max_history, MAX_HISTORY_LIMIT))
        if len(self.history) > limit:
            del self.history[limit:]


def _settings_from_dict(data: Any) -> Settings:
    settings = Settings()
    if isinstance(data, dict):
        known = {f.name for f in fields(Settings)}
        for key, value in data.items():
            if key in known:
                setattr(settings, key, value)
    return settings.normalized()


def _history_from_list(data: Any) -> list[HistoryEntry]:
    if not isinstance(data, list):
        return []
    entries = []
    for item in data:
        entry = HistoryEntry.from_dict(item)
        if entry:
            entries.append(entry)
    return entries


def _as_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _looks_like_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        Path(value)
        return True
    except (TypeError, ValueError):
        return False
