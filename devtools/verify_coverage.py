# -*- coding: utf-8 -*-
"""verify_coverage.py - 覆盖率验收门（CI 用，退出码 0=PASS / 1=FAIL）

用法：
    ./.venv/Scripts/python.exe devtools/verify_coverage.py

判据：total == verifiable 且 unverifiable == 0。

"可校验"= 该 routine 的每一步都能被 dry-run 规划出来（有明确的 type 与目标）。
"不可校验"通常意味着出现了 verify_live 认不出的锚点类型 —— 那批行为是
**完全没被度量**的，命中率分母里没有它，所以必须让它以非零退出码暴露出来。
"""
import json
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from webui.data import Store  # noqa: E402

CONFIG = os.path.join(BASE, "config.yaml")
DB = os.path.join(tempfile.gettempdir(), "autopilot_coverage.db")


def main() -> int:
    store = Store(CONFIG, DB)
    rep = store.verify_coverage()
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    ok = (rep.get("total") == rep.get("verifiable")
          and rep.get("unverifiable", 1) == 0)
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
