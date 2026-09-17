#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「已验证的候选锚点」写回 config.yaml（行级编辑，保留原有排版与注释）。

数据来源：devtools/calib/<app>/ui.xml | ui_after.xml 中真实存在的节点。
每条修复 = (app, behavior, label)；label 是在 dump 里实测到的完整文案，
以 textContains 语义写入 candidates 列表首位（最高置信度优先尝试）。

用法：
    python devtools/apply_candidate_fixes.py            # 预览（不写盘）
    python devtools/apply_candidate_fixes.py --apply    # 写回（自动备份）
"""
import argparse
import os
import shutil
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG = os.path.join(ROOT, "config.yaml")

# (app, behavior, 实测文案)  —— 顺序与 FIX_PLAN.md 的 candidate 项一致
FIXES = [
    ("一淘",           "watch",   "去福狸中心做任务"),
    ("今日头条极速版", "bonus",   "完成挑战得奖励"),
    ("喜番免费短剧",   "watch",   "去看剧"),
    ("微博移动版",     "bonus",   "点击领取"),
    ("悟空浏览器",     "watch",   "看剧"),
    ("抖音火山版",     "watch",   "点击赚钱"),
    ("星图金融",       "collect", "迎新福利"),
    ("梧桐免费小说",   "watch",   "福利商城"),
    ("河马剧场",       "watch",   "福利"),
    ("火龙漫剧",       "watch",   "福利"),
    ("点淘",           "collect", "待领取"),
    ("红果免费短剧",   "collect", "去领取"),
]

CAND_TPL = [
    "      - type: text",
    "        value: {v}",
]


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
    """返回 behavior 名字所在行号。"""
    for k in range(start, end):
        s = lines[k]
        if s.startswith("    ") and not s.startswith("     ") \
                and s.rstrip().endswith(":") and s.strip().rstrip(":") == behavior:
            return k
    return None


def behavior_span(lines, bstart, app_end):
    """behavior 块的结束行（下一个行为名 / app 结束）。"""
    for k in range(bstart + 1, app_end):
        s = lines[k]
        if s.startswith("    ") and not s.startswith("     ") and s.rstrip().endswith(":"):
            return k
    return app_end


def apply_one(lines, app, behavior, value):
    s, e = find_app_block(lines, app)
    if s is None:
        return None, f"未找到 app 块: {app}"
    b = find_behavior(lines, s, e, behavior)
    if b is None:
        return None, f"未找到行为: {app}.{behavior}"
    bend = behavior_span(lines, b, e)
    # 在该行为块里找第一个 click_first 的 candidates:
    ci = None
    for k in range(b + 1, bend):
        if lines[k].strip() == "- type: click_first":
            for m in range(k + 1, bend):
                if lines[m].strip() == "candidates:":
                    ci = m
                    break
                if lines[m].startswith("      - type:") or lines[m].strip().startswith("- type:"):
                    break
            if ci is not None:
                break
    if ci is None:
        return None, f"{app}.{behavior} 首个 click_first 未找到 candidates:"
    # 去重：若已存在同值候选则跳过
    for k in range(ci + 1, bend):
        if lines[k].strip().startswith("value:") and lines[k].split("value:", 1)[1].strip() == value:
            return None, f"{app}.{behavior} 已存在候选 {value!r}，跳过"
    ins = [tpl.format(v=value) for tpl in CAND_TPL]
    lines[ci + 1:ci + 1] = ins
    return ci, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写回 config.yaml")
    args = ap.parse_args()

    with open(CONFIG, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")

    ok, skip, fail = [], [], []
    # 从后往前应用，避免行号漂移
    planned = []
    for app, behavior, value in FIXES:
        planned.append((app, behavior, value))

    # 先做一次干跑收集行号，再倒序插入
    results = []
    work = list(lines)
    for app, behavior, value in planned:
        pos, err = apply_one(work, app, behavior, value)
        if err:
            (skip if "已存在" in err else fail).append(err)
        else:
            ok.append(f"{app}.{behavior} <- {value!r}")

    if fail:
        print("!! 有失败项，未写盘：")
        for x in fail:
            print("   ", x)
        return 1

    print(f"计划插入 {len(ok)} 处候选锚点：")
    for x in ok:
        print("   ", x)
    for x in skip:
        print("  [跳过]", x)

    if not args.apply:
        print("\n（预览模式，未写盘；加 --apply 生效）")
        return 0

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{CONFIG}.bak-cand-{ts}"
    shutil.copy2(CONFIG, bak)
    with open(CONFIG, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(work))
    print(f"\n已写回 {CONFIG}")
    print(f"备份: {bak}")

    # 复验
    try:
        import yaml
        cfg = yaml.safe_load(open(CONFIG, encoding="utf-8"))
        print(f"复验: config.yaml 加载成功, {len(cfg['apps'])} 个 app")
    except Exception as ex:  # noqa
        print(f"复验失败: {ex}，正在回滚")
        shutil.copy2(bak, CONFIG)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
