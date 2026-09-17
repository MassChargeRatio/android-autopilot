#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""抖音系「≡ 更多」侧边栏探针。

背景
----
抖音 / 抖音极速版 / 抖音火山版的「我的」页是**纯个人主页**，
金币/任务入口不在页面上，而在右上角 `≡ 更多`（实机 dump 里是
`content-desc="更多"`、中心约 (984, 174)）弹出的**侧边栏**里。
单步前置步覆盖不了，需要「我的 → ≡更多 → 目标」两级菜单。

本工具做的事：
    启动 → 等就绪 → 点「我的」→ 点「更多」→ dump 侧边栏
      → 报告侧边栏里的全部可点条目（文案 / rid / 坐标）
      → 顺便标注命中了哪些行为关键词（金币/任务/福利/签到/提现…）
      → 存截图供目视复核

产物：
    devtools/calib/<app>/sidebar.png
    devtools/calib/SIDEBAR_PROBE.md / .json

用法：
    python devtools/probe_sidebar.py
    python devtools/probe_sidebar.py --apps 抖音极速版
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
    parse_nodes, wait_ready, dismiss_popups, connect_device, safe_name,
    page_belongs_to,
)

DEFAULT_APPS = ["抖音", "抖音极速版", "抖音火山版"]

# 「更多」按钮的定位方式（实机 dump 实测：content-desc="更多" @ (984,174)）
MORE_DESC = "更多"
MORE_XY_FALLBACK = (0.911, 0.074)      # 984/1080, 174/2340

MINE_XY = (0.90, 0.915)

# 侧边栏条目里我们关心的行为关键词
BEHAVIOR_KEYWORDS = {
    "sign": ["签到", "打卡", "每日"],
    "watch": ["看视频", "刷视频", "视频", "任务", "赚钱", "金币"],
    "withdraw": ["提现", "钱包", "现金", "余额", "收益"],
    "bonus": ["红包", "宝箱", "抽奖", "领取", "福利"],
    "collect": ["任务中心", "福利", "领取", "金币"],
}


def find_more(nodes):
    """找「更多」按钮：优先 content-desc 精确/包含，其次比例坐标。"""
    for n in nodes:
        if (n["desc"] or "").strip() == MORE_DESC and n["clickable"]:
            return n["center"], "desc精确"
    for n in nodes:
        if MORE_DESC in (n["desc"] or "") and n["clickable"]:
            return n["center"], "desc包含"
    return None, "未找到"


