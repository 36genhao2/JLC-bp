"""修正失焦导致的整窗变暗帧。EasyEDA 失焦时叠加约 20% 暗色蒙版，out = in * 0.803。"""
from __future__ import annotations

import glob
import sys

import numpy as np
from PIL import Image

X0, Y0, X1, Y1 = 2280, 110, 2575, 1100  # 右侧图层面板，亮度稳定
THRESH = 215.0


def panel_mean(im: Image.Image) -> float:
    return float(np.asarray(im.convert("L"))[Y0:Y1, X0:X1].mean())


def main() -> None:
    files = sorted(glob.glob(r"C:\Users\1234\Documents\GitHub\JLC bp\frames_v7\*.png"))
    if not files:
        sys.exit("没有帧")

    ref = panel_mean(Image.open(files[60]))
    print(f"参考亮度 {ref:.1f}，共 {len(files)} 帧", flush=True)

    fixed = []
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGB")
        m = panel_mean(im)
        if m < THRESH:
            k = ref / m
            a = np.asarray(im, dtype=np.float32) * k
            Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(f)
            fixed.append((f.rsplit("\\", 1)[-1], round(m, 1)))
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{len(files)} 已修 {len(fixed)}", flush=True)

    print(f"完成，修正 {len(fixed)} 帧", flush=True)
    for x in fixed[:20]:
        print("  ", x)


if __name__ == "__main__":
    main()
