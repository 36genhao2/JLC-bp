"""逐帧渲染 + 截图。差分更新：只增删变化的焊盘。"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import time

try:  # 必须最先声明，否则 GetWindowRect 返回逻辑尺寸，右侧面板会被裁掉
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

import driver
import eda
import layout
from driver import frame_cells

JS_APPLY = """
const m = globalThis.__baMap || (globalThis.__baMap = new Map());
const P = %(pitch)s, OX = %(ox)s, OY = %(oytop)s, L = %(layer)s, SZ = %(pad)s;
const dels = [];
for (const [c, r] of %(del)s) {
  const k = c + ',' + r;
  const id = m.get(k);
  if (id) { dels.push(id); m.delete(k); }
}
if (dels.length) await eda.pcb_PrimitivePad.delete(dels);
const adds = [];
for (const [c, r] of %(add)s) {
  if (!m.has(c + ',' + r)) adds.push([c, r]);
}
const made = await Promise.all(adds.map(([c, r]) =>
  eda.pcb_PrimitivePad.create(L, '', OX + c * P, OY - r * P, 0, ['ELLIPSE', SZ, SZ], '', null, 0, 0, 0, false, 0)
    .catch(() => undefined)));
for (let i = 0; i < made.length; i++) {
  if (made[i]) m.set(adds[i][0] + ',' + adds[i][1], made[i].getState_PrimitiveId());
}
return {add: %(nadd)d, del: %(ndel)d, total: m.size};
"""


def apply(cells: set[tuple[int, int]], prev: set[tuple[int, int]], geo: dict,
          style: str = "smd") -> tuple[dict, float]:
    from render_one import STYLES

    layer, ratio, hole_ratio = STYLES[style]
    add = [[c, r] for (c, r) in cells - prev]
    dele = [[c, r] for (c, r) in prev - cells]
    if not add and not dele:
        return {"add": 0, "del": 0, "total": len(cells)}, 0.0

    js = JS_APPLY % {
        "pitch": geo["pitch"],
        "ox": geo["ox"],
        "oytop": geo["oytop"],
        "layer": layer,
        "pad": round(geo["pitch"] * ratio, 3),
        "add": json.dumps(add, separators=(",", ":")),
        "del": json.dumps(dele, separators=(",", ":")),
        "nadd": len(add),
        "ndel": len(dele),
    }
    t0 = time.time()
    res = eda.execute(js, timeout=180)
    return res, time.time() - t0


def _sig(path: str) -> str:
    """截图指纹：缩到 64x40 后取哈希，用于检测画面是否真的变了。"""
    import hashlib

    from PIL import Image

    im = Image.open(path).convert("L").resize((64, 40))
    return hashlib.md5(im.tobytes()).hexdigest()


def reset_board(holes: bool = False, layer: int = 1) -> None:
    """清空点阵焊盘（只清指定层，安装孔在多层不会被误删），重置差量状态。"""
    js = f"""
