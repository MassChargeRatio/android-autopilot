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
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import app_config_path, load_config  # noqa: E402

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
        # 拆分后 App 级文件：整文件即一个 App 块（首行 `name: xxx`）
        if lines and lines[0].strip() == f"name: {app_name}":
            start = 0
        else:
            return None, None
        end = len(lines)
        return start, end
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- name: "):
            end = j
            break
    return start, end


def behavior_indent(lines, start, end):
    """返回 behaviors 子键（行为名）的缩进空格数：拆分后 App 文件=2，旧单文件=4。"""
    for k in range(start, end):
        s = lines[k].rstrip()
        if s.endswith(":") and s.strip() == "behaviors":
            return len(s) - len(s.lstrip()) + 2
    return 4


def find_behavior(lines, start, end, behavior, indent=4):
    """返回 behavior 名字所在行号。"""
    for k in range(start, end):
        s = lines[k]
        if s.startswith(" " * indent) and not s.startswith(" " * (indent + 1)) \
                and s.rstrip().endswith(":") and s.strip().rstrip(":") == behavior:
            return k
    return None


def behavior_span(lines, bstart, app_end, indent=4):
    """behavior 块的结束行（下一个行为名 / app 结束）。"""
    for k in range(bstart + 1, app_end):
        s = lines[k]
        if s.startswith(" " * indent) and not s.startswith(" " * (indent + 1)) and s.rstrip().endswith(":"):
            return k
    return app_end


def apply_one(lines, app, behavior, value):
    s, e = find_app_block(lines, app)
    if s is None:
        return None, f"未找到 app 块: {app}"
    ind = behavior_indent(lines, s, e)
    b = find_behavior(lines, s, e, behavior, ind)
    if b is None:
        return None, f"未找到行为: {app}.{behavior}"
    bend = behavior_span(lines, b, e, ind)
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

    # 按 App 分组，逐 App 文件行级编辑（拆分后每 App 一个文件）
    by_app = {}
    for app, behavior, value in FIXES:
        by_app.setdefault(app, []).append((behavior, value))

    ok, skip, fail = [], [], []
    # 先做一次干跑收集行号，再倒序插入；任一失败则整体不写盘
    results = []
    for app, items in by_app.items():
        path = app_config_path(app)
        if not os.path.exists(path):
            fail.append(f"未找到 app 配置文件: {app} ({path})")
            continue
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")
        work = list(lines)
        local_ok = []
        for behavior, value in items:
            pos, err = apply_one(work, app, behavior, value)
            if err:
                (skip if "已存在" in err else fail).append(err)
            else:
                local_ok.append(f"{app}.{behavior} <- {value!r}")
        ok.extend(local_ok)
        if local_ok:
            results.append((app, path, work))

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

    for app, path, work in results:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = f"{path}.bak-cand-{ts}"
        shutil.copy2(path, bak)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(work))
        print(f"已写回 {path}")
        print(f"备份: {bak}")

    # 复验
    try:
        cfg = load_config(CONFIG)
        print(f"复验: config 加载成功, {len(cfg['apps'])} 个 app")
    except Exception as ex:  # noqa
        print(f"复验失败: {ex}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
