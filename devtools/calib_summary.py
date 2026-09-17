# -*- coding: utf-8 -*-
"""calib_summary.py - 汇总 devtools/calib/ 下所有校准报告

用法：
    python devtools/calib_summary.py            # 打印汇总表
    python devtools/calib_summary.py --out devtools/calib/SUMMARY.md
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(HERE, "calib"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows = []
    for p in sorted(glob.glob(os.path.join(args.dir, "*", "report.json"))):
        try:
            with open(p, "r", encoding="utf-8") as f:
                rows.append(json.load(f))
        except Exception as e:
            print(f"跳过 {p}: {e}")

    if not rows:
        print(f"{args.dir} 下没有找到 report.json，请先跑 devtools/calibrate.py")
        return 1

    rows.sort(key=lambda r: (r.get("entry_total", 0)
                             and r.get("entry_hit", 0) / r.get("entry_total", 1),
                             r.get("app", "")))

    md = ["# 18 个新 App 校准汇总", "",
          "> 入口命中率 = 每个行为**首个锚点动作**是否在 App 落地页命中。",
          "> 二级页命中率 = 用 VLM 点进底栏「我的」后再校验同一批入口。",
          "> 后续步骤依赖跳转后的页面，静态 dump 无法校验，需实跑。", "",
          "| App | 包名 | 首屏入口 | 二级页入口 | 落地页节点 | 前台包名 | 备注 |",
          "|---|---|---|---|---|---|---|"]
    th = tt = ah = at = 0
    problems = []
    for r in rows:
        h, t = r.get("entry_hit", 0), r.get("entry_total", 0)
        th += h
        tt += t
        aft = r.get("after") or {}
        a_h, a_t = aft.get("entry_hit", 0), aft.get("entry_total", 0)
        ah += a_h
        at += a_t
        note = ""
        fg = r.get("foreground") or ""
        if fg and fg != r.get("package"):
            note = f"⚠ 前台是 {fg}"
            problems.append(f"{r['app']}: 落地时前台为 {fg}（非目标包名，"
                            f"可能被登录页/弹窗/广告占据）")
        if t == 0:
            note = (note + " 无锚点类动作").strip()
        md.append(f"| {r['app']} | `{r['package']}` | {h}/{t} | "
                  f"{a_h}/{a_t} | {r.get('nodes', 0)} | `{fg}` | {note} |")
    md += ["", f"**首屏入口命中率合计: {th}/{tt} = "
              f"{(th / tt * 100 if tt else 0):.0f}%**  ",
           f"**二级页入口命中率合计: {ah}/{at} = "
           f"{(ah / at * 100 if at else 0):.0f}%**", ""]

    if problems:
        md += ["## 需要人工确认", ""] + [f"- {x}" for x in problems] + [""]

    md += ["## 各 App 入口明细（首屏 / 二级页）", ""]
    for r in rows:
        md.append(f"### {r['app']}  (`{r['package']}`)")
        md.append("")
        md.append("首屏：")
        for k, v in (r.get("entry_detail") or {}).items():
            mark = "✅" if v.get("status") == "命中" else "❌"
            md.append(f"- {mark} `{k}` [{v.get('type')}] {v.get('detail')}")
        aft = r.get("after") or {}
        if aft:
            md.append("")
            md.append(f"二级页（点击『{aft.get('prompt')}』-> {aft.get('click')}，"
                      f"节点 {aft.get('nodes')}）：")
            for k, v in (aft.get("entry_detail") or {}).items():
                mark = "✅" if v.get("status") == "命中" else "❌"
                md.append(f"- {mark} `{k}` [{v.get('type')}] {v.get('detail')}")
            if aft.get("candidate_anchors"):
                md.append("")
                md.append("二级页可用锚点：")
                for a in aft["candidate_anchors"][:12]:
                    if a.get("kw"):
                        md.append(f"  - `{a['label']}` @{a['center']} "
                                  f"kw={','.join(a['kw'])}")
        md.append("")

    text = "\n".join(md)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"已写出: {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
