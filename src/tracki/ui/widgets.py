"""Male opakovane pouzivane prvky UI."""
from __future__ import annotations

from typing import Any, Callable

import customtkinter as ctk

from . import theme


def autowrap(label: Any, container: Any, reserve_widget: Any = None,
             extra: int = 2 * theme.PAD, minimum: int = 140) -> None:
    """Zalamuje text podle skutecne sirky radku.

    Bez toho se dlouhy popisek schova pod ovladaci prvek vpravo a uzivatel
    uvidi jen jeho zacatek. Sirka se pocita az za behu, takze to drzi i pri
    zmene velikosti okna a pri jinem jazyce.
    """

    def on_configure(event: Any) -> None:
        reserve = 0
        if reserve_widget is not None:
            try:
                reserve = reserve_widget.winfo_width()
            except Exception:  # noqa: BLE001
                reserve = 0
        width = max(event.width - reserve - extra, minimum)
        try:
            if int(label.cget("wraplength")) != width:
                label.configure(wraplength=width)
        except Exception:  # noqa: BLE001
            pass

    container.bind("<Configure>", on_configure, add="+")


class Card(ctk.CTkFrame):
    """Panel s pozadim a obtazenim - zaklad vsech sekci."""

    def __init__(self, master: Any, **kwargs: Any) -> None:
        kwargs.setdefault("fg_color", theme.SURFACE)
        kwargs.setdefault("border_color", theme.BORDER)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("corner_radius", theme.RADIUS)
        super().__init__(master, **kwargs)


class SettingRow(ctk.CTkFrame):
    """Radek nastaveni: nazev + popisek vlevo, ovladaci prvek vpravo."""

    def __init__(
        self, master: Any, label: str, hint: str = "", fonts: dict | None = None
    ) -> None:
        super().__init__(master, fg_color="transparent")
        fonts = fonts or {}
        self.grid_columnconfigure(0, weight=1)

        text = ctk.CTkFrame(self, fg_color="transparent")
        text.grid(row=0, column=0, sticky="w", pady=(0, 2))
        self.label = ctk.CTkLabel(
            text, text=label, font=fonts.get("body_bold"), text_color=theme.TEXT,
            anchor="w", justify="left",
        )
        self.label.pack(anchor="w")
        self.hint_label = None
        if hint:
            self.hint_label = ctk.CTkLabel(
                text, text=hint, font=fonts.get("small"),
                text_color=theme.TEXT_MUTED, anchor="w", justify="left",
            )
            self.hint_label.pack(anchor="w")

        self.control = ctk.CTkFrame(self, fg_color="transparent")
        self.control.grid(row=0, column=1, sticky="e", padx=(theme.PAD, 0))

        autowrap(self.label, self, self.control)
        if self.hint_label is not None:
            autowrap(self.hint_label, self, self.control)

    def set_texts(self, label: str, hint: str = "") -> None:
        self.label.configure(text=label)
        if self.hint_label is not None:
            self.hint_label.configure(text=hint)


def primary_button(master: Any, text: str, command: Callable[[], None],
                   fonts: dict | None = None, **kwargs: Any) -> ctk.CTkButton:
    fonts = fonts or {}
    kwargs.setdefault("fg_color", theme.ACCENT)
    kwargs.setdefault("hover_color", theme.ACCENT_HOVER)
    kwargs.setdefault("text_color", theme.ACCENT_TEXT)
    kwargs.setdefault("corner_radius", theme.RADIUS_SMALL)
    kwargs.setdefault("height", 40)
    kwargs.setdefault("border_width", 0)
    return ctk.CTkButton(master, text=text, command=command,
                         font=fonts.get("body_bold"), **kwargs)


