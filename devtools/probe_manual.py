#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""manual 项实机探针：为「两页都没有文本锚点」的行为找到可点的视觉入口。

背景：`devtools/plan_anchor_fixes.py` 把 15 个行为判为 manual —— 落地页与
二级页的 dump 里都没有可用文本锚点。这类入口要么是**纯图片按钮**，要么
文案由图片/Canvas 绘制（dump 拿不到）。对此唯一可靠的办法是：

    启动 App -> 等待就绪 -> 导航到『我的』-> 截图
      -> 用 VLM 按「行为专属提示词」定位入口
      -> 命中则记录 (像素, 比例坐标, 生效提示词)，并把截图存盘供人工复核

产物：
    devtools/calib/<app>/manual_<behavior>.png   截图（可直接肉眼看）
    devtools/calib/MANUAL_PROBE.md               探针报告
    devtools/calib/MANUAL_PROBE.json             结构化结果（供写回脚本消费）

用法：
    python devtools/probe_manual.py --apps 抖音,点淘
    python devtools/probe_manual.py                 # 全部 15 个 manual 项
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

from config_loader import load_config  # noqa: E402
from calibrate import (  # noqa: E402
    parse_nodes, wait_ready, dismiss_popups, connect_device, safe_name,
)

# (app, behavior) —— 与 FIX_PLAN.md 的 manual 项一致
MANUAL = [
    ("今日看点极速版", "withdraw"),
    ("全民K歌",        "bonus"),
    ("喜番免费短剧",   "sign"),
    ("天天快讯极速版", "sign"),
    ("天天快讯极速版", "watch"),
    ("天天快讯极速版", "withdraw"),
    ("悟空浏览器",     "sign"),
    ("抖音",           "watch"),
    ("抖音",           "bonus"),
    ("抖音极速版",     "watch"),
    ("抖音火山版",     "sign"),
    ("河马剧场",       "sign"),
    ("点淘",           "watch"),
    ("点淘",           "withdraw"),
    ("蛋花免费小说",   "sign"),
]

# 行为专属提示词（按顺序回退，命中即止）
PROMPTS = {
    "sign": [
        "定位页面上『签到』按钮或签到入口的中心",
        "定位『每日签到』或『立即签到』按钮中心",
        "定位『签到领金币』或『已签到』卡片中心",
        "定位页面上『领取』按钮的中心",
    ],
    "watch": [
        "定位『看视频赚金币』任务入口中心",
        "定位『看剧赚钱』或『看视频』按钮中心",
        "定位『任务中心』入口中心",
        "定位『去完成』按钮中心",
    ],
    "bonus": [
        "定位『领红包』或『开宝箱』按钮中心",
        "定位『领取奖励』或『点击领取』按钮中心",
        "定位页面上金币/红包奖励图标的中心",
    ],
    "withdraw": [
        "定位『提现』按钮中心",
        "定位『现金』或『钱包』入口中心",
        "定位『余额』或『可提现』区域的中心",
    ],
    "collect": [
        "定位『任务中心』入口中心",
        "定位『福利』或『领福利』入口中心",
        "定位『去领取』按钮中心",
    ],
}

NAV_PROMPTS = [
    "定位屏幕底部导航栏最右侧的『我的』标签中心",
    "定位屏幕底部导航栏最右侧的『我』标签中心",
    "定位屏幕底部导航栏的个人中心（我的）标签中心",
]
MINE_XY = (0.9, 0.908)


def load_cfg(path):
    return load_config(path)


def goto_mine(d, loc, log):
    """导航到『我的』。返回 (nodes, 是否成功跳到新页)。"""
    x = y = None
    if loc is not None:
        try:
            img = d.screenshot()
            for p in NAV_PROMPTS:
                hit = loc.locate_on_screen(prompt=p, screen_img=img,
                                           app="probe", tag="nav")
                if hit is not None:
                    x, y = hit.x, hit.y
                    log.append(f"导航: VLM 命中『{p}』-> ({x},{y})")
                    break
        except Exception as e:
            log.append(f"导航: VLM 异常 {type(e).__name__}: {e}")
    if x is None:
        w, h = d.window_size()
        x, y = int(MINE_XY[0] * w), int(MINE_XY[1] * h)
        log.append(f"导航: 比例坐标 -> ({x},{y})")
    d.click(x, y)
    time.sleep(3.5)
    return parse_nodes(d.dump_hierarchy())


