"""Umisteni souboru: prenosny rezim vedle .exe, jinak %APPDATA%\\Tracki."""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP_NAME = "Tracki"
CONFIG_FILENAME = "tracki.json"

# Prazdny soubor s timto nazvem vedle .exe zapne prenosny rezim.
PORTABLE_MARKERS = ("tracki-portable.txt", "tracki-portable")

IS_WINDOWS = sys.platform == "win32"
IS_FROZEN = getattr(sys, "frozen", False)


def app_dir() -> Path:
    """Slozka, ze ktere aplikace bezi (u --onefile slozka s .exe)."""
    if IS_FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundle_dir() -> Path:
    """Slozka s rozbalenymi prilozenymi soubory (_MEIPASS u PyInstalleru)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def _is_writable(directory: Path) -> bool:
    try:
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".tracki-", delete=True):
            return True
    except OSError:
        return False


def portable_dir() -> Path | None:
    """Slozka vedle .exe, kdyz si uzivatel prenosny rezim vyslovne preje.

    Prenosny rezim se zapina prazdnym souborem tracki-portable.txt vedle
    Tracki.exe. Neni automaticky proto, ze .exe casto lezi na plose nebo ve
    Stazenych a nastaveni by se tam pletlo mezi ostatni soubory.
    """
    local = app_dir()
    for marker in PORTABLE_MARKERS:
        if (local / marker).is_file():
            return local if _is_writable(local) else None
    return None


def _roaming_dir() -> Path | None:
    """Standardni misto pro nastaveni aplikace v profilu uzivatele."""
    if IS_WINDOWS:
        base = os.environ.get("APPDATA")
        if not base:
            return None
        target = Path(base) / APP_NAME
    else:
        target = Path(
            os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        ) / APP_NAME.lower()

    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return target


def data_dir() -> Path:
    """Kam ukladat nastaveni a historii.

    Vychozi je %APPDATA%\\Tracki, aby vedle .exe nezustaval zadny dalsi
    soubor. Vedle .exe se uklada jen v prenosnem rezimu (viz portable_dir).
    """
    portable = portable_dir()
    if portable is not None:
        return portable

    roaming = _roaming_dir()
    if roaming is None:
        # Bez zapisovatelneho profilu je lepsi ulozit aspon nekam nez nikam.
        local = app_dir()
        return local if _is_writable(local) else Path.home()

    _migrate_legacy_config(app_dir(), roaming)
    return roaming


def _migrate_legacy_config(local: Path, roaming: Path) -> None:
    """Prestehuje nastaveni, ktere drivejsi verze nechavala vedle .exe.

    Bez toho by uzivatel po aktualizaci prisel o historii a stary soubor by mu
    zustal lezet treba na plose.
    """
    legacy = local / CONFIG_FILENAME
    target = roaming / CONFIG_FILENAME
    if target.exists() or not legacy.is_file():
        return

    try:
        shutil.move(str(legacy), str(target))
    except OSError:
        try:
            shutil.copy2(str(legacy), str(target))
        except OSError:
            pass  # nastaveni se proste zacne od vychozich hodnot


def config_path() -> Path:
    return data_dir() / CONFIG_FILENAME


# {374DE290-123F-4565-9164-39C4925E467B} = FOLDERID_Downloads
_FOLDERID_DOWNLOADS = "{374DE290-123F-4565-9164-39C4925E467B}"


def default_download_dir() -> Path:
    """Uzivatelova slozka Stazene. Na Windows pres SHGetKnownFolderPath, aby to
    fungovalo i kdyz si ji uzivatel presunul jinam nebo ma jinou jazykovou verzi.
    """
    if IS_WINDOWS:
        try:
            guid = ctypes.create_unicode_buffer(_FOLDERID_DOWNLOADS)
            fid = _GUID()
            if ctypes.windll.ole32.CLSIDFromString(guid, ctypes.byref(fid)) == 0:
                out = ctypes.c_wchar_p()
                res = ctypes.windll.shell32.SHGetKnownFolderPath(
                    ctypes.byref(fid), 0, None, ctypes.byref(out)
                )
                if res == 0 and out.value:
                    path = Path(out.value)
                    ctypes.windll.ole32.CoTaskMemFree(out)
                    if path.is_dir():
                        return path
        except (OSError, AttributeError, ValueError):
            pass

    candidate = Path.home() / "Downloads"
    if candidate.is_dir():
        return candidate
    return Path.home()


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def ffmpeg_path() -> str | None:
    """Cesta k prilozenemu ffmpeg.exe, nebo k systemovemu, nebo None."""
    names = ("ffmpeg.exe", "ffmpeg") if IS_WINDOWS else ("ffmpeg",)
    roots = (bundle_dir(), bundle_dir() / "ffmpeg", app_dir(), app_dir() / "ffmpeg")
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return str(candidate)

    from shutil import which

    return which("ffmpeg")


def explorer_select_command(path: Path) -> str:
    """Prikazova radka pro "explorer /select".

    Musi to byt jeden retezec, ne seznam argumentu. Kdyz se preda seznam,
    subprocess obali cely argument uvozovkami, jakmile v ceste najde mezeru:

        explorer "/select,C:\\Hudba\\Interpret - Skladba.mp3"

    Takovy zapis Pruzkumnik neprecte, soubor neoznaci a misto toho otevre
    vychozi slozku - tedy uplne jinou, nez uzivatel cekal. Spravne patri
    uvozovky jen kolem cesty:

        explorer /select,"C:\\Hudba\\Interpret - Skladba.mp3"
    """
    return f'explorer /select,"{path}"'


def open_folder(path: Path) -> None:
    """Otevre slozku v pruzkumniku; u souboru ho zaroven vybere."""
    path = Path(path)
    if IS_WINDOWS:
        if path.is_file():
            try:
                # Retezec zamerne misto seznamu - viz explorer_select_command.
                subprocess.Popen(explorer_select_command(path))
                return
            except OSError:
                pass  # spadneme na otevreni samotne slozky nize

        target = path if path.is_dir() else path.parent
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except OSError:
            subprocess.Popen(["explorer", str(target)])
        return

    target = path if path.is_dir() else path.parent
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(target)])


def open_file(path: Path) -> None:
    """Otevre soubor v prednastavenem prehravaci."""
    path = Path(path)
    if IS_WINDOWS:
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(path)])
