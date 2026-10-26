# -*- coding: utf-8 -*-
"""run_sign_regression.py - 12 份新 sign 配置真机回归驱动（Host 自执行版）

背景：verify_live/stability_run 只校验「有 calib dump 的 App」的入口命中率，
新配置的 12 个 App 无 dump 会被过滤。本驱动直接走 main.py 真实链路跑 sign，
逐 App 落盘日志 + 三级判读（A签=终态确认 / B走=有效交互未确认 / C断=断点崩溃），
并区分文案命中与坐标兜底（收敛后配置首次真机回归专用）。
安全约束：只跑 sign（不跑 withdraw/看视频后的提现）；发现资金类文案立即标记人工复核。
"""
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv", "Scripts", "python.exe")
LOGDIR = os.path.join(ROOT, "devtools", "calib", "sign_regression")

APPS = ["趣头条", "拼多多", "京东", "美团", "快手", "百度地图",
        "海马畅听", "UC浏览器极速版", "飞猪旅行", "米读小说",
        "米读极速版", "大众点评"]

# 资金类红线文案：日志里出现即视为该 App 触及资金面，标记人工复核
MONEY_RE = re.compile(r"提现|确认支付|立即支付|银行卡|实名|验证码|付款")

# 终态确认（2026-10-21 15:27 增补，补判读缺口）：
# 签到成功的 App 一般会把按钮/提示切成这些文案；日志出现即记 verified。
SIGNED_RE = re.compile(r"已签|签到成功|签过|明日签到|明天再签|已领取|领取成功|签到完成")

SUMMARY = []


def run_one(app, force=True, fast=True):
    os.makedirs(LOGDIR, exist_ok=True)
    logf = os.path.join(LOGDIR, f"{app}.log")
    t0 = time.time()
    cmd = [PY, os.path.join(ROOT, "main.py"), "--app", app, "--task", "签到"]
    if force:
        # 作息窗口 07:30-23:00 是给人看的；回归验证要全时段可跑，
        # 2026-10-20 首轮 6 个 App 1-2 秒退出就是被 wake_window 拦的。
        cmd.append("--force")
    if fast:
        # 启动随机等待 60-350s 纯睡眠，回归不需要；其余真人模拟保留
        cmd.append("--fast")
    with open(logf, "w", encoding="utf-8") as f:
        p = subprocess.run(
            cmd,
            cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=420)
    dur = time.time() - t0
    txt = open(logf, encoding="utf-8").read()
    money_hit = MONEY_RE.search(txt)
    # 判读（2026-10-21 二轮口径）：
    #  - 有效交互 = 文案命中（点击文本/控件/描述/多候选/滚动）或坐标兜底命中
    #  - optional 前置（弹窗清扫 any_of）miss 会打「optional 放行」，不算失败
    #  - Traceback = 引擎级失败（首轮的 window_size 崩溃族即此）
    has_sign = "意图[sign]" in txt or "目标 app:" in txt
    done = "任务执行完毕" in txt or "执行完毕" in txt
    crash = "Traceback" in txt
    text_hits = re.findall(
        r"点击文本: |点击控件: |点击描述: |多候选命中并点击: |滚动找到并点击: ", txt)
    coord_hits = re.findall(r"点击坐标: \((\d+),(\d+)\)", txt)
    effective = len(text_hits) + len(coord_hits)
    # 仅保留非 optional 的失败步（optional 放行不算）
    fails = [ln for ln in re.findall(r"步骤失败: ([^\n]+)", txt)
             if "所有候选均未出现" not in ln]
    optional_miss = txt.count("optional 放行")
    signed = bool(SIGNED_RE.search(txt))
    hit = bool(has_sign and done and effective > 0 and not crash)
    # 三级判读：verified=有已签终态文案；effective=走到有效交互未确认终态；
    # blocked=断点/崩溃/零交互
    grade = "verified" if (hit and signed) else (
        "effective" if hit else "blocked")
    return {
        "app": app, "rc": p.returncode, "dur": round(dur), "hit": hit,
        "sign": has_sign, "done": done, "crash": crash, "signed": signed,
        "grade": grade,
        "text_hits": len(text_hits), "coord_hits": len(coord_hits),
        "effective": effective, "optional_miss": optional_miss,
        "fails": fails,
        "money": money_hit.group(0) if money_hit else "",
        "coord_clicks": len(coord_hits), "log": logf,
    }


