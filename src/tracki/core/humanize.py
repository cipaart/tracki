"""Formatovani velikosti, rychlosti a casu pro UI."""
from __future__ import annotations


def size(num_bytes: float | None) -> str:
    value = float(num_bytes or 0)
    if value < 1024:
        return f"{int(value)} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.0f} kB"
    if value < 1024 * 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    return f"{value / (1024 * 1024 * 1024):.2f} GB"


def speed(bytes_per_second: float | None) -> str:
    if not bytes_per_second or bytes_per_second <= 0:
        return ""
    return f"{size(bytes_per_second)}/s"


def duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return ""
    total = int(seconds)
    if total < 60:
        return f"{total} s"
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes}:{secs:02d}"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}"


def shorten_path(path: str, limit: int = 52) -> str:
    """Zkrati cestu zprostredka, at je videt zacatek i nazev slozky."""
    text = str(path)
    if len(text) <= limit:
        return text
    keep = (limit - 3) // 2
    return f"{text[:keep]}...{text[-keep:]}"


def shorten(text: str, limit: int = 64) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
