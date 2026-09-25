"""Sestavi Tracki.exe. Spoustet na Windows: python build\\build.py

Kroky: ffmpeg -> PyInstaller -> oprava PE checksumu -> kontrola vysledku.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
EXE = DIST / "Tracki.exe"
SPEC = ROOT / "build" / "tracki.spec"


def run(command: list[str], label: str) -> None:
    print(f"\n=== {label} ===")
    print("$", " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"krok selhal: {label} (kod {result.returncode})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Tracki.exe")
    parser.add_argument("--skip-ffmpeg", action="store_true",
                        help="nestahovat ffmpeg (uz je v build/ffmpeg)")
    parser.add_argument("--skip-tests", action="store_true",
                        help="nespoustet testy pred buildem")
    args = parser.parse_args()

    if sys.platform != "win32":
        print("POZOR: Windows .exe se da sestavit jen na Windows.\n"
              "       PyInstaller neumi cross-kompilaci. Pouzijte GitHub Actions\n"
              "       workflow .github/workflows/build-windows.yml.", file=sys.stderr)
        return 2

    python = sys.executable

    if not args.skip_tests:
        run([python, "-m", "pytest", "-q"], "testy")

    if not args.skip_ffmpeg:
        run([python, str(ROOT / "build" / "fetch_ffmpeg.py")], "ffmpeg")

    for folder in (DIST, ROOT / "build" / "pyinstaller"):
        if folder.exists():
            shutil.rmtree(folder, ignore_errors=True)

    run([python, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", str(DIST),
         "--workpath", str(ROOT / "build" / "pyinstaller"),
         str(SPEC)], "PyInstaller")

    run([python, str(ROOT / "build" / "fix_checksum.py"), str(EXE)],
        "oprava PE checksumu")

    if not EXE.is_file():
        raise SystemExit("Tracki.exe nevznikl")

    size_mb = EXE.stat().st_size / (1024 * 1024)
    print(f"\nHOTOVO: {EXE} ({size_mb:.1f} MB)")
    print("Jde o jediny portable soubor - zadna instalace, zadne DLL vedle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