def main():
    # 用法：python run_sign_regression.py [App1 App2 ...]
    # 无参 = 全量 12 App；带参 = 只跑指定 App（二轮补跑 5 个 MISS 用）。
    targets = sys.argv[1:] or APPS
    os.makedirs(LOGDIR, exist_ok=True)
    for i, app in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {app} ...", flush=True)
        try:
            r = run_one(app)
        except subprocess.TimeoutExpired:
            r = {"app": app, "rc": -1, "dur": 420, "hit": False, "sign": True,
                 "done": False, "crash": False, "signed": False, "grade": "blocked",
                 "text_hits": 0, "coord_hits": 0,
                 "effective": 0, "optional_miss": 0, "fails": ["TIMEOUT"],
                 "money": "", "coord_clicks": 0, "log": "?"}
        SUMMARY.append(r)
        flag = {"verified": "A签", "effective": "B走", "blocked": "C断"}[r["grade"]]
        print(f"  -> {flag} rc={r['rc']} {r['dur']}s "
              f"text={r['text_hits']} coord={r['coord_hits']} "
              f"opt_miss={r['optional_miss']} fails={len(r['fails'])} "
              f"signed={r['signed']} money={r['money'] or '-'}", flush=True)
        if r["money"]:
            print(f"  !! 资金类文案出现: {r['money']} —— 已记录，需人工复核", flush=True)
    # 写汇总
    lines = [f"# sign 真机回归汇总（Host 自执行 · --force --fast · 目标 {len(SUMMARY)} App）", "",
             f"时间：{time.strftime('%Y-%m-%d %H:%M')}  设备：192.168.1.54:5555", "",
             "引擎版本锚点：`engine_snapshot_20261021_1527/`（marvis REFINE R1 完成后 / R2 前；"
             "若回归途中引擎再被修改，按 App 时间段在表格备注）", "",
             "判读口径：有效交互=文案命中或坐标兜底命中；optional 前置 miss 不计失败；",
             "Traceback=引擎级失败；终态确认=日志出现「已签/签到成功/明日签到」类文案。", "",
             "三级判读：**A签**=verified（终态确认）｜**B走**=effective（有交互未确认终态）｜**C断**=blocked", "",
             "| App | 判定 | 耗时s | 文案命中 | 坐标命中 | 终态确认 | optional miss | 非可选失败 | 资金标记 | 日志 |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in SUMMARY:
        lines.append(
            f"| {r['app']} | {r['grade']} | {r['dur']} | "
            f"{r['text_hits']} | {r['coord_hits']} | "
            f"{'✅' if r['signed'] else '-'} | {r['optional_miss']} | "
            f"{len(r['fails'])} | {r['money'] or '-'} | {os.path.basename(r['log'])} |")
    lines.append("")
    lines.append("## 失败步明细（非 optional）")
    any_fail = False
    for r in SUMMARY:
        if r["fails"]:
            any_fail = True
            lines.append(f"- **{r['app']}**: " + " / ".join(str(x)[:80] for x in r["fails"][:6]))
    if not any_fail:
        lines.append("（无）")
    lines.append("")
    lines.append("## 坐标兜底命中明细（待校准：文案 miss 说明真实文案与描述有出入）")
    for r in SUMMARY:
        if r["coord_hits"]:
            lines.append(f"- **{r['app']}**: 坐标命中 {r['coord_hits']} 次，"
                         f"详见 {os.path.basename(r['log'])}")
    out = os.path.join(LOGDIR, "SUMMARY.md")
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    hits = sum(1 for r in SUMMARY if r["hit"])
    print(f"\nDONE {hits}/{len(SUMMARY)} 命中 -> {out}", flush=True)


if __name__ == "__main__":
    main()
