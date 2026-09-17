# -*- coding: utf-8 -*-
"""e2e_vlm 适配版：VisionLocator + 可达网关 192.168.1.102:20128
用法：
  python e2e_vlm_adapt.py [--image <真实截图png>] [--prompt <描述>] [--expected x,y]
默认：合成 1080x2340 图上绘制红圆(540,2000)，期望 VLM 返回其中心坐标。
"""
import sys, os, argparse
from PIL import Image, ImageDraw

AP = r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_035592412ad44a818702fc4451ab37dd\output\android_autopilot"
sys.path.insert(0, AP)

import vision as vs

BASE = "http://192.168.1.102:20128/v1"
# Key 从环境变量读，不写进源码（硬编码的 Key 会随 git 一起推走）
KEY = os.environ.get("VLM_KEY") or os.environ.get("VLM_API_KEY") or ""

def make_cfg():
    return {
        "enabled": True,
        "template_dir": "templates",
        "template_threshold": 0.8,
        "template_scales": [0.6, 0.8, 1.0, 1.2, 1.4],
        "min_score": 0.5,
        "vlm": {
            "enabled": True,
            "base_url": BASE,
            "api_key": KEY,
            "model": "auto/best-vision",
            "timeout": 90,
            "fallback": {
                "base_url": BASE,
                "api_key": KEY,
                "model": "auto/vision",
                "timeout": 90,
            },
        },
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None, help="真实截图路径；缺省用合成图")
    ap.add_argument("--prompt", default="图片中红色圆钮的中心坐标")
    ap.add_argument("--expected", default=None, help="期望真实中心 x,y（用于算误差）")
    args = ap.parse_args()

    if args.image and os.path.exists(args.image):
        img = Image.open(args.image).convert("RGB")
        print(f"[input] 真实截图: {args.image} 尺寸={img.size}")
        expected = None
        if args.expected:
            ex, ey = args.expected.split(",")
            expected = (int(ex), int(ey))
    else:
        img = Image.new("RGB", (1080, 2340), (255, 255, 255))
        d = ImageDraw.Draw(img)
        d.ellipse([450, 1900, 630, 2080], fill=(230, 30, 30))
        print("[input] 合成图: 1080x2340, 红圆中心=(540,1990), 半径=90")
        expected = (540, 1990)

    locator = vs.VisionLocator(make_cfg(), base_dir=AP)
    hit = locator.locate_by_vlm(img, args.prompt)

    print("RESULT:", hit)
    if hit is not None:
        print(f"VLM 返回中心: ({hit.x:.1f}, {hit.y:.1f}) score={hit.score:.3f}")
        if expected:
            err = ((hit.x - expected[0]) ** 2 + (hit.y - expected[1]) ** 2) ** 0.5
            print(f"期望中心: {expected}  欧氏误差: {err:.1f}px")
    else:
        print("RESULT: None（VLM 未返回有效坐标）")

if __name__ == "__main__":
    main()
