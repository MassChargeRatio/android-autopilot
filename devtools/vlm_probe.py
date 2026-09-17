# -*- coding: utf-8 -*-
"""vlm_probe.py - 裸调 VLM 网关，区分「未命中」与「后端故障」

背景：locate_by_vlm 未命中目标时静默返回 None，容易误判为网关坏了。
本脚本绕过工程封装，直接 POST /chat/completions，打印原始状态码与响应片段。

用法：
    python devtools/vlm_probe.py --image shot.png --prompt "定位屏幕上的签到按钮"
    python devtools/vlm_probe.py --models          # 只列出可用模型
"""
import argparse
import base64
import json
import os
import sys

import requests

DEFAULT_BASE = "http://127.0.0.1:20128"


def config_key():
    """API Key 从环境变量或 `config.yaml` 读，**绝不写进源码**。

    硬编码的 Key 会随 git 一起被推走 —— 本项目实测踩过：本文件与 3 个
    `handover/02_适配脚本/` 脚本都硬编码了同一个 Key。
    优先级：`VLM_KEY` / `VLM_API_KEY` 环境变量 > `config.yaml` 的 `vision.vlm.api_key`。
    """
    key = os.environ.get("VLM_KEY") or os.environ.get("VLM_API_KEY")
    if key:
        return key
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import yaml
    except ImportError:      # 与 main.py 一致：无 PyYAML 时用内置解析器
        import miniyaml as yaml  # type: ignore
    try:
        with open(os.path.join(root, "config.yaml"), "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        return ((cfg.get("vision") or {}).get("vlm") or {}).get("api_key") or ""
    except Exception:        # noqa: BLE001 - 读不到就让调用方用 --key 传
        return ""


DEFAULT_KEY = config_key()


def list_models(base, key):
    r = requests.get(base.rstrip("/") + "/models",
                     headers={"Authorization": f"Bearer {key}"}, timeout=20)
    print("status:", r.status_code)
    try:
        for m in r.json().get("data", []):
            print("  -", m.get("id"))
    except Exception:
        print(r.text[:500])


def probe(base, key, model, image, prompt):
    with open(image, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
        "temperature": 0,
    }
    r = requests.post(base.rstrip("/") + "/chat/completions",
                      headers={"Authorization": f"Bearer {key}",
                               "Content-Type": "application/json"},
                      json=payload, timeout=120)
    print(f"=== model={model} status={r.status_code} ===")
    if r.status_code != 200:
        print("body:", r.text[:800])
        return None
    body = r.json()
    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    print("content:", str(content)[:400].replace("\n", " "))
    return content


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=None)
    ap.add_argument("--prompt", default='定位图中目标元素中心，只返回JSON：'
                                        '{"x": 中心x, "y": 中心y}')
    ap.add_argument("--base", default=os.environ.get("VLM_BASE", DEFAULT_BASE))
    ap.add_argument("--key", default=DEFAULT_KEY)
    ap.add_argument("--model", default="auto/best-vision")
    ap.add_argument("--models", action="store_true", help="仅列出模型")
    args = ap.parse_args()

    if args.models or not args.image:
        list_models(args.base, args.key)
        return
    for m in (args.model, "auto/vision"):
        probe(args.base, args.key, m, args.image, args.prompt)


if __name__ == "__main__":
    main()
