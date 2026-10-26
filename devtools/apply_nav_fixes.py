#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""根据实机探路结果（LIVE_PROBE_NAV.json）自动补导航前置步。

链路：verify_live.py --probe-nav 会对**所有**未命中项试一次「导航到我的」，
       命中则状态为 `导航可救(建议加前置步)`。
       本脚本把这类行为的前置步写回 config.yaml（幂等，自动备份）。

用法：
    python devtools/apply_nav_fixes.py                       # 预览
    python devtools/apply_nav_fixes.py --apply               # 写回
    python devtools/apply_nav_fixes.py --json <path> --apply
"""
import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import app_config_path, load_config  # noqa: E402
from plan_anchor_fixes import apply_prelude, NAV_ACTION  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")
DEFAULT_JSON = os.path.join(HERE, "calib", "LIVE_PROBE_NAV.json")

FIXABLE = "导航可救(建议加前置步)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=DEFAULT_JSON)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.json):
        print(f"找不到探路结果: {args.json}")
        return 1
    data = json.load(open(args.json, encoding="utf-8"))
    report = data.get("report", data)

    plan = {}
    for app, rows in report.items():
        for r in rows:
            if r.get("status") == FIXABLE:
                plan.setdefault(app, []).append(r["behavior"])

    if not plan:
        print("没有可补前置步的项（探路结果为 0）")
        return 0

    total = sum(len(v) for v in plan.values())
    print(f"计划补前置步 {total} 处：")
    for app, bs in plan.items():
        print(f"  {app}: {', '.join(bs)}")

    if not args.apply:
        print("\n（预览模式，未写盘；加 --apply 生效）")
        return 0

    bak = f"{CONFIG}.bak-nav-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(CONFIG, bak)
    print(f"已备份: {bak}")
    inserted = 0
    for app, bs in plan.items():
        path = app_config_path(app)
        if not os.path.exists(path):
            print(f"  !! 未找到 app 配置文件: {app} ({path})")
            continue
        bak_app = f"{path}.bak-nav-{time.strftime('%Y%m%d-%H%M%S')}"
        shutil.copy2(path, bak_app)
        n = apply_prelude(path, app, set(bs))
        print(f"  {app}: 插入 {n} 处（{len(bs)} 个行为中 {len(bs) - n} 个已有前置步）")
        inserted += n
    print(f"共插入 {inserted} 处")
    try:
        cfg = load_config(CONFIG)
        print(f"复验: config 加载成功, {len(cfg['apps'])} 个 app")
    except Exception as ex:
        print(f"复验失败: {ex}，回滚")
        shutil.copy2(bak, CONFIG)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
