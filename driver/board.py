"""板面框架：外框、安装孔。3.2.186 只能往铜层画线，所以外框走 TOP 铜。"""
from __future__ import annotations

import json

import eda

COLS, ROWS = 128, 96
PITCH = 23.622
OX, OY = 2000.0, 2000.0

PAD = 13.0

BOARD_L, BOARD_R = 1700.0, 5300.0
BOARD_B, BOARD_T = 1700.0, 4560.0

FRAME_W = 14.0
LAYER_TOP = 1
LAYER_MULTI = 12


def wipe() -> dict:
    """清掉当前板上的线、焊盘，回到干净状态。"""
    js = """
const out={lines:0,pads:0};
try{const ls=await eda.pcb_PrimitiveLine.getAll(); const lids=(ls||[]).map(x=>x.getState_PrimitiveId?x.getState_PrimitiveId():x);
 if(lids.length){await eda.pcb_PrimitiveLine.delete(lids); out.lines=lids.length;}}catch(e){}
try{const ps=await eda.pcb_PrimitivePad.getAll(); const pids=(ps||[]).map(x=>x.getState_PrimitiveId?x.getState_PrimitiveId():x);
 if(pids.length){await eda.pcb_PrimitivePad.delete(pids); out.pads=pids.length;}}catch(e){}
globalThis.__ba_ids=[];
return out;
"""
    return eda.execute(js, timeout=300)


def build_frame() -> dict:
    pts = [(BOARD_L, BOARD_B), (BOARD_R, BOARD_B), (BOARD_R, BOARD_T), (BOARD_L, BOARD_T)]
    segs = [[pts[i][0], pts[i][1], pts[(i + 1) % 4][0], pts[(i + 1) % 4][1]] for i in range(4)]
    js = f"""
const segs={json.dumps(segs)};
const ids=[];
for(const [x1,y1,x2,y2] of segs){{
  const l=await eda.pcb_PrimitiveLine.create('',{LAYER_TOP},x1,y1,x2,y2,{FRAME_W});
  if(l) ids.push(l.getState_PrimitiveId());
}}
globalThis.__ba_frame=ids;
return ids.length;
"""
    return {"frame": eda.execute(js, timeout=120)}


def build_holes() -> dict:
    """安装孔按当前板框计算，避免板框改动后孔落进点阵区。"""
    import layout

    b = layout.outline_bbox()
    inset = 120.0  # 孔心到板边，减去半径 90 后与板框留 30 mil
    xs = [b["left"] + inset, b["right"] - inset]
    ys = [b["bottom"] + inset, b["top"] - inset]
    holes = [[x, y] for y in ys for x in xs]
    js = f"""
const hs={json.dumps(holes)};
const ids=[];
for(const [x,y] of hs){{
  const p=await eda.pcb_PrimitivePad.create({LAYER_MULTI},'',x,y,0,['ELLIPSE',180,180],'',['ROUND',110],0,0,0,false,0);
  if(p) ids.push(p.getState_PrimitiveId());
}}
globalThis.__ba_holes=ids;
return ids.length;
"""
    return {"holes": eda.execute(js, timeout=120)}


if __name__ == "__main__":
    print("wipe:", json.dumps(wipe(), ensure_ascii=False))
    print("frame:", json.dumps(build_frame(), ensure_ascii=False))
    print("holes:", json.dumps(build_holes(), ensure_ascii=False))
