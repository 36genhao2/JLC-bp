"""嘉立创EDA 桥接客户端：通过 run-api-gateway 在编辑器里执行 JS。"""
from __future__ import annotations

import json
import urllib.request

PORT = 49620
BASE = f"http://127.0.0.1:{PORT}"


def _post(path: str, payload: dict, timeout: float = 120.0) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(path: str, timeout: float = 10.0) -> dict:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(BASE + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def health() -> dict:
    return _get("/health")


def execute(code: str, timeout: float = 120.0) -> dict:
    """在编辑器里执行 code；code 需自带 return。"""
    try:
        res = _post("/execute", {"code": code}, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:600]}") from None
    if not res.get("success"):
        raise RuntimeError(res.get("error") or res)
    return res.get("result")


def js(expr: str, timeout: float = 120.0):
    return execute(f"return ({expr});", timeout)


if __name__ == "__main__":
    print(json.dumps(health(), ensure_ascii=False))
    print(js("typeof eda"))