def secondary_button(master: Any, text: str, command: Callable[[], None],
                     fonts: dict | None = None, **kwargs: Any) -> ctk.CTkButton:
    fonts = fonts or {}
    kwargs.setdefault("fg_color", "transparent")
    kwargs.setdefault("hover_color", theme.SURFACE_ALT)
    kwargs.setdefault("text_color", theme.TEXT)
    kwargs.setdefault("border_color", theme.BORDER)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("corner_radius", theme.RADIUS_SMALL)
    kwargs.setdefault("height", 32)
    return ctk.CTkButton(master, text=text, command=command,
                         font=fonts.get("body"), **kwargs)


def danger_button(master: Any, text: str, command: Callable[[], None],
                  fonts: dict | None = None, **kwargs: Any) -> ctk.CTkButton:
    fonts = fonts or {}
    kwargs.setdefault("fg_color", "transparent")
    kwargs.setdefault("hover_color", theme.SURFACE_ALT)
    kwargs.setdefault("text_color", theme.DANGER)
    kwargs.setdefault("border_color", theme.BORDER)
    kwargs.setdefault("border_width", 1)
    kwargs.setdefault("corner_radius", theme.RADIUS_SMALL)
    kwargs.setdefault("height", 32)
    return ctk.CTkButton(master, text=text, command=command,
                         font=fonts.get("body"), **kwargs)


class ConfirmDialog(ctk.CTkToplevel):
    """Modalni potvrzeni. Enter = ano, Esc = ne, sipky prepinaji tlacitka."""

    def __init__(self, master: Any, message: str, yes: str, no: str,
                 fonts: dict | None = None, title: str = "Tracki") -> None:
        super().__init__(master)
        fonts = fonts or {}
        self.result = False

        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self.transient(master)

        ctk.CTkLabel(
            self, text=message, font=fonts.get("body"), text_color=theme.TEXT,
            justify="left", wraplength=340,
        ).pack(padx=theme.PAD + 4, pady=(theme.PAD + 4, theme.PAD))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=theme.PAD + 4, pady=(0, theme.PAD + 4), fill="x")

        self._no = secondary_button(row, no, self._decline, fonts, width=110)
        self._no.pack(side="right")
        self._yes = primary_button(row, yes, self._accept, fonts, width=110, height=32)
        self._yes.pack(side="right", padx=(0, theme.PAD_SMALL))

        self._buttons = [self._yes, self._no]
        self._index = 0

        self.bind("<Return>", self._on_enter)
        self.bind("<Escape>", lambda _e: self._decline())
        self.bind("<Up>", lambda _e: self._move(-1))
        self.bind("<Down>", lambda _e: self._move(1))
        self.bind("<Left>", lambda _e: self._move(-1))
        self.bind("<Right>", lambda _e: self._move(1))
        self.protocol("WM_DELETE_WINDOW", self._decline)

        self.after(10, self._setup_modal)

    def _setup_modal(self) -> None:
        _center_on_parent(self)
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass
        self._highlight()

    def _move(self, delta: int) -> None:
        self._index = (self._index + delta) % len(self._buttons)
        self._highlight()

    def _highlight(self) -> None:
        for index, button in enumerate(self._buttons):
            focused = index == self._index
            button.configure(border_width=2 if focused else (0 if index == 0 else 1),
                             border_color=theme.ACCENT if focused else theme.BORDER)
        self._buttons[self._index].focus_set()

    def _on_enter(self, _event: Any = None) -> None:
        self._buttons[self._index].invoke()

    def _accept(self) -> None:
        self.result = True
        self.destroy()

    def _decline(self) -> None:
        self.result = False
        self.destroy()

    @classmethod
    def ask(cls, master: Any, message: str, yes: str, no: str,
            fonts: dict | None = None) -> bool:
        dialog = cls(master, message, yes, no, fonts)
        master.wait_window(dialog)
        return dialog.result


def _center_on_parent(window: ctk.CTkToplevel) -> None:
    try:
        window.update_idletasks()
        parent = window.master
        x = parent.winfo_rootx() + (parent.winfo_width() - window.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - window.winfo_height()) // 3
        window.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    except Exception:  # noqa: BLE001
        pass
