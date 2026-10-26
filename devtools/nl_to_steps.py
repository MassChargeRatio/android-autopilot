# -*- coding: utf-8 -*-
"""nl_to_steps.py - 自然语言 → 动作链 YAML（AUTOP-NL-2026-10-22-A 第1层：模板填槽）

把一句中文自然语言 + App 名，生成可直接插入 config/apps/<app>.yaml 的
behaviors.<bid> 动作链 YAML 片段。**只产出片段，不写配置**（写回由
devtools/yaml_writer.py 负责，Host 已落地并通过 14 例测试）。

设计取舍（与结构约束一一对应，违反即返工）：
  1. 每个 hop 独立成一个 `any_of`：choices[0] = 文案支（click_first + 显式
     candidates_from + 仅 tab 跳 zone: tab_zone），choices[1] = 坐标支
     （click_point + vision: false）。
     原因：any_of 分支内任一步失败即整支 break（behavior_runner._step_any_of
     文档已述），写在同一支里坐标永远执行不到。
  2. 文案支/坐标支必须分属两个 choice；后续步骤**不复制进两个分支**
     （反例：config/apps/10_米读小说.yaml 的嵌套复制会让配置指数膨胀）。
  3. tab 跳显式 candidates_from: nav_tab，hub 跳 task_center，sign 跳 sign。
     原因：candidates_from 缺省时按当前行为自动推断（sign 行为里点 tab 会
     被推断成 sign 词表），不能依赖它。
  4. 坐标兜底默认单点；--h5 时才在坐标支内追加 wait 1.5 + 下移 --h5-offset
     （默认 60px，实测 32/43/60 均有效）。原因：_step_click_point 除视觉
     分支外没有 return，_run_kind 把 None 当成功 —— 多点若拆成两个 choice，
     第二个永远不可达。
  5. 任何 *_xy 缺省 → 该跳只出文案支 + warning「缺坐标兜底，建议真机校准后补」，
     绝不猜坐标。
  6. 文案来源只走 candidates.candidates_for(category, app_cfg)；本模块
     不含任何词表副本（词表门禁：tests 里 assert 无中文词表字面量）。
"""
from __future__ import annotations

import argparse
import os
import re
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import candidates  # noqa: E402
from devtools import yaml_writer  # noqa: E402
import config_loader  # noqa: E402

# ---------- 解析：纯函数（无 IO、无设备、无全局状态） ----------

_SPLIT_RE = r"[，,；;。]|然后|接着|之后|再|并(?=[点滑等返找翻])|\s*->\s*"

# 长词优先：先按长度降序匹配（"点击「带引号的目标」" 不能被 "点" 截胡）
_VERBS = [
    ("向上滑", "swipe"), ("往下滑", "swipe"),
    ("点击", "tap"), ("点开", "tap"), ("打开", "tap"),
    ("上滑", "swipe"), ("下滑", "swipe"),
    ("翻页", "scroll_to"), ("滚动", "scroll_to"),
    ("等待", "wait"), ("停留", "wait"),
    ("返回", "back"), ("后退", "back"),
    ("查找", "find"), ("出现", "find"),
    ("点", "tap"), ("戳", "tap"), ("按", "tap"),
    ("滑", "swipe"), ("翻", "scroll_to"),
    ("等", "wait"),
    ("找", "find"),
]

_POS = {
    "右下角": (0.90, 0.914), "右上角": (0.93, 0.12),
    "底部最右": (0.90, 0.914), "底部右二": (0.70, 0.914),
    "底部左二": (0.30, 0.914), "底部最左": (0.10, 0.914),
    "屏幕中间": (0.50, 0.50), "中间": (0.50, 0.50),
}

_CN_DIGIT = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_CN_UNITS = {"秒": 1.0, "分": 60.0, "分钟": 60.0, "小时": 3600.0}


def _strip_quotes(s: str) -> str:
    """剥掉成对引号：「」""''《》『』。"""
    s = (s or "").strip()
    for left, right in (("「", "」"), ("『", "』"), ("“", "”"),
                        ("\"", "\""), ("'", "'"), ("《", "》")):
        if len(s) >= 2 and s[0] == left and s[-1] == right:
            s = s[1:-1].strip()
            break
    return s


