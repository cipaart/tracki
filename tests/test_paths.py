"""Testy otevirani slozek.

Hlavni vec, kterou tu hlidame: prikaz pro "explorer /select" se musi skladat
jako jeden retezec s uvozovkami kolem cesty. Pri predani seznamu argumentu
subprocess obali uvozovkami cely argument "/select,...", jakmile je v ceste
mezera - Pruzkumnik to neprecte a otevre uplne jinou slozku.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path, PureWindowsPath

import pytest

from tracki import paths

WINDOWS_FILE = Path(r"C:\Users\cipaa\Desktop\Tracki\Bedřich Ludvík - Stromy.mp3")


# --- sestaveni prikazu ------------------------------------------------------
def test_select_command_quotes_only_the_path():
    command = paths.explorer_select_command(WINDOWS_FILE)
    assert command.startswith('explorer /select,"')
    assert command.endswith('.mp3"')
    # uvozovka nesmi byt hned za "explorer " - tam zacina prepinac
    assert not command.startswith('explorer "')


def test_select_command_is_not_the_broken_list_form():
    """Regrese: takhle to vypadalo, kdyz se predaval seznam argumentu."""
    broken = subprocess.list2cmdline(["explorer", f"/select,{WINDOWS_FILE}"])
    assert broken == f'explorer "/select,{WINDOWS_FILE}"'  # co delal chybny kod
    assert paths.explorer_select_command(WINDOWS_FILE) != broken


@pytest.mark.parametrize("name", [
    "Bedřich Ludvík - Stromy.mp3",      # mezery i diakritika
    "Priessnitz - Sluníčko.mp3",
    "BezMezer.mp3",
    "100% Live Session.mp3",
    "Skladba (feat. Někdo).mp3",
])
def test_select_command_survives_real_filenames(name):
    # PureWindowsPath, aby test spojoval cesty po windowsku i kdyz bezi jinde
    command = paths.explorer_select_command(PureWindowsPath(r"C:\Hudba") / name)
    assert command == f'explorer /select,"C:\\Hudba\\{name}"'
    assert name in command


# --- chovani open_folder ----------------------------------------------------
@pytest.fixture
def windows(monkeypatch):
    """Predstira Windows a odchytava, co by se spustilo."""
    calls: dict[str, list] = {"popen": [], "startfile": []}
    monkeypatch.setattr(paths, "IS_WINDOWS", True)
    monkeypatch.setattr(paths.subprocess, "Popen",
                        lambda command, *a, **kw: calls["popen"].append(command))
    monkeypatch.setattr(os, "startfile", calls["startfile"].append, raising=False)
    return calls


def test_file_is_selected_with_a_string_command(windows, tmp_path):
    target = tmp_path / "Interpret - Skladba.mp3"
    target.write_bytes(b"x")

    paths.open_folder(target)

    assert len(windows["popen"]) == 1
    command = windows["popen"][0]
    assert isinstance(command, str), "seznam argumentu Pruzkumnik neprecte"
    assert command == f'explorer /select,"{target}"'
    assert not windows["startfile"]


def test_directory_is_opened_directly(windows, tmp_path):
    paths.open_folder(tmp_path)

    assert windows["startfile"] == [str(tmp_path)]
    assert not windows["popen"]


def test_missing_file_falls_back_to_its_folder(windows, tmp_path):
    missing = tmp_path / "uz-tu-neni.mp3"

    paths.open_folder(missing)

    assert windows["startfile"] == [str(tmp_path)]
    assert not windows["popen"]


def test_startfile_failure_falls_back_to_explorer(monkeypatch, tmp_path):
    popen_calls: list = []

    def boom(_path):
        raise OSError("neco se pokazilo")

    monkeypatch.setattr(paths, "IS_WINDOWS", True)
    monkeypatch.setattr(os, "startfile", boom, raising=False)
    monkeypatch.setattr(paths.subprocess, "Popen",
                        lambda command, *a, **kw: popen_calls.append(command))

    paths.open_folder(tmp_path)

    assert popen_calls == [["explorer", str(tmp_path)]]


# --- ostatni systemy --------------------------------------------------------
def test_non_windows_opens_parent_folder_of_a_file(monkeypatch, tmp_path):
    calls: list = []
    monkeypatch.setattr(paths, "IS_WINDOWS", False)
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setattr(paths.subprocess, "Popen",
                        lambda command, *a, **kw: calls.append(command))

    target = tmp_path / "song.mp3"
    target.write_bytes(b"x")
    paths.open_folder(target)

    assert calls == [["xdg-open", str(tmp_path)]]


# --- kam se uklada nastaveni -----------------------------------------------
@pytest.fixture
def fake_windows_profile(monkeypatch, tmp_path):
    """Predstira Windows s profilem uzivatele a slozkou, kde lezi .exe."""
    exe_dir = tmp_path / "Desktop" / "Tracki"
    appdata = tmp_path / "AppData" / "Roaming"
    exe_dir.mkdir(parents=True)
    appdata.mkdir(parents=True)

    monkeypatch.setattr(paths, "IS_WINDOWS", True)
    monkeypatch.setattr(paths, "app_dir", lambda: exe_dir)
    monkeypatch.setenv("APPDATA", str(appdata))
    return exe_dir, appdata / "Tracki"


def test_config_does_not_land_next_to_the_exe(fake_windows_profile):
    exe_dir, roaming = fake_windows_profile

    assert paths.data_dir() == roaming
    assert paths.config_path() == roaming / "tracki.json"
    # ve slozce s .exe nesmi nic pribyt, i kdyz je zapisovatelna
    assert list(exe_dir.iterdir()) == []


def test_portable_marker_keeps_config_next_to_the_exe(fake_windows_profile):
    exe_dir, _roaming = fake_windows_profile
    (exe_dir / "tracki-portable.txt").write_text("", encoding="utf-8")

    assert paths.data_dir() == exe_dir
    assert paths.portable_dir() == exe_dir


def test_old_config_next_to_exe_is_moved_away(fake_windows_profile):
    exe_dir, roaming = fake_windows_profile
    legacy = exe_dir / "tracki.json"
    legacy.write_text('{"settings": {"theme": "dark"}}', encoding="utf-8")

    assert paths.data_dir() == roaming

    moved = roaming / "tracki.json"
    assert moved.is_file()
    assert "dark" in moved.read_text(encoding="utf-8")
    assert not legacy.exists(), "stary soubor mel z plochy zmizet"


def test_migration_keeps_history_readable(fake_windows_profile, monkeypatch):
    from tracki.core.config import Store

    exe_dir, roaming = fake_windows_profile
    (exe_dir / "tracki.json").write_text(
        '{"settings": {"language": "en"},'
        ' "history": [{"title": "Skladba", "path": "C:/x/Skladba.mp3"}]}',
        encoding="utf-8",
    )

    store = Store(paths.config_path()).load()
    assert store.settings.language == "en"
    assert [entry.title for entry in store.history] == ["Skladba"]


def test_migration_never_overwrites_existing_config(fake_windows_profile):
    exe_dir, roaming = fake_windows_profile
    roaming.mkdir(parents=True, exist_ok=True)
    (roaming / "tracki.json").write_text('{"settings": {"theme": "light"}}',
                                         encoding="utf-8")
    (exe_dir / "tracki.json").write_text('{"settings": {"theme": "dark"}}',
                                         encoding="utf-8")

    paths.data_dir()

    assert "light" in (roaming / "tracki.json").read_text(encoding="utf-8")
    assert (exe_dir / "tracki.json").is_file()  # cizi soubor se nemaze


def test_portable_mode_does_not_migrate(fake_windows_profile):
    exe_dir, roaming = fake_windows_profile
    (exe_dir / "tracki-portable.txt").write_text("", encoding="utf-8")
    (exe_dir / "tracki.json").write_text("{}", encoding="utf-8")

    assert paths.data_dir() == exe_dir
    assert (exe_dir / "tracki.json").is_file()
    assert not (roaming / "tracki.json").exists()


def test_missing_appdata_falls_back_without_crashing(monkeypatch, tmp_path):
    exe_dir = tmp_path / "app"
    exe_dir.mkdir()
    monkeypatch.setattr(paths, "IS_WINDOWS", True)
    monkeypatch.setattr(paths, "app_dir", lambda: exe_dir)
    monkeypatch.delenv("APPDATA", raising=False)

    assert paths.data_dir() == exe_dir
