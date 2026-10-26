# -*- coding: utf-8 -*-
"""plan_anchor_fixes.py - 数据驱动地规划并（可选）应用锚点修补

依据 devtools/calib/<app>/ 下的两份 dump（落地页 ui.xml + 二级页 ui_after.xml）
判断每个行为的入口该怎么修：

  A. 首屏已命中          -> 不动
  B. 首屏未命中、二级页命中 -> 在行为最前面插一步「导航到我的」（click_point + vlm_prompt）
  C. 两页都无文本锚点     -> 需 click_point 坐标 / VLM 专项，本脚本只报告
  D. 只差"语义"（text 找不到但 desc 能找到） -> 给候选追加一条同值 desc 候选

用法：
    python devtools/plan_anchor_fixes.py                 # 只出计划（默认）
    python devtools/plan_anchor_fixes.py --apply          # 写回 config.yaml（自动备份）
    python devtools/plan_anchor_fixes.py --apps 一淘,抖音  # 限定 App
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import app_config_path, load_config  # noqa: E402
from calibrate import parse_nodes, match_selector  # noqa: E402

ANCHOR_TYPES = ("click_text", "click_id", "click_desc", "click_first")

# 二级页导航前置步：先试 VLM 视觉定位，失败则用比例坐标兜底
NAV_ACTION = [
    "    - type: click_point",
    "      vlm_prompt: \"定位屏幕底部导航栏最右侧的『我的』标签中心\"",
    "      x: 0.9",
    "      y: 0.908",
    "      optional: true",
    "    - type: think",
]

# 用于给「纯图片按钮」兜底的通用文案（按行为）
BEHAVIOR_KEYWORDS = {
    "sign": ["签到", "每日签到", "立即签到", "去签到", "打卡", "签到领"],
    "watch": ["看视频", "看广告", "看剧", "去完成", "任务", "赚钱", "福利"],
    "withdraw": ["提现", "可提现", "余额", "现金", "钱包", "我的"],
    "collect": ["任务中心", "福利", "开宝箱", "领取", "做任务"],
    "bonus": ["领红包", "领金币", "领取", "奖励", "红包"],
}


def load_cfg():
    return load_config(os.path.join(ROOT, "config.yaml"))


def first_anchor_action(actions):
    variants = actions if all(isinstance(a, list) for a in actions) else [actions]
    for vi, variant in enumerate(variants):
        for i, act in enumerate(variant or []):
            if isinstance(act, dict) and act.get("type") in ANCHOR_TYPES + ("any_of",):
                return vi, i, act
    return None, None, None


def _cands_of_one(act):
    t = act.get("type")
    if t == "click_first":
        return [c for c in (act.get("candidates") or [])
                if isinstance(c, dict) and c.get("value")]
    if t == "click_text":
        return [{"type": "text", "value": act.get("text", "")}]
    if t == "click_id":
        return [{"type": "id", "value": act.get("res_id", "")}]
    return [{"type": "desc", "value": act.get("desc", "")}]


def candidates_of(act):
    """展开锚点动作的候选；any_of 时汇总所有分支里的候选。"""
    if act.get("type") == "any_of":
        out = []
        for ch in act.get("choices") or []:
            for a in (ch if isinstance(ch, list) else [ch]):
                if isinstance(a, dict) and a.get("type") in ANCHOR_TYPES:
                    out += _cands_of_one(a)
        return out
    return _cands_of_one(act)


def hit_native(nodes, cands):
    """只按候选自身声明的语义匹配（与 executor 的真实行为一致）"""
    for c in cands:
        k, v = c.get("type", "text"), str(c.get("value") or "")
        if v and match_selector(nodes, k, v):
            return k, v
    return None


def hit_cross(nodes, cands):
    """在候选里找命中；先按自身语义，再跨 text/desc 语义。返回 (kind, value) 或 None"""
    for c in cands:
        k, v = c.get("type", "text"), str(c.get("value") or "")
        if not v:
            continue
        if match_selector(nodes, k, v):
            return k, v
        for k2 in ("text", "desc"):
            if k2 != k and match_selector(nodes, k2, v):
                return k2, v
    return None


def scan_keywords(nodes, keywords):
    """在节点里搜关键词，返回 [(label, kind, center)]"""
    out = []
    for kw in keywords:
        for kind in ("text", "desc"):
            for h in match_selector(nodes, kind, kw):
                label = (h["text"] or h["desc"]).strip()
                limit = max(len(kw) + 6, len(kw) * 3)
                if len(label) > limit and not h["clickable"]:
                    continue          # 长文案误命中，跳过
                out.append((label, kind, kw, h["center"]))
    return out


# rid（resource-id）关键词表：很多 App 的入口图标 text/desc 全空，
# 但 resource-id 稳定且带语义（实测河马剧场 item_cash=提现 / item_wallet=福利）。
# 注意：只用「强信号」词，且匹配时要求剥离前缀后**以关键词开头**
# （否则 tl_home_capture_video_btn 会被 "video" 误判成看视频入口）。
RID_KEYWORDS = {
    "sign": ["sign", "checkin", "check_in", "qiandao", "clock", "daily"],
    "watch": ["watch", "video_task", "browse", "read", "task"],
    "withdraw": ["cash", "wallet", "withdraw", "balance", "purse", "asset"],
    "collect": ["task_center", "taskcenter", "mission", "welfare",
                "benefit", "mall"],
    "bonus": ["reward", "redpacket", "red_packet", "box", "bonus",
              "lucky", "prize", "gift"],
}

# rid 常见无意义前缀，剥离后再判断
RID_PREFIXES = ("item_", "btn_", "iv_", "tv_", "ll_", "img_", "icon_",
                "fl_", "rl_", "layout_", "button_")


def scan_rid(nodes, behavior):
    """扫 rid 语义锚点：返回 (rid, center, size) 或 None。

    只在「text/desc 全空但 rid 有语义」的可点击节点里找，
    避免抢掉已有的文本锚点。匹配要求剥离前缀后以关键词开头。
    """
    kws = RID_KEYWORDS.get(behavior, [])
    if not kws:
        return None
    best = None
    for n in nodes:
        if not n["clickable"]:
            continue
        if (n["text"] or n["desc"]).strip():
            continue                      # 有文案的交给文本扫描
        rid = n["rid"]
        if not rid:
            continue
        short = rid.split("/")[-1].lower()
        core = short
        for p in RID_PREFIXES:
            if core.startswith(p):
                core = core[len(p):]
                break
        for kw in kws:
            if core.startswith(kw):
                score = -len(short)       # 越短的 rid 越可能是叶子按钮本身
                if best is None or score > best[0]:
                    best = (score, rid, n["center"], n["size"])
                break
    if best is None:
        return None
    return best[1], best[2], best[3]



def analyze(app, app_dir):
    land = os.path.join(app_dir, "ui.xml")
    aft = os.path.join(app_dir, "ui_after.xml")
    lnodes = parse_nodes(open(land, encoding="utf-8").read()) if os.path.exists(land) else []
    anodes = parse_nodes(open(aft, encoding="utf-8").read()) if os.path.exists(aft) else []
    plan = []
    for bid, actions in (app.get("behaviors") or {}).items():
        if not actions:
            continue
        vi, si, act = first_anchor_action(actions)
        if act is None:
            continue
        cands = candidates_of(act)
        ln = hit_native(lnodes, cands)
        lc = hit_cross(lnodes, cands)
        an = hit_native(anodes, cands)
        ac = hit_cross(anodes, cands)
        if ln:
            plan.append({"behavior": bid, "action": "keep",
                         "why": f"首屏已命中 {ln[0]}={ln[1]}"})
        elif lc:
            plan.append({"behavior": bid, "action": "candidate",
                         "why": f"首屏只在 {lc[0]} 语义命中 {lc[1]!r}"
                                f"（候选声明的是其它语义，执行器会漏）",
                         "suggest": {"type": lc[0], "value": lc[1]}})
        elif an:
            plan.append({"behavior": bid, "action": "prelude",
                         "why": f"首屏无、二级页命中 {an[0]}={an[1]}"})
        elif ac:
            plan.append({"behavior": bid, "action": "prelude",
                         "why": f"首屏无、二级页只在 {ac[0]} 语义命中 {ac[1]!r}",
                         "suggest": {"type": ac[0], "value": ac[1]}})
        else:
            kws = BEHAVIOR_KEYWORDS.get(bid, [])
            alt = scan_keywords(anodes, kws) or scan_keywords(lnodes, kws)
            if alt:
                label, kind, kw, center = alt[0]
                plan.append({"behavior": bid, "action": "candidate",
                             "why": f"两页均未命中；发现可用锚点 "
                                    f"{kind}={label!r} @{center}（关键词 {kw}）",
                             "suggest": {"type": kind, "value": kw}})
            else:
                # 文本/desc 都没有 -> 退到 rid 语义（纯图标按钮）
                rid = scan_rid(anodes, bid)
                page = "二级页"
                if rid is None:
                    rid = scan_rid(lnodes, bid)
                    page = "首屏"
                if rid:
                    rv, center, size = rid
                    plan.append({"behavior": bid, "action": "rid",
                                 "why": f"两页均无文本锚点；发现 rid 锚点 "
                                        f"{rv!r} @{center} sz={size}（{page}）",
                                 "suggest": {"type": "id", "value": rv}})
                else:
                    plan.append({"behavior": bid, "action": "manual",
                                 "why": "两页均无可用文本/rid 锚点，"
                                        "需 click_point 坐标 / VLM 专项"})
    return plan


def apply_prelude(path, app_name, behaviors):
    """在指定 App 的这些行为最前面插入导航前置步。"""
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")
    # 定位 App 块
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
            return 0
    end = len(lines)
    if start != 0:
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("- name: "):
                end = j
                break
    # 从后往前插，避免行号漂移
    ind = 4
    for k in range(start, end):
        s = lines[k].rstrip()
        if s.endswith(":") and s.strip() == "behaviors":
            ind = len(s) - len(s.lstrip()) + 2
            break
    targets = []
    for k in range(start, end):
        s = lines[k]
        if s.startswith(" " * ind) and not s.startswith(" " * (ind + 1)) and s.rstrip().endswith(":"):
            bid = s.strip().rstrip(":")
            if bid in behaviors:
                targets.append(k)
    inserted = 0
    for k in sorted(targets, reverse=True):
        # 幂等守卫：若行为块开头已是导航前置步，则跳过，避免重复插入
        nxt = lines[k + 1:k + 1 + len(NAV_ACTION)]
        if nxt == list(NAV_ACTION):
            continue
        lines[k + 1:k + 1] = list(NAV_ACTION)
        inserted += 1
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    return inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写回 config.yaml")
    ap.add_argument("--apps", default=None, help="逗号分隔，限定 App")
    ap.add_argument("--out", default=os.path.join(HERE, "calib",
                                                  "FIX_PLAN.md"))
    args = ap.parse_args()

    cfg = load_cfg()
    apps = {a.get("name"): a for a in (cfg.get("apps") or [])}
    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None

    md = ["# 锚点修补计划（数据驱动）", "",
          "> 依据 `devtools/calib/<app>/ui.xml`（首屏）与 `ui_after.xml`（二级页）。",
          "> `prelude` = 在行为最前面插一步导航到「我的」；`candidate` = 追加候选；",
          "> `rid` = 纯图标按钮，用 resource-id 锚定；`manual` = 需人工给坐标/VLM。", ""]
    counts = {"keep": 0, "prelude": 0, "candidate": 0, "rid": 0, "manual": 0}
    prelude_by_app = {}

    for name in sorted(apps):
        if only and name not in only:
            continue
        app_dir = os.path.join(HERE, "calib", name)
        if not os.path.isdir(app_dir):
            continue
        plan = analyze(apps[name], app_dir)
        if not plan:
            continue
        md.append(f"## {name}  (`{apps[name].get('package')}`)")
        md.append("")
        md.append("| 行为 | 处置 | 依据 |")
        md.append("|---|---|---|")
        for p in plan:
            counts[p["action"]] += 1
            md.append(f"| {p['behavior']} | {p['action']} | {p['why']} |")
            if p["action"] == "prelude":
                prelude_by_app.setdefault(name, []).append(p["behavior"])
        md.append("")

    md += ["## 统计", "",
           f"- 保持不动: {counts['keep']}",
           f"- 加导航前置步(prelude): {counts['prelude']}",
           f"- 追加候选(candidate): {counts['candidate']}",
           f"- rid 锚点(rid): {counts['rid']}",
           f"- 需人工(manual): {counts['manual']}", ""]

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"计划已写出: {args.out}")
    print(f"keep={counts['keep']} prelude={counts['prelude']} "
          f"candidate={counts['candidate']} rid={counts['rid']} "
          f"manual={counts['manual']}")

    if args.apply and prelude_by_app:
        total = 0
        for name, bids in prelude_by_app.items():
            path = app_config_path(name)
            bak = f"{path}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.copy2(path, bak)
            print(f"已备份: {bak}")
            n = apply_prelude(path, name, set(bids))
            print(f"  {name}: 插入 {n} 处导航前置步")
            total += n
        print(f"共插入 {total} 处")
        # 立刻校验可加载
        cfg2 = load_cfg()
        print(f"复验: config 加载成功, {len(cfg2.get('apps') or [])} 个 app")
    return 0


if __name__ == "__main__":
    sys.exit(main())