def probe_one(d, app_cfg, behavior, loc, log):
    name = app_cfg["name"]
    pkg = app_cfg["package"]
    log.append(f"启动 {pkg}")
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
        if fg == pkg or pkg in fg:
            break
        log.append(f"前台={fg} 非目标包，重试一次")
        time.sleep(2)

    nodes = goto_mine(d, loc, log)
    dismiss_popups(d, nodes, log)
    outdir = os.path.join(HERE, "calib", safe_name(name))
    os.makedirs(outdir, exist_ok=True)
    shot = os.path.join(outdir, f"manual_{behavior}.png")
    try:
        d.screenshot(shot)
        log.append(f"截图: {shot}")
    except Exception as e:
        log.append(f"截图失败: {e}")

    res = {"app": name, "behavior": behavior, "hit": False,
           "prompt": None, "xy": None, "ratio": None,
           "shot": shot, "nodes_after": len(nodes)}
    if loc is None:
        log.append("VLM 不可用，仅存截图")
        return res
    for p in PROMPTS.get(behavior, []):
        try:
            img = d.screenshot()
            hit = loc.locate_on_screen(prompt=p, screen_img=img,
                                       app="probe", tag=behavior)
        except Exception as e:
            log.append(f"VLM 异常 {type(e).__name__}: {e}")
            continue
        if hit is not None:
            w, h = d.window_size()
            res.update(hit=True, prompt=p, xy=[hit.x, hit.y],
                       ratio=[round(hit.x / w, 3), round(hit.y / h, 3)])
            log.append(f"VLM 命中『{p}』-> ({hit.x},{hit.y}) "
                       f"ratio=({res['ratio'][0]},{res['ratio'][1]})")
            break
        log.append(f"未命中 -> {p}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--apps", default=None, help="逗号分隔，限定 App")
    ap.add_argument("--behaviors", default=None, help="逗号分隔，限定行为")
    ap.add_argument("--md", default=os.path.join(HERE, "calib", "MANUAL_PROBE.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "MANUAL_PROBE.json"))
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    apps = {a["name"]: a for a in (cfg.get("apps") or []) if a.get("name")}
    only_a = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    only_b = set(x.strip() for x in args.behaviors.split(",")) if args.behaviors else None

    targets = [(a, b) for a, b in MANUAL
               if (not only_a or a in only_a) and (not only_b or b in only_b)]
    print(f"待探针: {len(targets)} 项")

    serial = (cfg.get("device") or {}).get("serial")
    d = connect_device(serial)

    loc = None
    try:
        import vision as vs
        cand = vs.VisionLocator(cfg.get("vision") or {}, base_dir=ROOT)
        if cand.enabled and cand.vlm_available:
            loc = cand
            print("VLM: 可用")
        else:
            print("VLM: 不可用（仅存截图）")
    except Exception as e:
        print(f"VLM 初始化失败: {e}")

    results, logs = [], {}
    for app, beh in targets:
        if app not in apps:
            print(f"跳过（配置无此 App）: {app}")
            continue
        print(f"\n===== {app} / {beh} =====")
        log = []
        try:
            r = probe_one(d, apps[app], beh, loc, log)
        except Exception as e:
            log.append(f"探针异常: {type(e).__name__}: {e}")
            r = {"app": app, "behavior": beh, "hit": False,
                 "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        logs[f"{app}.{beh}"] = log
        print(f"  -> {'命中 ' + str(r.get('ratio')) if r.get('hit') else '未命中'}")

    hit = sum(1 for r in results if r.get("hit"))
    print(f"\n===== 探针汇总: 命中 {hit}/{len(results)} =====")

    os.makedirs(os.path.dirname(os.path.abspath(args.md)), exist_ok=True)
    md = ["# manual 项实机探针报告", "",
          f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
          f"> 设备: {serial}",
          f"> 命中: {hit}/{len(results)}", "",
          "| App | 行为 | 结果 | 比例坐标 | 生效提示词 | 截图 |",
          "|---|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {r['app']} | {r['behavior']} | "
                  f"{'命中' if r.get('hit') else '未命中'} | "
                  f"{r.get('ratio') or '-'} | {r.get('prompt') or '-'} | "
                  f"`{os.path.basename(r.get('shot') or '')}` |")
    md.append("")
    for k, v in logs.items():
        md.append(f"<details><summary>{k}</summary>")
        md.append("")
        md.append("```")
        md += v
        md.append("```")
        md.append("</details>")
        md.append("")
    open(args.md, "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump(results, open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"报告: {args.md}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
