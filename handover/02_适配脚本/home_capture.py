# -*- coding: utf-8 -*-
"""捕获取当前主屏 + 滑动到第2屏 + 截图"""
import subprocess, os, time

ADB = r"C:\Users\Administrator\platform-tools\platform-tools\adb.exe"
DEV = "192.168.1.54:5555"
OUT = r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_277511131d59420bac41e2e16244f382\temp"

def run(args, t=60):
    return subprocess.run([ADB, "-s", DEV, "shell"] + args, capture_output=True, timeout=t)

def snap(name):
    p = subprocess.run([ADB, "-s", DEV, "exec-out", "screencap", "-p"], capture_output=True, timeout=60)
    path = os.path.join(OUT, name)
    open(path, "wb").write(p.stdout)
    print(name, "size", len(p.stdout), "magic", p.stdout[:8] == b"\x89PNG\r\n\x1a\n")
    return path

# 第1屏
snap("home_p1.png")
# 滑动：从右向左 -> 第2屏
r = run(["input", "swipe", "900", "1200", "150", "1200", "500"])
print("swipe exit", r.returncode)
time.sleep(1.5)
snap("home_p2.png")
# 滑动回第1屏（留待确认）
