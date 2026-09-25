"""Vstupni skript pro PyInstaller.

Musi byt mimo balicek a pouzivat absolutni importy - zabalene exe spousti
tento soubor jako __main__, kde relativni importy nefunguji.
"""
from __future__ import annotations

import sys


def main() -> int:
    from tracki.app import main as run

    return run()


if __name__ == "__main__":
    sys.exit(main())
