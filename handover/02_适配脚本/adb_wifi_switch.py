# -*- coding: utf-8 -*-
"""捕获 device 稳定窗口 -> 立即开启无线 adb (tcpip 5555) 并获取手机局域网 IP。"""
import subprocess, time, sys, re

ADB = r"C:\Users\Administrator\platform-tools\platform-tools\adb.exe"
SERIAL = "83437b02"
TIMEOUT = float(sys.argv[1]) if len(sys.argv) > 1 else 180

def run(args, timeout=30):
    try:
        return subprocess.run([ADB] + args, capture_output=True, timeout=timeout)
    except Exception as e:
        return None

def device_serial():
    p = run(["devices"])
    if not p: return None
    for line in p.stdout.decode(errors="ignore").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            return parts[0]
    return None

t0 = time.time()
while time.time() - t0 < TIMEOUT:
    s = device_serial()
    if s:
        print(f"[{(time.time()-t0):.0f}s] device online: {s}")
        # 1) 开启 tcpip
        p1 = run(["-s", s, "tcpip", "5555"], timeout=30)
        print("tcpip:", "exit=" + str(p1.returncode) if p1 else "None",
              (p1.stdout.decode(errors="ignore") + p1.stderr.decode(errors="ignore")).strip() if p1 else "")
        time.sleep(3)
        # 2) 获取 wifi IP
        ip = None
        for cmd in (["shell", "ip", "-f", "inet", "addr", "show", "wlan0"],
                    ["shell", "ifconfig", "wlan0"],
                    ["shell", "ip", "addr", "show"]):
            p2 = run(["-s", s] + cmd, timeout=30)
            if not p2: continue
            text = (p2.stdout or b"").decode(errors="ignore")
            if re.search(r"\.\.\d{1,3}\.", text) or "inet " in text:
                m = re.search(r"inet ([0-9.]+)", text)
                if m and re.match(r"(192\.168|10\.|172\.)", m.group(1)):
                    ip = m.group(1)
                    print("wifi ip:", ip)
                    break
        if not ip:
            print("未能拿到手机局域网 IP，退出")
            sys.exit(2)
        # 3) connect 无线
        p3 = run(["connect", f"{ip}:5555"], timeout=40)
        print("connect:", (p3.stdout.decode(errors="ignore") +
                           p3.stderr.decode(errors="ignore")).strip() if p3 else "None")
        time.sleep(3)
        print("final devices:")
        p4 = run(["devices", "-l"], timeout=30)
        print(p4.stdout.decode(errors="ignore") if p4 else "None")
        sys.exit(0)
    time.sleep(1)
print("TIMEOUT")
sys.exit(1)
