"""Prepinani jazyka. Chybejici klic nikdy nespadne - vrati sam sebe."""
from __future__ import annotations

from . import cs, en

LANGUAGES: dict[str, dict[str, str]] = {"cs": cs.TEXTS, "en": en.TEXTS}
FALLBACK = "cs"


class Translator:
    def __init__(self, language: str = FALLBACK) -> None:
        self.language = language if language in LANGUAGES else FALLBACK

    def set_language(self, language: str) -> None:
        self.language = language if language in LANGUAGES else FALLBACK

    def __call__(self, key: str, **params: object) -> str:
        return self.text(key, **params)

    def text(self, key: str, **params: object) -> str:
        template = LANGUAGES[self.language].get(key)
        if template is None:
            template = LANGUAGES[FALLBACK].get(key)
        if template is None:
            # Radeji ukazat klic nez spadnout - chybejici preklad je kosmeticka vada.
            return key
        try:
            return template.format(**params) if params else template
        except (KeyError, IndexError, ValueError):
            return template
