#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三级导航探针：验证「我的 → 任务中心/福利 → 签到」这条路径是否成立。

背景
----
剩余缺口里 `sign` 类占 8/16。签到入口普遍不在「我的」首层，
而在「我的 → 任务中心 / 福利」子页里。现有配置只表达到第二层，
所以这类行为必然未命中。

本工具做的事：
    启动 App → 等待就绪 → 关弹窗 → 点「我的」
      → dump：在二级页找「任务中心/福利/赚钱/金币…」入口
        → 找到就点进去
          → dump：在三级页找目标锚点（签到/看视频/提现…）
            → 报告命中情况 + 存三级页截图供目视复核

产物：
    devtools/calib/<app>/deep_<behavior>_L2.png / _L3.png
    devtools/calib/DEEP_PROBE.md / .json

用法：
    python devtools/probe_deep.py --apps 一淘,河马剧场 --behaviors sign
    python devtools/probe_deep.py                 # 默认跑全部 sign 缺口
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

from calibrate import (  # noqa: E402
    parse_nodes, match_selector, wait_ready, dismiss_popups,
    connect_device, safe_name, page_belongs_to,
)

# 默认目标：本轮实机回归里未命中的 sign 行为
DEFAULT_TARGETS = [
    ("一淘", "sign"),
    ("今日看点极速版", "sign"),
    ("天天快讯极速版", "sign"),
    ("蛋花免费小说", "sign"),
    ("喜番免费短剧", "sign"),
    ("河马剧场", "sign"),
    ("悟空浏览器", "sign"),
    ("抖音火山版", "sign"),
]

# 二级页上的「任务/福利」入口候选（按优先级）。
# 末尾几项来自实机 dump 里见过的真实文案（点淘「元宝中心」等）。
L2_CANDIDATES = [
    "任务中心", "福利中心", "我的福利", "福利", "赚钱", "金币",
    "领金币", "天天领", "做任务", "任务", "钱包", "现金",
    "元宝中心", "金币中心", "福利商城", "任务广场", "赚金币",
    "看剧赚钱", "看书赚钱", "看视频赚钱", "我的金币", "现金奖励",
]

# 目标锚点（三级页上要找的东西）
# 注意：sign 里**不要**放裸的「打卡」—— 实测会误报「喝水打卡」「早起打卡」
# 这类与每日签到无关的任务（今日看点极速版的 我的 页就有「喝水打卡」）。
L3_KEYWORDS = {
    "sign": ["签到", "每日签到", "立即签到", "去签到", "已签到",
             "签到领金币", "签到得金币", "连续签到", "签到打卡"],
    "watch": ["看视频", "看剧赚钱", "去完成", "任务", "赚钱"],
    "withdraw": ["提现", "立即提现", "余额", "可提现"],
    "bonus": ["领红包", "开宝箱", "领取", "红包"],
    "collect": ["任务中心", "去领取", "领取", "福利"],
}

MINE_XY = (0.90, 0.915)


def find_all(nodes, keywords, limit=6):
    """按关键词顺序收集**多个**候选入口（按 label+center 去重，可点击优先）。

    为什么要多个：实测「我的」页上常有多个任务/福利类入口，
    签到可能只在其中某一个里面（例如天天快讯极速版要进「福利中心」，
    蛋花的「福利」页里却没有签到）。只试第一个会漏判。

    为什么不做「必须可点击」的硬过滤：实测入口文案常常挂在**不可点击的
    text 子节点**上，真正可点的是它的父容器（一淘的「去福狸中心做任务」
    就是这种）。硬过滤会把入口整个滤掉。所以只做**排序**（可点击在前），
    点击时用文案中心坐标，uiautomator2 会命中其上层容器。
    """
    out, seen = [], set()
    for kw in keywords:
        for kind in ("text", "desc"):
            hits = match_selector(nodes, kind, kw)
            hits = [h for h in hits if _ok_len(h, kw, kind)]
            hits.sort(key=lambda h: (not h["clickable"], len(
                h["text"] if kind == "text" else h["desc"])))
            for h in hits:
                lab = (h["text"] or h["desc"]).strip()
                key = (lab, h["center"])
                if key in seen:
                    continue
                seen.add(key)
                out.append((lab, h["center"], kind))
                if len(out) >= limit:
                    return out
    return out


def find_first(nodes, keywords, require_clickable=False):
    """按关键词顺序找节点，返回 (label, center, kind)。

    排序上**可点击优先**；`require_clickable=True` 时才硬过滤 ——
    仅在「判断这是不是一个入口」且不能容忍标签误报时使用。
    """
    for kw in keywords:
        for kind in ("text", "desc"):
            hits = match_selector(nodes, kind, kw)
            hits = [h for h in hits if _ok_len(h, kw, kind)]
            if require_clickable:
                hits = [h for h in hits if h["clickable"]]
            if hits:
                hits.sort(key=lambda h: (not h["clickable"], len(
                    h["text"] if kind == "text" else h["desc"])))
                h = hits[0]
                lab = (h["text"] or h["desc"]).strip()
                return lab, h["center"], kind
    return None


