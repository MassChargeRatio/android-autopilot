# -*- coding: utf-8 -*-
"""propose_anchors.py - 基于校准 dump 生成锚点修补建议（只读，不改配置）

对每个已校准的 App：
  - 读 devtools/calib/<app>/ui.xml
  - 对该 App 每个行为的**入口动作**，把候选锚点分别在 text / desc / id 三种语义下搜索，
    做"跨语义交叉匹配"（很多 App 把按钮做成图片，文案在 content-desc 里，
    只按 text 匹配必然未命中 —— 这是新 18 App 大量"未命中"的主因之一）
  - 输出：现状 / 建议候选（含实际命中文案与坐标）/ 或"无文本锚点，需坐标或 VLM"

用法：
    python devtools/propose_anchors.py
    python devtools/propose_anchors.py --out devtools/calib/ANCHOR_PROPOSAL.md
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config_loader import load_config  # noqa: E402
from calibrate import parse_nodes, match_selector  # noqa: E402

ANCHOR_TYPES = ("click_text", "click_id", "click_desc", "click_first")


def load_cfg():
    return load_config(os.path.join(ROOT, "config.yaml"))


def search_all_kinds(nodes, value):
    """在 text/desc/id 三种语义下搜索 value，返回 {kind: [(label, center)]}"""
    out = {}
    for kind in ("text", "desc"):
        hits = match_selector(nodes, kind, value)
        if hits:
            out[kind] = [(h["text"] or h["desc"], h["center"]) for h in hits]
    hits = match_selector(nodes, "id", value)
    if hits:
        out["id"] = [(h["rid"], h["center"]) for h in hits]
    return out


def first_anchor_action(actions):
    """返回 (index, action)；actions 可能是单模板或多候选模板。"""
    variants = actions if all(isinstance(a, list) for a in actions) else [actions]
    for vi, variant in enumerate(variants):
        for i, act in enumerate(variant or []):
            if isinstance(act, dict) and act.get("type") in ANCHOR_TYPES:
                return vi, i, act
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "calib",
                                                 "ANCHOR_PROPOSAL.md"))
    args = ap.parse_args()

    cfg = load_cfg()
    apps = {a.get("name"): a for a in (cfg.get("apps") or [])}

    lines = ["# 锚点修补建议（基于真机校准 dump）", "",
             "> 由 `devtools/propose_anchors.py` 生成，**只读不改配置**。",
             "> 「跨语义命中」= 候选文案虽然在 text 里找不到，但在 content-desc 里找到了。",
             "> 这类锚点只需给候选加一条 `type: desc` 即可修复，无需重新截图。", ""]

    fixed_cnt = need_coord = no_dump = 0

    for path in sorted(glob.glob(os.path.join(HERE, "calib", "*", "ui.xml"))):
        app_dir = os.path.dirname(path)
        app_name = os.path.basename(app_dir)
        app = apps.get(app_name)
        if not app:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                nodes = parse_nodes(f.read())
        except Exception as e:
            lines.append(f"## {app_name}\n\n读取 dump 失败: {e}\n")
            no_dump += 1
            continue

        lines.append(f"## {app_name}  (`{app.get('package')}`)")
        lines.append("")
        lines.append("| 行为 | 入口动作 | 候选 | 现状 | 跨语义命中 | 建议 |")
        lines.append("|---|---|---|---|---|---|")

        for bid, actions in (app.get("behaviors") or {}).items():
            if not actions:
                continue
            vi, si, act = first_anchor_action(actions)
            if act is None:
                continue
            t = act.get("type")
            if t == "click_first":
                cands = [c for c in (act.get("candidates") or [])
                         if isinstance(c, dict) and c.get("value")]
            elif t == "click_text":
                cands = [{"type": "text", "value": act.get("text", "")}]
            elif t == "click_id":
                cands = [{"type": "id", "value": act.get("res_id", "")}]
            else:
                cands = [{"type": "desc", "value": act.get("desc", "")}]

            found_any = False
            detail_rows = []
            for c in cands:
                val = str(c.get("value") or "")
                if not val:
                    continue
                res = search_all_kinds(nodes, val)
                native = c.get("type", "text")
                native_hit = bool(res.get(native))
                alt = {k: v for k, v in res.items() if k != native and v}
                if native_hit:
                    found_any = True
                    label, center = res[native][0]
                    detail_rows.append((val, native, "命中",
                                        f"{native}:{label} @{center}", "无需修改"))
                elif alt:
                    found_any = True
                    k = list(alt)[0]
                    label, center = alt[k][0]
                    detail_rows.append((val, native, "未命中",
                                        f"{k}:{label} @{center}",
                                        f"加候选 `{{type: {k}, value: \"{val}\"}}`"))
                else:
                    detail_rows.append((val, native, "未命中", "-", "落地页无此锚点"))

            if not found_any:
                need_coord += 1
                detail_rows.append(("—", "—", "—", "—",
                                    "⚠ 落地页无可用文本锚点，需 click_point(坐标/VLM)"))
            else:
                fixed_cnt += 1

            for val, native, st, cross, sug in detail_rows:
                lines.append(f"| {bid} | {t} | `{val}` | {st} | {cross} | {sug} |")
        lines.append("")

    lines += ["## 统计", "",
              f"- 入口有可用文本锚点的行为: **{fixed_cnt}**",
              f"- 落地页无文本锚点、需坐标/VLM 的行为: **{need_coord}**", ""]

    text = "\n".join(lines)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"已写出: {args.out}")
    print(f"入口有文本锚点: {fixed_cnt} | 需坐标/VLM: {need_coord}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
