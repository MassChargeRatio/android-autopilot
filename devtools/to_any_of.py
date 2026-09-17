#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「导航前置步 + 锚点」改造成 `any_of` 条件分支（消除页面波动带来的失败）。

背景
----
App 启动后的落地页不确定（开屏广告/活动弹窗/新手引导/上次退出的 tab/登录态/
灰度活动页）。同一行为的入口可能在首屏、也可能只在二级页：
  * 写死前置步  → 首屏那条路径被堵死（"先跳走再找"）；
  * 只写首屏锚点 → 页面漂移时全灭。

`any_of` 让两条路径共存：

    - type: any_of
      optional: true
      choices:
      - - type: click_first          # 分支1：首屏直接找
          candidates: [...]
          optional: false            # 必须非 optional，否则"没找到"会被当成成功
      - - type: click_point          # 分支2：先跳「我的」再找
          vlm_prompt: "..."
          x: 0.9
          y: 0.915
          optional: true
        - type: think
        - type: click_first
          candidates: [...]
          optional: false

转换规则
--------
1. 行为里已有「导航前置步」+ 锚点 → 自动转成 any_of（分支1=首屏，分支2=原前置步+锚点）。
2. 无前置步但用 `--add-nav app.behavior,...` 指定 → 也转成 any_of，并补一个
   导航分支（用于「锚点只在二级页、但首屏偶尔也有」的行为）。
3. 已有 any_of 的行为不动（幂等）。

用法
----
    python devtools/to_any_of.py                                  # 预览
    python devtools/to_any_of.py --apply                          # 写回（自动备份）
    python devtools/to_any_of.py --add-nav 今日看点极速版.sign --apply
