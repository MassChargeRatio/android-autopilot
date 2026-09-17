# -*- coding: utf-8 -*-
"""vlm_bench.py - VLM 定位后端量化基准

为什么需要它：VLM 定位是"元素定位失败后的最后兜底"，一旦它幻觉出坐标，
executor 会照着错误坐标去点——可能点到广告、甚至点到提现/支付按钮。
所以必须量化两件事：
  - 正向命中率与像素误差（目标真实存在时）
  - 负向误报率（目标不存在时是否仍给出坐标）

用法：
    python devtools/vlm_bench.py --image devtools/out/p1.png --trials 5
    python devtools/vlm_bench.py --image p1.png --positive "设置:173,1609" \
        --negative "抖音" --negative "网易云音乐"
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import vision as vs  # noqa: E402


def build_locator():
    try:
        import yaml
        with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as f:
            cfg = (yaml.safe_load(f) or {}).get("vision") or {}
    except Exception:
        cfg = {}
    return vs.VisionLocator(cfg, base_dir=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--positive", action="append", default=[],
                    help="正向用例，格式 目标名:期望x,期望y（可重复）")
    ap.add_argument("--negative", action="append", default=[],
                    help="负向用例（目标不存在，可重复）")
    ap.add_argument("--tol", type=float, default=120.0,
                    help="判定为命中的像素容差（默认 120px）")
    args = ap.parse_args()

    from PIL import Image
    img = Image.open(args.image).convert("RGB")
    print(f"图像: {args.image} {img.size}  试验次数={args.trials} 容差={args.tol}px")
    loc = build_locator()
    print(f"vision.enabled={loc.enabled} vlm_available={loc.vlm_available}\n")

    if not args.positive and not args.negative:
        args.positive = ["设置:173,1609"]

    print("=== 正向用例（应命中） ===")
    for case in args.positive:
        name, _, xy = case.partition(":")
        ex, ey = (float(v) for v in xy.split(","))
        hits, errs = 0, []
        for i in range(args.trials):
            hit = loc.locate_by_vlm(img, f"定位屏幕上『{name}』应用图标的中心")
            if hit is not None:
                err = ((hit.x - ex) ** 2 + (hit.y - ey) ** 2) ** 0.5
                errs.append(err)
                if err <= args.tol:
                    hits += 1
                print(f"  #{i+1} -> ({hit.x},{hit.y}) 误差 {err:.0f}px "
                      f"{'命中' if err <= args.tol else '偏离'}")
            else:
                print(f"  #{i+1} -> None（未命中）")
        rate = hits / args.trials * 100
        avg = sum(errs) / len(errs) if errs else float("nan")
        print(f"  [{name}] 命中率 {hits}/{args.trials} = {rate:.0f}%, "
              f"平均误差 {avg:.0f}px\n")

    print("=== 负向用例（应返回 None） ===")
    for name in args.negative:
        false_pos = 0
        for i in range(args.trials):
            hit = loc.locate_by_vlm(img, f"定位屏幕上『{name}』应用图标的中心")
            if hit is not None:
                false_pos += 1
                print(f"  #{i+1} -> ({hit.x},{hit.y}) 误报！")
            else:
                print(f"  #{i+1} -> None（正确）")
        rate = false_pos / args.trials * 100
        print(f"  [{name}] 误报率 {false_pos}/{args.trials} = {rate:.0f}%\n")


if __name__ == "__main__":
    main()
