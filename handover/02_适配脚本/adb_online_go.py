# -*- coding: utf-8 -*-
"""设备已在线：立即 tcpip 切换 -> 无线 connect -> 截图校验（USB 抖动保底方案）。"""
import subprocess, time, re, os, sys

ADB = r"C:\Users\Administrator\platform-tools\platform-tools\adb.exe"
SERIAL = "83437b02"
OUT = r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_277511131d59420bac41e2e16244f382\temp\real_shot_5.png"

def run(a, t=30):
    try:
        return subprocess.run([ADB]+a, capture_output=True, timeout=t)
    except Exception as e:
        print("run err", e); return None

def text(p):
    return ((p.stdout or b"") + (p.stderr or b"")).decode(errors="ignore").strip()

# 1) 确认在线
p = run(["devices"])
print("devices:", text(p).replace("\n", " | "))

# 2) tcpip 切换
p1 = run(["-s", SERIAL, "tcpip", "5555"], t=30)
print("tcpip:", text(p1) or f"exit={p1.returncode}")
time.sleep(3)

# 3) 获取 IP
ip = None
for cmd in (["-s", SERIAL, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"],
            ["-s", SERIAL, "shell", "ip", "addr", "show"]):
    p2 = run(cmd, t=25)
    if not p2: continue
    t2 = (p2.stdout or b"").decode(errors="ignore")
    m = re.search(r"inet (192\.168\.|10\.|172\.)[0-9.]+", t2)
    if m:
        ip = m.group(1)
        break
print("wlan ip:", ip)

# 4) 无线 connect
if ip:
    p3 = run(["connect", f"{ip}:5555"], t=40)
    print("connect:", text(p3) or f"exit={p3.returncode}")
    time.sleep(3)

# 5) 截图（优先尝试无线，失败退回 USB）
def shot(serial=None):
    a = ["exec-out", "screencap", "-p"]
    if serial: a = ["-s", serial] + a
    else: a = [ADB] and [ser_opt] + ["exec-out", "screencap", "-p"] if False else a
    return run(a, t=60)

def shot_gen(prefix=""):
    a = ["exec-out", "screencap", "-p"]
    return run(a, t=60)

seq = []
# 无线设备名
if ip:
    w = f"{ip}:5555"
    p4 = run(["devices"])
    if w in text(p4):
        seq.append((w, run(["-s", w, "exec-out", "screencap", "-p"], t=60)))
# USB 兜底
seq.append((SERIAL, run(["-s", SERIAL, "exec-out", "screencap", "-p"], t=60)))

for name, p5 in seq:
    if p5 and p5.returncode == 0 and p5.stdout:
        with open(OUT, "wb") as f:
            f.write(p5.stdout)
        sz = os.path.getsize(OUT)
        ok = open(OUT, "rb").read(8) == b"\x89PNG\r\n\x1a\n"
        print(f"shot via {name}: size={sz} magic={'OK' if ok else 'BAD'}")
        if ok and sz > 100000:
            print("SCREENSHOT_OK")
            sys.exit(0)
    else:
        print(f"shot via {name}: FAIL {text(p5) if p5 else 'no data'}")
print("SCREENSHOT_FAIL")
sys.exit(1)
