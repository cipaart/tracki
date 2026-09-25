"""Stahne ffmpeg.exe pro Windows do build/ffmpeg/.

Pouziva se LGPL varianta z BtbN/FFmpeg-Builds - staticka, takze staci jediny
soubor ffmpeg.exe bez DLL. Skript je idempotentni: kdyz uz soubor je, nedela nic.
"""
from __future__ import annotations

import hashlib
import io
import pathlib
import sys
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "build" / "ffmpeg"
TARGET = TARGET_DIR / "ffmpeg.exe"

URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-lgpl.zip"
)


def main() -> int:
    if TARGET.is_file() and TARGET.stat().st_size > 1_000_000:
        print(f"ffmpeg.exe uz je na miste ({TARGET.stat().st_size / 1e6:.1f} MB)")
        return 0

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"stahuji {URL}")
    with urllib.request.urlopen(URL, timeout=300) as response:
        payload = response.read()
    print(f"stazeno {len(payload) / 1e6:.1f} MB, sha256={hashlib.sha256(payload).hexdigest()[:16]}…")

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [n for n in archive.namelist() if n.endswith("bin/ffmpeg.exe")]
        if not members:
            print("CHYBA: ffmpeg.exe v archivu nenalezen", file=sys.stderr)
            return 1
        with archive.open(members[0]) as source:
            TARGET.write_bytes(source.read())

        # Licence se distribuuji spolu s binarkou.
        for name in archive.namelist():
            if name.endswith(("LICENSE.txt", "LICENSE")):
                (TARGET_DIR / "FFMPEG-LICENSE.txt").write_bytes(
                    archive.read(name)
                )
                break

    print(f"ffmpeg.exe pripraven: {TARGET} ({TARGET.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