def _cn_number(s: str) -> float | None:
    """中文时长 -> 秒；支持 三秒/五秒/十秒/半分钟；无法识别返回 None。"""
    if not s:
        return None
    s = _strip_quotes(s)
    m = re.search(r"半\s*(分钟|分)", s)
    if m:
        return 30.0
    m = re.search(r"([一二两三四五六七八九十]+)\s*(小时|分钟|分|秒)", s)
    if not m:
        return None
    n = _CN_DIGIT.get(m.group(1))
    if n is None:
        return None
    return float(n) * _CN_UNITS[m.group(2)]


def _extract_seconds(s: str) -> float | None:
    """阿拉伯数字秒 -> 秒（3秒 / 1.5s）。"""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:秒|s|S)", s or "")
    return float(m.group(1)) if m else None


def _parse_xy(v):
    """坐标兜底入参归一：'0.5,0.641' / (0.5, 0.641) / [0.5, 0.641] -> (x, y)。"""
    if v is None:
        raise ValueError("坐标不能为 None")
    if isinstance(v, (tuple, list)) and len(v) == 2:
        return float(v[0]), float(v[1])
    s = str(v).strip().strip("()[]（）")
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 2:
        raise ValueError(f"坐标格式应为 x,y: {v!r}")
    return float(parts[0]), float(parts[1])


def _match_verb(text: str) -> tuple[str | None, str | None]:
    for v, kind in _VERBS:  # 已按长度降序
        if v in text:
            return v, kind
    return None, None


def parse_line(text: str) -> tuple[list[dict], list[str]]:
    """解析一句自然语言 -> (steps, warnings)。

    steps 元素: {"verb","target","pos","seconds","raw"}（缺省 None）；
    无法识别动词 → verb="unknown" + warning，不抛异常。
    """
    raw = (text or "").strip()
    if not raw:
        return [], ["空行无法解析"]
    s = _strip_quotes(raw)
    verb, kind = _match_verb(s)
    if verb is None:
        return [{"verb": "unknown", "target": s, "pos": None,
                 "seconds": None, "raw": raw}], [f"无法识别动词: {raw}"]

    idx = s.find(verb)
    head = s[:idx]
    tail = s[idx + len(verb):]
    step = {"verb": kind, "target": None, "pos": None,
            "seconds": None, "raw": raw}

    # 位置词（右下角/右上角/底部最右/...）
    for pos_word, xy in _POS.items():
        if pos_word in s:
            step["pos"] = xy
            head = head.replace(pos_word, "")
            tail = tail.replace(pos_word, "")
            break

    # 次数（两次/三次/...）
    m = re.search(r"([一二两三四五六七八九十])次", head + tail)
    if m:
        step["count"] = _CN_DIGIT[m.group(1)]
        head = head.replace(m.group(0), "")
        tail = tail.replace(m.group(0), "")

    # 连词噪声（split 未消掉的引导词）
    for w in ("最后", "首先", "先", "然后", "接着", "之后"):
        head = head.replace(w, "")
        tail = tail.replace(w, "")

    if kind == "wait":
        secs = _cn_number(s) or _extract_seconds(tail or head or s)
        step["seconds"] = secs if secs is not None else 1.0

    t = _strip_quotes((tail or head).strip()).strip()
    if kind in ("back", "swipe", "wait"):
        step["target"] = None
    else:
        step["target"] = t or None
    return [step], []


def parse_script(text: str) -> tuple[list[dict], list[str]]:
    """多行/多句：按 _SPLIT_RE 切分后逐句 parse_line。"""
    parts = [p.strip() for p in re.split(_SPLIT_RE, text or "") if p.strip()]
    steps: list[dict] = []
    warnings: list[str] = []
    for p in parts:
        ss, ww = parse_line(p)
        steps.extend(ss)
        warnings.extend(ww)
    return steps, warnings


# ---------- 模板（结构化，非字符串拼接） ----------

TEMPLATES = {
    "personal_center": {"hops": ["tab", "hub", "sign"]},
    "feed_ball": {"hops": ["tab", "ball", "sign"]},
    "home_direct": {"hops": ["anchor", "sign"]},
}

