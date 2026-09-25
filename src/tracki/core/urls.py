"""Rozpoznani a validace YouTube odkazu.

Cil neni byt liberalni, ale umet rict PRESNE, co je na odkazu spatne. Proto se
rozpoznava i to, co podporovane neni (kanaly, vyhledavani, jine sluzby) - jen
aby o tom slo dat uzivateli konkretni hlasku misto "neplatny odkaz".
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse, urlunparse

from .errors import TrackiError

VIDEO = "video"
PLAYLIST = "playlist"

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_PLAYLIST_ID = re.compile(r"^[A-Za-z0-9_-]{2,}$")

_YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtube-nocookie.com", "www.youtube-nocookie.com",
}
_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}

# Cesty, ktere na YouTube existuji, ale jedno video/playlist z nich neudelame.
_CHANNEL_PREFIXES = ("/channel/", "/c/", "/user/", "/@")
_FEED_PATHS = ("/feed", "/results", "/hashtag", "/playlists")


@dataclass(frozen=True)
class ParsedUrl:
    kind: str                 # VIDEO nebo PLAYLIST
    url: str                  # normalizovany odkaz pro yt-dlp
    video_id: str | None = None
    playlist_id: str | None = None

    @property
    def is_playlist(self) -> bool:
        return self.kind == PLAYLIST


def parse(raw: str) -> ParsedUrl:
    """Vrati ParsedUrl, nebo vyhodi TrackiError s konkretnim kodem."""
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        raise TrackiError("URL_EMPTY")

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", text):
        # Uzivatel vlozil samotne video ID - prijmeme to.
        return ParsedUrl(VIDEO, f"https://www.youtube.com/watch?v={text}", video_id=text)

    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        text = "https://" + text

    try:
        parts = urlparse(text)
    except ValueError as exc:
        raise TrackiError("URL_MALFORMED", str(exc)) from exc

    if parts.scheme not in ("http", "https"):
        raise TrackiError("URL_BAD_SCHEME", params={"scheme": parts.scheme})

    host = (parts.hostname or "").lower()
    if not host:
        raise TrackiError("URL_MALFORMED", text)

    if host in _SHORT_HOSTS:
        return _parse_short(parts)
    if host in _YOUTUBE_HOSTS:
        return _parse_youtube(parts)

    raise TrackiError("URL_NOT_YOUTUBE", params={"host": host})


def _parse_short(parts) -> ParsedUrl:
    """youtu.be/<id> pripadne s ?list="""
    video_id = parts.path.lstrip("/").split("/")[0]
    if not video_id:
        raise TrackiError("URL_MISSING_VIDEO_ID")
    if not _VIDEO_ID.match(video_id):
        raise TrackiError("URL_BAD_VIDEO_ID", params={"value": video_id})

    query = parse_qs(parts.query)
    playlist_id = _first(query.get("list"))
    if playlist_id and _wants_playlist(playlist_id):
        return ParsedUrl(
            PLAYLIST,
            f"https://www.youtube.com/playlist?list={playlist_id}",
            video_id=video_id,
            playlist_id=playlist_id,
        )
    return ParsedUrl(VIDEO, f"https://www.youtube.com/watch?v={video_id}", video_id=video_id)


def _parse_youtube(parts) -> ParsedUrl:
    path = parts.path.rstrip("/") or "/"
    query = parse_qs(parts.query)

    if path in ("/playlist", "/playlist/"):
        playlist_id = _first(query.get("list"))
        if not playlist_id:
            raise TrackiError("URL_MISSING_PLAYLIST_ID")
        if not _PLAYLIST_ID.match(playlist_id):
            raise TrackiError("URL_BAD_PLAYLIST_ID", params={"value": playlist_id})
        return ParsedUrl(
            PLAYLIST,
            f"https://www.youtube.com/playlist?list={playlist_id}",
            playlist_id=playlist_id,
        )

    if path in ("/watch", "/watch/"):
        video_id = _first(query.get("v"))
        if not video_id:
            raise TrackiError("URL_MISSING_VIDEO_ID")
        if not _VIDEO_ID.match(video_id):
            raise TrackiError("URL_BAD_VIDEO_ID", params={"value": video_id})

        playlist_id = _first(query.get("list"))
        if playlist_id and _wants_playlist(playlist_id):
            return ParsedUrl(
                PLAYLIST,
                f"https://www.youtube.com/playlist?list={playlist_id}",
                video_id=video_id,
                playlist_id=playlist_id,
            )
        return ParsedUrl(VIDEO, f"https://www.youtube.com/watch?v={video_id}",
                         video_id=video_id)

    for prefix in ("/shorts/", "/live/", "/embed/", "/v/"):
        if path.startswith(prefix):
            video_id = path[len(prefix):].split("/")[0]
            if not video_id:
                raise TrackiError("URL_MISSING_VIDEO_ID")
            if not _VIDEO_ID.match(video_id):
                raise TrackiError("URL_BAD_VIDEO_ID", params={"value": video_id})
            return ParsedUrl(VIDEO, f"https://www.youtube.com/watch?v={video_id}",
                             video_id=video_id)

    if path.startswith(_CHANNEL_PREFIXES):
        raise TrackiError("URL_IS_CHANNEL")
    if path.startswith(_FEED_PATHS):
        if path.startswith("/results"):
            raise TrackiError("URL_IS_SEARCH")
        raise TrackiError("URL_IS_CHANNEL")
    if path == "/":
        raise TrackiError("URL_IS_HOMEPAGE")

    raise TrackiError("URL_UNSUPPORTED_PATH", params={"path": parts.path})


def _wants_playlist(playlist_id: str) -> bool:
    """Rozhodne, jestli se ?list= ma brat jako playlist.

    RD* jsou automaticky generovane "mixy" (Radio) - ty nejsou stabilni seznamy
    a uzivatel je nechtel; WL je Watch Later, ktery bez prihlaseni nefunguje.
    """
    if not _PLAYLIST_ID.match(playlist_id):
        return False
    upper = playlist_id.upper()
    return not (upper.startswith("RD") or upper == "WL" or upper == "LL")


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    value = values[0].strip()
    return value or None


def strip_tracking(url: str) -> str:
    """Odstrani z odkazu sledovaci parametry (si, pp, feature...)."""
    parts = urlparse(url)
    keep = {"v", "list"}
    query = parse_qs(parts.query)
    kept = "&".join(f"{k}={v[0]}" for k, v in query.items() if k in keep and v)
    return urlunparse(parts._replace(query=kept, fragment=""))
