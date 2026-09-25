"""Testy prekladu hlasek yt-dlp na nase kody chyb.

Tabulka nize jsou skutecne hlasky, ktere YouTube a yt-dlp vraceji. Kdyz nejaka
spadne do UNKNOWN, uzivatel misto vysvetleni uvidi obecne "Neco se nepovedlo" -
prave proto se tu kontroluje i to, ze UNKNOWN zustava opravdu jen pro neznamy
text.
"""
from __future__ import annotations

import pytest

from tracki.core.errors import TrackiError, classify, clean_message, from_exception
from tracki.i18n import LANGUAGES

REAL_MESSAGES = [
    # --- nedostupne video ---
    ("[youtube] 6E5Zb4gbDqo: This video is not available", "VIDEO_UNAVAILABLE"),
    ("ERROR: [youtube] X: Video unavailable", "VIDEO_UNAVAILABLE"),
    ("ERROR: [youtube] X: This video is unavailable", "VIDEO_UNAVAILABLE"),
    ("ERROR: [youtube] X: This video has been removed by the uploader",
     "VIDEO_UNAVAILABLE"),
    ("ERROR: [youtube] X: This video is no longer available because the YouTube "
     "account associated with this video has been terminated.", "VIDEO_UNAVAILABLE"),
    # --- soukrome a omezene ---
    ("ERROR: [youtube] X: Private video. Sign in if you've been granted access to "
     "this video", "VIDEO_PRIVATE"),
    ("ERROR: [youtube] X: Join this channel to get access to members-only content",
     "VIDEO_MEMBERS_ONLY"),
    ("ERROR: [youtube] X: Sign in to confirm your age. This video may be "
     "inappropriate for some users.", "VIDEO_AGE_RESTRICTED"),
    # --- zeme a pravni duvody ---
    ("ERROR: [youtube] X: The uploader has not made this video available in your "
     "country", "VIDEO_GEO_BLOCKED"),
    ("ERROR: [youtube] X: Video unavailable. This video contains content from XYZ, "
     "who has blocked it in your country on copyright grounds", "VIDEO_GEO_BLOCKED"),
    ("ERROR: [youtube] X: This video has been removed for violating YouTube's "
     "Terms of Service", "VIDEO_BLOCKED_LEGAL"),
    # --- casovani ---
    ("ERROR: [youtube] X: Premieres in 3 hours", "VIDEO_NOT_STARTED"),
    ("ERROR: [youtube] X: This live event will begin in 2 hours", "VIDEO_NOT_STARTED"),
    # --- youtube nas ma za robota ---
    ("ERROR: [youtube] X: Sign in to confirm you're not a bot", "YOUTUBE_BOT_CHECK"),
    ("ERROR: [youtube] X: Please sign in to prove you're not a bot",
     "YOUTUBE_BOT_CHECK"),
    # --- sit a technika ---
    ("ERROR: unable to download webpage: <urlopen error [Errno -3] Temporary "
     "failure in name resolution>", "NETWORK"),
    ("ERROR: Unable to download webpage: The read operation timed out", "NETWORK"),
    ("ERROR: [youtube] X: HTTP Error 429: Too Many Requests", "RATE_LIMITED"),
    ("ERROR: requested format is not available", "FORMAT_UNAVAILABLE"),
    ("ERROR: ffprobe/ffmpeg not found. Please install", "FFMPEG_FAILED"),
    ("OSError: [Errno 28] No space left on device", "DISK_FULL"),
    ("PermissionError: [Errno 13] Permission denied", "PERMISSION_DENIED"),
    ("ERROR: Unsupported URL: https://example.com/video", "URL_UNSUPPORTED"),
]


@pytest.mark.parametrize("message,expected", REAL_MESSAGES)
def test_real_messages_are_classified(message, expected):
    assert classify(clean_message(message)) == expected


@pytest.mark.parametrize("message,_expected", REAL_MESSAGES)
def test_no_real_message_ends_up_unknown(message, _expected):
    assert classify(clean_message(message)) != "UNKNOWN"


@pytest.mark.parametrize("message,expected", REAL_MESSAGES)
def test_every_classified_code_has_a_translation(message, expected):
    for language in LANGUAGES:
        assert f"error.{expected}.title" in LANGUAGES[language]
        assert f"error.{expected}.hint" in LANGUAGES[language]


# --- poradi vzoru je soucast chovani, ne nahoda ----------------------------
def test_specific_wins_over_general_availability():
    """Siroky vzor "not available" nesmi pohltit konkretnejsi hlasky."""
    assert classify("requested format is not available") == "FORMAT_UNAVAILABLE"
    assert classify("the uploader has not made this video available in your "
                    "country") == "VIDEO_GEO_BLOCKED"


def test_country_block_wins_over_copyright():
    # Hlaska obsahuje "copyright" i "unavailable", ale pro uzivatele je
    # podstatne, ze jde o omezeni na zemi.
    message = ("video unavailable. this video contains content from abc, who has "
               "blocked it in your country on copyright grounds")
    assert classify(message) == "VIDEO_GEO_BLOCKED"


def test_unknown_stays_for_genuinely_unknown_text():
    assert classify("neco naprosto nesrozumitelneho") == "UNKNOWN"
    assert classify("") == "UNKNOWN"


# --- cisteni hlasek ---------------------------------------------------------
def test_clean_message_strips_prefixes_and_colors():
    assert clean_message("ERROR: neco") == "neco"
    assert clean_message("WARNING: neco") == "neco"
    assert clean_message("\x1b[0;31mERROR:\x1b[0m neco").endswith("neco")
    assert clean_message(None) == ""


# --- prevod vyjimek ---------------------------------------------------------
def test_from_exception_keeps_our_own_errors():
    original = TrackiError("VIDEO_LIVE", "detail")
    assert from_exception(original) is original


def test_from_exception_detects_disk_and_permission_errors():
    disk = OSError("no space")
    disk.errno = 28
    assert from_exception(disk).code == "DISK_FULL"
    assert from_exception(PermissionError("denied")).code == "PERMISSION_DENIED"


def test_from_exception_carries_detail_for_diagnostics():
    error = from_exception(Exception("ERROR: [youtube] X: This video is not available"))
    assert error.code == "VIDEO_UNAVAILABLE"
    assert "not available" in error.detail
    assert not error.detail.startswith("ERROR:")
