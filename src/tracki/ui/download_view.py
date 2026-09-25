"""Hlavni obrazovka: vlozeni odkazu, prubeh, vysledek, chyba.

Stavova plocha ma ctyri podoby (idle / working / done / error) a prepina se
jejich schovavanim, takze se pri kazdem stahovani nestavi widgety znovu.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk

from .. import paths
from ..core import humanize
from ..core.config import DEFAULT_QUALITY, QUALITY_PRESETS
from ..core.errors import TrackiError
from . import theme, widgets


class DownloadView(ctk.CTkFrame):
    def __init__(self, master: Any, app: Any) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.t = app.t
        self.fonts = app.fonts
        self._detail_open = False
        self._last_error: TrackiError | None = None
        self._result_paths: list[Path] = []

        self.grid_columnconfigure(0, weight=1)
        self._build_input()
        self._build_status()
        self._build_footer()
        self.show_idle()

    # --- stavba -----------------------------------------------------------
    def _build_input(self) -> None:
        card = widgets.Card(self)
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        self.url_label = ctk.CTkLabel(
            card, text=self.t("main.url.label"), font=self.fonts["small"],
            text_color=theme.TEXT_MUTED, anchor="w",
        )
        self.url_label.grid(row=0, column=0, columnspan=2, sticky="w",
                            padx=theme.PAD, pady=(theme.PAD, 4))

        self.url_entry = ctk.CTkEntry(
            card, placeholder_text=self.t("main.url.placeholder"),
            font=self.fonts["body"], height=40, corner_radius=theme.RADIUS_SMALL,
            fg_color=theme.SURFACE_ALT, border_color=theme.BORDER, border_width=1,
            text_color=theme.TEXT,
        )
        self.url_entry.grid(row=1, column=0, sticky="ew", padx=(theme.PAD, 6))
        self.url_entry.bind("<Return>", lambda _e: self.start())

        self.paste_button = widgets.secondary_button(
            card, self.t("main.paste"), self.paste_from_clipboard, self.fonts,
            width=84, height=40,
        )
        self.paste_button.grid(row=1, column=1, sticky="e", padx=(0, theme.PAD))

        # Vyber kvality - zobrazi se jen kdyz je v nastaveni zapnuty dotaz.
        self.quality_row = ctk.CTkFrame(card, fg_color="transparent")
        self.quality_row.grid(row=2, column=0, columnspan=2, sticky="ew",
                              padx=theme.PAD, pady=(theme.PAD_SMALL, 0))
        self.quality_label = ctk.CTkLabel(
            self.quality_row, text=self.t("main.quality.label"),
            font=self.fonts["small"], text_color=theme.TEXT_MUTED,
        )
        self.quality_label.pack(side="left", padx=(0, theme.PAD_SMALL))
        self.quality_menu = ctk.CTkOptionMenu(
            self.quality_row, values=self._quality_values(),
            command=self._on_quality_pick, font=self.fonts["body"],
            width=180, height=30, corner_radius=theme.RADIUS_SMALL,
            fg_color=theme.SURFACE_ALT, button_color=theme.SURFACE_ALT,
            button_hover_color=theme.BORDER, text_color=theme.TEXT,
            dropdown_fg_color=theme.SURFACE, dropdown_text_color=theme.TEXT,
            dropdown_hover_color=theme.SURFACE_ALT,
        )
        self.quality_menu.pack(side="left")
        self._chosen_quality = self.app.store.settings.quality

        self.download_button = widgets.primary_button(
            card, self.t("main.download"), self.start, self.fonts,
        )
        self.download_button.grid(row=3, column=0, columnspan=2, sticky="ew",
                                  padx=theme.PAD, pady=(theme.PAD, theme.PAD_SMALL))

        dest = ctk.CTkFrame(card, fg_color="transparent")
        dest.grid(row=4, column=0, columnspan=2, sticky="ew",
                  padx=theme.PAD, pady=(0, theme.PAD))
        self.dest_label = ctk.CTkLabel(
            dest, text="", font=self.fonts["small"], text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.dest_label.pack(side="left")
        self.dest_button = ctk.CTkButton(
            dest, text=self.t("main.dest.change"), command=self.app.choose_output_dir,
            font=self.fonts["small"], fg_color="transparent",
            hover_color=theme.SURFACE_ALT, text_color=theme.ACCENT,
            width=60, height=22, border_width=0, corner_radius=theme.RADIUS_SMALL,
        )
        self.dest_button.pack(side="left", padx=(6, 0))

    def _build_status(self) -> None:
        self.status_card = widgets.Card(self)
        self.status_card.grid(row=1, column=0, sticky="ew", pady=(theme.PAD, 0))
        self.status_card.grid_columnconfigure(0, weight=1)

        # --- prubeh ---
        self.working = ctk.CTkFrame(self.status_card, fg_color="transparent")
        self.working.grid_columnconfigure(0, weight=1)
        self.stage_label = ctk.CTkLabel(
            self.working, text="", font=self.fonts["body_bold"],
            text_color=theme.TEXT, anchor="w", justify="left",
        )
        self.stage_label.grid(row=0, column=0, sticky="w", padx=theme.PAD,
                              pady=(theme.PAD, 2))
        self.item_label = ctk.CTkLabel(
            self.working, text="", font=self.fonts["small"],
            text_color=theme.TEXT_MUTED, anchor="w", justify="left",
        )
        self.item_label.grid(row=1, column=0, sticky="w", padx=theme.PAD, pady=(0, 8))

        self.progress = ctk.CTkProgressBar(
            self.working, height=8, corner_radius=4,
            progress_color=theme.ACCENT, fg_color=theme.TRACK,
        )
        self.progress.grid(row=2, column=0, sticky="ew", padx=theme.PAD)
        self.progress.set(0)

        self.meta_label = ctk.CTkLabel(
            self.working, text="", font=self.fonts["small"],
            text_color=theme.TEXT_MUTED, anchor="w",
        )
        self.meta_label.grid(row=3, column=0, sticky="w", padx=theme.PAD, pady=(6, 0))

        self.overall_progress = ctk.CTkProgressBar(
            self.working, height=5, corner_radius=3,
            progress_color=theme.SUCCESS, fg_color=theme.TRACK,
        )
        self.overall_label = ctk.CTkLabel(
            self.working, text="", font=self.fonts["small"],
            text_color=theme.TEXT_MUTED, anchor="w",
        )

        self.cancel_button = widgets.secondary_button(
            self.working, self.t("main.cancel"), self.app.cancel_download, self.fonts,
            width=110,
        )
        self.cancel_button.grid(row=6, column=0, sticky="w", padx=theme.PAD,
                                pady=(theme.PAD, theme.PAD))

        # --- hotovo ---
        self.done = ctk.CTkFrame(self.status_card, fg_color="transparent")
        self.done.grid_columnconfigure(0, weight=1)
        self.done_title = ctk.CTkLabel(
            self.done, text="", font=self.fonts["heading"],
            text_color=theme.SUCCESS, anchor="w",
        )
        self.done_title.grid(row=0, column=0, sticky="w", padx=theme.PAD,
                             pady=(theme.PAD, 2))
        self.done_file = ctk.CTkLabel(
            self.done, text="", font=self.fonts["body"], text_color=theme.TEXT,
            anchor="w", justify="left", wraplength=430,
        )
        self.done_file.grid(row=1, column=0, sticky="w", padx=theme.PAD, pady=(0, 2))
        self.done_summary = ctk.CTkLabel(
            self.done, text="", font=self.fonts["small"],
            text_color=theme.TEXT_MUTED, anchor="w", justify="left", wraplength=430,
        )
        self.done_summary.grid(row=2, column=0, sticky="w", padx=theme.PAD, pady=(0, 2))

        done_actions = ctk.CTkFrame(self.done, fg_color="transparent")
        done_actions.grid(row=3, column=0, sticky="w", padx=theme.PAD,
                          pady=(theme.PAD_SMALL, theme.PAD))
        self.open_folder_button = widgets.primary_button(
            done_actions, self.t("result.open_folder"), self._open_result_folder,
            self.fonts, height=32, width=150,
        )
        self.open_folder_button.pack(side="left")
        self.play_button = widgets.secondary_button(
            done_actions, self.t("result.play"), self._play_result, self.fonts,
            width=100,
        )
        self.play_button.pack(side="left", padx=(theme.PAD_SMALL, 0))
        self.again_button = widgets.secondary_button(
            done_actions, self.t("result.again"), self.reset, self.fonts, width=140,
        )
        self.again_button.pack(side="left", padx=(theme.PAD_SMALL, 0))

        # --- chyba ---
        self.error = ctk.CTkFrame(self.status_card, fg_color="transparent")
        self.error.grid_columnconfigure(0, weight=1)
        self.error_title = ctk.CTkLabel(
            self.error, text="", font=self.fonts["heading"],
            text_color=theme.DANGER, anchor="w", justify="left", wraplength=430,
        )
        self.error_title.grid(row=0, column=0, sticky="w", padx=theme.PAD,
                              pady=(theme.PAD, 4))
        self.error_hint = ctk.CTkLabel(
            self.error, text="", font=self.fonts["body"], text_color=theme.TEXT,
            anchor="w", justify="left", wraplength=430,
        )
        self.error_hint.grid(row=1, column=0, sticky="w", padx=theme.PAD, pady=(0, 4))

        error_actions = ctk.CTkFrame(self.error, fg_color="transparent")
        error_actions.grid(row=2, column=0, sticky="w", padx=theme.PAD,
                           pady=(theme.PAD_SMALL, 0))
        self.detail_button = ctk.CTkButton(
            error_actions, text=self.t("error.details.show"),
            command=self._toggle_detail, font=self.fonts["small"],
            fg_color="transparent", hover_color=theme.SURFACE_ALT,
            text_color=theme.ACCENT, width=140, height=24, border_width=0,
        )
        self.detail_button.pack(side="left")
        self.copy_button = ctk.CTkButton(
            error_actions, text=self.t("error.copy"), command=self._copy_detail,
            font=self.fonts["small"], fg_color="transparent",
            hover_color=theme.SURFACE_ALT, text_color=theme.ACCENT,
            width=120, height=24, border_width=0,
        )

        self.detail_box = ctk.CTkTextbox(
            self.error, height=96, font=self.fonts["mono"],
            fg_color=theme.SURFACE_ALT, text_color=theme.TEXT_MUTED,
            border_color=theme.BORDER, border_width=1,
            corner_radius=theme.RADIUS_SMALL, wrap="word",
        )

        self.retry_button = widgets.primary_button(
            self.error, self.t("main.download"), self.start, self.fonts,
            height=32, width=150,
        )
        self.retry_button.grid(row=4, column=0, sticky="w", padx=theme.PAD,
                               pady=(theme.PAD, theme.PAD))

    def _build_footer(self) -> None:
        self.hint_label = ctk.CTkLabel(
            self, text=self.t("common.hint.keys"), font=self.fonts["small"],
            text_color=theme.TEXT_MUTED,
        )
        self.hint_label.grid(row=2, column=0, sticky="w", pady=(theme.PAD, 0))

    # --- stavy ------------------------------------------------------------
    def _hide_all(self) -> None:
        for frame in (self.working, self.done, self.error):
            frame.grid_remove()

    def show_idle(self) -> None:
        self._hide_all()
        self.status_card.grid_remove()
        self._set_download_enabled(True)
        self.url_entry.configure(state="normal")
        self.refresh_texts()
        self.app.rebuild_focus_ring()

    def show_working(self) -> None:
        self._hide_all()
        self.status_card.grid()
        self.working.grid(row=0, column=0, sticky="ew")
        self.progress.set(0)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.stage_label.configure(text=self.t("progress.resolving"))
        self.item_label.configure(text="")
        self.meta_label.configure(text="")
        self.overall_progress.grid_remove()
        self.overall_label.grid_remove()
        self._set_download_enabled(False)
        self.app.rebuild_focus_ring()
        self.app.focus_widget(self.cancel_button)

    def show_done(self, files: list[Path], summary: str, cancelled: bool = False) -> None:
        self._hide_all()
        self.status_card.grid()
        self.done.grid(row=0, column=0, sticky="ew")
        self._result_paths = list(files)
        count = len(files)

        if cancelled:
            title = (self.t("result.cancelled.partial", count=count) if count
                     else self.t("result.cancelled"))
            self.done_title.configure(text=title, text_color=theme.TEXT_MUTED)
        elif count == 1:
            self.done_title.configure(text=self.t("result.done.one"),
                                      text_color=theme.SUCCESS)
        else:
            self.done_title.configure(text=self.t("result.done.many", count=count),
                                      text_color=theme.SUCCESS)

        if count == 1:
            self.done_file.configure(text=files[0].name)
        elif count > 1:
            preview = "\n".join(f"· {p.name}" for p in files[:3])
            if count > 3:
                preview += f"\n· … (+{count - 3})"
            self.done_file.configure(text=preview)
        else:
            self.done_file.configure(text="")

        self.done_summary.configure(text=summary)
        state = "normal" if count else "disabled"
        self.open_folder_button.configure(state=state)
        self.play_button.configure(state="normal" if count == 1 else "disabled")
        self._set_download_enabled(True)
        self.app.rebuild_focus_ring()

        if count and not cancelled:
            # Po uspesnem stazeni je pole hned prazdne a zamerene, aby slo
            # rovnou dat Ctrl+V a Enter. Vysledek zustava videt nad nim.
            self.clear_url()
            self.app.focus_widget(self.url_entry)
        else:
            # Po zruseni nebo kdyz nic nevzniklo necháme odkaz v poli -
            # uzivatel ho nejspis bude chtit zkusit znovu.
            self.app.focus_widget(
                self.open_folder_button if count else self.again_button
            )

    def show_error(self, error: TrackiError) -> None:
        self._hide_all()
        self.status_card.grid()
        self.error.grid(row=0, column=0, sticky="ew")
        self._last_error = error

        self.error_title.configure(text=self.t(f"error.{error.code}.title", **error.params)
                                   or self.t("error.UNKNOWN.title"))
        self.error_hint.configure(text=self.t(f"error.{error.code}.hint", **error.params))

        self._detail_open = False
        self.detail_box.grid_remove()
        self.copy_button.pack_forget()
        has_detail = bool(self._detail_text())
        if has_detail:
            self.detail_button.configure(text=self.t("error.details.show"))
            self.detail_button.pack(side="left")
        else:
            self.detail_button.pack_forget()

        self._set_download_enabled(True)
        self.app.rebuild_focus_ring()
        self.app.focus_widget(self.retry_button)

    def clear_url(self) -> None:
        """Vyprazdni pole s odkazem a nastavi do nej kurzor."""
        self.url_entry.configure(state="normal")
        self.url_entry.delete(0, "end")
        self.url_entry.focus_set()

    def reset(self) -> None:
        self.show_idle()
        self.clear_url()

    def _set_download_enabled(self, enabled: bool) -> None:
        """Zakazane tlacitko musi i vypadat zakazane, jinak na nej lidi klikaji."""
        self.download_button.configure(
            state="normal" if enabled else "disabled",
            text=self.t("main.download"),
            fg_color=theme.ACCENT if enabled else theme.SURFACE_ALT,
            hover_color=theme.ACCENT_HOVER if enabled else theme.SURFACE_ALT,
            text_color=theme.ACCENT_TEXT if enabled else theme.TEXT_MUTED,
        )

    # --- prubeh -----------------------------------------------------------
    def set_stage(self, text: str, item: str = "") -> None:
        self.stage_label.configure(text=text)
        if item:
            self.item_label.configure(text=item)

    def set_progress(self, percent: float, meta: str = "") -> None:
        if str(self.progress.cget("mode")) == "indeterminate":
            self.progress.stop()
            self.progress.configure(mode="determinate")
        self.progress.set(max(0.0, min(percent / 100.0, 1.0)))
        self.meta_label.configure(text=meta)

    def set_overall(self, done: int, total: int) -> None:
        if total <= 1:
            self.overall_progress.grid_remove()
            self.overall_label.grid_remove()
            return
        self.overall_progress.grid(row=4, column=0, sticky="ew", padx=theme.PAD,
                                   pady=(theme.PAD_SMALL, 4))
        self.overall_label.grid(row=5, column=0, sticky="w", padx=theme.PAD)
        self.overall_progress.set(done / total if total else 0)
        self.overall_label.configure(text=self.t("progress.overall", done=done, total=total))

    def set_indeterminate(self, text: str) -> None:
        self.stage_label.configure(text=text)
        if str(self.progress.cget("mode")) != "indeterminate":
            self.progress.configure(mode="indeterminate")
            self.progress.start()
        self.meta_label.configure(text="")

    # --- akce -------------------------------------------------------------
    def start(self) -> None:
        self.app.start_download(self.url_entry.get(), self.current_quality())

    def current_quality(self) -> str:
        settings = self.app.store.settings
        if not settings.ask_quality:
            return settings.quality
        return self._chosen_quality

    def paste_from_clipboard(self) -> None:
        try:
            text = self.clipboard_get()
        except Exception:  # noqa: BLE001 - prazdna schranka vyhodi TclError
            return
        text = (text or "").strip()
        if not text:
            return
        self.url_entry.configure(state="normal")
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, text)
        self.url_entry.focus_set()
        self.url_entry.icursor("end")
        self.app.focus_widget(self.url_entry)

    def focus_url(self) -> None:
        self.url_entry.focus_set()
        self.url_entry.icursor("end")

    def _open_result_folder(self) -> None:
        if self._result_paths:
            paths.open_folder(self._result_paths[0])

    def _play_result(self) -> None:
        if len(self._result_paths) == 1:
            try:
                paths.open_file(self._result_paths[0])
            except OSError:
                paths.open_folder(self._result_paths[0])

    def _detail_text(self) -> str:
        if not self._last_error:
            return ""
        parts = [f"code: {self._last_error.code}"]
        if self._last_error.params:
            parts.append(f"params: {self._last_error.params}")
        if self._last_error.detail:
            parts.append(self._last_error.detail)
        return "\n".join(parts)

    def _toggle_detail(self) -> None:
        self._detail_open = not self._detail_open
        if self._detail_open:
            self.detail_box.configure(state="normal")
            self.detail_box.delete("1.0", "end")
            self.detail_box.insert("1.0", self._detail_text())
            self.detail_box.configure(state="disabled")
            self.detail_box.grid(row=3, column=0, sticky="ew", padx=theme.PAD,
                                 pady=(theme.PAD_SMALL, 0))
            self.detail_button.configure(text=self.t("error.details.hide"))
            self.copy_button.pack(side="left", padx=(theme.PAD_SMALL, 0))
        else:
            self.detail_box.grid_remove()
            self.detail_button.configure(text=self.t("error.details.show"))
            self.copy_button.pack_forget()
        self.app.rebuild_focus_ring()

    def _copy_detail(self) -> None:
        text = self._detail_text()
        if not text:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
        except Exception:  # noqa: BLE001
            return
        self.copy_button.configure(text=self.t("error.copied"))
        self.after(1500, lambda: self.copy_button.configure(text=self.t("error.copy")))

    def _on_quality_pick(self, label: str) -> None:
        self._chosen_quality = self._quality_from_label(label)

    def _quality_values(self) -> list[str]:
        return [self._quality_label(value) for value in QUALITY_PRESETS]

    def _quality_label(self, value: str) -> str:
        if value == DEFAULT_QUALITY:
            return self.t("settings.quality.best")
        return self.t("settings.quality.kbps", value=value)

    def _quality_from_label(self, label: str) -> str:
        for value in QUALITY_PRESETS:
            if self._quality_label(value) == label:
                return value
        return DEFAULT_QUALITY

    # --- prekresleni po zmene jazyka/nastaveni ----------------------------
    def refresh_texts(self) -> None:
        settings = self.app.store.settings
        self.url_label.configure(text=self.t("main.url.label"))
        self.url_entry.configure(placeholder_text=self.t("main.url.placeholder"))
        self.paste_button.configure(text=self.t("main.paste"))
        self.download_button.configure(text=self.t("main.download"))
        self.cancel_button.configure(text=self.t("main.cancel"))
        self.open_folder_button.configure(text=self.t("result.open_folder"))
        self.play_button.configure(text=self.t("result.play"))
        self.again_button.configure(text=self.t("result.again"))
        self.retry_button.configure(text=self.t("main.download"))
        self.copy_button.configure(text=self.t("error.copy"))
        self.quality_label.configure(text=self.t("main.quality.label"))
        self.dest_button.configure(text=self.t("main.dest.change"))
        self.hint_label.configure(text=self.t("common.hint.keys"))
        self.dest_label.configure(text=self.t(
            "main.dest", path=humanize.shorten_path(str(settings.download_dir))
        ))

        if settings.ask_quality:
            self.quality_row.grid()
            self.quality_menu.configure(values=self._quality_values())
            if self._chosen_quality not in QUALITY_PRESETS:
                self._chosen_quality = settings.quality
            self.quality_menu.set(self._quality_label(self._chosen_quality))
        else:
            self.quality_row.grid_remove()

    # --- klavesove poradi -------------------------------------------------
    def register_focus(self, ring: Any) -> None:
        ring.add(self.url_entry, self.start)
        ring.add(self.paste_button)
        if self.app.store.settings.ask_quality:
            ring.add(self.quality_menu)
        if str(self.download_button.cget("state")) != "disabled":
            ring.add(self.download_button)
        if self.working.winfo_ismapped():
            ring.add(self.cancel_button)
        if self.done.winfo_ismapped():
            for button in (self.open_folder_button, self.play_button, self.again_button):
                if str(button.cget("state")) != "disabled":
                    ring.add(button)
        if self.error.winfo_ismapped():
            ring.add(self.retry_button)
            if self._detail_text():
                ring.add(self.detail_button)
            if self._detail_open:
                ring.add(self.copy_button)
        ring.add(self.dest_button)
