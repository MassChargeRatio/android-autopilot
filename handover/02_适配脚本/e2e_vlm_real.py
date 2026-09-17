# -*- coding: utf-8 -*-
"""真机主屏 VLM 定位验证：截图 -> VisionLocator.locate_by_vlm -> 坐标"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
out_dir = r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_277511131d59420bac41e2e16244f382\temp"
sys.path.insert(0, r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_035592412ad44a818702fc4451ab37dd\output\android_autopilot")
from vision import VisionLocator
from PIL import Image

shot = out_dir + r"\real_shot_6.png"
cfg = {
    "enabled": True,
    "min_score": 0.5,
    "vlm": {
        "enabled": True,
        "base_url": "http://192.168.1.102:20128",
        # Key 从环境变量读，不写进源码（硬编码的 Key 会随 git 一起推走）
        "api_key": os.environ.get("VLM_KEY") or os.environ.get("VLM_API_KEY") or "",
        "model": "auto/best-vision",
        "timeout": 60,
    },
}
loc = VisionLocator(cfg=cfg)
img = Image.open(shot)
img = img.convert("RGB")
print("screen size:", img.size)
for prompt in ("主屏上的设置应用图标", "底部导航栏最左边的返回键"):
    m = loc.locate_by_vlm(img, prompt)
    if m:
        print(f"[HIT] {prompt} -> x={m.x:.0f} y={m.y:.0f} score={m.score:.2f}")
    else:
        print(f"[MISS] {prompt} -> None")
