import re

from tracki.i18n import LANGUAGES, Translator

PLACEHOLDER = re.compile(r"\{(\w+)")


def test_all_languages_have_the_same_keys():
    keys = {name: set(texts) for name, texts in LANGUAGES.items()}
    reference = keys["cs"]
    for name, own in keys.items():
        assert own == reference, f"{name} se lisi: {own ^ reference}"


def test_placeholders_match_across_languages():
    for key, template in LANGUAGES["cs"].items():
        expected = set(PLACEHOLDER.findall(template))
        actual = set(PLACEHOLDER.findall(LANGUAGES["en"][key]))
        assert expected == actual, f"{key}: {expected} vs {actual}"


def test_every_error_code_has_title_and_hint():
    codes = {
        key.split(".")[1]
        for key in LANGUAGES["cs"]
        if key.startswith("error.") and key.count(".") == 2
        and key.split(".")[1].isupper()
    }
    assert len(codes) > 20  # at test nekontroluje prazdnou mnozinu
    for code in codes:
        for lang in LANGUAGES:
            assert f"error.{code}.title" in LANGUAGES[lang]
            assert f"error.{code}.hint" in LANGUAGES[lang]


def test_error_codes_raised_by_code_are_all_translated():
    from tracki.core import errors, urls  # noqa: F401
    import inspect

    sources = [inspect.getsource(m) for m in (urls, errors)]
    from tracki.core import downloader

    sources.append(inspect.getsource(downloader))
    raised = set(re.findall(r'TrackiError\(\s*"([A-Z_]+)"', "\n".join(sources)))
    raised |= {code for _, code in errors._PATTERNS}
    raised.add("UNKNOWN")

    missing = [c for c in raised if f"error.{c}.title" not in LANGUAGES["cs"]]
    assert not missing, f"chybi preklad pro: {missing}"


def test_translator_formats_and_falls_back():
    t = Translator("cs")
    assert "vimeo.com" in t("error.URL_NOT_YOUTUBE.hint", host="vimeo.com")
    assert t("naprosto.neexistujici.klic") == "naprosto.neexistujici.klic"
    # chybejici parametr nesmi shodit UI
    assert t("error.URL_NOT_YOUTUBE.hint") != ""


def test_language_switch():
    t = Translator("en")
    assert t("nav.settings") == "Settings"
    t.set_language("cs")
    assert t("nav.settings") == "Nastavení"
    t.set_language("zz")
    assert t.language == "cs"
