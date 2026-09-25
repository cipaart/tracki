"""Obrazovka nastaveni. Kazda zmena se ulozi hned, zadne tlacitko Ulozit."""
from __future__ import annotations

from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from .. import paths
from ..core import humanize
from ..core.config import (
    DEFAULT_QUALITY,
    EXISTING_POLICIES,
    LANGUAGES,
    QUALITY_PRESETS,
    THEMES,
)
from . import theme, widgets

VERSION = "1.0.0"
HISTORY_CHOICES = ("25", "50", "100", "250", "500")
PLAYLIST_CHOICES = ("0", "10", "20", "50", "100")


class SettingsView(ctk.CTkFrame):
    def __init__(self, master: Any, app: Any) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.t = app.t
        self.fonts = app.fonts
        self._switches: list[ctk.CTkSwitch] = []
        self._menus: list[ctk.CTkOptionMenu] = []
        self._rows: list[tuple[widgets.SettingRow, str, str]] = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.title_label = ctk.CTkLabel(
            self, text=self.t("settings.title"), font=self.fonts["heading"],
            text_color=theme.TEXT, anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="w", pady=(0, theme.PAD_SMALL))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        self._build_download_section()
        self._build_appearance_section()
        self._build_behavior_section()
        self._build_about_section()

        self.hint_label = ctk.CTkLabel(
            self, text=self.t("common.hint.keys"), font=self.fonts["small"],
            text_color=theme.TEXT_MUTED,
        )
        self.hint_label.grid(row=2, column=0, sticky="w", pady=(theme.PAD_SMALL, 0))

        self.refresh()

    # --- sekce ------------------------------------------------------------
    def _section(self, key: str, row: int) -> ctk.CTkFrame:
        heading = ctk.CTkLabel(
            self.scroll, text=self.t(key), font=self.fonts["small"],
            text_color=theme.TEXT_MUTED, anchor="w",
        )
        heading.grid(row=row * 2, column=0, sticky="w",
                     pady=(theme.PAD if row else 0, 4), padx=2)
        card = widgets.Card(self.scroll)
        card.grid(row=row * 2 + 1, column=0, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self._rows.append((heading, key, ""))  # type: ignore[arg-type]
        return card

    def _row(self, parent: ctk.CTkFrame, index: int, label_key: str,
             hint_key: str = "") -> widgets.SettingRow:
        row = widgets.SettingRow(
            parent, self.t(label_key), self.t(hint_key) if hint_key else "", self.fonts,
        )
        row.grid(row=index, column=0, sticky="ew", padx=theme.PAD,
                 pady=(theme.PAD if index == 0 else theme.PAD_SMALL, theme.PAD_SMALL))
        self._rows.append((row, label_key, hint_key))
        return row

    def _build_download_section(self) -> None:
        card = self._section("settings.section.download", 0)

        self.dir_row = self._row(card, 0, "settings.output_dir", "settings.output_dir.hint")
        self.dir_value = ctk.CTkLabel(
            self.dir_row.control, text="", font=self.fonts["small"],
            text_color=theme.TEXT_MUTED,
        )
        self.dir_value.pack(side="left", padx=(0, theme.PAD_SMALL))
        self.dir_button = widgets.secondary_button(
            self.dir_row.control, self.t("settings.output_dir.browse"),
            self._choose_dir, self.fonts, width=96, height=30,
        )
        self.dir_button.pack(side="left")
        self.dir_reset = ctk.CTkButton(
            self.dir_row.control, text="⟲", command=self._reset_dir,
            font=self.fonts["body"], fg_color="transparent",
            hover_color=theme.SURFACE_ALT, text_color=theme.ACCENT,
            width=30, height=30, border_width=0,
        )
        self.dir_reset.pack(side="left", padx=(6, 0))

        self.quality_row = self._row(card, 1, "settings.quality", "settings.quality.hint")
        self.quality_menu = self._option_menu(
            self.quality_row.control, self._quality_values(), self._on_quality, width=180,
        )

        self.ask_quality_row = self._row(card, 2, "settings.ask_quality")
        self.ask_quality_switch = self._switch(
            self.ask_quality_row.control, self._on_ask_quality,
        )

        self.existing_row = self._row(card, 3, "settings.existing")
        self.existing_menu = self._option_menu(
            self.existing_row.control, self._existing_values(), self._on_existing,
            width=220,
        )

    def _build_appearance_section(self) -> None:
        card = self._section("settings.section.appearance", 1)

        self.theme_row = self._row(card, 0, "settings.theme")
        self.theme_menu = self._option_menu(
            self.theme_row.control, self._theme_values(), self._on_theme, width=160,
        )

        self.language_row = self._row(card, 1, "settings.language")
        self.language_menu = self._option_menu(
            self.language_row.control, self._language_values(), self._on_language,
            width=160,
        )

    def _build_behavior_section(self) -> None:
        card = self._section("settings.section.behavior", 2)

        self.tags_row = self._row(card, 0, "settings.write_tags")
        self.tags_switch = self._switch(self.tags_row.control, self._on_tags)

        self.cover_row = self._row(card, 1, "settings.embed_cover")
        self.cover_switch = self._switch(self.cover_row.control, self._on_cover)

        self.clean_titles_row = self._row(
            card, 2, "settings.clean_titles", "settings.clean_titles.hint",
        )
        self.clean_titles_switch = self._switch(
            self.clean_titles_row.control, self._on_clean_titles,
        )

        self.open_after_row = self._row(card, 3, "settings.open_folder_after")
        self.open_after_switch = self._switch(
            self.open_after_row.control, self._on_open_after,
        )

        self.history_row = self._row(card, 4, "settings.max_history")
        self.history_menu = self._option_menu(
            self.history_row.control,
            [self.t("settings.max_history.value", count=int(c)) for c in HISTORY_CHOICES],
            self._on_history, width=160,
        )

        self.playlist_row = self._row(card, 5, "settings.confirm_playlist")
        self.playlist_menu = self._option_menu(
            self.playlist_row.control, self._playlist_values(), self._on_playlist,
            width=160,
        )

    def _build_about_section(self) -> None:
        card = self._section("settings.section.about", 3)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=theme.PAD, pady=theme.PAD)

        self.version_label = ctk.CTkLabel(
            inner, text=self.t("settings.about.version", version=VERSION),
            font=self.fonts["body_bold"], text_color=theme.TEXT, anchor="w",
        )
        self.version_label.pack(anchor="w")
        self.privacy_label = ctk.CTkLabel(
            inner, text=self.t("settings.about.privacy"), font=self.fonts["small"],
            text_color=theme.TEXT_MUTED, anchor="w", justify="left",
        )
        self.privacy_label.pack(anchor="w", pady=(6, 8))
        self.config_label = ctk.CTkLabel(
            inner, text=f'{self.t("settings.about.config")} {paths.config_path()}',
            font=self.fonts["small"], text_color=theme.TEXT_MUTED,
            anchor="w", justify="left", wraplength=430,
        )
        self.config_label.pack(anchor="w")
        self.config_button = widgets.secondary_button(
            inner, self.t("settings.about.open_config"),
            lambda: paths.open_folder(paths.data_dir()), self.fonts, width=220,
        )
        self.config_button.pack(anchor="w", pady=(theme.PAD_SMALL, theme.PAD_SMALL))
        self.portable_label = ctk.CTkLabel(
            inner, text=self.t("settings.about.portable"), font=self.fonts["small"],
            text_color=theme.TEXT_MUTED, anchor="w", justify="left", wraplength=430,
        )
        self.portable_label.pack(anchor="w")

    # --- pomocnici pro ovladaci prvky -------------------------------------
    def _option_menu(self, parent: Any, values: list[str], command: Any,
                     width: int = 160) -> ctk.CTkOptionMenu:
        menu = ctk.CTkOptionMenu(
            parent, values=values, command=command, font=self.fonts["body"],
            width=width, height=30, corner_radius=theme.RADIUS_SMALL,
            fg_color=theme.SURFACE_ALT, button_color=theme.SURFACE_ALT,
            button_hover_color=theme.BORDER, text_color=theme.TEXT,
            dropdown_fg_color=theme.SURFACE, dropdown_text_color=theme.TEXT,
            dropdown_hover_color=theme.SURFACE_ALT,
        )
        menu.pack(side="left")
        self._menus.append(menu)
        return menu

    def _switch(self, parent: Any, command: Any) -> ctk.CTkSwitch:
        switch = ctk.CTkSwitch(
            parent, text="", command=command, width=44,
            progress_color=theme.ACCENT, fg_color=theme.TRACK,
            button_color=("#ffffff", "#e6e9ef"),
        )
        switch.pack(side="left")
        self._switches.append(switch)
        return switch

    # --- hodnoty <-> popisky ---------------------------------------------
    def _quality_values(self) -> list[str]:
        return [self._quality_label(v) for v in QUALITY_PRESETS]

    def _quality_label(self, value: str) -> str:
        if value == DEFAULT_QUALITY:
            return self.t("settings.quality.best")
        return self.t("settings.quality.kbps", value=value)

    def _existing_values(self) -> list[str]:
        return [self.t(f"settings.existing.{p}") for p in EXISTING_POLICIES]

    def _theme_values(self) -> list[str]:
        return [self.t(f"settings.theme.{v}") for v in THEMES]

    def _language_values(self) -> list[str]:
        return [self.t(f"settings.language.{v}") for v in LANGUAGES]

    def _playlist_values(self) -> list[str]:
        return [
            self.t("common.no") if c == "0"
            else self.t("settings.confirm_playlist.value", count=int(c))
            for c in PLAYLIST_CHOICES
        ]

    @staticmethod
    def _pick(values: list[str], options: tuple[str, ...], label: str,
              fallback: str) -> str:
        for option, text in zip(options, values):
            if text == label:
                return option
        return fallback

    # --- obsluha zmen -----------------------------------------------------
    def _on_quality(self, label: str) -> None:
        self._save(quality=self._pick(self._quality_values(), QUALITY_PRESETS,
                                      label, DEFAULT_QUALITY))

    def _on_ask_quality(self) -> None:
        self._save(ask_quality=bool(self.ask_quality_switch.get()))
        self.app.download_view.refresh_texts()
        self.app.rebuild_focus_ring()

    def _on_existing(self, label: str) -> None:
        self._save(existing_policy=self._pick(self._existing_values(),
                                              EXISTING_POLICIES, label, "rename"))

    def _on_theme(self, label: str) -> None:
        value = self._pick(self._theme_values(), THEMES, label, "system")
        self._save(theme=value)
        theme.apply_mode(value)

    def _on_language(self, label: str) -> None:
        value = self._pick(self._language_values(), tuple(LANGUAGES), label, "cs")
        self._save(language=value)
        self.app.set_language(value)

    def _on_tags(self) -> None:
        self._save(write_tags=bool(self.tags_switch.get()))

    def _on_cover(self) -> None:
        self._save(embed_cover=bool(self.cover_switch.get()))

    def _on_clean_titles(self) -> None:
        self._save(clean_titles=bool(self.clean_titles_switch.get()))

    def _on_open_after(self) -> None:
        self._save(open_folder_after=bool(self.open_after_switch.get()))

    def _on_history(self, label: str) -> None:
        values = [self.t("settings.max_history.value", count=int(c))
                  for c in HISTORY_CHOICES]
        choice = self._pick(values, HISTORY_CHOICES, label, "100")
        self._save(max_history=int(choice))
        self.app.store.load_error = None
        self.app.history_view.refresh()

    def _on_playlist(self, label: str) -> None:
        choice = self._pick(self._playlist_values(), PLAYLIST_CHOICES, label, "20")
        self._save(confirm_playlist_over=int(choice))

    def _choose_dir(self) -> None:
        current = str(self.app.store.settings.download_dir)
        chosen = filedialog.askdirectory(
            parent=self.app, initialdir=current, mustexist=True,
        )
        if chosen:
            self._save(output_dir=chosen)
            self.refresh()
            self.app.download_view.refresh_texts()

    def _reset_dir(self) -> None:
        self._save(output_dir=str(paths.default_download_dir()))
        self.refresh()
        self.app.download_view.refresh_texts()

    def _save(self, **changes: Any) -> None:
        settings = self.app.store.settings
        for key, value in changes.items():
            setattr(settings, key, value)
        settings.normalized()
        self.app.store.save()

    # --- napojeni hodnot na UI -------------------------------------------
    def refresh(self) -> None:
        settings = self.app.store.settings
        self.quality_menu.set(self._quality_label(settings.quality))
        self.existing_menu.set(self.t(f"settings.existing.{settings.existing_policy}"))
        self.theme_menu.set(self.t(f"settings.theme.{settings.theme}"))
        self.language_menu.set(self.t(f"settings.language.{settings.language}"))
        self.history_menu.set(
            self.t("settings.max_history.value", count=settings.max_history)
        )
        self.playlist_menu.set(
            self.t("common.no") if settings.confirm_playlist_over == 0
            else self.t("settings.confirm_playlist.value",
                        count=settings.confirm_playlist_over)
        )
        self.dir_value.configure(
            text=humanize.shorten_path(str(settings.download_dir), 34)
        )
        for switch, value in (
            (self.ask_quality_switch, settings.ask_quality),
            (self.tags_switch, settings.write_tags),
            (self.cover_switch, settings.embed_cover),
            (self.clean_titles_switch, settings.clean_titles),
            (self.open_after_switch, settings.open_folder_after),
        ):
            switch.select() if value else switch.deselect()

    def refresh_texts(self) -> None:
        self.title_label.configure(text=self.t("settings.title"))
        self.hint_label.configure(text=self.t("common.hint.keys"))
        for row, label_key, hint_key in self._rows:
            if isinstance(row, widgets.SettingRow):
                row.set_texts(self.t(label_key), self.t(hint_key) if hint_key else "")
            else:
                row.configure(text=self.t(label_key))

        self.quality_menu.configure(values=self._quality_values())
        self.existing_menu.configure(values=self._existing_values())
        self.theme_menu.configure(values=self._theme_values())
        self.language_menu.configure(values=self._language_values())
        self.playlist_menu.configure(values=self._playlist_values())
        self.history_menu.configure(values=[
            self.t("settings.max_history.value", count=int(c)) for c in HISTORY_CHOICES
        ])
        self.dir_button.configure(text=self.t("settings.output_dir.browse"))
        self.version_label.configure(
            text=self.t("settings.about.version", version=VERSION)
        )
        self.privacy_label.configure(text=self.t("settings.about.privacy"))
        self.config_label.configure(
            text=f'{self.t("settings.about.config")} {paths.config_path()}'
        )
        self.config_button.configure(text=self.t("settings.about.open_config"))
        self.portable_label.configure(text=self.t("settings.about.portable"))
        self.refresh()

    def register_focus(self, ring: Any) -> None:
        ring.add(self.dir_button)
        ring.add(self.dir_reset)
        ring.add(self.quality_menu)
        ring.add(self.ask_quality_switch)
        ring.add(self.existing_menu)
        ring.add(self.theme_menu)
        ring.add(self.language_menu)
        ring.add(self.tags_switch)
        ring.add(self.cover_switch)
        ring.add(self.clean_titles_switch)
        ring.add(self.open_after_switch)
        ring.add(self.history_menu)
        ring.add(self.playlist_menu)
        ring.add(self.config_button)
