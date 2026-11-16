"""不连 EDA 也能看效果：把栅格结果画成 LED 点阵预览图。

用法:
    BA_GRID=16x16 BA_FIT=crop python driver/preview.py 0 400 900 1400
"""
from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import driver  # noqa: E402
from grid import COLS, ROWS  # noqa: E402

CELL = 40
LIT = (255, 70, 40)
LIT_CORE = (255, 220, 180)
DIM = (38, 38, 40)
DIM_RING = (58, 58, 62)
HOLE = (12, 12, 13)


def draw_frame(idx: int) -> Image.Image:
    cells = {(c, r) for c, r in driver.frame_cells(idx)}
    img = Image.new("RGB", (COLS * CELL, ROWS * CELL), (18, 18, 20))
    d = ImageDraw.Draw(img)
    pad_r = int(CELL * 0.55 / 2)
    hole_r = max(2, int(CELL * 0.25 / 2))
    for r in range(ROWS):
        for c in range(COLS):
            cx, cy = c * CELL + CELL // 2, r * CELL + CELL // 2
            lit = (c, r) in cells
            if lit:
                d.ellipse([cx - pad_r - 2, cy - pad_r - 2, cx + pad_r + 2, cy + pad_r + 2], fill=(120, 30, 20))
            d.ellipse([cx - pad_r, cy - pad_r, cx + pad_r, cy + pad_r],
                      fill=LIT if lit else DIM, outline=LIT if lit else DIM_RING)
            d.ellipse([cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r],
                      fill=LIT_CORE if lit else HOLE)
    return img


def main() -> None:
    frames = [int(x) for x in sys.argv[1:]] or [0]
    imgs = [draw_frame(f) for f in frames]
    w, h = imgs[0].size
    sheet = Image.new("RGB", (w * len(imgs) + 8 * (len(imgs) - 1), h), (10, 10, 10))
    for i, im in enumerate(imgs):
        sheet.paste(im, (i * (w + 8), 0))
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "preview_grid.png")
    sheet.save(out)
    counts = [len(driver.frame_cells(f)) for f in frames]
    print("帧", frames, "点亮数", counts, "->", out)


if __name__ == "__main__":
    main()
