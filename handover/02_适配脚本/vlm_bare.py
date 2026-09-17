# -*- coding: utf-8 -*-
"""裸调 VLM 网关，打印原始返回，隔离后端故障"""
import sys, io, base64, os, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
out_dir = r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_277511131d59420bac41e2e16244f382\temp"

shot = out_dir + r"\real_shot_6.png"
b64 = base64.b64encode(open(shot, "rb").read()).decode("ascii")

base = "http://192.168.1.102:20128"
# Key 从环境变量读，不写进源码（硬编码的 Key 会随 git 一起推走）
key = os.environ.get("VLM_KEY") or os.environ.get("VLM_API_KEY") or ""
for model in ("auto/best-vision", "auto/vision"):
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": '定位主屏上的设置应用图标中心，只返回一个JSON对象：{"x": 中心x, "y": 中心y}，不要任何其他文字。'},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
        "temperature": 0,
    }
    try:
        r = requests.post(base + "/chat/completions", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=90)
        print(f"=== model={model} status={r.status_code} ===")
        print("body head:", r.text[:600].replace("\n", " "))
    except Exception as e:
        print(f"=== model={model} ERROR: {type(e).__name__}: {e} ===")
