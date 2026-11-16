"""在嘉立创EDA 的当前 PCB 上渲染一帧，并测时。"""
from __future__ import annotations

import json
import sys
import time

import eda
from driver import frame_cells

PITCH = 23.622
PAD = 11.811
OX, OY = 2000.0, 2000.0


def build_js(cells: list[list[int]], clear: bool = True) -> str:
    arr = json.dumps(cells, separators=(",", ":"))
    pre = "if(globalThis.__ba_ids){await eda.pcb_PrimitivePad.delete(globalThis.__ba_ids);}" if clear else ""
    return f"""
{pre}
const cells={arr};
const t0=performance.now();
const ps=cells.map(([c,r])=>eda.pcb_PrimitivePad.create(1,'',{OX}+c*{PITCH},{OY}+r*{PITCH},0,['ELLIPSE',{PAD},{PAD}],'',null,0,0,0,false,0));
const arr2=await Promise.all(ps);
const ms=performance.now()-t0;
globalThis.__ba_ids=arr2.filter(Boolean).map(p=>p.getState_PrimitiveId());
return {{n:globalThis.__ba_ids.length, ms:ms, perPad:ms/Math.max(globalThis.__ba_ids.length,1)}};
"""


def main() -> None:
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    t = time.time()
    cells = frame_cells(idx)
    print(f"frame {idx}: {len(cells)} cells ({time.time() - t:.2f}s)")

    res = eda.execute(build_js(cells), timeout=300)
    print("create:", json.dumps(res, ensure_ascii=False))
    print(f"总耗时 {time.time() - t:.1f}s")


if __name__ == "__main__":
    main()