"""
import argparse
import copy
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

CONFIG = os.path.join(ROOT, "config.yaml")
NAV_MARK = "最右侧"
ANCHOR_TYPES = ("click_first", "click_text", "click_id", "click_desc")

# 标准导航前置步（与 plan_anchor_fixes.NAV_ACTION 等价的结构）
# `vision: false`：跳过视觉兜底，直接用比例坐标。理由：这是**每个行为都要跑**
# 的固定步骤，而本机 VLM 图像请求常 90s 超时；比例坐标已被 18 个 App 实机验证。
# 保留 vlm_prompt 仅作语义标注（devtools 靠它识别「导航前置步」）。
NAV_POINT = {
    "type": "click_point",
    "vlm_prompt": "定位屏幕底部导航栏最右侧的『我的』标签中心",
    "x": 0.9,
    "y": 0.915,
    "vision": False,
    "optional": True,
}

# 需要原样保留的注释（PyYAML dump 会丢注释，写回后补上）
COMMENTS = [
    ("    coord_space: norm1000",
     "    # 坐标空间：norm1000 = 模型返回 0-1000 归一化坐标（本网关实测为默认行为，\n"
     "    # 明确要求并换算后误差可到 ~1px）；pixel = 模型直接返回像素坐标。\n"),
    ("    attempts: 3",
     "    # 每个后端重试次数。网关偶发返回内容安全串（\"User Safety: safe\"）而非 JSON，\n"
     "    # 重试可显著提升可用率。\n"),
]


def is_nav_point(act):
    return (isinstance(act, dict) and act.get("type") == "click_point"
            and NAV_MARK in str(act.get("vlm_prompt", "")))


def is_anchor(act):
    return isinstance(act, dict) and act.get("type") in ANCHOR_TYPES


def convert_one(actions, add_nav=False):
    """把单个行为的动作列表转成 any_of。返回 (new_actions, changed, why)。"""
    if not isinstance(actions, list) or not actions:
        return actions, False, ""
    # 变体结构 [[..],[..]] 暂不处理（保持原样）
    if all(isinstance(a, list) for a in actions):
        return actions, False, "变体结构，跳过"
    # 已经是 any_of
    if any(isinstance(a, dict) and a.get("type") == "any_of" for a in actions):
        return actions, False, "已是 any_of，跳过"

    ai = next((i for i, a in enumerate(actions) if is_anchor(a)), None)
    if ai is None:
        return actions, False, "无锚点动作，跳过"

    anchor = copy.deepcopy(actions[ai])
    pre = [copy.deepcopy(a) for a in actions[:ai]]
    has_nav = any(is_nav_point(a) for a in pre)
    if not has_nav and not add_nav:
        return actions, False, "无前置步（未指定 --add-nav），跳过"

    anchor["optional"] = False          # 分支内必须能"报未命中"
    branch1 = [copy.deepcopy(anchor)]
    if has_nav:
        branch2 = pre + [copy.deepcopy(anchor)]
    else:
        branch2 = [copy.deepcopy(NAV_POINT), {"type": "think"},
                   copy.deepcopy(anchor)]

    any_of = {
        "type": "any_of",
        "optional": bool(anchor_optional(actions[ai])),
        "choices": [branch1, branch2],
    }
    new = [any_of] + [copy.deepcopy(a) for a in actions[ai + 1:]]
    why = "首屏直连 + " + ("原前置步" if has_nav else "补导航分支")
    return new, True, why


def anchor_optional(act):
    return act.get("optional", False)


# 二级页上的「任务/福利」入口候选（与 probe_deep.L2_CANDIDATES 保持一致）。
# 用于三级导航分支：点「我的」后再点这里，才能到签到所在的三级页。
DEEP_L2_CANDIDATES = [
    "任务中心", "福利中心", "我的福利", "福利", "赚钱", "金币",
    "领金币", "天天领", "做任务", "任务", "钱包", "现金",
    "元宝中心", "金币中心", "福利商城", "任务广场", "赚金币",
    "看剧赚钱", "看书赚钱", "看视频赚钱", "我的金币", "现金奖励",
]


def convert_deep(actions, l2_label=None, extra_steps=None):
    """三级导航版 any_of：首屏直连 / 我的 / 我的→(中间步骤)→锚点。

    l2_label   : probe_deep 在二级页实测到的入口**文案**（如 '任务中心'）。
                 为 None 表示「我的」页本身就能命中锚点 -> 只加一层导航。
    extra_steps: 显式指定中间步骤（优先于 l2_label）。
                 用于入口不是 text 而是 desc/坐标的场景，例如抖音系
                 「我的 → ≡更多(desc='更多') → 金币」：
                     extra_steps=[{"type": "click_desc", "desc": "更多",
                                   "timeout": 6, "optional": False}]
    """
    if not isinstance(actions, list) or not actions:
        return actions, False, ""
    if all(isinstance(a, list) for a in actions):
        return actions, False, "变体结构，跳过"
    if any(isinstance(a, dict) and a.get("type") == "any_of" for a in actions):
        return actions, False, "已是 any_of，跳过"
    ai = next((i for i, a in enumerate(actions) if is_anchor(a)), None)
    if ai is None:
        return actions, False, "无锚点动作，跳过"

    anchor = copy.deepcopy(actions[ai])
    anchor["optional"] = False
    branch1 = [copy.deepcopy(anchor)]

    mid = []
    if extra_steps:
        mid = [copy.deepcopy(a) for a in extra_steps]
        why = "三级导航(我的→自定义入口)"
    elif l2_label:
        cands = [{"type": "text", "value": l2_label}]
        cands += [{"type": "text", "value": kw}
                  for kw in DEEP_L2_CANDIDATES if kw != l2_label]
        mid = [{"type": "click_first", "candidates": cands,
                "timeout": 8, "optional": False}]
        why = f"三级导航(我的→{l2_label})"
    else:
        why = "二级导航(我的)"

    branch2 = [copy.deepcopy(NAV_POINT), {"type": "think"}]
    for st in mid:
        branch2.append(copy.deepcopy(st))
        branch2.append({"type": "think"})
    branch2.append(copy.deepcopy(anchor))

    any_of = {
        "type": "any_of",
        "optional": bool(anchor_optional(actions[ai])),
        "choices": [branch1, branch2],
    }
    new = [any_of] + [copy.deepcopy(a) for a in actions[ai + 1:]]
    return new, True, why


def restore_comments(text):
    for line, comment in COMMENTS:
        if line in text and comment not in text:
            text = text.replace(line, comment + line, 1)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--add-nav", default=None,
                    help="逗号分隔的 app.behavior，无前置步也补导航分支")
    ap.add_argument("--deep-json", default=None,
                    help="probe_deep.py 产出的 DEEP_PROBE.json（可逗号分隔多个）；"
                         "对其中命中的 app.behavior 加三级导航分支")
    ap.add_argument("--apps", default=None, help="逗号分隔，限定 App")
    args = ap.parse_args()

    import yaml
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # 探针结果 -> {(app, behavior): 二级入口文案 or None(我的页即命中)}
    # 支持多个探针文件（分轮跑的合并）
    deep_map = {}
    if args.deep_json:
        import json
        for path in [p.strip() for p in args.deep_json.split(",") if p.strip()]:
            if not os.path.exists(path):
                print(f"⚠ 探针文件不存在，跳过: {path}")
                continue
            with open(path, encoding="utf-8") as f:
                rows = json.load(f)
            for r in rows:
                if r.get("error"):
                    continue
                if r.get("l3"):
                    lab = (r.get("l2") or "")
                    lab = lab.split("=", 1)[1] if "=" in lab else None
                    deep_map[(r["app"], r["behavior"])] = lab or None
                elif r.get("on_l2"):
                    deep_map[(r["app"], r["behavior"])] = None
        print(f"探针结果可用: {len(deep_map)} 项 -> "
              f"{sorted(f'{a}.{b}' for a, b in deep_map)}")

    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    force = set(x.strip() for x in args.add_nav.split(",")) if args.add_nav else set()

    changed = []
    for app in cfg.get("apps") or []:
        name = app.get("name")
        if only and name not in only:
            continue
        for bid, actions in (app.get("behaviors") or {}).items():
            if not actions:
                continue
            key = f"{name}.{bid}"
            if (name, bid) in deep_map:
                new, ch, why = convert_deep(actions, deep_map[(name, bid)])
            else:
                new, ch, why = convert_one(actions, add_nav=(key in force))
            if ch:
                app["behaviors"][bid] = new
                changed.append((key, why))

    if not changed:
        print("没有需要转换的行为")
        return 0
    print(f"计划转换 {len(changed)} 个行为为 any_of：")
    for key, why in changed:
        print(f"  {key}  ({why})")

    if not args.apply:
        print("\n（预览模式，未写盘；加 --apply 生效）")
        return 0

    bak = f"{args.config}.bak-anyof-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(args.config, bak)
    out = yaml.dump(cfg, allow_unicode=True, sort_keys=False,
                    default_flow_style=False, width=200)
    out = restore_comments(out)
    with open(args.config, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print(f"已写回 {args.config}\n备份: {bak}")

    # 复验
    try:
        cfg2 = yaml.safe_load(open(args.config, encoding="utf-8"))
        n = sum(1 for a in cfg2["apps"] for b, acts in (a.get("behaviors") or {}).items()
                if isinstance(acts, list) and any(
                    isinstance(x, dict) and x.get("type") == "any_of" for x in acts))
        print(f"复验: 加载成功, {len(cfg2['apps'])} 个 app, "
              f"{n} 个行为已用 any_of")
    except Exception as ex:
        print(f"复验失败: {ex}，回滚")
        shutil.copy2(bak, args.config)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
