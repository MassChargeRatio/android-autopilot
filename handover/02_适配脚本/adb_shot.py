# -*- coding: utf-8 -*-
"""受控 adb 截图：subprocess 直接写字节，避免 PowerShell 重定向损坏。"""
import subprocess, sys

ADB = r"C:\Users\Administrator\platform-tools\platform-tools\adb.exe"
out = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_277511131d59420bac41e2e16244f382\temp\real_shot_2.png"

p = subprocess.run([ADB, "exec-out", "screencap", "-p"], capture_output=True, timeout=60)
print("adb exit:", p.returncode, "stderr:", p.stderr[:200] if p.stderr else "")
with open(out, "wb") as f:
    f.write(p.stdout)
import os
print("saved:", out, os.path.getsize(out), "bytes")
# PNG 完整性校验
sig = open(out, "rb").read(8)
print("magic ok:", sig == b"\x89PNG\r\n\x1a\n")