# kind -> (text 槽位, xy 槽位)
_HOP_KEYS = {
    "tab": ("tab_text", "tab_xy"),
    "hub": ("hub_text", "hub_xy"),
    "sign": (None, "sign_xy"),
    "ball": (None, "ball_xy"),
    "anchor": ("anchor_text", "anchor_xy"),
}

# kind -> 显式 candidates_from 类别（缺省时按当前行为自动推断，不能依赖）
_HOP_CATEGORY = {
    "tab": "nav_tab",
    "hub": "task_center",
    "sign": "sign",
    "anchor": "sign",
    "ball": "nav_tab",
}


def template_names() -> list[str]:
    return list(TEMPLATES.keys())


def guess_entry(text: str) -> str:
    """含「我的/个人中心」→personal_center；含「浮球/金币/右上」→feed_ball；
    否则 home_direct。"""
    s = text or ""
    if "个人中心" in s or "我的" in s:
        return "personal_center"
    if "浮球" in s or "金币" in s or "右上" in s:
        return "feed_ball"
    return "home_direct"


def render_hop(kind: str, params: dict, category: str,
               app_cfg: dict | None = None) -> list[dict]:
    """渲染单个 hop（any_of：文案支 + 可选坐标支）。"""
    params = params or {}
    if kind not in _HOP_KEYS:
        raise ValueError(f"未知 hop 类型: {kind!r}（可选 {list(_HOP_KEYS)}）")
    text_key, xy_key = _HOP_KEYS[kind]
    eff_cat = _HOP_CATEGORY.get(kind, category)

    choices: list[list[dict]] = []

    # 文案支
    text_branch: list[dict] = [{
        "type": "click_first",
        "candidates_from": eff_cat,
        "timeout": 8,
        "optional": False,
    }]
    text_val = params.get(text_key) if text_key else None
    if text_val:
        text_branch[0]["candidates"] = [{"type": "text", "value": text_val}]
    if kind == "tab":
        text_branch[0]["zone"] = "tab_zone"
    choices.append(text_branch)

    # 坐标支（缺 xy 不出坐标支，绝不猜坐标）
    xy_val = params.get(xy_key)
    if xy_val:
        x, y = _parse_xy(xy_val)
        point = {
            "type": "click_point", "x": x, "y": y,
            "timeout": 8, "optional": False, "vision": False,
            "desc": f"{kind}坐标兜底（待真机校准）",
        }
        if params.get("h5"):
            offset = float(params.get("h5_offset") or 60)
            y2 = round(y + offset / 2340.0, 6)
            choices.append([
                point,
                {"type": "wait", "seconds": 1.5},
                {"type": "click_point", "x": x, "y": y2,
                 "timeout": 8, "optional": False, "vision": False,
                 "desc": f"{kind}坐标兜底（h5 下移 {offset}px）"},
            ])
        else:
            choices.append([point])

    return [{"type": "any_of", "optional": True, "choices": choices}]


def render_chain(entry: str, params: dict, category: str,
                 app_cfg: dict | None = None) -> tuple[list[dict], list[str]]:
    """按模板 hops 渲染整条动作链 -> (actions, warnings)。"""
    if entry not in TEMPLATES:
        raise ValueError(f"未知模板: {entry!r}（可选 {template_names()}）")
    params = params or {}
    actions: list[dict] = []
    warnings: list[str] = []
    for kind in TEMPLATES[entry]["hops"]:
        xy_key = _HOP_KEYS[kind][1]
        if not params.get(xy_key):
            warnings.append(f"{kind} 跳缺坐标兜底，建议真机校准后补")
        if kind == "sign" and params.get("scroll_text"):
            actions.append({
                "type": "scroll_to",
                "text": str(params["scroll_text"]),
                "max_pages": 6,
            })
        actions.extend(render_hop(kind, params, category, app_cfg))
    if params.get("confirm_text"):
        actions.append({
            "type": "click_first",
            "candidates": [{"type": "text", "value": str(params["confirm_text"])}],
            "candidates_from": _HOP_CATEGORY.get("sign", category),
            "timeout": 6,
            "optional": True,
        })
    return actions, warnings


