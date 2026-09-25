"""ID3 tagy pro vysledny MP3.

Proc vlastni tagovani misto postprocessoru FFmpegMetadata z yt-dlp: ten pri
chybejicich hudebnich metadatech dosazuje za interpreta nazev kanalu
(v jeho zdrojaku doslova
`add('artist', ('artist', 'artists', 'creator', 'creators', 'uploader', ...))`).
U beznych uploadu je nazev kanalu s pisnickou nesouvisejici text, takze je
lepsi nechat pole interpret prazdne nez do nej zapsat nesmysl.

Poradi, ze ktereho se interpret bere:
  1. hudebni metadata od YouTube (artist / track / album) - kdyz existuji,
     jsou spolehliva,
  2. rozdeleni nazvu videa na "Interpret - Skladba",
  3. nic. Nazev kanalu se nepouziva nikdy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Oddelovace, ktere se v nazvech videi pouzivaji mezi interpretem a skladbou.
# Zamerne jen varianty pomlcky s mezerami - "AC/DC" nebo "Bratri Ebenove"
# by se jinak rozpadly na pulky.
_SEPARATORS = (" - ", " – ", " — ", " ‒ ", " − ")

# Leva strana, ktera je jen cislo nebo poradi ("01", "3.", "12 -") neni
# interpret, ale cislo skladby.
_TRACK_NUMBER = re.compile(r"^\s*\d{1,3}\s*[.)\]]?\s*$")

MAX_ARTIST_LEN = 80


@dataclass(frozen=True)
class Tags:
    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""
    track_number: str = ""

    def is_empty(self) -> bool:
        return not any((self.title, self.artist, self.album, self.year,
                        self.track_number))


def derive(info: dict[str, Any], clean: bool = True) -> Tags:
    """Z informaci o videu udela tagy. Nazev kanalu ignoruje.

    clean=True navic odstrani z nazvu marketingovy balast (viz strip_noise).
    """
    info = info or {}

    music_title = _clean(info.get("track"))
    music_artist = _first_value(info, ("artist", "artists", "album_artist",
                                      "album_artists", "creator", "creators"))
    album = _clean(info.get("album"))
    year = _year(info)

    if music_title:
        # YouTube o videu vi, ze je to konkretni skladba - tomu se veri.
        if clean:
            music_title = strip_noise(music_title)
        return Tags(title=music_title, artist=music_artist, album=album, year=year)

    video_title = _clean(info.get("title"))
    if clean:
        video_title = strip_noise(video_title)
    artist, title, track_number = _split_title(video_title)
    if music_artist:
        artist = music_artist

    return Tags(title=title, artist=artist, album=album, year=year,
                track_number=track_number)


# --- cisteni nazvu videa ----------------------------------------------------
# Co se ma smazat, jen kdyz to tvori CELY obsah zavorky nebo cely konec nazvu
# za oddelovacem. Zamerne tu NENI "live", "acoustic", "remastered", "remix",
# "cover", "demo", "feat" ani "radio edit" - to jsou udaje o konkretni verzi
# nahravky a jejich smazanim by se ztratila informace.
_NOISE = re.compile(
    r"""^(?:
        (?:the\s+)?official\s*(?:music\s+|lyrics?\s+)?
            (?:video|audio|visuali[sz]er|clip|version|mv)?
      | (?:music\s+|lyrics?\s+)?video(?:clip)?
      | lyrics?(?:\s+video)?
      | with\s+lyrics
      | audio
      | visuali[sz]er
      | full\s*hd | u?hd | hq | [48]k | \d{3,4}p
      | ofici[aá]ln[ií]\s*(?:videoklip|klip|video|audio|verze)
      | videoklip | klip
      | text(?:\s+p[ií]sn[eě])?
      | hudebn[ií]\s+video
    )$""",
    re.IGNORECASE | re.VERBOSE,
)

# Zavorky, ktere se prohledavaji.
_BRACKETS = ((r"\(", r"\)"), (r"\[", r"\]"), (r"\{", r"\}"))

# Kvalita nalepena na konec bez zavorky ("Pisnicka HD"). Zamerne uzky seznam -
# u holych slov bez zavorky je riziko, ze jsou soucasti nazvu, mnohem vetsi.
_TRAILING_QUALITY = re.compile(
    r"\s+(?:full\s*hd|u?hd|hq|[48]k|\d{3,4}p)$", re.IGNORECASE
)

# Oddelovace, za kterymi muze balast viset bez zavorky ("Pisnicka | Official Video").
_TAIL_SEPARATORS = ("|", "•", "·", "‖")


def strip_noise(title: str) -> str:
    """Odstrani z nazvu videa marketingovy balast.

    Maze se jen to, co tvori cely obsah zavorky nebo cely konec nazvu za
    oddelovacem - "(Official Video)" ano, "(Live at Wembley)" ani
    "(feat. XY)" ne. Kdyz by po vycisteni nezbylo nic, vraci se puvodni nazev.
    """
    text = _clean(title)
    if not text:
        return ""

    original = text

    for opening, closing in _BRACKETS:
        pattern = re.compile(rf"\s*{opening}([^{opening}{closing}]*){closing}")

        def drop(match: "re.Match[str]") -> str:
            return "" if _NOISE.match(match.group(1).strip()) else match.group(0)

        text = pattern.sub(drop, text)

    # Balast za oddelovacem na konci, klidne nekolikrat po sobe.
    for _ in range(3):
        stripped = _strip_tail(text)
        if stripped == text:
            break
        text = stripped

    text = _tidy(text)
    return text or original


def _strip_tail(text: str) -> str:
    for separator in _TAIL_SEPARATORS:
        head, found, tail = text.rpartition(separator)
        if found and head.strip() and _NOISE.match(tail.strip()):
            return head.strip()
    return text


def _tidy(text: str) -> str:
    """Uklidi zbytky po mazani - dvojite mezery a visici oddelovace."""
    text = re.sub(r"\s{2,}", " ", text).strip()
    for _ in range(2):
        shortened = _TRAILING_QUALITY.sub("", text).strip()
        if shortened == text:
            break
        # Pojistka: kdyz by po smazani zbyl jen interpret a visici pomlcka,
        # bylo to cele jmeno skladby ("Kapela - 4K") a mazat se nesmi.
        if re.search(r"[\-–—|]\s*$", shortened) or not shortened:
            break
        text = shortened
    text = re.sub(r"[\s\-–—|•·]+$", "", text).strip()
    text = re.sub(r"^[\s|•·]+", "", text).strip()
    return text


def _split_title(video_title: str) -> tuple[str, str, str]:
    """Rozdeli "Interpret - Skladba". Vraci (interpret, nazev, cislo skladby)."""
    if not video_title:
        return "", "", ""

    for separator in _SEPARATORS:
        if separator not in video_title:
            continue
        left, _, right = video_title.partition(separator)
        left, right = left.strip(), right.strip()
        if not left or not right:
            continue

        if _TRACK_NUMBER.match(left):
            return "", right, re.sub(r"\D", "", left)
        if len(left) > MAX_ARTIST_LEN:
            # Prilis dlouha leva strana je spis veta nez jmeno interpreta.
            break
        return left, right, ""

    return "", video_title, ""


def _first_value(info: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = info.get(key)
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(item) for item in value if item)
        text = _clean(value)
        if text:
            return text
    return ""


def _year(info: dict[str, Any]) -> str:
    value = info.get("release_year")
    if isinstance(value, int) and 1900 <= value <= 2200:
        return str(value)
    text = _clean(value)
    if re.fullmatch(r"(19|20|21)\d{2}", text):
        return text
    # Datum nahrani zamerne nepouzivame - rok uploadu neni rok vydani.
    return ""


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("", "none", "na", "n/a") else text


def write(path: Path, tags: Tags) -> bool:
    """Zapise tagy do MP3. Vraci False, kdyz to neslo.

    Existujici ramce (napr. obal vlozeny yt-dlp) zustavaji zachovane. Uklada
    se jako ID3v2.3, protoze Pruzkumnik Windows cte verzi 2.3 spolehliveji
    nez 2.4.
    """
    if tags.is_empty():
        return True

    try:
        from mutagen.id3 import (
            ID3,
            TALB,
            TDRC,
            TIT2,
            TPE1,
            TRCK,
            ID3NoHeaderError,
        )
    except ImportError:
        return False

    try:
        try:
            frames = ID3(str(path))
        except ID3NoHeaderError:
            frames = ID3()

        mapping = (
            ("TIT2", TIT2, tags.title),
            ("TPE1", TPE1, tags.artist),
            ("TALB", TALB, tags.album),
            ("TDRC", TDRC, tags.year),
            ("TRCK", TRCK, tags.track_number),
        )
        for key, frame, value in mapping:
            if value:
                frames.setall(key, [frame(encoding=3, text=[value])])

        frames.save(str(path), v2_version=3)
        return True
    except Exception:  # noqa: BLE001 - tagy nejsou duvod zahodit stazene MP3
        return False
