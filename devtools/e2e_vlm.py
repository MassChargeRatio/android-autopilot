# -*- coding: utf-8 -*-
"""e2e_vlm.py - 真机截图 -> VisionLocator -> 坐标 端到端回测

替代交接包里硬编码旧机路径的 e2e_vlm_adapt.py / e2e_vlm_real.py。
直接复用工程自身的 vision.VisionLocator，保证测的就是实际执行路径。

用法：
    python devtools/e2e_vlm.py --prompt "定位屏幕上的『设置』应用图标"
    python devtools/e2e_vlm.py --image shot.png --prompt "..." --expected 281,1610
    python devtools/e2e_vlm.py --image shot.png            # 不连真机，用已有截图
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import vision as vs  # noqa: E402


def build_cfg():
    try:
        import yaml
        with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("vision") or {}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None, help="截图路径；缺省则现场截真机")
    ap.add_argument("--prompt", default="定位屏幕上『设置』应用图标的中心")
    ap.add_argument("--expected", default=None, help="期望中心 x,y，用于算误差")
    ap.add_argument("--save", default=None, help="现场截图保存路径")
    args = ap.parse_args()

    path = args.image
    if not path:
        from adbkit import Adb
        a = Adb()
        a.ensure()
        path = args.save or os.path.join(HERE, "out", "e2e_input.png")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        a.screenshot(path)
        print(f"[shot] 真机截图 -> {path} ({os.path.getsize(path)} bytes)")

    locator = vs.VisionLocator(build_cfg(), base_dir=ROOT)
    print(f"[cfg] vision.enabled={locator.enabled} "
          f"vlm_available={locator.vlm_available}")

    from PIL import Image
    img = Image.open(path).convert("RGB")
    print(f"[input] {path} size={img.size}")
    print(f"[prompt] {args.prompt}")

    hit = locator.locate_on_screen(prompt=args.prompt, screen_img=img,
                                   app="devtools", tag="e2e")
    if hit is None:
        print("RESULT: None（未命中，或 VLM 未配置/不可用）")
        print("提示：先跑 devtools/vlm_probe.py --models 确认网关可用。")
        return 1
    print(f"RESULT: 命中 ({hit.x:.1f}, {hit.y:.1f}) score={hit.score}")
    if args.expected:
        ex, ey = (int(v) for v in args.expected.split(","))
        err = ((hit.x - ex) ** 2 + (hit.y - ey) ** 2) ** 0.5
        print(f"期望中心 ({ex},{ey})  欧氏误差 {err:.1f}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
