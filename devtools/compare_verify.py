#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""对比两次 verify_live.py 的结果，量化 any_of / 前置步改造的净效果。

用法：
    python devtools/compare_verify.py \
        --base devtools/calib/LIVE_VERIFY.json \
        --new  devtools/calib/LIVE_VERIFY_ANYOF.json

输出：
    - 总体命中率变化（首屏命中 + 导航后命中 视为「命中」）
    - 逐行为 diff：改善 / 恶化 / 持平
    - 结果波动清单（同一行为两次状态不同）
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# 视为「命中」的状态（锚点最终在某个层级上被找到）
HIT_STATUS = {"首屏命中", "导航后命中", "导航可救(建议加前置步)"}
# 明确不可用（污染/异常），不参与命中率计算
VOID_STATUS = {"数据作废(页面非目标App)", "数据作废(前台非目标App)", "异常"}


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("report") or {}


def flatten(report):
    """{(app, behavior): status}"""
    out = {}
    for app, rows in report.items():
        for r in rows:
            out[(app, r["behavior"])] = r.get("status", "?")
    return out


def is_hit(st):
    return st in HIT_STATUS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", default=None, help="可选：写一份 markdown 报告")
    args = ap.parse_args()

    base = flatten(load(args.base))
    new = flatten(load(args.new))
    keys = sorted(set(base) | set(new))

    improved, worsened, same, voided = [], [], [], []
    for k in keys:
        b, n = base.get(k), new.get(k)
        if n in VOID_STATUS:
            voided.append((k, b, n))
            continue
        if b is None:
            improved.append((k, b, n))
        elif n is None:
            worsened.append((k, b, n))
        elif is_hit(n) and not is_hit(b):
            improved.append((k, b, n))
        elif is_hit(b) and not is_hit(n):
            worsened.append((k, b, n))
        elif b != n:
            same.append((k, b, n))          # 状态不同但命中与否一致（如首屏->导航后）
        else:
            same.append((k, b, n))

    def rate(d):
        vals = [v for v in d.values() if v not in VOID_STATUS]
        h = sum(1 for v in vals if is_hit(v))
        return h, len(vals)

    bh, bt = rate(base)
    nh, nt = rate(new)
    print("=" * 68)
    print(f"基线命中: {bh}/{bt}" + (f" = {bh / bt * 100:.1f}%" if bt else ""))
    print(f"新  命中: {nh}/{nt}" + (f" = {nh / nt * 100:.1f}%" if nt else ""))
    if bt and nt:
        print(f"净变化  : {(nh / nt - bh / bt) * 100:+.1f} 个百分点")
    print("=" * 68)

    def dump(title, items):
        print(f"\n## {title}（{len(items)}）")
        for (app, beh), b, n in items:
            print(f"  {app:16s} {beh:10s} {b}  ->  {n}")

    dump("改善", improved)
    dump("恶化", worsened)
    dump("持平/层级变化", same)
    if voided:
        print(f"\n## 本轮作废（不计入统计）（{len(voided)}）")
        for (app, beh), b, n in voided:
            print(f"  {app:16s} {beh:10s} {b}  ->  {n}")

    if args.out:
        md = ["# any_of 改造前后对比", "",
              f"- 基线: `{os.path.basename(args.base)}` → 命中 **{bh}/{bt}**",
              f"- 新结果: `{os.path.basename(args.new)}` → 命中 **{nh}/{nt}**", ""]
        for title, items in (("改善", improved), ("恶化", worsened),
                             ("持平/层级变化", same), ("本轮作废", voided)):
            md += [f"## {title}（{len(items)}）", "",
                   "| App | 行为 | 基线 | 新 |", "|---|---|---|---|"]
            for (app, beh), b, n in items:
                md.append(f"| {app} | {beh} | {b} | {n} |")
            md.append("")
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        print(f"\n报告: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
