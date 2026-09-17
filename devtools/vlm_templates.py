# -*- coding: utf-8 -*-
"""vlm_templates.py - 提示词模板横向评测

背景：实测同一张图、同一个目标，网关的表现差异极大：
  - 中文提示词常被内容安全拦截，返回字符串 "User Safety: safe"（不是坐标）；
  - 英文提示词成功率更高，但坐标精度波动大（41px ~ 205px）。
本脚本对候选模板做 N 次重复，统计「可用率（返回可解析 JSON）」与「平均误差」，
用于挑选写回 config.yaml 的默认模板。

用法：
    python devtools/vlm_templates.py --image devtools/out/p1.png \
        --target 设置 --truth 170,1685 --trials 3
"""
import argparse
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import requests  # noqa: E402

SUFFIX_ZH = ("\n严格按以下要求作答：\n"
             "1) 坐标基于原图像素，左上角为原点，x 向右增大，y 向下增大；\n"
             "2) 只有图中确实存在该目标时才给坐标，否则返回 {\"x\": null, \"y\": null}；\n"
             "3) 只返回一个 JSON 对象，不要任何其他文字。")

SUFFIX_EN = ("\nAnswer strictly as follows:\n"
             "1) Coordinates are in the ORIGINAL image pixel space, "
             "origin at top-left, x to the right, y downward.\n"
             "2) Only give coordinates if the target is clearly visible; "
             "otherwise return {\"x\": null, \"y\": null}. Never guess.\n"
             "3) Return exactly one JSON object {\"x\": <int>, \"y\": <int>} "
             "and nothing else.")

TEMPLATES = {
    "T1_中文体+中文后缀": lambda t: f"定位屏幕上『{t}』图标的中心" + SUFFIX_ZH,
    "T2_中文体+英文后缀": lambda t: f"定位屏幕上『{t}』图标的中心" + SUFFIX_EN,
    "T3_英文体+英文后缀": lambda t: (
        f"This is a phone screenshot. Locate the '{t}' app icon and "
        f"return its center pixel coordinate." + SUFFIX_EN),
    "T4_纯JSON约束": lambda t: (
        f"Output the center pixel coordinate of the '{t}' icon in this "
        f"screenshot. Reply with JSON only: {{\"x\": int, \"y\": int}}. "
        f"If absent, reply {{\"x\": null, \"y\": null}}."),
}


def build_cfg():
    try:
        import yaml
        with open(os.path.join(ROOT, "config.yaml"), "r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("vision") or {}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--target", default="设置")
    ap.add_argument("--truth", default=None, help="真值 x,y")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    cfg = build_cfg()
    vlm = cfg.get("vlm") or {}
    url = (vlm.get("base_url") or "http://127.0.0.1:20128/v1").rstrip("/") \
        + "/chat/completions"
    key = vlm.get("api_key") or ""
    model = args.model or vlm.get("model") or "auto/best-vision"
    truth = None
    if args.truth:
        truth = tuple(float(v) for v in args.truth.split(","))

    from PIL import Image
    img = Image.open(args.image).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = buf.getvalue()
    import base64
    b64 = base64.b64encode(b64).decode()

    print(f"image={args.image} {img.size} model={model} trials={args.trials}")
    print(f"target={args.target} truth={truth}\n")

    for name, fn in TEMPLATES.items():
        prompt = fn(args.target)
        ok, errs, raws = 0, [], []
        for i in range(args.trials):
            try:
                r = requests.post(url, headers={"Authorization": f"Bearer {key}"},
                                  json={"model": model, "temperature": 0,
                                        "messages": [{"role": "user", "content": [
                                            {"type": "text", "text": prompt},
                                            {"type": "image_url", "image_url": {
                                                "url": "data:image/png;base64," + b64}}]}]},
                                  timeout=180, allow_redirects=False)
                content = r.json()["choices"][0]["message"]["content"]
            except Exception as e:
                raws.append(f"ERR {type(e).__name__}")
                continue
            m = re.search(r"\{.*?\}", str(content), re.S)
            if not m:
                raws.append(str(content).strip()[:40])
                continue
            try:
                d = json.loads(m.group(0))
            except Exception:
                raws.append("JSON解析失败")
                continue
            x, y = d.get("x"), d.get("y")
            if x is None or y is None:
                raws.append("null(未命中)")
                continue
            ok += 1
            raws.append(f"({x},{y})")
            if truth:
                errs.append(((float(x) - truth[0]) ** 2
                             + (float(y) - truth[1]) ** 2) ** 0.5)
            time.sleep(0.4)
        rate = ok / args.trials * 100
        avg = f"{sum(errs) / len(errs):.0f}px" if errs else "-"
        print(f"{name}: 可用率 {ok}/{args.trials} = {rate:.0f}%  平均误差 {avg}")
        print(f"    样本: {raws}")


if __name__ == "__main__":
    main()
