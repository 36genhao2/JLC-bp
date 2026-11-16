"""栅格配置。COLS/ROWS/MARGIN 是布局与取帧的唯一来源，避免两处各写一份。

默认 128×96，可用环境变量覆盖：
    BA_GRID=16x16      # 栅格列x行
    BA_MARGIN=300      # 板框内缩（mil）
"""
from __future__ import annotations

import os

_DEFAULT_COLS, _DEFAULT_ROWS = 128, 96
_DEFAULT_MARGIN = 250.0


def _parse_grid() -> tuple[int, int]:
    raw = os.environ.get("BA_GRID", "").strip().lower()
    if not raw:
        return _DEFAULT_COLS, _DEFAULT_ROWS
    for sep in ("x", "*", ",", "×"):
        if sep in raw:
            a, b = raw.split(sep, 1)
            return int(a), int(b)
    raise ValueError(f"BA_GRID 格式应为 宽x高，收到：{raw!r}")


COLS, ROWS = _parse_grid()
MARGIN = float(os.environ.get("BA_MARGIN", _DEFAULT_MARGIN))
THRESH = 128
