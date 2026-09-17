# -*- coding: utf-8 -*-
"""轮询 adb，捕获 device 稳定窗口后立即完成：tcpip 切换 + 截图校验 + 打印最终状态。
日志式输出，方便观察链路波动。"""
import subprocess, time, sys, os, re

ADB = r"C:\Users\Administrator\platform-tools\platform-tools\adb.exe"
SERIAL = "83437b02"
OUT = r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_277511131d59420bac41e2e16244f382\temp\real_shot_4.png"
TIMEOUT = float(sys.argv[1]) if len(sys.argv) > 1 else 300

def run(args, timeout=30):
    try:
        return subprocess.run([ADB] + args, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None

def states():
    """返回 {serial: state}"""
    p = run(["devices"])
    out = {}
    if not p: return out
    for line in p.stdout.decode(errors="ignore").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0]] = parts[1]
    return out

t0 = time.time()
last_sig = None
while time.time() - t0 < TIMEOUT:
    st = states()
    sig = tuple(sorted(st.items()))
    if sig != last_sig:
        print(f"[{(time.time()-t0):.0f}s] devices={st}")
        last_sig = sig
    if st.get(SERIAL) == "device":
        # 双稳确认
        time.sleep(1.5)
        st2 = states()
        if st2.get(SERIAL) != "device":
            continue
        p1 = run(["-s", SERIAL, "tcpip", "5555"], timeout=30)
        print("tcpip:", p1.returncode if p1 else "None", (p1.stdout or b"").decode(errors="ignore").strip())
        time.sleep(2)
        ip = None
        for cmd in (["-s", SERIAL, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"],
                    ["-s", SERIAL, "shell", "ip", "addr", "show"]):
            p2 = run(cmd, timeout=30)
            if not p2: continue
            text = (p2.stdout or b"").decode(errors="ignore")
            m = re.search(r"inet (192\.168|10\.|172\.)[0-9.]+", text)
            if m:
                ip = m.group(1).split("inet ")[1]
                break
        print("wlan ip:", ip)
        if ip:
            p3 = run(["connect", f"{ip}:5555"], timeout=40)
            print("connect:", (p3.stdout or b"").decode(errors="ignore").strip() if p3 else "None")
            time.sleep(2)
        # 截图（无线或USB）
        p4 = run(["exec-out", "screencap", "-p"], timeout=60)
        if p4 and p4.returncode == 0:
            with open(OUT, "wb") as f:
                f.write(p4.stdout)
            sz = os.path.getsize(OUT)
            ok = open(OUT, "rb").read(8) == b"\x89PNG\r\n\x1a\n"
            print(f"screenshot: size={sz} magic={'OK' if ok else 'BAD'}")
            if ok and sz > 100000:
                print("CAPTURE_OK")
                sys.exit(0)
    time.sleep(1)
print("TIMEOUT")
sys.exit(1)
