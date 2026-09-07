"""Recolor Nodus coral/orange chart accents → Gravitre brand green #16a374.
Leaves structure intact; does not invent new UI content.
"""
from __future__ import annotations

import colorsys
from pathlib import Path

from PIL import Image

BRAND = (0x16, 0xA3, 0x74)  # #16a374
ROOT = Path(__file__).resolve().parents[1]
PATHS = [
    ROOT / "apps/web/public/nodus/dashboard@3x.png",
    ROOT / "apps/web/public/nodus/dashboard.png",
]


def map_warm_to_green(r: int, g: int, b: int, a: int) -> tuple[int, int, int, int]:
    if a < 16:
        return r, g, b, a
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    # Nodus coral / salmon / peach accents (warm reds–oranges, mid-high sat)
    warm = s >= 0.18 and v >= 0.35 and (h <= 0.08 or h >= 0.92 or 0.02 <= h <= 0.13)
    if not warm:
        return r, g, b, a
    # Preserve value/sat relative feel; lock hue to brand green (~0.42)
    bh, bs, bv = colorsys.rgb_to_hsv(BRAND[0] / 255.0, BRAND[1] / 255.0, BRAND[2] / 255.0)
    # Soften extreme highlights toward lighter brand tints
    out_s = min(0.72, max(0.22, s * 0.95))
    out_v = min(0.92, max(0.28, v * 0.98))
    nr, ng, nb = colorsys.hsv_to_rgb(bh, out_s, out_v)
    return int(nr * 255), int(ng * 255), int(nb * 255), a


def recolor(path: Path) -> None:
    im = Image.open(path).convert("RGBA")
    pixels = list(im.getdata())
    out = [map_warm_to_green(*p) for p in pixels]
    im.putdata(out)
    im.save(path, optimize=True)
    print(f"recolored {path} ({im.size[0]}x{im.size[1]})")


def main() -> None:
    for p in PATHS:
        if not p.exists():
            print(f"skip missing {p}")
            continue
        recolor(p)


if __name__ == "__main__":
    main()
