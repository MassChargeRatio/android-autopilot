#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""多轮稳定性跑批：同一批配置连跑 N 轮，统计每个行为的**命中率**。

为什么需要
----------
单轮 pass/fail 不可信（见 `devtools/calib/ROUND2_FINAL.md` §五）：
同一批配置、同一台设备，不同轮次结果差异显著 ——
一淘.sign 三轮三种结果；火龙漫剧 3 个行为在「全未命中 / 全导航后命中 /
全首屏命中」之间跳。根因是 **App 落地页不确定**（开屏广告 / 活动弹窗 /
新手引导 / 上次退出的 tab / 登录态 / 灰度活动页），不是锚点写错。

所以判定「锚点好不好」「any_of 改造有没有用」必须看多轮统计：
  * 命中率 = 命中的轮数 / 有效轮数（数据作废的轮次不计入分母）
  * 一个只在 1/3 轮命中的锚点，和 3/3 命中的锚点，价值完全不同

命中口径
--------
    命中   = 首屏命中 / 导航后命中 / 导航可救(建议加前置步)
    未命中 = 首屏未命中 / 导航后仍未命中 / 导航后也未命中(不可救)
    作废   = 数据作废(...)  -> 不计入分母（宁可不给结论，也不给错结论）

用法
----
    python devtools/stability_run.py --rounds 3
    python devtools/stability_run.py --rounds 3 --apps 一淘,河马剧场
    python devtools/stability_run.py --rounds 3 --nav-fast --probe-nav
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from calibrate import connect_device, safe_name  # noqa: E402
from verify_live import verify_app  # noqa: E402

HIT_STATUS = {"首屏命中", "导航后命中", "导航可救(建议加前置步)"}
VOID_PREFIX = "数据作废"


def is_void(st):
    return (st or "").startswith(VOID_PREFIX) or st in ("异常", "无锚点动作")


def is_hit(st):
    return st in HIT_STATUS


def aggregate(acc):
    """把 {(app, behavior): [status,...]} 聚合成逐行为统计。

    口径（决定头条指标，务必与文档一致）：
      * valid  = 非作废的轮数（作废轮次**不进分母** —— 宁可不给结论也不给错结论）
      * hits   = valid 里判为命中的轮数
      * rate   = hits / valid；valid 为 0 时 rate=None（该行不参与总命中率）
    返回 (per_behavior, total)；per_behavior 按 (app, behavior) 排序。
    """
    per_behavior = []
    for (app, beh), sts in sorted(acc.items()):
        valid = [s for s in sts if not is_void(s)]
        hits = sum(1 for s in valid if is_hit(s))
        per_behavior.append({
            "app": app, "behavior": beh, "statuses": list(sts),
            "valid": len(valid), "void": len(sts) - len(valid), "hits": hits,
            "rate": (hits / len(valid)) if valid else None,
        })
    total = {
        "hits": sum(x["hits"] for x in per_behavior),
        "valid": sum(x["valid"] for x in per_behavior),
        "void": sum(x["void"] for x in per_behavior),
    }
    return per_behavior, total


