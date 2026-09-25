from tracki.core import humanize


def test_size_units():
    assert humanize.size(0) == "0 B"
    assert humanize.size(512) == "512 B"
    assert humanize.size(2048) == "2 kB"
    assert humanize.size(5 * 1024 * 1024) == "5.0 MB"
    assert humanize.size(3 * 1024**3).endswith("GB")
    assert humanize.size(None) == "0 B"


def test_speed_hides_nonsense():
    assert humanize.speed(None) == ""
    assert humanize.speed(0) == ""
    assert humanize.speed(-5) == ""
    assert humanize.speed(1_500_000).endswith("/s")


def test_duration():
    assert humanize.duration(None) == ""
    assert humanize.duration(-1) == ""
    assert humanize.duration(45) == "45 s"
    assert humanize.duration(75) == "1:15"
    assert humanize.duration(3725) == "1:02:05"


def test_shorten_path_keeps_both_ends():
    out = humanize.shorten_path("C:/Users/jan/Music/a/b/c/d/stazene", 20)
    assert out.startswith("C:/Users")
    assert out.endswith("stazene")
    assert len(out) <= 21


def test_shorten_path_leaves_short_paths_alone():
    assert humanize.shorten_path("C:/Music") == "C:/Music"


def test_shorten_adds_ellipsis():
    assert humanize.shorten("x" * 100, 10).endswith("…")
    assert humanize.shorten("short", 10) == "short"
