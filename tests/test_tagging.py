"""Testy ID3 tagu.

Klicove pravidlo: nazev kanalu se do tagu nedostane nikdy. yt-dlp ho pri
chybejicich hudebnich metadatech dosazuje za interpreta, coz u beznych
uploadu dava nesmysl.
"""
from __future__ import annotations

import pytest

from tracki.core import tagging
from tracki.core.tagging import Tags, derive


# --- odvozeni z nazvu videa ------------------------------------------------
def test_channel_name_never_becomes_artist():
    tags = derive({
        "title": "Interpret - Skladba",
        "uploader": "Nahodny Kanal 123",
        "uploader_id": "@nahodnykanal",
        "channel": "Nahodny Kanal 123",
        "creator": None,
    })
    assert tags.artist == "Interpret"
    assert "Kanal" not in tags.artist


def test_no_separator_leaves_artist_empty_instead_of_channel():
    tags = derive({"title": "Sestrih z dovolene 2019", "uploader": "Pepa Novak",
                   "channel": "Pepa Novak"})
    assert tags.title == "Sestrih z dovolene 2019"
    assert tags.artist == ""


def test_title_is_split_on_dash():
    tags = derive({"title": "Kapela - Nazev pisnicky"})
    assert (tags.artist, tags.title) == ("Kapela", "Nazev pisnicky")


@pytest.mark.parametrize("separator", [" - ", " – ", " — ", " ‒ ", " − "])
def test_all_dash_variants_are_handled(separator):
    tags = derive({"title": f"Kapela{separator}Pisnicka"})
    assert (tags.artist, tags.title) == ("Kapela", "Pisnicka")


def test_only_first_separator_splits():
    tags = derive({"title": "Kapela - Pisnicka - live 2020"})
    assert tags.artist == "Kapela"
    assert tags.title == "Pisnicka - live 2020"


def test_dash_without_spaces_is_not_a_separator():
    # "AC/DC"-like nazvy a spojovniky uvnitr slov se nesmi rozpadat
    tags = derive({"title": "Post-punkova pisnicka"})
    assert tags.artist == ""
    assert tags.title == "Post-punkova pisnicka"


def test_leading_number_is_track_number_not_artist():
    tags = derive({"title": "01 - Prvni skladba", "uploader": "Kanal"})
    assert tags.artist == ""
    assert tags.title == "Prvni skladba"
    assert tags.track_number == "1" or tags.track_number == "01"


def test_long_left_side_is_not_treated_as_artist():
    long_left = "x" * (tagging.MAX_ARTIST_LEN + 5)
    tags = derive({"title": f"{long_left} - konec"})
    assert tags.artist == ""
    assert tags.title == f"{long_left} - konec"


def test_empty_side_does_not_split():
    # s cistenim se visici pomlcka uklidi, bez cisteni zustava - v obou
    # pripadech se ale nesmi rozdelit na interpreta a nazev
    tags = derive({"title": "Kapela - "})
    assert tags.artist == ""
    assert tags.title == "Kapela"

    raw = derive({"title": "Kapela - "}, clean=False)
    assert raw.artist == ""
    assert raw.title == "Kapela -"


# --- hudebni metadata od YouTube -------------------------------------------
def test_music_metadata_wins_over_title_parsing():
    tags = derive({
        "title": "Neco jineho - v nazvu videa",
        "track": "Skutecny nazev",
        "artist": "Skutecny interpret",
        "album": "Skutecne album",
        "release_year": 2011,
        "uploader": "VEVO kanal",
    })
    assert tags.title == "Skutecny nazev"
    assert tags.artist == "Skutecny interpret"
    assert tags.album == "Skutecne album"
    assert tags.year == "2011"


def test_artist_list_is_joined():
    tags = derive({"title": "x", "track": "Song", "artists": ["A", "B"]})
    assert tags.artist == "A, B"


def test_music_artist_supplements_parsed_title():
    tags = derive({"title": "Neco - Pisnicka", "artist": "Overeny interpret"})
    assert tags.artist == "Overeny interpret"
    assert tags.title == "Pisnicka"


def test_upload_year_is_not_used_as_release_year():
    tags = derive({"title": "Pisnicka", "upload_date": "20240301"})
    assert tags.year == ""


@pytest.mark.parametrize("value", [None, "None", "NA", "n/a", "", "   "])
def test_junk_values_are_ignored(value):
    tags = derive({"title": "Pisnicka", "artist": value, "album": value})
    assert tags.artist == ""
    assert tags.album == ""


def test_missing_info_does_not_crash():
    assert derive({}).is_empty()
    assert derive(None).is_empty()


