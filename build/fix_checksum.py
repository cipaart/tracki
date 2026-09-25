"""Dopocita a zapise PE checksum hotoveho .exe.

PyInstaller nechava v hlavicce nulovy (tedy neplatny) checksum. Nekterym
antivirovym heuristikam to staci k oznaceni souboru za podezrely, takze ho po
buildu spocitame a zapiseme.

Pozn. k API: kolujici snippet "pe.close(); pe.save(path)" s dnesnim pefile
nefunguje - metoda save() neexistuje (spravne je write()) a close() navic
uvolni data, ze kterych se zapisuje. Poradi je proto: nastavit -> write() ->
close() -> overit znovunactenim.
"""
from __future__ import annotations

import pathlib
import sys


def fix(path: pathlib.Path) -> int:
    import pefile

    if not path.is_file():
        print(f"CHYBA: {path} neexistuje", file=sys.stderr)
        return 1

    pe = pefile.PE(str(path), fast_load=True)
    try:
        before = pe.OPTIONAL_HEADER.CheckSum
        computed = pe.generate_checksum()
        if before == computed:
            print(f"checksum uz je spravny: 0x{before:08x}")
            return 0
        pe.OPTIONAL_HEADER.CheckSum = computed
        pe.write(str(path))
    finally:
        pe.close()

    print(f"checksum zapsan: 0x{before:08x} -> 0x{computed:08x}")

    # Overeni na znovunactenem souboru - zapis, ktery neprosel, nesmi projit tise.
    verify = pefile.PE(str(path), fast_load=True)
    try:
        stored = verify.OPTIONAL_HEADER.CheckSum
        expected = verify.generate_checksum()
    finally:
        verify.close()

    if stored != expected:
        print(f"CHYBA: checksum po zapisu nesedi "
              f"(v souboru 0x{stored:08x}, spocteno 0x{expected:08x})",
              file=sys.stderr)
        return 1

    print(f"checksum overen: 0x{stored:08x}")
    return 0


def main() -> int:
    if len(sys.argv) > 1:
        target = pathlib.Path(sys.argv[1])
    else:
        target = pathlib.Path(__file__).resolve().parents[1] / "dist" / "Tracki.exe"
    return fix(target)


if __name__ == "__main__":
    sys.exit(main())
