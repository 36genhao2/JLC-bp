"""从原片导出逐帧 PNG。产物供 driver.frame_cells 读取。

用法:
    python driver/extract_frames.py              # 导出到 source/frames/
    python driver/extract_frames.py -o D:\\tmp\\f  # 自定义目录
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "source", "badapple.m4s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default=os.path.join(ROOT, "source", "frames"))
    ap.add_argument("-i", "--input", default=SRC)
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"找不到原片：{args.input}")

    os.makedirs(args.out, exist_ok=True)
    existing = [f for f in os.listdir(args.out) if f.endswith(".png")]
    if existing:
        print(f"目标目录已有 {len(existing)} 张 PNG，先清空再导出")
        for f in existing:
            os.remove(os.path.join(args.out, f))

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", args.input,
        "-vsync", "0",
        os.path.join(args.out, "%05d.png"),
    ]
    print("导出中:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    n = len([f for f in os.listdir(args.out) if f.endswith(".png")])
    print(f"完成：{n} 帧 → {args.out}")

    # ffmpeg 从 00001 开始编号，转成从 00000 开始，与渲染脚本对齐
    files = sorted(f for f in os.listdir(args.out) if f.endswith(".png"))
    if files and files[0] == "00001.png":
        for f in files:
            i = int(f[:5]) - 1
            os.rename(os.path.join(args.out, f), os.path.join(args.out, f"{i:05d}.png"))
        print("已重编号为 00000 起始")


if __name__ == "__main__":
    main()