globalThis.__baMap = new Map();
const all = await eda.pcb_PrimitivePad.getAll();
const ids = (all || []).filter(p => p.getState_Layer() === {layer}).map(p => p.getState_PrimitiveId());
if (ids.length) await eda.pcb_PrimitivePad.delete(ids);
return ids.length;
"""
    n = eda.execute(js, timeout=300)
    print("清空焊盘:", n)
    if holes:
        import board

        print("重建安装孔:", board.build_holes())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("-n", type=int, default=30)
    ap.add_argument("-o", "--out", default=r"C:\Users\1234\Documents\GitHub\JLC bp\frames")
    ap.add_argument("--settle", type=float, default=0.08)
    ap.add_argument("--record", default="")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--crop", default="946,345,1668,909", help="x0,y0,x1,y1")
    ap.add_argument("--zoom", default="677,6523,5467,901", help="l,r,t,b")
    ap.add_argument("--holes", action="store_true", help="reset 时重建四角安装孔")
    ap.add_argument("--style", default="smd", choices=["smd", "led", "via", "big"], help="焊盘样式")
    args = ap.parse_args()
    args.crop = tuple(int(v) for v in args.crop.split(",")) if args.crop else None

    geo = layout.grid_layout()
    print(f"pitch={geo['pitch']} origin=({geo['ox']},{geo['oy']})")

    if args.reset:
        from render_one import STYLES

        reset_board(holes=args.holes, layer=STYLES[args.style][0])
        eda.js("await eda.pcb_SelectControl.clearSelected()", timeout=60)

    tab = None
    try:
        import render_one

        tab = render_one.pcb_tab()
        if args.zoom:
            eda.js(f'await eda.dmt_EditorControl.zoomToRegion({args.zoom},"{tab}")', timeout=60)
            time.sleep(3.0)
            print("视口已锁定:", args.zoom)
        else:
            print("保持当前视口不动")
    except Exception as e:
        print("视口处理失败:", e)

    os.makedirs(args.out, exist_ok=True)
    win = driver.find_eda_window()
    if not win:
        raise SystemExit("找不到 EDA 窗口")
    hwnd = win[0]

    l, t, r, b = driver.window_rect(hwnd)
    if (r - l) < 800 or (b - t) < 600:
        raise SystemExit(f"窗口尺寸异常 {(r - l)}x{(b - t)}，可能被最小化，已中止")

    # 非活动层默认会被压暗（暗红+60%透明），焊盘层不是当前层时几乎看不见
    try:
        eda.js("await eda.pcb_Layer.setInactiveLayerDisplayMode(0)", timeout=30)
        print("非活动层显示：正常亮度")
    except Exception as e:
        print("设置层显示失败:", e)

    rec = None
    if args.record:
        l, t, r, b = driver.window_rect(hwnd)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "gdigrab", "-framerate", "15",
            "-offset_x", str(max(l, 0)), "-offset_y", str(max(t, 0)),
            "-video_size", f"{r - max(l, 0)}x{b - max(t, 0)}",
            "-i", "desktop",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", args.record,
        ]
        rec = subprocess.Popen(cmd)
        print("录屏已启动:", args.record)

    prev: set[tuple[int, int]] = set()
    prev_sig = None
    nudges = 0
    stale = 0
    t_all = time.time()
    slow = 0.0
    try:
        for i in range(args.n):
            idx = args.start + i
            t1 = time.time()
            cells = {(c, r) for c, r in frame_cells(idx)}
            info, js_s = apply(cells, prev, geo, args.style)
            changed = cells != prev
            prev = cells
            time.sleep(args.settle)
            path = os.path.join(args.out, f"{idx:05d}.png")
            size = driver.capture(hwnd, path, crop=args.crop)
            if size[0] < 1000:
                raise SystemExit(f"窗口尺寸异常 {size}，已中止（窗口被最小化？）")

            # 画布偶尔停止重绘：数据变了但截图没变，最小化还原强制合成后重截
            sig = _sig(path)
            if prev_sig is not None and sig == prev_sig and changed:
                nudges += 1
                stale += 1
                driver.nudge(hwnd)
                time.sleep(0.35)
                size = driver.capture(hwnd, path, crop=args.crop)
                sig = _sig(path)
                if sig == prev_sig:
                    if stale >= 30:
                        raise SystemExit(f"画布连续 {stale} 帧未更新，停在 {idx}，需重启 EDA 后用 --start {idx} 续跑")
                else:
                    stale = 0
            prev_sig = sig
            slow += js_s
            if i % 10 == 0 or i == args.n - 1:
                el = time.time() - t1
                print(f"[{idx}] +{info['add']} -{info['del']} total={info['total']} "
                      f"js={js_s:.2f}s 帧={el:.2f}s 累计={time.time() - t_all:.0f}s", flush=True)
    finally:
        if rec:
            rec.terminate()
            print("录屏已停止")
    print(f"完成 {args.n} 帧，总 {time.time() - t_all:.1f}s，平均 {(time.time() - t_all) / args.n:.2f}s/帧")
    if nudges:
        print(f"期间强制重绘 {nudges} 次")


if __name__ == "__main__":
    main()