# --- zapis do souboru ------------------------------------------------------
def read_back(path):
    from mutagen.id3 import ID3

    return ID3(str(path))


def test_write_sets_expected_frames(tmp_path):
    target = tmp_path / "song.mp3"
    target.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 4096)

    assert tagging.write(target, Tags(title="Máci", artist="O5 & Radeček",
                                      album="Album", year="2007",
                                      track_number="3"))

    frames = read_back(target)
    assert frames["TIT2"].text == ["Máci"]
    assert frames["TPE1"].text == ["O5 & Radeček"]
    assert frames["TALB"].text == ["Album"]
    assert str(frames["TDRC"].text[0]) == "2007"
    assert frames["TRCK"].text == ["3"]


def test_write_preserves_existing_cover(tmp_path):
    from mutagen.id3 import ID3, APIC

    target = tmp_path / "song.mp3"
    target.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 4096)

    existing = ID3()
    existing.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover",
                      data=b"\xff\xd8\xff\xe0fake-jpeg"))
    existing.save(str(target))

    assert tagging.write(target, Tags(title="Song", artist="Artist"))

    frames = read_back(target)
    assert frames.getall("APIC"), "obal se pri zapisu tagu ztratil"
    assert frames["TIT2"].text == ["Song"]


def test_write_skips_when_nothing_to_write(tmp_path):
    target = tmp_path / "song.mp3"
    target.write_bytes(b"data")
    assert tagging.write(target, Tags()) is True
    assert target.read_bytes() == b"data"  # soubor se nesmi ani otevrit


def test_write_on_missing_file_reports_failure(tmp_path):
    assert tagging.write(tmp_path / "neni.mp3", Tags(title="x")) is False


# --- cisteni nazvu ---------------------------------------------------------
@pytest.mark.parametrize("raw,expected", [
    ("Kapela - Pisnicka (Official Video)", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka [Official Music Video]", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka {Official Audio}", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka | Official Video", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka (Oficiální videoklip)", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka (oficialni klip)", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka (Text písně)", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka (Lyrics)", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka (Lyric Video)", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka (Visualizer)", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka (Official Audio) [HD]", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka (Official Video) 1080p", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka HD", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka 4K", "Kapela - Pisnicka"),
    ("Kapela - Pisnicka (Official)", "Kapela - Pisnicka"),
])
def test_noise_is_removed(raw, expected):
    assert tagging.strip_noise(raw) == expected


@pytest.mark.parametrize("raw", [
    "Kapela - Pisnicka",
    "Kapela - Pisnicka (Live)",
    "Kapela - Pisnicka (Live at Wembley 1985)",
    "Kapela - Pisnicka (Acoustic)",
    "Kapela - Pisnicka (Remastered 2011)",
    "Kapela - Pisnicka (feat. Nekdo)",
    "Kapela - Pisnicka (Radio Edit)",
    "Kapela - Pisnicka (Remix)",
    "Kapela - Pisnicka (Cover)",
    "Kapela - Pisnicka (Demo)",
    "Kapela - Pisnicka (Instrumental)",
    "Kapela - Pisnicka (Extended Version 12'')",
])
def test_meaningful_details_are_kept(raw):
    assert tagging.strip_noise(raw) == raw


def test_whole_title_made_of_noise_is_kept():
    # radeji divny nazev nez prazdny soubor
    assert tagging.strip_noise("Official Video") == "Official Video"
    assert tagging.strip_noise("(Official Video)") == "(Official Video)"


def test_quality_that_is_the_actual_song_name_is_kept():
    assert tagging.strip_noise("Kapela - 4K") == "Kapela - 4K"
    assert tagging.strip_noise("Kapela - HD") == "Kapela - HD"
    assert tagging.strip_noise("4K") == "4K"


def test_leftovers_are_tidied():
    assert tagging.strip_noise("Kapela  -  Pisnicka   (HD)") == "Kapela - Pisnicka"
    assert tagging.strip_noise("Kapela - Pisnicka (HD) |") == "Kapela - Pisnicka"


def test_noise_removal_feeds_artist_split():
    tags = derive({"title": "O5 & Radeček - Máci (Oficiální videoklip) [HD]",
                   "uploader": "Radoslav Outrata - Monty"})
    assert tags.artist == "O5 & Radeček"
    assert tags.title == "Máci"


def test_cleaning_can_be_turned_off():
    tags = derive({"title": "Kapela - Pisnicka (Official Video)"}, clean=False)
    assert tags.title == "Pisnicka (Official Video)"


def test_strip_noise_handles_empty_input():
    assert tagging.strip_noise("") == ""
    assert tagging.strip_noise(None) == ""
