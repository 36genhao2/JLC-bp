"""渲染一帧并截图，用于观感对比。栅格参数由板框推导。"""
from __future__ import annotations

import json
import sys
import time

import driver
import eda
import layout
from driver import frame_cells

def pcb_tab() -> str:
    """取当前 PCB 文档的 tabId（docType 3）。"""
    tree = eda.js("await eda.dmt_EditorControl.getSplitScreenTree()")
    for t in tree.get("tabs", []):
        if (t.get("data") or {}).get("doctype") == 3:
            return t["tabId"]
    raise RuntimeError("当前没有打开 PCB 文档")

STYLES = {
    "smd": (1, 0.50, None),   # 顶层贴片，边长 = 栅距 * 0.50
    "led": (1, 0.68, None),   # 顶层贴片，更大更圆；顶层放不了钻孔，要孔只能用 via
    "via": (12, 0.55, 0.25),  # 多层通孔，带钻孔
    "big": (1, 0.64, None),
}


def render(cells, style: str = "smd", geo: dict | None = None, chunk: int = 1200) -> dict:
    geo = geo or layout.grid_layout()
    pitch, ox, oytop = geo["pitch"], geo["ox"], geo["oytop"]
    layer, ratio, hole_ratio = STYLES[style]
    pad = round(pitch * ratio, 3)
    hole_js = "null" if hole_ratio is None else f"['ROUND',{round(pitch * hole_ratio, 3)}]"

    # 桥接单次请求 30 秒超时，整体重建必须分批
    # 只清同层焊盘：安装孔在多层(12)，不能被点阵清空带走
    eda.execute(
        "globalThis.__baMap=new Map();"
        "const a=await eda.pcb_PrimitivePad.getAll();"
        f"const ids=(a||[]).filter(x=>x.getState_Layer()==={layer}).map(x=>x.getState_PrimitiveId());"
        "if(ids.length) await eda.pcb_PrimitivePad.delete(ids);"
        f"return {{deleted:ids.length}};",
        timeout=120,
    )

    t0 = time.time()
    total = 0
    for i in range(0, len(cells), chunk):
        part = json.dumps(cells[i:i + chunk], separators=(",", ":"))
        js = f"""
const m = globalThis.__baMap;
const OY = {oytop}, OX = {ox}, P = {pitch};
const cells = {part};
const made = await Promise.all(cells.map(([c, r]) =>
  eda.pcb_PrimitivePad.create({layer}, '', OX + c * P, OY - r * P, 0, ['ELLIPSE', {pad}, {pad}], '', {hole_js}, 0, 0, 0, false, 0)
    .catch(() => undefined)));
for (let k = 0; k < made.length; k++) {{
  if (made[k]) m.set(cells[k][0] + ',' + cells[k][1], made[k].getState_PrimitiveId());
}}
return made.filter(Boolean).length;
"""
        total += eda.execute(js, timeout=120)

    return {"n": total, "ms": (time.time() - t0) * 1000, "pitch": pitch, "pad": pad, "style": style}


def frame_view(pad: float = 200.0) -> dict:
    """按板框把视图居中，返回取景区域。"""
    b = layout.outline_bbox()
    return {
        "l": b["left"] - pad,
        "r": b["right"] + pad,
        "t": b["top"] + pad,
        "b": b["bottom"] - pad,
    }


def main() -> None:
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    style = sys.argv[2] if len(sys.argv) > 2 else "smd"
    cells = frame_cells(idx)
    print(f"frame {idx}: {len(cells)} cells, style={style}")
    t = time.time()
    print("render:", json.dumps(render(cells, style), ensure_ascii=False))

    v = frame_view()
    tab = pcb_tab()
    eda.js(f'await eda.dmt_EditorControl.zoomToRegion({v["l"]},{v["r"]},{v["t"]},{v["b"]},"{tab}")', timeout=60)
    time.sleep(3.0)
    w = driver.find_eda_window()
    out = rf"C:\Users\1234\Documents\GitHub\JLC bp\preview\eda_{style}.png"
    print("capture:", driver.capture(w[0], out), f"{time.time() - t:.1f}s")


if __name__ == "__main__":
    main()
