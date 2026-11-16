"""从板框反推点阵布局：栅格自动内缩居中，板框改了不用改代码。"""
from __future__ import annotations

import json

import eda

from grid import COLS, MARGIN, ROWS

LAYER_OUTLINE = 11


def outline_bbox() -> dict | None:
    """读取板框层折线，返回包围盒（mil）。"""
    js = f"""
const all = await eda.pcb_PrimitivePolyline.getAll();
const cand = (all||[]).filter(p=>p.getState_Layer&&p.getState_Layer()=={LAYER_OUTLINE});
if(!cand.length) return null;
let minX=1e18,minY=1e18,maxX=-1e18,maxY=-1e18;
for(const p of cand){{
  const g = p.getState_Polygon();
  const arr = (typeof g==='string')? JSON.parse(g) : g;
  const poly = arr.polygon || arr;
  for(let i=0;i<poly.length;i++){{
    const it = poly[i];
    if(it==='R'){{
      const x=poly[i+1], y=poly[i+2], w=poly[i+3], h=poly[i+4];
      const x2=x+w, y2=y-h;
      minX=Math.min(minX,x,x2); maxX=Math.max(maxX,x,x2);
      minY=Math.min(minY,y,y2); maxY=Math.max(maxY,y,y2);
      i+=5;
    }} else if(it==='C'||it==='A'){{
      const x=poly[i+1], y=poly[i+2];
      minX=Math.min(minX,x); maxX=Math.max(maxX,x);
      minY=Math.min(minY,y); maxY=Math.max(maxY,y);
      i+=2;
    }} else if(it==='L'){{
      const x1=poly[i+1],y1=poly[i+2];
      minX=Math.min(minX,x1); maxX=Math.max(maxX,x1);
      minY=Math.min(minY,y1); maxY=Math.max(maxY,y1);
      i+=2;
    }}
  }}
}}
return {{left:minX,bottom:minY,right:maxX,top:maxY,n:cand.length}};
"""
    return eda.execute(js, timeout=90)


def grid_layout(box: dict | None = None) -> dict:
    """在板框内算出 COLS x ROWS 的点阵参数。"""
    box = box or outline_bbox()
    if not box:
        raise RuntimeError("板框层没有找到闭合轮廓")

    w = box["right"] - box["left"] - 2 * MARGIN
    h = box["top"] - box["bottom"] - 2 * MARGIN
    pitch = min(w / (COLS - 1), h / (ROWS - 1))

    grid_w = pitch * (COLS - 1)
    grid_h = pitch * (ROWS - 1)
    ox = box["left"] + (box["right"] - box["left"] - grid_w) / 2
    oy = box["bottom"] + (box["top"] - box["bottom"] - grid_h) / 2

    return {
        "pitch": round(pitch, 4),
        "ox": round(ox, 3),
        "oy": round(oy, 3),
        "oytop": round(oy + grid_h, 3),  # 第 0 行对应的 y（坐标系 y 向上）
        "cols": COLS,
        "rows": ROWS,
        "board": box,
    }


if __name__ == "__main__":
    box = outline_bbox()
    print("板框:", json.dumps(box, ensure_ascii=False))
    print("布局:", json.dumps(grid_layout(box), ensure_ascii=False))
