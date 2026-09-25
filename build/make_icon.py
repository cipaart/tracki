"""Vygeneruje assets/tracki.ico.

Motiv: kazeta na podstavci - hudba, ktera prave dosedla na disk. Kazeta je
mezi ikonami dost nezameniltelna a hlavne se pozna i v 16 px, kde by se
detailnejsi kresba slila.

Dve veci, ktere delaji ikonu ostrou:
  * kazda velikost se kresli zvlast a souradnice se zarovnavaji na pixelovou
    mrizku vysledne velikosti (funkce snap) - jinak vzniknou polovicate
    pixely a ikona pusobi rozmazane,
  * silueta zustava ve vsech velikostech stejna, meni se jen tloustka tahu.
    Ubirat detaily jen u malych velikosti se neosvedcilo: tvar se tim zmenil
    a ikona prestala byt poznatelna.

Spoustet jen pri zmene ikony, vysledek se commituje:
    python build/make_icon.py
"""
from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "tracki.ico"
PREVIEW = ROOT / "assets" / "tracki-preview.png"

# Velikosti, ktere Windows opravdu pouziva (20 a 40 pri 125 % a 150 % zvetseni).
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

SUPERSAMPLE = 8

PALETTES = {
    "amber":  ((255, 186, 60), (240, 96, 42)),
    "sunset": ((255, 146, 74), (228, 56, 98)),
    "violet": ((138, 116, 255), (80, 44, 200)),
    "teal":   ((45, 212, 191), (13, 118, 146)),
}
PALETTE = "violet"   # amber | sunset | violet | teal

WHITE = (255, 255, 255, 255)

# Geometrie v podilech plochy
TILE_RADIUS = 0.225
BODY = (0.13, 0.20, 0.87, 0.64)     # telo kazety
BODY_RADIUS = 0.06
REEL_RADIUS = 0.105
REEL_Y = 0.42
REEL_X = (0.355, 0.645)
# Podstavec je zamerne stejne siroky jako telo kazety. Uzsi pruh pod telem
# cetl jako usta a z ikony se stal oblicej.
BASE = (0.13, 0.75, 0.87, 0.84)     # podstavec
BASE_RADIUS = 0.045


def _snap(size: int, fraction: float) -> int:
    """Zarovna souradnici na pixelovou mrizku vysledne velikosti."""
    return round(fraction * size) * SUPERSAMPLE


def _tile(size: int) -> Image.Image:
    """Zaoblena dlazdice se svislym prechodem."""
    top, bottom = PALETTES[PALETTE]
    canvas = size * SUPERSAMPLE
    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))

    gradient = Image.new("RGBA", (canvas, canvas))
    draw = ImageDraw.Draw(gradient)
    for y in range(canvas):
        ratio = y / max(canvas - 1, 1)
        color = tuple(
            int(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3)
        )
        draw.line([(0, y), (canvas, y)], fill=color + (255,))

    mask = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, canvas - 1, canvas - 1], radius=int(canvas * TILE_RADIUS), fill=255
    )
    image.paste(gradient, (0, 0), mask)
    return image


def render(size: int) -> Image.Image:
    image = _tile(size)
    canvas = size * SUPERSAMPLE
    f = lambda value: _snap(size, value)  # noqa: E731

    # Telo kazety s vyriznutymi civkami - dirami prosvita prechod pod nimi.
    shape = Image.new("L", (canvas, canvas), 0)
    draw = ImageDraw.Draw(shape)
    draw.rounded_rectangle([f(BODY[0]), f(BODY[1]), f(BODY[2]), f(BODY[3])],
                           radius=f(BODY_RADIUS), fill=255)
    for center_x in REEL_X:
        draw.ellipse(
            [f(center_x - REEL_RADIUS), f(REEL_Y - REEL_RADIUS),
             f(center_x + REEL_RADIUS), f(REEL_Y + REEL_RADIUS)],
            fill=0,
        )
    image.paste(Image.new("RGBA", (canvas, canvas), WHITE), (0, 0), shape)

    # Podstavec
    ImageDraw.Draw(image).rounded_rectangle(
        [f(BASE[0]), f(BASE[1]), f(BASE[2]), f(BASE[3])],
        radius=f(BASE_RADIUS), fill=WHITE,
    )

    return image.resize((size, size), Image.LANCZOS)


def build_preview(images: list[Image.Image]) -> Image.Image:
    """Nahled: skutecne velikosti vedle sebe na tmavem i svetlem podkladu."""
    strip_height = 2 * (max(SIZES) + 24)
    width = sum(size + 24 for size in SIZES) + 24
    preview = Image.new("RGBA", (width, strip_height), (26, 28, 34, 255))
    ImageDraw.Draw(preview).rectangle(
        [0, strip_height // 2, width, strip_height], fill=(244, 245, 247, 255)
    )

    x = 24
    for size, image in zip(SIZES, images):
        preview.alpha_composite(image, (x, (strip_height // 2 - size) // 2))
        preview.alpha_composite(
            image, (x, strip_height // 2 + (strip_height // 2 - size) // 2)
        )
        x += size + 24
    return preview


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    images = [render(size) for size in SIZES]

    # Nejvetsi obrazek nese celou sadu velikosti dovnitr .ico.
    images[-1].save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
    build_preview(images).save(PREVIEW)

    print(f"zapsano {OUT} ({OUT.stat().st_size} B), velikosti: {list(SIZES)}")
    print(f"nahled  {PREVIEW}")


if __name__ == "__main__":
    main()
