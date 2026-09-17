#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""移除某个行为最前面的「导航前置步」。

为什么需要：前置步不是越多越好。若某个行为的锚点本来就在**落地页**，
而配置里又给它加了「先点『我的』」的前置步，真实执行时会
「先跳到我的页 → 再找落地页才有的锚点」→ 必然失败。
实测 `今日看点极速版.sign`（首屏就有 `签到`）就是这种情况。

用法：
    python devtools/remove_prelude.py --app 今日看点极速版 --behavior sign
    python devtools/remove_prelude.py --app X --behavior sign --apply
    python devtools/remove_prelude.py --list          # 列出所有带前置步的行为
"""
import argparse
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from plan_anchor_fixes import NAV_ACTION  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")


def find_app_block(lines, app_name):
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == f"- name: {app_name}":
            start = i
            break
    if start is None:
        return None, None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- name: "):
            end = j
            break
    return start, end


def find_behavior(lines, start, end, behavior):
    for k in range(start, end):
        s = lines[k]
        if s.startswith("    ") and not s.startswith("     ") \
                and s.rstrip().endswith(":") and s.strip().rstrip(":") == behavior:
            return k
    return None


def list_preludes(lines):
    out = []
    app = None
    for i, ln in enumerate(lines):
        if ln.startswith("- name: "):
            app = ln[len("- name: "):].strip()
        if ln.startswith("    ") and not ln.startswith("     ") \
                and ln.rstrip().endswith(":"):
            bid = ln.strip().rstrip(":")
            if lines[i + 1:i + 1 + len(NAV_ACTION)] == list(NAV_ACTION):
                out.append((app, bid, i))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app")
    ap.add_argument("--behavior")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    lines = open(CONFIG, encoding="utf-8").read().split("\n")

    if args.list:
        found = list_preludes(lines)
        print(f"带导航前置步的行为共 {len(found)} 个：")
        for app, bid, ln in found:
            print(f"  {app}.{bid}  (行 {ln + 1})")
        return 0

    if not (args.app and args.behavior):
        print("需要 --app 和 --behavior（或用 --list 查看）")
        return 1

    s, e = find_app_block(lines, args.app)
    if s is None:
        print(f"未找到 app: {args.app}")
        return 1
    b = find_behavior(lines, s, e, args.behavior)
    if b is None:
        print(f"未找到行为: {args.app}.{args.behavior}")
        return 1
    if lines[b + 1:b + 1 + len(NAV_ACTION)] != list(NAV_ACTION):
        print(f"{args.app}.{args.behavior} 开头不是标准导航前置步，未改动")
        return 1

    print(f"将移除 {args.app}.{args.behavior} 的前置步（{len(NAV_ACTION)} 行）")
    if not args.apply:
        print("（预览模式，未写盘；加 --apply 生效）")
        return 0

    bak = f"{CONFIG}.bak-rmprelude-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(CONFIG, bak)
    del lines[b + 1:b + 1 + len(NAV_ACTION)]
    with open(CONFIG, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    print(f"已写回；备份 {bak}")
    try:
        import yaml
        cfg = yaml.safe_load(open(CONFIG, encoding="utf-8"))
        print(f"复验: config.yaml 加载成功, {len(cfg['apps'])} 个 app")
    except Exception as ex:
        print(f"复验失败: {ex}，回滚")
        shutil.copy2(bak, CONFIG)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