def render_steps(steps: list[dict], params: dict, category: str,
                 app_cfg: dict | None = None) -> tuple[list[dict], list[str]]:
    """把 parse_line/parse_script 的自由步骤渲染成动作链（模板之外的兜底入口）。"""
    params = params or {}
    actions: list[dict] = []
    warnings: list[str] = []
    for st in steps:
        kind = st.get("verb")
        raw = st.get("raw") or ""
        if kind == "unknown":
            warnings.append(f"无法识别的步骤: {raw}")
            continue
        if kind == "wait":
            actions.append({"type": "wait", "seconds": float(st.get("seconds") or 1.0)})
        elif kind == "tap":
            if st.get("pos"):
                x, y = st["pos"]
                actions.append({
                    "type": "click_point", "x": x, "y": y,
                    "timeout": 8, "optional": True, "vision": False,
                    "desc": f"点击坐标兜底（待真机校准）",
                })
            elif st.get("target"):
                actions.append({
                    "type": "click_first",
                    "candidates": [{"type": "text", "value": st["target"]}],
                    "candidates_from": category,
                    "timeout": 8, "optional": True,
                })
            else:
                warnings.append(f"缺少点击目标: {raw}")
        elif kind == "swipe":
            up = "上" in raw and "下" not in raw
            cnt = int(st.get("count") or 1)
            for _ in range(cnt):
                if up:
                    actions.append({"type": "swipe", "from": [0.5, 0.7],
                                    "to": [0.5, 0.3], "duration": 0.8, "natural": True})
                else:
                    actions.append({"type": "swipe", "from": [0.5, 0.3],
                                    "to": [0.5, 0.7], "duration": 0.8, "natural": True})
        elif kind in ("scroll_to", "find"):
            actions.append({"type": "scroll_to",
                            "text": str(st.get("target") or ""), "max_pages": 6})
        elif kind == "back":
            actions.append({"type": "back"})
        else:
            warnings.append(f"暂不支持的步骤类型: {kind}")
    return actions, warnings


# ---------- 组装 / 输出 ----------

def build_behavior(text: str, app_name: str, bid: str, *,
                   entry: str = "auto", params: dict | None = None,
                   app_cfg: dict | None = None) -> dict:
    """-> {"behavior","entry","actions","warnings","candidates_used"}。"""
    params = dict(params or {})
    warnings: list[str] = []
    if entry == "auto":
        entry = guess_entry(text)
    if entry not in TEMPLATES:
        warnings.append(f"未知模板: {entry!r}，已回退 home_direct")
        entry = "home_direct"
    category = candidates.category_for_intent(bid) or "sign"
    actions, hop_warnings = render_chain(entry, params, category, app_cfg)
    warnings.extend(hop_warnings)
    used: dict[str, list[str]] = {}
    for kind in TEMPLATES[entry]["hops"]:
        cat = _HOP_CATEGORY.get(kind, category)
        used.setdefault(cat, list(candidates.candidates_for(cat, app_cfg)))
    return {"behavior": bid, "entry": entry, "actions": actions,
            "warnings": warnings, "candidates_used": used}


def to_yaml_fragment(actions: list[dict], indent: int = 2) -> str:
    """动作链 -> YAML 文本（转调 yaml_writer.render_actions，PyYAML 风格）。"""
    return "\n".join(yaml_writer.render_actions(actions, indent))


# ---------- CLI ----------

def _load_app_cfg(app_name: str) -> dict | None:
    try:
        snap = yaml_writer.snapshot()
    except Exception:  # noqa: BLE001 - CLI 容错，配置加载失败按无 App 微调处理
        return None
    return snap.get(app_name) if snap else None


