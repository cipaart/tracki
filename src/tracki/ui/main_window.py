"""Okno aplikace: navigace, klavesy a preklapeni udalosti ze stahovaciho vlakna.

Vsechny zmeny UI se deji tady, v hlavnim vlakne. Stahovaci vlakno jen strka
udalosti do fronty, kterou si tohle okno v pravidelnem tiku vybira.
"""
from __future__ import annotations

import queue
import time
from pathlib import Path
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from .. import paths
from ..core import downloader as dl
from ..core import humanize, urls
from ..core.config import HistoryEntry, Store
from ..core.errors import TrackiError, from_exception
from ..i18n import Translator
from . import theme, widgets
from .download_view import DownloadView
from .keynav import FocusRing
from .history_view import HistoryView
from .settings_view import SettingsView

PUMP_INTERVAL_MS = 70
MAX_EVENTS_PER_TICK = 40


class TrackiApp(ctk.CTk):
    def __init__(self, store: Store) -> None:
        super().__init__()
        self.store = store
        self.translator = Translator(store.settings.language)
        self.t = self.translator
        self.fonts = theme.fonts()

        self.events: "queue.Queue[dl.Event]" = queue.Queue()
        self.job: dl.DownloadJob | None = None
        self._completed: list[dl.ItemFinished] = []
        self._playlist_total = 1
        self._playlist_asked = False
        self._pending_history: list[HistoryEntry] = []
        self._skipped = 0
        self._failed: list[dl.ItemFailed] = []

        # Ring a mapa obrazovek musi existovat driv nez samotne obrazovky -
        # ty si do ringu registruji prvky uz pri sestaveni.
        self.ring = FocusRing()
        self.views: dict[str, Any] = {}
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self.current_screen = "download"

        self._setup_window()
        self._build_header()
        self._build_body()
        self._bind_keys()

        self.show_screen(store.settings.last_screen, remember=False)
        # Pole pro odkaz je aktivni hned po spusteni, i kdyz se otevre jina
        # obrazovka - Ctrl+V a Enter tak funguji okamzite.
        self.after(60, self._initial_focus)
        self.after(PUMP_INTERVAL_MS, self._pump)

    # --- stavba okna ------------------------------------------------------
    def _setup_window(self) -> None:
        self.title(self.t("app.title"))
        self.geometry("560x640")
        self.minsize(520, 560)
        self.configure(fg_color=theme.BG)
        theme.apply_mode(self.store.settings.theme)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        _set_window_icon(self)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=theme.PAD, pady=(theme.PAD, 0))
        header.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(brand, text=self.t("app.title"), font=self.fonts["title"],
                     text_color=theme.TEXT).pack(side="left")
        ctk.CTkLabel(brand, text=self.t("app.tagline"), font=self.fonts["small"],
                     text_color=theme.TEXT_MUTED).pack(side="left", padx=(8, 0), pady=(6, 0))

        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.grid(row=0, column=2, sticky="e")
        for screen, key in (("download", "nav.download"), ("history", "nav.history"),
                            ("settings", "nav.settings")):
            button = ctk.CTkButton(
                nav, text=self.t(key), font=self.fonts["body"],
                command=lambda s=screen: self.show_screen(s),
                fg_color="transparent", hover_color=theme.SURFACE_ALT,
                text_color=theme.TEXT_MUTED, width=84, height=30,
                corner_radius=theme.RADIUS_SMALL, border_width=0,
            )
            button.pack(side="left", padx=2)
            self.nav_buttons[screen] = button

    def _build_body(self) -> None:
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=theme.PAD,
                       pady=(theme.PAD_SMALL, theme.PAD))
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

        self.download_view = DownloadView(self.body, self)
        self.history_view = HistoryView(self.body, self)
        self.settings_view = SettingsView(self.body, self)
        self.views.update({
            "download": self.download_view,
            "history": self.history_view,
            "settings": self.settings_view,
        })

    def _bind_keys(self) -> None:
        self.bind_all("<Up>", self._on_up)
        self.bind_all("<Down>", self._on_down)
        self.bind_all("<Return>", self._on_return)
        self.bind_all("<KP_Enter>", self._on_return)
        self.bind_all("<Escape>", self._on_escape)
        self.bind_all("<Control-v>", self._on_paste)
        self.bind_all("<Control-V>", self._on_paste)

    def _initial_focus(self) -> None:
        self.download_view.focus_url()
        if self.current_screen == "download":
            self.focus_widget(self.download_view.url_entry)

    # --- navigace ---------------------------------------------------------
    def show_screen(self, screen: str, remember: bool = True) -> None:
        if screen not in self.views:
            screen = "download"
        for view in self.views.values():
            view.grid_remove()
        self.views[screen].grid(row=0, column=0, sticky="nsew")
        self.current_screen = screen

        for name, button in self.nav_buttons.items():
            active = name == screen
            button.configure(
                fg_color=theme.SURFACE if active else "transparent",
                text_color=theme.TEXT if active else theme.TEXT_MUTED,
            )

        if screen == "history":
            self.history_view.refresh()
        elif screen == "settings":
            self.settings_view.refresh()

        if remember and self.store.settings.last_screen != screen:
            self.store.settings.last_screen = screen
            self.store.save()

        self.rebuild_focus_ring()
        if screen == "download" and not self.is_working:
            self.download_view.focus_url()
            self.focus_widget(self.download_view.url_entry)
        else:
            self.ring.focus_first()

    def set_language(self, language: str) -> None:
        self.translator.set_language(language)
        self.title(self.t("app.title"))
        for screen, key in (("download", "nav.download"), ("history", "nav.history"),
                            ("settings", "nav.settings")):
            self.nav_buttons[screen].configure(text=self.t(key))
        for view in self.views.values():
            view.refresh_texts()
        self.rebuild_focus_ring()

    # --- klavesy ----------------------------------------------------------
    def _on_up(self, _event: Any = None) -> str:
        self.ring.move(-1)
        return "break"

    def _on_down(self, _event: Any = None) -> str:
        self.ring.move(1)
        return "break"

    def _on_return(self, _event: Any = None) -> str:
        self.ring.activate()
        return "break"

    def _on_escape(self, _event: Any = None) -> str | None:
        if self.current_screen != "download":
            self.show_screen("download")
            return "break"
        if self.is_working:
            # Behem stahovani Esc zamerne nedela nic - zruseni je vedomy krok
            # pres tlacitko, at se dlouhy playlist nezrusi omylem.
            return "break"
        if self.download_view.status_card.winfo_ismapped():
            self.download_view.reset()
            return "break"
        return None

    def _on_paste(self, _event: Any = None) -> str | None:
        if self._focus_in_url():
            return None  # necha probehnout normalni vlozeni do pole
        if self.current_screen != "download":
            self.show_screen("download")
        self.download_view.paste_from_clipboard()
        return "break"

    def _focus_in_url(self) -> bool:
        try:
            focused = self.focus_get()
        except Exception:  # noqa: BLE001
            return False
        if focused is None:
            return False
        return str(focused).startswith(str(self.download_view.url_entry))

    def rebuild_focus_ring(self) -> None:
        self.ring.clear()
        view = self.views.get(self.current_screen)
        if view is not None and hasattr(view, "register_focus"):
            view.register_focus(self.ring)
        for button in self.nav_buttons.values():
            self.ring.add(button)

    def focus_widget(self, widget: Any) -> None:
        self.ring.focus_widget(widget)

    # --- stahovani --------------------------------------------------------
    @property
    def is_working(self) -> bool:
        return self.job is not None and self.job.is_alive()

    def start_download(self, raw_url: str, quality: str) -> None:
        if self.is_working:
            return
        try:
            parsed = urls.parse(raw_url)
        except TrackiError as error:
            self.download_view.show_error(error)
            return

        request = dl.DownloadRequest.from_settings(
            parsed, self.store.settings, quality=quality
        )
        self._completed = []
        self._pending_history = []
        self._playlist_total = 1
        self._playlist_asked = False
        self._skipped = 0
        self._failed: list[dl.ItemFailed] = []

        self.events = queue.Queue()
        self.job = dl.DownloadJob(request, self.events)
        self.download_view.show_working()
        self.job.start()

    def cancel_download(self) -> None:
        if self.job is not None:
            self.job.cancel()
            self.download_view.set_indeterminate(self.t("main.cancel"))

    def choose_output_dir(self) -> None:
        chosen = filedialog.askdirectory(
            parent=self, initialdir=str(self.store.settings.download_dir),
            mustexist=True,
        )
        if not chosen:
            return
        self.store.settings.output_dir = chosen
        self.store.settings.normalized()
        self.store.save()
        self.download_view.refresh_texts()
        self.settings_view.refresh()

    # --- pumpa udalosti ---------------------------------------------------
    def _pump(self) -> None:
        try:
            for _ in range(MAX_EVENTS_PER_TICK):
                try:
                    event = self.events.get_nowait()
                except queue.Empty:
                    break
                self._handle(event)
        except Exception as exc:  # noqa: BLE001 - pumpa nesmi umrit
            self.download_view.show_error(from_exception(exc))
        finally:
            self.after(PUMP_INTERVAL_MS, self._pump)

    def _handle(self, event: dl.Event) -> None:
        view = self.download_view

        if isinstance(event, dl.Resolving):
            view.set_indeterminate(self.t("progress.resolving"))

        elif isinstance(event, dl.PlaylistResolved):
            self._playlist_total = max(event.total, 1)
            view.set_stage(self.t("progress.playlist",
                                  title=humanize.shorten(event.title, 34),
                                  total=event.total))
            view.set_overall(0, self._playlist_total)
            self._maybe_confirm_playlist(event.total)

        elif isinstance(event, dl.ItemStarted):
            self._playlist_total = max(event.total, self._playlist_total)
            view.set_stage(self.t("progress.downloading", percent=0),
                           self.t("progress.item", index=event.index,
                                  total=event.total,
                                  title=humanize.shorten(event.title, 40) or "…"))
            view.set_progress(0)

        elif isinstance(event, dl.Progress):
            view.set_stage(self.t("progress.downloading", percent=event.percent))
            view.set_progress(event.percent, self._progress_meta(event))

        elif isinstance(event, dl.Converting):
            view.set_indeterminate(self.t("progress.converting"))

        elif isinstance(event, dl.ItemFinished):
            self._completed.append(event)
            self._pending_history.append(HistoryEntry(
                title=event.title, path=str(event.path),
                url=self.download_view.url_entry.get().strip(),
                timestamp=time.time(), size=event.size,
                quality=self.download_view.current_quality(),
            ))
            view.set_overall(len(self._completed), self._playlist_total)

        elif isinstance(event, dl.ItemSkipped):
            self._skipped += 1
            view.set_overall(len(self._completed) + self._skipped,
                             self._playlist_total)

        elif isinstance(event, dl.ItemFailed):
            self._failed.append(event)

        elif isinstance(event, dl.JobFinished):
            self._finish(event)

        elif isinstance(event, dl.JobFailed):
            self.job = None
            view.show_error(event.error)

    def _progress_meta(self, event: dl.Progress) -> str:
        parts = []
        if event.total_bytes:
            parts.append(f"{humanize.size(event.downloaded)} / "
                         f"{humanize.size(event.total_bytes)}")
        speed = humanize.speed(event.speed)
        if speed:
            parts.append(speed)
        eta = humanize.duration(event.eta)
        if eta:
            parts.append(self.t("progress.eta", eta=eta))
        return " · ".join(parts)

    def _maybe_confirm_playlist(self, total: int) -> None:
        threshold = self.store.settings.confirm_playlist_over
        if self._playlist_asked or threshold <= 0 or total <= threshold:
            return
        self._playlist_asked = True
        confirmed = widgets.ConfirmDialog.ask(
            self, self.t("common.confirm.playlist", count=total),
            self.t("common.yes"), self.t("common.no"), self.fonts,
        )
        if not confirmed:
            self.cancel_download()

    def _finish(self, event: dl.JobFinished) -> None:
        self.job = None
        files = [item.path for item in self._completed]

        for entry in self._pending_history:
            self.store.add_history(entry)
        if self._pending_history:
            self.store.save()
            self.history_view.refresh()
        self._pending_history = []

        summary_parts = []
        skipped = self._skipped
        failed = self._failed
        if skipped:
            summary_parts.append(self.t("result.summary.skipped", count=skipped))
        if failed:
            summary_parts.append(self.t("result.summary.failed", count=len(failed)))
            names = [humanize.shorten(item.title or "?", 34) for item in failed[:3]]
            summary_parts.append(f'{self.t("result.failed.list")} ' + ", ".join(names))

        if not files and failed and not event.cancelled:
            # Nic se nestahlo a mame konkretni chybu - ukazeme ji misto "hotovo".
            self.download_view.show_error(failed[0].error)
            return

        self.download_view.show_done(files, "\n".join(summary_parts),
                                     cancelled=event.cancelled)

        if files and self.store.settings.open_folder_after and not event.cancelled:
            paths.open_folder(files[0])

    # --- ukonceni ---------------------------------------------------------
    def on_close(self) -> None:
        if self.job is not None:
            self.job.cancel()
        self.store.settings.last_screen = self.current_screen
        self.store.save()
        self.destroy()


def _set_window_icon(window: ctk.CTk) -> None:
    candidates = [
        paths.bundle_dir() / "assets" / "tracki.ico",
        paths.app_dir() / "assets" / "tracki.ico",
    ]
    for candidate in candidates:
        if candidate.is_file():
            try:
                window.iconbitmap(str(candidate))
                return
            except Exception:  # noqa: BLE001 - ikona neni kriticka
                continue