def classify(per_behavior):
    """分成 稳定命中 / 波动 / 从未命中 三类（valid=0 的行不进任何一类）。"""
    stable = [x for x in per_behavior if x["valid"] and x["hits"] == x["valid"]]
    flaky = [x for x in per_behavior if x["valid"] and 0 < x["hits"] < x["valid"]]
    never = [x for x in per_behavior if x["valid"] and x["hits"] == 0]
    return stable, flaky, never


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--apps", default=None)
    ap.add_argument("--behaviors", default=None)
    ap.add_argument("--probe-nav", action="store_true")
    ap.add_argument("--nav-fast", action="store_true")
    ap.add_argument("--pause", type=float, default=4.0,
                    help="轮次之间的间隔秒数")
    ap.add_argument("--md", default=os.path.join(HERE, "calib", "STABILITY.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "STABILITY.json"))
    args = ap.parse_args()

    import yaml
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    vision_cfg = cfg.get("vision") or {}
    serial = (cfg.get("device") or {}).get("serial")

    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    only_b = set(x.strip() for x in args.behaviors.split(",")) if args.behaviors else None
    apps = [a for a in (cfg.get("apps") or []) if not only or a.get("name") in only]
    apps = [a for a in apps
            if os.path.isdir(os.path.join(HERE, "calib", safe_name(a.get("name", ""))))]

    print(f"待跑 App: {len(apps)} -> {[a['name'] for a in apps]}")
    print(f"轮数: {args.rounds}  probe_nav={args.probe_nav}  nav_fast={args.nav_fast}")
    d = connect_device(serial)

    # {(app, behavior): [status, ...]}
    acc = {}
    all_log = {}
    for rnd in range(1, args.rounds + 1):
        print(f"\n########## 第 {rnd}/{args.rounds} 轮 ##########")
        for a in apps:
            name = a.get("name")
            print(f"\n===== [R{rnd}] {name} =====")
            log = []
            try:
                rows = verify_app(a, only_b, d, vision_cfg, log,
                                  probe_nav=args.probe_nav,
                                  nav_fast=args.nav_fast)
            except Exception as e:
                log.append(f"验证异常: {type(e).__name__}: {e}")
                rows = [{"behavior": "-", "status": "异常", "detail": str(e)}]
            all_log.setdefault(name, []).append({"round": rnd, "log": log})
            for row in rows:
                key = (name, row["behavior"])
                acc.setdefault(key, []).append(row.get("status", "?"))
                print(f"  {row['behavior']:10s} {row['status']:14s} "
                      f"{row.get('detail', '')[:120]}")
            if args.pause:
                time.sleep(args.pause)

    # ---- 汇总 ----
    per_behavior, tot = aggregate(acc)
    tot_h, tot_v, tot_void = tot["hits"], tot["valid"], tot["void"]
    stable_hit, flaky, never = classify(per_behavior)

    print("\n" + "=" * 70)
    print(f"多轮统计（{args.rounds} 轮）")
    print("=" * 70)
    print(f"  总命中: {tot_h}/{tot_v}"
          + (f" = {tot_h / tot_v * 100:.1f}%" if tot_v else "")
          + f"   作废轮次: {tot_void}")
    print(f"  稳定命中（每轮都中）: {len(stable_hit)}")
    print(f"  波动（有时中）      : {len(flaky)}")
    print(f"  从未命中            : {len(never)}")

    def dump(title, items):
        if not items:
            return
        print(f"\n## {title}（{len(items)}）")
        for x in items:
            rate = "-" if x["rate"] is None else f"{x['hits']}/{x['valid']}"
            print(f"  {x['app']:16s} {x['behavior']:10s} {rate:6s} "
                  f"{' | '.join(x['statuses'])}")

    dump("稳定命中", stable_hit)
    dump("波动（重点观察）", flaky)
    dump("从未命中", never)

    md = ["# 多轮稳定性报告", "",
          f"> 生成: {time.strftime('%Y-%m-%d %H:%M:%S')}",
          f"> 设备: {serial} · 轮数: {args.rounds} · "
          f"probe_nav={args.probe_nav} nav_fast={args.nav_fast}", "",
          "## 汇总", "",
          f"- 总命中: **{tot_h}/{tot_v}**"
          + (f" = **{tot_h / tot_v * 100:.1f}%**" if tot_v else ""),
          f"- 作废轮次: {tot_void}",
          f"- 稳定命中（每轮都中）: **{len(stable_hit)}**",
          f"- 波动（有时中）: **{len(flaky)}**",
          f"- 从未命中: **{len(never)}**", "",
          "## 逐行为明细", "",
          "| App | 行为 | 命中率 | 各轮状态 |", "|---|---|---|---|"]
    for x in per_behavior:
        rate = "-" if x["rate"] is None else f"{x['hits']}/{x['valid']}"
        md.append(f"| {x['app']} | {x['behavior']} | {rate} | "
                  f"{' / '.join(x['statuses'])} |")
    md += ["", "## 执行日志", ""]
    for name, rounds in all_log.items():
        for item in rounds:
            md.append(f"<details><summary>{name} · 第 {item['round']} 轮</summary>")
            md.append("")
            md.append("```")
            md += item["log"]
            md.append("```")
            md.append("</details>")
            md.append("")

    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    with open(args.md, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    json.dump({"rounds": args.rounds, "per_behavior": per_behavior,
               "total": {"hits": tot_h, "valid": tot_v, "void": tot_void},
               "stable_hit": len(stable_hit), "flaky": len(flaky),
               "never": len(never)},
              open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n报告: {args.md}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
