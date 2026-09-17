#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""给「导航到我的」前置步补上 `vision: false`（幂等）。

为什么
------
`click_point` 若带 `vlm_prompt`，执行器会**先走视觉兜底**（截屏 + VLM 识别）。
本机 VLM 图像请求常 90s 超时或返回 `User Safety: safe`（非确定性），
而导航「我的」是**每个行为都要执行**的固定步骤 —— 让它走视觉既慢又不稳。

比例坐标 (0.90, 0.915) 已在 18 个 App 上实机验证可靠（各 App『我的』中心
y 落在 2106~2192）。因此导航步显式关闭视觉兜底，直接点比例坐标。

保留 `vlm_prompt` 字段：devtools（plan_anchor_fixes / verify_live /
to_any_of）靠它识别「这是导航前置步」，删了会破坏前置步检测。

用法
----
    python devtools/patch_nav_vision.py            # 预览
    python devtools/patch_nav_vision.py --apply    # 写回（自动备份）
"""
import argparse
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG = os.path.join(ROOT, "config.yaml")
NAV_MARK = "最右侧"


def patch(node, counter):
    """递归给导航 click_point 加 vision: false（原地修改）。"""
    if isinstance(node, dict):
        if (node.get("type") == "click_point"
                and NAV_MARK in str(node.get("vlm_prompt", ""))
                and node.get("vision", True) is not False):
            node["vision"] = False
            counter["patched"] += 1
        else:
            if (node.get("type") == "click_point"
                    and NAV_MARK in str(node.get("vlm_prompt", ""))):
                counter["already"] += 1
        for v in node.values():
            patch(v, counter)
    elif isinstance(node, list):
        for v in node:
            patch(v, counter)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    import yaml
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    counter = {"patched": 0, "already": 0}
    patch(cfg.get("apps") or [], counter)
    print(f"导航前置步: 待补 {counter['patched']} 处，"
          f"已补过 {counter['already']} 处")

    if not counter["patched"]:
        print("无需改动")
        return 0
    if not args.apply:
        print("\n（预览模式，未写盘；加 --apply 生效）")
        return 0

    # 保留关键注释（PyYAML dump 会丢注释）
    import to_any_of as T
    bak = f"{args.config}.bak-navvision-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(args.config, bak)
    out = yaml.dump(cfg, allow_unicode=True, sort_keys=False,
                    default_flow_style=False, width=200)
    out = T.restore_comments(out)
    with open(args.config, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    print(f"已写回 {args.config}\n备份: {bak}")

    try:
        cfg2 = yaml.safe_load(open(args.config, encoding="utf-8"))
        c2 = {"patched": 0, "already": 0}
        patch(cfg2.get("apps") or [], c2)
        print(f"复验: 加载成功, {len(cfg2['apps'])} 个 app, "
              f"仍待补 {c2['patched']} 处（应为 0）")
        if c2["patched"]:
            raise RuntimeError("复验发现仍有未补项")
    except Exception as ex:
        print(f"复验失败: {ex}，回滚")
        shutil.copy2(bak, args.config)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
