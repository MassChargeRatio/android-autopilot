# -*- coding: utf-8 -*-
"""vocab_report.py - 打印跨 App 共性词表的归纳结果（AUTOP-NL-2026-10-22 第3项观察工具）

用途：人工复核「哪些词被自动升级为共性词」，以及每个行为的最终候选池。
只读，不写任何文件。

用法：
    ./.venv/Scripts/python.exe devtools/vocab_report.py
    ./.venv/Scripts/python.exe devtools/vocab_report.py --app 拼多多
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import candidates  # noqa: E402
from config_loader import load_config  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", help="只看某个 App 的候选池")
    args = ap.parse_args()

    cfg = load_config(CONFIG)
    apps = cfg.get("apps") or []
    candidates.register_apps(apps)

    print(f"App 总数: {len(apps)}")
    print(f"归纳门槛: 同一行为下 >= {candidates.MIN_APP_SUPPORT} 个 App 用过\n")

    mined = candidates.mine_words()
    if not mined:
        print("归纳结果: 空（所有共性词都已在人工词表中）")
    else:
        print("归纳出的表外共性词：")
        for cat, words in sorted(mined.items()):
            print(f"  [{cat}] {', '.join(words)}")

    print("\n各行为最终候选池：")
    for bid in sorted(candidates.INTENT_TO_CATEGORY):
        cat = candidates.INTENT_TO_CATEGORY[bid]
        pool = candidates.candidates_for(cat)
        print(f"  {bid:10s} -> {cat:12s} ({len(pool)} 个) {', '.join(pool)}")

    if args.app:
        target = next((a for a in apps if a.get("name") == args.app
                       or args.app in (a.get("aliases") or [])), None)
        if not target:
            print(f"\n未找到 App: {args.app}")
            return 1
        print(f"\n{target.get('name')} 的行为与候选池：")
        for bid in (target.get("behaviors") or {}):
            cat = candidates.category_for_intent(bid)
            if cat:
                pool = candidates.candidates_for(cat, target)
                print(f"  {bid:10s} -> {len(pool)} 个候选")
            else:
                print(f"  {bid:10s} -> （该行为不参与词表推断）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
