"""Chybove stavy prelozene do lidske reci.

Kazda chyba ma tri urovne: kratkou hlasku, napovedu "co s tim" a technicky
detail, ktery jde rozbalit. Bezny uzivatel si vystaci s prvnimi dvema, pri
hlaseni problemu je ten treti to, co pomuze.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TrackiError(Exception):
    """Chyba s kodem, ktery se v UI preklada pres i18n."""

    code: str
    detail: str = ""
    params: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}" if self.detail else self.code


# --- mapovani vyjimek yt-dlp na nase kody -----------------------------------
# Poradi je zamerne: specifictejsi vzory driv nez obecne.
_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"private video|this video is private", "VIDEO_PRIVATE"),
    (r"members-only|join this channel", "VIDEO_MEMBERS_ONLY"),
    (r"sign in to confirm your age|age-restricted|inappropriate for some users",
     "VIDEO_AGE_RESTRICTED"),
    # Geoblokace musi byt pred obecnou nedostupnosti i pred autorskymi pravy:
    # hlaska o blokaci v zemi casto obsahuje zaroven "unavailable" i "copyright",
    # ale pro uzivatele je podstatne prave to omezeni na zemi.
    (r"not available in your country|available in your country"
     r"|blocked it in your country|geo.?restrict|country.?block",
     "VIDEO_GEO_BLOCKED"),
    (r"copyright|violating youtube'?s? (terms|policy)|terms of service",
     "VIDEO_BLOCKED_LEGAL"),
    (r"premieres in|this live event will begin|is not yet available"
     r"|scheduled for", "VIDEO_NOT_STARTED"),
    (r"live stream|is live|live event", "VIDEO_LIVE"),
    (r"sign in to confirm you.?re not a bot|confirm you are not a bot"
     r"|sign in to prove you.?re not a bot", "YOUTUBE_BOT_CHECK"),
    (r"unable to download webpage|failed to resolve|getaddrinfo|name or service not known"
     r"|connection (reset|refused|aborted)|timed out|timeout|network is unreachable"
     r"|temporary failure in name resolution|ssl|certificate", "NETWORK"),
    (r"http error 429|too many requests", "RATE_LIMITED"),
    (r"ffmpeg|ffprobe", "FFMPEG_FAILED"),
    (r"no space left|disk (is )?full|not enough space", "DISK_FULL"),
    (r"permission denied|access is denied|errno 13", "PERMISSION_DENIED"),
    (r"unsupported url|no suitable inforextractor|is not a valid url",
     "URL_UNSUPPORTED"),
    (r"incomplete youtube id|does not look like a youtube", "URL_BAD_VIDEO_ID"),
    (r"requested format (is )?not available", "FORMAT_UNAVAILABLE"),
    # Uplne nakonec obecna nedostupnost videa: vzor "not available" je tak
    # siroky, ze by jinak pohltil i konkretnejsi hlasky nad sebou
    # (napr. "requested format is not available").
    (r"video is unavailable|video unavailable|is not available|not available"
     r"|has been removed|no longer available|has been terminated"
     r"|does not exist|removed by the uploader", "VIDEO_UNAVAILABLE"),
)


def classify(message: str) -> str:
    """Z textu vyjimky yt-dlp urci nas kod chyby."""
    text = (message or "").lower()
    for pattern, code in _PATTERNS:
        if re.search(pattern, text):
            return code
    return "UNKNOWN"


def from_exception(exc: BaseException) -> TrackiError:
    """Prelozi libovolnou vyjimku na TrackiError. Uz prelozene necha byt."""
    if isinstance(exc, TrackiError):
        return exc

    raw = clean_message(str(exc))
    if isinstance(exc, PermissionError):
        return TrackiError("PERMISSION_DENIED", raw)
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == 28:
        return TrackiError("DISK_FULL", raw)

    return TrackiError(classify(raw), raw)


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def clean_message(message: str) -> str:
    """Odstrani ANSI barvy a prefixy, ktere yt-dlp pridava do hlasek."""
    text = _ANSI.sub("", message or "").strip()
    for prefix in ("ERROR: ", "WARNING: "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    return text
