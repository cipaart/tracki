from tracki.core.naming import MAX_STEM, escape_outtmpl, resolve_target, safe_stem


def test_strips_windows_forbidden_characters():
    stem = safe_stem('A/B\\C:D*E?F"G<H>I|J')
    for char in '/\\:*?"<>|':
        assert char not in stem


def test_strips_trailing_dots_and_spaces():
    assert safe_stem("Nazev pisnicky...  ") == "Nazev pisnicky"
    assert not safe_stem("test. . .").endswith((".", " "))


def test_collapses_whitespace_and_control_chars():
    assert safe_stem("a\t\n  b\x07c") == "a bc"


def test_reserved_device_names_get_suffix():
    assert safe_stem("CON") == "CON_"
    assert safe_stem("nul") == "nul_"
    assert safe_stem("COM1.mp3") != "COM1.mp3"


def test_length_is_capped():
    assert len(safe_stem("x" * 400)) <= MAX_STEM


def test_empty_title_uses_fallback():
    assert safe_stem("") == "audio"
    assert safe_stem("   ...   ") == "audio"
    assert safe_stem("", fallback="track") == "track"


def test_unicode_is_preserved():
    assert safe_stem("Zpěvák – Písnička č. 3") == "Zpěvák – Písnička č. 3"


def test_escape_outtmpl():
    assert escape_outtmpl("100% cotton") == "100%% cotton"


def test_resolve_target_free_name(tmp_path):
    assert resolve_target(tmp_path, "song", "rename") == tmp_path / "song.mp3"


def test_resolve_target_rename(tmp_path):
    (tmp_path / "song.mp3").touch()
    assert resolve_target(tmp_path, "song", "rename") == tmp_path / "song (2).mp3"
    (tmp_path / "song (2).mp3").touch()
    assert resolve_target(tmp_path, "song", "rename") == tmp_path / "song (3).mp3"


def test_resolve_target_overwrite(tmp_path):
    (tmp_path / "song.mp3").touch()
    assert resolve_target(tmp_path, "song", "overwrite") == tmp_path / "song.mp3"


def test_resolve_target_skip(tmp_path):
    (tmp_path / "song.mp3").touch()
    assert resolve_target(tmp_path, "song", "skip") is None
