"""Barvy a fonty.

Kazda barva je dvojice (svetly, tmavy) - customtkinter si z ni vybere podle
aktivniho motivu, takze se nic neprepisuje rucne pri prepnuti.
"""
from __future__ import annotations

import customtkinter as ctk

# Paleta vychazi z ikony (fialovy prechod #8A74FF -> #502CC8). Neutralni tony
# maji lehky fialovy nadech, aby cela aplikace drzela pohromade s ikonou.
# Cisla za kazdym akcentem jsou overeny kontrast vuci textu, ktery na nem lezi.
BG = ("#f6f5fa", "#15131d")
SURFACE = ("#ffffff", "#1e1b29")
SURFACE_ALT = ("#ecebf3", "#272338")
BORDER = ("#dcd9e6", "#332d47")
TEXT = ("#141220", "#efedf6")            # 18.5:1 / 14.6:1
TEXT_MUTED = ("#5e5872", "#a79fbe")      # 6.7:1 / 6.7:1
ACCENT = ("#5b33d6", "#9280ff")          # s ACCENT_TEXT 7.3:1 / 6.1:1
ACCENT_HOVER = ("#4a1fbf", "#a390ff")
ACCENT_TEXT = ("#ffffff", "#12101c")
SUCCESS = ("#0f7a4a", "#3fd38a")
DANGER = ("#c22f27", "#ff7167")
DANGER_HOVER = ("#a3251e", "#ff8f87")
TRACK = ("#e0dcea", "#2e2940")

RADIUS = 10
RADIUS_SMALL = 8
PAD = 16
PAD_SMALL = 8

_FAMILY = "Segoe UI"


def apply_mode(theme: str) -> None:
    """theme je 'system' | 'dark' | 'light'."""
    ctk.set_appearance_mode(theme if theme in ("system", "dark", "light") else "system")


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=_FAMILY, size=size, weight=weight)


def fonts() -> dict[str, ctk.CTkFont]:
    """Fonty se vytvari az po vzniku okna, proto jako funkce."""
    return {
        "title": font(22, "bold"),
        "heading": font(15, "bold"),
        "body": font(13),
        "body_bold": font(13, "bold"),
        "small": font(11),
        "mono": ctk.CTkFont(family="Consolas", size=11),
    }
