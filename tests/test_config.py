import json

from tracki.core.config import (
    MAX_HISTORY_LIMIT,
    HistoryEntry,
    Settings,
    Store,
)


def make_store(tmp_path):
    return Store(tmp_path / "tracki.json")


def test_defaults_when_file_missing(tmp_path):
    store = make_store(tmp_path).load()
    assert store.settings.language == "cs"
    assert store.settings.quality == "best"
    assert store.settings.output_dir  # doplni se slozka Stazene
    assert store.history == []
    assert store.load_error is None


def test_roundtrip(tmp_path):
    store = make_store(tmp_path).load()
    store.settings.theme = "dark"
    store.settings.language = "en"
    store.add_history(HistoryEntry(title="Song", path=str(tmp_path / "Song.mp3")))
    assert store.save()

    reloaded = make_store(tmp_path).load()
    assert reloaded.settings.theme == "dark"
    assert reloaded.settings.language == "en"
    assert [e.title for e in reloaded.history] == ["Song"]


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "tracki.json"
    path.write_text("{ this is not json", encoding="utf-8")
    store = Store(path).load()
    assert store.settings.theme == "system"
    assert store.load_error is not None


def test_unknown_and_invalid_values_are_repaired(tmp_path):
    path = tmp_path / "tracki.json"
    path.write_text(json.dumps({
        "settings": {
            "theme": "neon",
            "language": "de",
            "quality": "1411",
            "existing_policy": "explode",
            "max_history": -5,
            "write_tags": "yes",
            "unknown_key": 1,
        },
        "history": "not a list",
    }), encoding="utf-8")

    store = Store(path).load()
    assert store.settings.theme == "system"
    assert store.settings.language == "cs"
    assert store.settings.quality == "best"
    assert store.settings.existing_policy == "rename"
    assert store.settings.max_history == Settings().max_history
    assert store.settings.write_tags is True
    assert not hasattr(store.settings, "unknown_key")
    assert store.history == []


def test_history_drops_unusable_entries(tmp_path):
    path = tmp_path / "tracki.json"
    path.write_text(json.dumps({
        "history": [
            {"title": "ok", "path": "C:/x/ok.mp3"},
            {"title": "", "path": "C:/x/no-title.mp3"},
            {"title": "no path"},
            "garbage",
            None,
        ]
    }), encoding="utf-8")

    store = Store(path).load()
    assert [e.title for e in store.history] == ["ok"]


def test_add_history_deduplicates_by_path_and_keeps_newest_first(tmp_path):
    store = make_store(tmp_path).load()
    store.add_history(HistoryEntry(title="A", path="C:/a.mp3"))
    store.add_history(HistoryEntry(title="B", path="C:/b.mp3"))
    store.add_history(HistoryEntry(title="A again", path="C:/a.mp3"))

    assert [e.title for e in store.history] == ["A again", "B"]


def test_history_respects_limit(tmp_path):
    store = make_store(tmp_path).load()
    store.settings.max_history = 3
    for i in range(10):
        store.add_history(HistoryEntry(title=f"t{i}", path=f"C:/{i}.mp3"))
    assert len(store.history) == 3
    assert store.history[0].title == "t9"


def test_history_limit_is_capped(tmp_path):
    store = make_store(tmp_path).load()
    store.settings.max_history = 10**6
    assert store.load().settings.max_history <= MAX_HISTORY_LIMIT


def test_save_failure_is_reported_not_raised(tmp_path):
    store = Store(tmp_path / "nested" / "dir" / "tracki.json").load()
    assert store.save() is True
    # soubor misto slozky -> zapis neprojde, ale nesmi vyhodit vyjimku
    blocked = tmp_path / "blocked"
    blocked.write_text("x", encoding="utf-8")
    assert Store(blocked / "tracki.json").save() is False
