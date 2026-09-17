# -*- coding: utf-8 -*-
"""轮询等待设备进入 device 状态，稳定后立即截图。"""
import subprocess, time, sys, os

ADB = r"C:\Users\Administrator\platform-tools\platform-tools\adb.exe"
OUT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_277511131d59420bac41e2e16244f382\temp\real_shot_3.png"
TIMEOUT = float(sys.argv[2]) if len(sys.argv) > 2 else 150

def run(args, timeout=30):
    return subprocess.run([ADB] + args, capture_output=True, timeout=timeout)

def state():
    p = run(["devices"])
    text = p.stdout.decode(errors="ignore")
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None

t0 = time.time()
last = None
while time.time() - t0 < TIMEOUT:
    s = state()
    if s != last:
        print(f"[{(time.time()-t0):.0f}s] state -> {s or 'none'}")
        last = s
    if s:
        # 连续两次稳定则截图
        time.sleep(1.5)
        s2 = state()
        if s2:
            p = run(["exec-out", "screencap", "-p"], timeout=60)
            with open(OUT, "wb") as f:
                f.write(p.stdout)
            ok = p.returncode == 0 and open(OUT, "rb").read(8) == b"\x89PNG\r\n\x1a\n"
            print(f"screencap exit={p.returncode} magic={'OK' if ok else 'BAD'} size={os.path.getsize(OUT)}")
            if ok:
                sys.exit(0)
    time.sleep(0.8)
print("TIMEOUT: 未捕获到稳定 device 状态")
sys.exit(1)
