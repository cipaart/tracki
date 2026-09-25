"""Prevod nazvu videa na nazev souboru, ktery Windows prijme."""
from __future__ import annotations

import re
from pathlib import Path

from yt_dlp.utils import sanitize_filename

# Nazvy, ktere Windows rezervuje pro zarizeni - soubor se tak jmenovat nesmi.
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

MAX_STEM = 150


def safe_stem(title: str, fallback: str = "audio") -> str:
    """Z nazvu videa udela bezpecny nazev souboru bez pripony."""
    stem = sanitize_filename(title or "", restricted=False)
    stem = re.sub(r"[\x00-\x1f\x7f]", "", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    # Windows umaze koncove tecky a mezery sam - radeji to udelame my.
    stem = stem.rstrip(". ")

    if len(stem) > MAX_STEM:
        stem = stem[:MAX_STEM].rstrip(". ")

    if stem.upper() in _RESERVED or stem.split(".")[0].upper() in _RESERVED:
        stem = f"{stem}_"

    return stem or fallback


def escape_outtmpl(stem: str) -> str:
    """Zneskodni procenta, aby si je yt-dlp nespletl se sablonou."""
    return stem.replace("%", "%%")


def resolve_target(directory: Path, stem: str, policy: str, suffix: str = ".mp3") -> Path | None:
    """Vrati cilovou cestu podle nastaveni pro uz existujici soubor.

    None znamena "preskocit" (policy 'skip' a soubor uz existuje).
    """
    target = directory / f"{stem}{suffix}"
    if not target.exists():
        return target

    if policy == "skip":
        return None
    if policy == "overwrite":
        return target

    for index in range(2, 1000):
        candidate = directory / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
    return directory / f"{stem} ({id(target)}){suffix}"
