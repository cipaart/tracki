"""Klavesova navigace.

Kazda obrazovka si zaregistruje prvky v poradi, v jakem po nich ma chodit
sipka nahoru/dolu. Enter aktivuje zamereny prvek, Esc resi obrazovka sama.
Zamereny prvek se zvyrazni obtazenim, aby bylo videt, kde uzivatel je.
"""
from __future__ import annotations

from typing import Any, Callable


class FocusRing:
    def __init__(self) -> None:
        self._items: list[dict[str, Any]] = []
        self._index: int = -1

    # --- sprava prvku -----------------------------------------------------
    def clear(self) -> None:
        self._unhighlight()
        self._items = []
        self._index = -1

    def add(
        self,
        widget: Any,
        activate: Callable[[], None] | None = None,
        *,
        highlight: bool = True,
    ) -> Any:
        """Zaregistruje prvek do poradi. activate je akce pro Enter."""
        original: dict[str, Any] = {}
        if highlight:
            for option in ("border_width", "border_color"):
                try:
                    original[option] = widget.cget(option)
                except Exception:  # noqa: BLE001 - ne kazdy widget to ma
                    pass

        self._items.append({
            "widget": widget,
            "activate": activate,
            "highlight": highlight and bool(original),
            "original": original,
        })
        # Klik mysi ma posunout i logicky kurzor, aby sipky pokracovaly odtud.
        try:
            widget.bind("<FocusIn>", lambda _event, w=widget: self._sync(w), add="+")
            widget.bind("<Button-1>", lambda _event, w=widget: self._sync(w), add="+")
        except Exception:  # noqa: BLE001
            pass
        return widget

    # --- pohyb ------------------------------------------------------------
    def focus_first(self) -> None:
        if self._items:
            self._focus(0)

    def focus_widget(self, widget: Any) -> None:
        for index, item in enumerate(self._items):
            if item["widget"] is widget:
                self._focus(index)
                return

    def move(self, delta: int) -> None:
        if not self._items:
            return
        usable = [i for i, item in enumerate(self._items) if _is_usable(item["widget"])]
        if not usable:
            return
        if self._index in usable:
            position = usable.index(self._index)
            target = usable[(position + delta) % len(usable)]
        else:
            target = usable[0] if delta > 0 else usable[-1]
        self._focus(target)

    def activate(self) -> bool:
        """Vraci True, kdyz se neco stalo (aby sla udalost spolknout)."""
        item = self._current()
        if not item:
            return False
        action = item["activate"]
        widget = item["widget"]
        if action:
            action()
            return True
        for method in ("invoke", "toggle"):
            func = getattr(widget, method, None)
            if callable(func):
                func()
                return True
        return False

    # --- vnitrnosti -------------------------------------------------------
    def _current(self) -> dict[str, Any] | None:
        if 0 <= self._index < len(self._items):
            return self._items[self._index]
        return None

    def _sync(self, widget: Any) -> None:
        for index, item in enumerate(self._items):
            if item["widget"] is widget:
                if index != self._index:
                    self._unhighlight()
                    self._index = index
                    self._highlight()
                return

    def _focus(self, index: int) -> None:
        self._unhighlight()
        self._index = index
        item = self._current()
        if not item:
            return
        widget = item["widget"]
        try:
            widget.focus_set()
        except Exception:  # noqa: BLE001
            pass
        self._highlight()

    def _highlight(self) -> None:
        item = self._current()
        if not item or not item["highlight"]:
            return
        from . import theme

        try:
            item["widget"].configure(border_width=2, border_color=theme.ACCENT)
        except Exception:  # noqa: BLE001
            pass

    def _unhighlight(self) -> None:
        item = self._current()
        if not item or not item["highlight"]:
            return
        try:
            item["widget"].configure(**item["original"])
        except Exception:  # noqa: BLE001
            pass


def _is_usable(widget: Any) -> bool:
    """Preskoci schovane a vypnute prvky."""
    try:
        if not widget.winfo_exists() or not widget.winfo_ismapped():
            return False
    except Exception:  # noqa: BLE001
        return False
    try:
        if str(widget.cget("state")) == "disabled":
            return False
    except Exception:  # noqa: BLE001
        pass
    return True
