import pytest

from tracki.core import urls
from tracki.core.errors import TrackiError

VID = "aBcD1234_-x"


@pytest.mark.parametrize("raw", [
    f"https://www.youtube.com/watch?v={VID}",
    f"http://youtube.com/watch?v={VID}",
    f"https://m.youtube.com/watch?v={VID}",
    f"https://music.youtube.com/watch?v={VID}",
    f"youtube.com/watch?v={VID}",
    f"https://youtu.be/{VID}",
    f"https://youtu.be/{VID}?si=abcdef",
    f"https://www.youtube.com/shorts/{VID}",
    f"https://www.youtube.com/live/{VID}",
    f"https://www.youtube.com/embed/{VID}",
    f"  https://www.youtube.com/watch?v={VID}  ",
    f'"https://www.youtube.com/watch?v={VID}"',
    VID,
])
def test_single_video(raw):
    parsed = urls.parse(raw)
    assert parsed.kind == urls.VIDEO
    assert parsed.video_id == VID
    assert parsed.url == f"https://www.youtube.com/watch?v={VID}"


def test_playlist_url():
    parsed = urls.parse("https://www.youtube.com/playlist?list=PL1234567890")
    assert parsed.is_playlist
    assert parsed.playlist_id == "PL1234567890"


def test_watch_inside_playlist_is_playlist():
    parsed = urls.parse(f"https://www.youtube.com/watch?v={VID}&list=PLabc123")
    assert parsed.is_playlist
    assert parsed.playlist_id == "PLabc123"
    assert parsed.video_id == VID


@pytest.mark.parametrize("list_id", ["RDabc123", "WL", "LL"])
def test_mix_and_private_lists_fall_back_to_single_video(list_id):
    parsed = urls.parse(f"https://www.youtube.com/watch?v={VID}&list={list_id}")
    assert parsed.kind == urls.VIDEO


@pytest.mark.parametrize("raw,code", [
    ("", "URL_EMPTY"),
    ("   ", "URL_EMPTY"),
    ("https://vimeo.com/12345", "URL_NOT_YOUTUBE"),
    ("https://www.spotify.com/track/x", "URL_NOT_YOUTUBE"),
    ("ftp://youtube.com/watch?v=x", "URL_BAD_SCHEME"),
    ("https://www.youtube.com/watch", "URL_MISSING_VIDEO_ID"),
    ("https://www.youtube.com/watch?v=tooshort", "URL_BAD_VIDEO_ID"),
    ("https://www.youtube.com/playlist", "URL_MISSING_PLAYLIST_ID"),
    ("https://www.youtube.com/@someuser", "URL_IS_CHANNEL"),
    ("https://www.youtube.com/channel/UCabc", "URL_IS_CHANNEL"),
    ("https://www.youtube.com/c/somechannel", "URL_IS_CHANNEL"),
    ("https://www.youtube.com/feed/subscriptions", "URL_IS_CHANNEL"),
    ("https://www.youtube.com/results?search_query=test", "URL_IS_SEARCH"),
    ("https://www.youtube.com/", "URL_IS_HOMEPAGE"),
    ("https://www.youtube.com/account", "URL_UNSUPPORTED_PATH"),
])
def test_errors(raw, code):
    with pytest.raises(TrackiError) as excinfo:
        urls.parse(raw)
    assert excinfo.value.code == code


def test_error_carries_host_for_diagnostics():
    with pytest.raises(TrackiError) as excinfo:
        urls.parse("https://vimeo.com/12345")
    assert excinfo.value.params["host"] == "vimeo.com"


def test_strip_tracking():
    out = urls.strip_tracking(f"https://www.youtube.com/watch?v={VID}&si=xx&pp=yy")
    assert "si=" not in out and "pp=" not in out and f"v={VID}" in out
