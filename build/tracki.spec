# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec pro jediny portable Tracki.exe.

Dve veci jsou tu zamerne:
  * upx=False - komprimovane exe soubory hlasi antiviry jako podezrele
    vyrazne casteji, takze se radeji smirime s vetsi velikosti,
  * version_info - exe s poradnymi metadaty projde heuristikami lip
    nez soubor bez nich.
"""
import pathlib

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = pathlib.Path(SPECPATH).resolve().parent
SRC = ROOT / "src"

datas = []
binaries = []

# Vzhledy customtkinteru jsou JSON soubory - bez nich se okno nepostavi.
datas += collect_data_files("customtkinter")

# Ikona do balicku, aby si ji okno naslo za behu.
icon_file = ROOT / "assets" / "tracki.ico"
if icon_file.is_file():
    datas.append((str(icon_file), "assets"))

# Prilozeny ffmpeg.exe. Bez nej aplikace nahlasi FFMPEG_MISSING.
ffmpeg = ROOT / "build" / "ffmpeg" / "ffmpeg.exe"
if ffmpeg.is_file():
    datas.append((str(ffmpeg), "ffmpeg"))
ffmpeg_license = ROOT / "build" / "ffmpeg" / "FFMPEG-LICENSE.txt"
if ffmpeg_license.is_file():
    datas.append((str(ffmpeg_license), "ffmpeg"))

# Vstupni skript je zamerne tracki_main.py, ne tracki/app.py: zabalene exe
# spousti vstup jako __main__ a relativni importy uvnitr balicku by selhaly.
a = Analysis(
    [str(SRC / "tracki_main.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # Jazyky se vybiraji za behu podle nastaveni, staticka analyza je
        # proto nevidi jako pouzite.
        "tracki.i18n.cs",
        "tracki.i18n.en",
        "tracki.ui.main_window",
        "darkdetect",
        # yt-dlp si extraktory dohledava dynamicky.
        *collect_submodules("yt_dlp"),
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Nic z toho aplikace nepouziva a jen by to nafouklo exe.
        "matplotlib", "numpy", "scipy", "pandas", "pytest",
        "setuptools", "pip", "wheel",
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "tkinter.test", "test", "unittest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Tracki",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_file) if icon_file.is_file() else None,
    version=str(ROOT / "build" / "version_info.txt"),
)
