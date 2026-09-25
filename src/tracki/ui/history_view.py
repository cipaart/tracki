"""Seznam naposledy stazenych souboru."""
from __future__ import annotations

import time
from typing import Any

import customtkinter as ctk

from .. import paths
from ..core import humanize
from ..core.config import HistoryEntry
from . import theme, widgets


class HistoryView(ctk.CTkFrame):
    def __init__(self, master: Any, app: Any) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.t = app.t
        self.fonts = app.fonts
        self._rows: list[dict[str, Any]] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, theme.PAD_SMALL))
        header.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(
            header, text=self.t("history.title"), font=self.fonts["heading"],
            text_color=theme.TEXT, anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        self.clear_button = widgets.danger_button(
            header, self.t("history.clear"), self._clear, self.fonts, width=140,
        )
        self.clear_button.grid(row=0, column=1, sticky="e")

        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=theme.SURFACE, corner_radius=theme.RADIUS,
            border_color=theme.BORDER, border_width=1,
        )
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        self.empty_label = ctk.CTkLabel(
            self.scroll, text=self.t("history.empty"), font=self.fonts["body"],
            text_color=theme.TEXT_MUTED, justify="center",
        )

        self.hint_label = ctk.CTkLabel(
            self, text=self.t("common.hint.keys"), font=self.fonts["small"],
            text_color=theme.TEXT_MUTED,
        )
        self.hint_label.grid(row=2, column=0, sticky="w", pady=(theme.PAD_SMALL, 0))

    # --- vykresleni -------------------------------------------------------
    def refresh(self) -> None:
        for row in self._rows:
            row["frame"].destroy()
        self._rows = []

        entries = self.app.store.history
        if not entries:
            self.empty_label.grid(row=0, column=0, pady=48)
            self.clear_button.configure(state="disabled")
            return

        self.empty_label.grid_remove()
        self.clear_button.configure(state="normal")
        for index, entry in enumerate(entries):
            self._rows.append(self._build_row(index, entry))

    def _build_row(self, index: int, entry: HistoryEntry) -> dict[str, Any]:
        frame = ctk.CTkFrame(self.scroll, fg_color="transparent",
                             corner_radius=theme.RADIUS_SMALL)
        frame.grid(row=index, column=0, sticky="ew", padx=6, pady=3)
        frame.grid_columnconfigure(0, weight=1)

        exists = entry.exists()
        text = ctk.CTkFrame(frame, fg_color="transparent")
        text.grid(row=0, column=0, sticky="ew", padx=(theme.PAD_SMALL, 0), pady=6)

        title_label = ctk.CTkLabel(
            text, text=humanize.shorten(entry.title, 58), font=self.fonts["body_bold"],
            text_color=theme.TEXT if exists else theme.TEXT_MUTED, anchor="w",
            justify="left",
        )
        title_label.pack(anchor="w")

        meta_parts = [_when(entry.timestamp)]
        if entry.size:
            meta_parts.append(humanize.size(entry.size))
        if not exists:
            meta_parts.append(self.t("history.missing"))
        meta_label = ctk.CTkLabel(
            text, text=" · ".join(p for p in meta_parts if p),
            font=self.fonts["small"], text_color=theme.TEXT_MUTED, anchor="w",
            justify="left",
        )
        meta_label.pack(anchor="w")

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=0, column=1, sticky="e", padx=(0, theme.PAD_SMALL))

        play = widgets.secondary_button(
            actions, self.t("history.play"), lambda e=entry: self._play(e),
            self.fonts, width=88, height=28,
        )
        play.pack(side="left")
        folder = widgets.secondary_button(
            actions, self.t("history.open_folder"), lambda e=entry: self._open(e),
            self.fonts, width=124, height=28,
        )
        folder.pack(side="left", padx=(6, 0))
        remove = widgets.danger_button(
            actions, "✕", lambda e=entry: self._remove(e), self.fonts,
            width=30, height=28,
        )
        remove.pack(side="left", padx=(6, 0))

        if not exists:
            play.configure(state="disabled")

        widgets.autowrap(title_label, frame, actions)
        widgets.autowrap(meta_label, frame, actions)

        return {"frame": frame, "entry": entry, "buttons": [play, folder, remove]}

    # --- akce -------------------------------------------------------------
    def _play(self, entry: HistoryEntry) -> None:
        if entry.exists():
            try:
                paths.open_file(entry.file)
                return
            except OSError:
                pass
        paths.open_folder(entry.file)

    def _open(self, entry: HistoryEntry) -> None:
        target = entry.file if entry.exists() else entry.file.parent
        if not target.exists():
            target = self.app.store.settings.download_dir
        paths.open_folder(target)

    def _remove(self, entry: HistoryEntry) -> None:
        self.app.store.remove_history(entry)
        self.app.store.save()
        self.refresh()
        self.app.rebuild_focus_ring()

    def _clear(self) -> None:
        if not self.app.store.history:
            return
        confirmed = widgets.ConfirmDialog.ask(
            self.app, self.t("history.clear.confirm"),
            self.t("common.yes"), self.t("common.no"), self.fonts,
        )
        if not confirmed:
            return
        self.app.store.clear_history()
        self.app.store.save()
        self.refresh()
        self.app.rebuild_focus_ring()

    def refresh_texts(self) -> None:
        self.title_label.configure(text=self.t("history.title"))
        self.clear_button.configure(text=self.t("history.clear"))
        self.empty_label.configure(text=self.t("history.empty"))
        self.hint_label.configure(text=self.t("common.hint.keys"))
        self.refresh()

    def register_focus(self, ring: Any) -> None:
        for row in self._rows:
            for button in row["buttons"]:
                if str(button.cget("state")) != "disabled":
                    ring.add(button)
        if str(self.clear_button.cget("state")) != "disabled":
            ring.add(self.clear_button)


def _when(timestamp: float) -> str:
    try:
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(timestamp))
    except (ValueError, OSError):
        return ""
