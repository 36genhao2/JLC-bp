"""Bad Apple -> 嘉立创EDA 逐帧驱动。

用法:
    python driver.py bench                 # 只测一帧的建盘耗时
    python driver.py capture -n 30         # 抓 30 帧存 PNG
    python driver.py capture --start 1200 -n 150 -o out/

扩展端需在嘉立创EDA 的 PCB 页面点 "Bad Apple -> 连接驱动"。
"""
from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import os
import sys
import time
import zipfile
from ctypes import wintypes

import numpy as np
import websockets
from PIL import Image, ImageGrab

from grid import COLS, ROWS, THRESH
# 帧源优先级：BA_FRAMES_DIR 环境变量 > source/frames/ > 原始图包（不完整，仅兼容旧流程）
_SOURCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "source", "frames")
FRAMES_DIR = os.environ.get("BA_FRAMES_DIR") or (_SOURCE_DIR if os.path.isdir(_SOURCE_DIR) else "")
Z1 = r"C:\Users\1234\Desktop\Temp\be\1.zip"
Z2 = r"C:\Users\1234\Desktop\Temp\be\2.zip"
PORT = 8765

_zip_cache: dict[str, zipfile.ZipFile] = {}


def _zip_for(idx: int) -> zipfile.ZipFile:
    path = Z1 if idx <= 3281 else Z2
    if path not in _zip_cache:
        _zip_cache[path] = zipfile.ZipFile(path)
    return _zip_cache[path]