def _ok_len(node, target, kind):
    if kind not in ("text", "desc"):
        return True
    label = node["text"] if kind == "text" else node["desc"]
    limit = max(len(str(target)) + 6, len(str(target)) * 3)
    return not (len(label) > limit and not node["clickable"])


def probe_one(d, app_cfg, behavior, log, max_l2=3):
    name, pkg = app_cfg["name"], app_cfg["package"]
    outdir = os.path.join(HERE, "calib", safe_name(name))
    os.makedirs(outdir, exist_ok=True)
    res = {"app": name, "behavior": behavior, "l2": None, "l3": None,
           "l2_xy": None, "l3_xy": None, "shot_l2": None, "shot_l3": None,
           "on_l2": None}

    ok_page, dom, mine, dom_n, fg = False, "", 0, 0, ""
    for attempt in (1, 2):
        try:
            d.app_start(pkg, wait=True)
        except Exception as e:
            log.append(f"启动异常: {type(e).__name__}: {e}")
        xml, nodes, waited = wait_ready(d, pkg, max_wait=75, min_nodes=25, log=log)
        log.append(f"就绪: 节点={len(nodes)} 等待={waited:.1f}s")
        dismiss_popups(d, nodes, log)
        try:
            fg = d.info.get("currentPackageName") or ""
        except Exception:
            fg = ""
        # 归属以 dump 自身为准（前台包名在崩溃/切换时序下会失真）
        ok_page, dom, mine, dom_n = page_belongs_to(xml, pkg)
        log.append(f"归属校验: 主导包={dom}（{dom_n} 节点） 目标包={mine} 节点"
                   f" 前台={fg} -> {'属于目标 App' if ok_page else '不属于'}")
        if ok_page:
            break
        log.append("归属校验失败，重试")
        time.sleep(3)
    if not ok_page:
        log.append(f"归属校验最终失败（主导包 {dom}），作废")
        res["error"] = f"页面非目标App(主导={dom})"
        return res

    # 第一层：点「我的」
    w, h = d.window_size()
    x, y = int(MINE_XY[0] * w), int(MINE_XY[1] * h)
    log.append(f"点『我的』({x},{y})")
    d.click(x, y)
    time.sleep(3.5)
    xml2 = d.dump_hierarchy()
    nodes2 = parse_nodes(xml2)
    dismiss_popups(d, nodes2, log)
    ok2, dom2, _m2, _d2 = page_belongs_to(xml2, pkg)
    log.append(f"二级页节点={len(nodes2)} 主导包={dom2}"
               f"{'' if ok2 else ' -> 已离开目标 App，作废'}")
    if not ok2:
        res["error"] = f"二级页非目标App(主导={dom2})"
        return res
    try:
        p = os.path.join(outdir, f"deep_{behavior}_L2.png")
        d.screenshot(p)
        res["shot_l2"] = p
    except Exception as e:
        log.append(f"二级页截图失败: {e}")

    # 有些 App 的签到入口**就在二级页**（「我的」页本身就有签到按钮），
    # 先就地找一次，避免漏判成「不可救」。
    # 两段式：先找可点击的（真入口），没有再退而求其次找文案（可能是标签，
    # 结果标注 [低置信]，人工复核时优先看这类）。
    hit_on_l2 = find_first(nodes2, L3_KEYWORDS.get(behavior, []),
                           require_clickable=True)
    low_conf = False
    if hit_on_l2 is None:
        hit_on_l2 = find_first(nodes2, L3_KEYWORDS.get(behavior, []))
        low_conf = hit_on_l2 is not None
    if hit_on_l2 is not None:
        lab, c, kind = hit_on_l2
        res["on_l2"] = f"{kind}={lab}" + (" [低置信]" if low_conf else "")
        res["l2_xy"] = c
        log.append(f"★ 二级页即命中: {kind}={lab!r} @{c}"
                   + ("（不可点击，可能只是标签，需人工复核）" if low_conf
                      else "（可点击入口，无需三级导航）"))
        return res

    # 第二层：收集「任务中心/福利」类入口，依次尝试
    entries = find_all(nodes2, L2_CANDIDATES, limit=max_l2)
    if not entries:
        log.append("二级页未找到任务/福利入口")
        return res
    log.append(f"二级页候选入口 {len(entries)} 个: "
               f"{[f'{lab}@{c}' for lab, c, _ in entries]}")
    res["attempts"] = []
    for idx, (lab2, c2, kind2) in enumerate(entries):
        if idx:
            # 回到「我的」页再试下一个入口
            try:
                d.press("back")
                time.sleep(2.0)
                d.click(int(MINE_XY[0] * w), int(MINE_XY[1] * h))
                time.sleep(3.0)
            except Exception as e:
                log.append(f"回退失败: {type(e).__name__}: {e}")
        log.append(f"[{idx + 1}/{len(entries)}] 点入口 {kind2}={lab2!r} @{c2}")
        d.click(c2[0], c2[1])
        time.sleep(3.5)
        xml3 = d.dump_hierarchy()
        nodes3 = parse_nodes(xml3)
        dismiss_popups(d, nodes3, log)
        ok3, dom3, _m3, _d3 = page_belongs_to(xml3, pkg)
        log.append(f"  三级页节点={len(nodes3)} 主导包={dom3}"
                   f"{'' if ok3 else ' -> 已离开目标 App，本次作废'}")
        if not ok3:
            res["attempts"].append({"l2": f"{kind2}={lab2}", "l3": None,
                                    "error": f"页面非目标App(主导={dom3})"})
            continue
        try:
            p = os.path.join(outdir, f"deep_{behavior}_L3_{idx + 1}.png")
            d.screenshot(p)
            res["shot_l3"] = p
        except Exception as e:
            log.append(f"三级页截图失败: {e}")
        hit3 = find_first(nodes3, L3_KEYWORDS.get(behavior, []))
        if hit3 is None:
            log.append("  三级页未找到目标锚点")
            res["attempts"].append({"l2": f"{kind2}={lab2}", "l3": None})
            continue
        lab3, c3, kind3 = hit3
        res["l2"] = f"{kind2}={lab2}"
        res["l2_xy"] = c2
        res["l3"] = f"{kind3}={lab3}"
        res["l3_xy"] = c3
        res["attempts"].append({"l2": f"{kind2}={lab2}",
                                "l3": f"{kind3}={lab3}"})
        log.append(f"  ★ 三级页命中: {kind3}={lab3!r} @{c3}")
        return res
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--apps", default=None)
    ap.add_argument("--behaviors", default=None)
    ap.add_argument("--max-l2", type=int, default=3,
                    help="每个 App 最多依次尝试几个二级入口（默认 3）")
    ap.add_argument("--md", default=os.path.join(HERE, "calib", "DEEP_PROBE.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "DEEP_PROBE.json"))
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load(open(args.config, encoding="utf-8")) or {}
    apps = {a["name"]: a for a in (cfg.get("apps") or []) if a.get("name")}
    only_a = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    only_b = set(x.strip() for x in args.behaviors.split(",")) if args.behaviors else None

    targets = [(a, b) for a, b in DEFAULT_TARGETS
               if (not only_a or a in only_a) and (not only_b or b in only_b)]
    print(f"待探针: {len(targets)} 项 -> {targets}")

    serial = (cfg.get("device") or {}).get("serial")
    d = connect_device(serial)

    results, logs = [], {}
    for app, beh in targets:
        if app not in apps:
            print(f"跳过（配置无此 App）: {app}")
            continue
        print(f"\n===== {app} / {beh} =====")
        log = []
        try:
            r = probe_one(d, apps[app], beh, log, max_l2=args.max_l2)
        except Exception as e:
            log.append(f"异常: {type(e).__name__}: {e}")
            r = {"app": app, "behavior": beh, "error": str(e)}
        results.append(r)
        logs[f"{app}.{beh}"] = log
        if r.get("l3"):
            print(f"  ★ 三级页命中 {r['l3']} @{r['l3_xy']}（二级入口 {r['l2']}）")
        elif r.get("on_l2"):
            print(f"  ★ 二级页即命中 {r['on_l2']} @{r['l2_xy']}")
        elif r.get("l2"):
            print(f"  二级入口 {r['l2']} 找到，但三级页未命中锚点")
        else:
            print(f"  二级页未找到任务/福利入口（{r.get('error') or ''}）")

    ok3 = sum(1 for r in results if r.get("l3"))
    ok2 = sum(1 for r in results if r.get("on_l2"))
    l2 = sum(1 for r in results if r.get("l2"))
    print(f"\n===== 汇总: 三级页命中 {ok3}/{len(results)}；"
          f"二级页即命中 {ok2}；找到二级入口 {l2} =====")

    md = ["# 三级导航探针报告", "",
          f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
          f"> 设备: {serial}",
          f"> 三级页命中: {ok3}/{len(results)}；二级页即命中: {ok2}；"
          f"找到二级入口: {l2}", "",
          "| App | 行为 | 二级页即命中 | 尝试过的二级入口 | 命中的入口 | 三级锚点 |",
          "|---|---|---|---|---|---|"]
    for r in results:
        tried = r.get("attempts") or []
        tried_s = "<br>".join(
            f"{a.get('l2')} → {a.get('l3') or ('✗ ' + (a.get('error') or '未命中'))}"
            for a in tried) or "-"
        md.append(f"| {r['app']} | {r['behavior']} | {r.get('on_l2') or '-'} | "
                  f"{tried_s} | {r.get('l2') or '-'} | {r.get('l3') or '-'} |")
    md.append("")
    for k, v in logs.items():
        md.append(f"<details><summary>{k}</summary>")
        md.append("")
        md.append("```")
        md += v
        md.append("```")
        md.append("</details>")
        md.append("")
    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    open(args.md, "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(results, open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"报告: {args.md}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