def probe_one(d, app_cfg, log):
    name, pkg = app_cfg["name"], app_cfg["package"]
    outdir = os.path.join(HERE, "calib", safe_name(name))
    os.makedirs(outdir, exist_ok=True)
    res = {"app": name, "package": pkg, "more_xy": None, "more_via": None,
           "items": [], "hits": {}, "shot": None, "error": None}

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
        ok_page, dom, mine, dom_n = page_belongs_to(xml, pkg)
        log.append(f"归属校验: 主导包={dom}（{dom_n} 节点） 目标包={mine} 节点"
                   f" -> {'属于目标 App' if ok_page else '不属于'}")
        if ok_page:
            break
        log.append("归属校验失败，重试")
        time.sleep(3)
    if not ok_page:
        res["error"] = f"页面非目标App(主导={dom})"
        log.append(f"归属校验最终失败（主导包 {dom}），作废")
        return res

    # 第一层：点「我的」
    w, h = d.window_size()
    mx, my = int(MINE_XY[0] * w), int(MINE_XY[1] * h)
    log.append(f"点『我的』({mx},{my})")
    d.click(mx, my)
    time.sleep(3.5)
    xml2 = d.dump_hierarchy()
    nodes2 = parse_nodes(xml2)
    dismiss_popups(d, nodes2, log)
    ok2, dom2, _, _ = page_belongs_to(xml2, pkg)
    log.append(f"二级页节点={len(nodes2)} 主导包={dom2}")
    if not ok2:
        res["error"] = f"二级页非目标App(主导={dom2})"
        return res

    # 第二层：点「更多」
    xy, via = find_more(nodes2)
    if xy is None:
        xy = (int(MORE_XY_FALLBACK[0] * w), int(MORE_XY_FALLBACK[1] * h))
        log.append(f"未在 dump 里找到『更多』按钮，用比例坐标兜底 {xy}")
    else:
        log.append(f"找到『更多』按钮（{via}）@{xy}")
    res["more_xy"], res["more_via"] = xy, via
    d.click(xy[0], xy[1])
    time.sleep(3.0)
    xml3 = d.dump_hierarchy()
    nodes3 = parse_nodes(xml3)
    ok3, dom3, _, _ = page_belongs_to(xml3, pkg)
    log.append(f"侧边栏节点={len(nodes3)} 主导包={dom3}")
    try:
        p = os.path.join(outdir, "sidebar.png")
        d.screenshot(p)
        res["shot"] = p
    except Exception as e:
        log.append(f"截图失败: {e}")

    # 收集侧边栏里的可点条目
    items = []
    for n in nodes3:
        t = (n["text"] or "").strip()
        dd = (n["desc"] or "").strip()
        label = t or dd
        if not label or len(label) > 20:
            continue
        items.append({"label": label, "text": t, "desc": dd,
                      "rid": n["rid"], "center": n["center"],
                      "clickable": n["clickable"]})
    res["items"] = items
    log.append(f"侧边栏可点/可见条目 {len(items)} 条")

    # 行为关键词命中
    for beh, kws in BEHAVIOR_KEYWORDS.items():
        found = []
        for it in items:
            if any(k in it["label"] for k in kws):
                found.append(f"{it['label']}@{it['center']}")
        if found:
            res["hits"][beh] = found
    for beh, found in res["hits"].items():
        log.append(f"  [{beh}] {found}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--apps", default=None)
    ap.add_argument("--md", default=os.path.join(HERE, "calib", "SIDEBAR_PROBE.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "SIDEBAR_PROBE.json"))
    args = ap.parse_args()

    import yaml
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    apps = {a["name"]: a for a in (cfg.get("apps") or []) if a.get("name")}
    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    targets = [a for a in DEFAULT_APPS if not only or a in only]
    print(f"待探针: {targets}")

    serial = (cfg.get("device") or {}).get("serial")
    d = connect_device(serial)

    results, logs = [], {}
    for name in targets:
        if name not in apps:
            print(f"跳过（配置无此 App）: {name}")
            continue
        print(f"\n===== {name} =====")
        log = []
        try:
            r = probe_one(d, apps[name], log)
        except Exception as e:
            log.append(f"异常: {type(e).__name__}: {e}")
            r = {"app": name, "error": str(e), "items": [], "hits": {}}
        results.append(r)
        logs[name] = log
        if r.get("error"):
            print(f"  ✗ {r['error']}")
        else:
            print(f"  「更多」@ {r.get('more_xy')}（{r.get('more_via')}）"
                  f" 侧边栏条目 {len(r.get('items') or [])}")
            for beh, found in (r.get("hits") or {}).items():
                print(f"    [{beh}] {found}")

    md = ["# 抖音系「≡ 更多」侧边栏探针", "",
          f"> 生成: {time.strftime('%Y-%m-%d %H:%M:%S')}", f"> 设备: {serial}", ""]
    for r in results:
        md += [f"## {r['app']}", "",
               f"- 包名: `{r.get('package')}`",
               f"- 「更多」坐标: {r.get('more_xy')}（{r.get('more_via')}）",
               f"- 截图: `{os.path.basename(r.get('shot') or '')}`",
               f"- 错误: {r.get('error') or '无'}", ""]
        if r.get("hits"):
            md += ["### 行为关键词命中", ""]
            for beh, found in r["hits"].items():
                md.append(f"- **{beh}**: {', '.join(found)}")
            md.append("")
        md += ["### 侧边栏条目", "", "| 文案 | resource-id | 坐标 | 可点 |",
               "|---|---|---|---|"]
        for it in (r.get("items") or [])[:80]:
            md.append(f"| {it['label']} | `{it['rid'][-40:]}` | {it['center']} | "
                      f"{it['clickable']} |")
        md.append("")
        md.append("<details><summary>执行日志</summary>")
        md.append("")
        md.append("```")
        md += logs.get(r["app"], [])
        md.append("```")
        md.append("</details>")
        md.append("")

    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    with open(args.md, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    json.dump(results, open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n报告: {args.md}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