def _fit(img: Image.Image) -> Image.Image:
    """缩到栅格尺寸。BA_FIT: contain 等比留边 / crop 等比裁切 / stretch 拉伸。"""
    mode = os.environ.get("BA_FIT", "contain").lower()
    if mode == "stretch":
        return img.resize((COLS, ROWS), Image.LANCZOS)
    w, h = img.size
    if mode == "crop":
        scale = max(COLS / w, ROWS / h)
        nw, nh = max(COLS, round(w * scale)), max(ROWS, round(h * scale))
        big = img.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - COLS) // 2, (nh - ROWS) // 2
        return big.crop((left, top, left + COLS, top + ROWS))
    scale = min(COLS / w, ROWS / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    small = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("L", (COLS, ROWS), 0)
    canvas.paste(small, ((COLS - nw) // 2, (ROWS - nh) // 2))
    return canvas


def frame_cells(idx: int) -> list[list[int]]:
    """读第 idx 帧，缩到栅格尺寸后取白场作为点亮的焊盘。"""
    if FRAMES_DIR:
        img = Image.open(os.path.join(FRAMES_DIR, f"{idx:05d}.png"))
    else:
        with _zip_for(idx).open(f"{idx}.png") as f:
            img = Image.open(f)
            img.load()  # zip 句柄离开 with 就关闭，必须当场读完
    a = np.array(_fit(img.convert("L")))
    # BA_INVERT=1 时取暗部点亮（暗底亮人），否则取亮部点亮（亮底暗人）
    if os.environ.get("BA_INVERT", "0") == "1":
        ys, xs = np.nonzero(a <= THRESH)
    else:
        ys, xs = np.nonzero(a > THRESH)
    return [[int(x), int(y)] for x, y in zip(xs, ys)]


# ---------- 窗口 ----------

_sw = ctypes.windll.user32


def find_eda_window() -> tuple[int, str] | None:
    found: list[tuple[int, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        n = _sw.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        _sw.GetWindowTextW(hwnd, buf, n + 1)
        title = buf.value
        low = title.lower()
        if _sw.IsWindowVisible(hwnd) and ("lceda" in low or "easyeda" in low or "嘉立创" in title):
            r = wintypes.RECT()
            _sw.GetWindowRect(hwnd, ctypes.byref(r))
            if (r.right - r.left) > 400 and (r.bottom - r.top) > 300:
                found.append((hwnd, title))
        return True

    _sw.EnumWindows(cb, 0)
    return found[0] if found else None


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    _sw.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def _grab(hwnd: int) -> Image.Image:
    """PrintWindow 抓一次窗口内容。"""
    import win32gui
    import win32ui

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    w, h = right - left, bottom - top
    hwnd_dc = win32gui.GetWindowDC(hwnd)
    src_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    mem_dc = src_dc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(src_dc, w, h)
    mem_dc.SelectObject(bmp)
    ctypes.windll.user32.PrintWindow(wintypes.HWND(hwnd), mem_dc.GetSafeHdc(), 2)
    bits = bmp.GetBitmapBits(True)
    img = Image.frombuffer("RGB", (w, h), bits, "raw", "BGRX", 0, 1).copy()

    win32gui.DeleteObject(bmp.GetHandle())
    mem_dc.DeleteDC()
    src_dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwnd_dc)
    return img


def _std(img: Image.Image) -> float:
    from PIL import ImageStat

    return ImageStat.Stat(img.convert("L")).stddev[0]


def nudge(hwnd: int, wait: float = 0.30) -> None:
    """强制窗口重绘。只用 RedrawWindow，不改前后台顺序、不抢焦点。"""
    RDW_INVALIDATE = 0x0001
    RDW_ALLCHILDREN = 0x0080
    RDW_UPDATENOW = 0x0100
    RDW_FRAME = 0x0400
    _sw.RedrawWindow(wintypes.HWND(hwnd), None, None,
                     RDW_INVALIDATE | RDW_ALLCHILDREN | RDW_UPDATENOW | RDW_FRAME)
    time.sleep(wait)


def capture(hwnd: int, path: str, crop: tuple[int, int, int, int] | None = None) -> tuple[int, int]:
    """抓窗口内容；PrintWindow 返回空白时置前重试，再不行退回屏幕抓取。"""
    import win32gui

    img = _grab(hwnd)
    if _std(img) < 5:
        nudge(hwnd)
        img = _grab(hwnd)
    if _std(img) < 5:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)

    if crop:
        img = img.crop(crop)

    img.save(path)
    return img.size


# ---------- 服务 ----------

class Driver:
    def __init__(self) -> None:
        self.ws = None
        self.pending: asyncio.Future | None = None

    async def handler(self, ws) -> None:
        self.ws = ws
        peer = ws.remote_address
        print(f"[ws] 扩展已连接 {peer}")
        try:
            async for raw in ws:
                msg = json.loads(raw)
                t = msg.get("t")
                if t == "hello":
                    print(f"[ws] hello v{msg.get('version')} pads={msg.get('pads')}")
                    if self.pending and not self.pending.done():
                        self.pending.set_result(msg)
                elif t in ("done", "bench", "cleared", "pong", "error"):
                    if self.pending and not self.pending.done():
                        self.pending.set_result(msg)
                    if t == "error":
                        print("[ws] 扩展报错:", msg.get("msg"))
        finally:
            print("[ws] 连接断开")
            self.ws = None

    async def send(self, obj: dict, timeout: float = 120.0) -> dict:
        if self.ws is None:
            raise RuntimeError("扩展未连接")
        loop = asyncio.get_running_loop()
        self.pending = loop.create_future()
        await self.ws.send(json.dumps(obj))
        return await asyncio.wait_for(self.pending, timeout)


async def run(args) -> None:
    drv = Driver()
    async with websockets.serve(drv.handler, "127.0.0.1", PORT, max_size=8 * 1024 * 1024):
        print(f"[ws] 监听 127.0.0.1:{PORT}，请到嘉立创EDA 点 Bad Apple -> 连接驱动")
        t0 = time.time()
        while drv.ws is None:
            if time.time() - t0 > args.wait:
                print("[ws] 等待超时")
                return
            await asyncio.sleep(0.2)

        if args.mode == "bench":
            cells = frame_cells(args.start)
            print(f"[bench] 帧 {args.start} 共 {len(cells)} 个焊盘")
            for i in range(3):
                m = await drv.send({"cmd": "bench", "cells": cells})
                print(f"  #{i + 1}: +{m.get('added')} -{m.get('removed')} total={m.get('total')} {m.get('ms', 0):.0f} ms")
            return

        win = find_eda_window()
        if win is None:
            print("找不到嘉立创EDA 窗口")
            return
        hwnd, title = win
        print(f"[cap] 窗口: {title}")

        os.makedirs(args.out, exist_ok=True)
        n_done = 0
        t_all = time.time()
        for i in range(args.n):
            idx = args.start + i
            cells = frame_cells(idx)
            t1 = time.time()
            m = await drv.send({"cmd": "frame", "cells": cells})
            if m.get("t") == "error":
                print(f"[{idx}] 失败: {m.get('msg')}")
                continue
            await asyncio.sleep(args.delay)
            p = os.path.join(args.out, f"{n_done:04d}.png")
            size = capture(hwnd, p)
            n_done += 1
            if n_done % 10 == 0 or n_done == 1:
                dt = time.time() - t1
                print(f"[{idx}] pads={m.get('total')} 建盘 {m.get('ms', 0):.0f}ms 单帧 {dt:.2f}s -> {size[0]}x{size[1]}")

        print(f"[done] {n_done} 帧，总耗时 {time.time() - t_all:.1f}s")


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["bench", "capture"])
    ap.add_argument("-n", type=int, default=10)
    ap.add_argument("--start", type=int, default=1200)
    ap.add_argument("-o", "--out", default="shots")
    ap.add_argument("--delay", type=float, default=0.15)
    ap.add_argument("--wait", type=float, default=180)
    args = ap.parse_args()

    if sys.platform != "win32":
        sys.exit("仅支持 Windows")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