def _print_templates() -> None:
    print("可用模板（3 种入口）与槽位：")
    for name in template_names():
        hops = " -> ".join(TEMPLATES[name]["hops"])
        print(f"  {name}: {hops}")
    print("公共槽位: tab_text/tab_xy/hub_text/hub_xy/ball_xy/anchor_text/"
          "anchor_xy/sign_xy/scroll_text/confirm_text/h5/h5_offset")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="自然语言 → 动作链 YAML 片段（只产出片段，--apply 才写盘）")
    parser.add_argument("--app", help="App 名（config/apps/<app>.yaml）")
    parser.add_argument("--behavior", default="sign", help="行为 ID（默认 sign）")
    parser.add_argument("--text", help="中文自然语言描述")
    parser.add_argument("--entry", default="auto",
                        choices=["auto"] + template_names(),
                        help="入口模板（默认 auto 自动猜测）")
    parser.add_argument("--h5", action="store_true",
                        help="H5 页：坐标支内追加 wait 1.5 + 下移 --h5-offset")
    parser.add_argument("--h5-offset", type=float, default=60.0,
                        help="H5 下移像素（默认 60，屏幕高按 2340 归一）")
    parser.add_argument("--xy", help="签到步坐标兜底，如 0.5,0.641")
    parser.add_argument("--tab-text", help="tab 跳文案（如 我的/福利）")
    parser.add_argument("--tab-xy", help="tab 跳坐标兜底，如 0.9,0.914")
    parser.add_argument("--hub-text", help="hub 跳文案（如 福利中心）")
    parser.add_argument("--hub-xy", help="hub 跳坐标兜底")
    parser.add_argument("--anchor-text", help="anchor 跳文案（首页直落型）")
    parser.add_argument("--anchor-xy", help="anchor 跳坐标兜底")
    parser.add_argument("--ball-xy", help="ball 跳坐标兜底（内容流浮球型）")
    parser.add_argument("--print-yaml", action="store_true", help="打印 YAML 片段")
    parser.add_argument("--apply", action="store_true",
                        help="写盘（insert_behavior apply=True）")
    parser.add_argument("--force", action="store_true",
                        help="行为已存在时走 replace_behavior(force=True)")
    parser.add_argument("--allow-money", action="store_true",
                        help="允许为资金类行为生成配置（默认拒绝）")
    parser.add_argument("--templates", action="store_true",
                        help="列出 3 模板与槽位后退出")
    args = parser.parse_args(argv)

    if args.templates:
        _print_templates()
        return 0
    if not args.app or not args.text:
        parser.error("--app 与 --text 必填（或使用 --templates）")

    # 资金类行为拒绝（config_loader.money_behaviors，缺省 {"withdraw"}）
    try:
        cfg = config_loader.load_config(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml"))
    except Exception:  # noqa: BLE001
        cfg = {}
    money = config_loader.money_behaviors(cfg)
    if args.behavior in money and not args.allow_money:
        print(f"拒绝为资金类行为生成配置: {args.behavior}（money_behaviors="
              f"{sorted(money)}；如确需生成请加 --allow-money）", file=sys.stderr)
        return 1

    app_cfg = _load_app_cfg(args.app)
    params: dict = {}
    if args.h5:
        params["h5"] = True
        params["h5_offset"] = args.h5_offset
    if args.xy:
        params["sign_xy"] = args.xy
    # 真机校准后的多跳坐标兜底（AUTOP-NL 真机实跑补：只有 --xy 时 tab/hub 无坐标支）
    for flag, key in (("--tab-text", "tab_text"), ("--tab-xy", "tab_xy"),
                      ("--hub-text", "hub_text"), ("--hub-xy", "hub_xy"),
                      ("--anchor-text", "anchor_text"), ("--anchor-xy", "anchor_xy"),
                      ("--ball-xy", "ball_xy")):
        val = getattr(args, flag.lstrip("-").replace("-", "_"))
        if val:
            params[key] = val

    result = build_behavior(args.text, args.app, args.behavior,
                            entry=args.entry, params=params, app_cfg=app_cfg)
    for w in result["warnings"]:
        print(f"WARN: {w}", file=sys.stderr)
    fragment = to_yaml_fragment(result["actions"])
    if args.print_yaml or not args.apply:
        print(f"# {args.app} / {args.behavior} / entry={result['entry']}")
        print(fragment)
    if not args.apply:
        return 0

    path = yaml_writer.app_path(args.app)
    if not args.force:
        wr = yaml_writer.insert_behavior(path, args.behavior,
                                         result["actions"], apply=True)
    else:
        wr = yaml_writer.replace_behavior(path, args.behavior,
                                          result["actions"], apply=True,
                                          force=True)
    print(f"write action={wr.action} path={wr.path}")
    for w in wr.warnings:
        print(f"WRITE-WARN: {w}", file=sys.stderr)
    if wr.action == "skipped" and not args.force:
        print("提示：该行为已存在；如需覆盖请加 --force", file=sys.stderr)
    return 0 if wr.changed else (0 if wr.action == "skipped" else 1)


if __name__ == "__main__":
    sys.exit(main())
