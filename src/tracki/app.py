"""Vstupni bod aplikace."""
from __future__ import annotations

from .core.config import Store
from .ui import theme


def main() -> int:
    store = Store().load()

    theme.apply_mode(store.settings.theme)

    from .ui.main_window import TrackiApp

    app = TrackiApp(store)
    app.mainloop()
    return 0
