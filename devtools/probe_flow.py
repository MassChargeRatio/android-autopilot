# -*- coding: utf-8 -*-
"""probe_flow.py - 按描述路径逐屏抓锚点（Host 一次性探针）

用法:
  python probe_flow.py <serial> <app_name> <package>
交互: 它会启动App并打印当前屏可点元素(text/id/desc/坐标)。
      输入序号点击元素，输入 d 重新dump，输入 n 进入下一屏(只重新dump)，q 退出。
      每屏的 dump 自动存 devtools/calib/uiprobe/<pkg>/NN.xml + NN.png
"""
import os
import re
import subprocess
import sys

PROJ = os.path.dirname(os.path.abspath(__file))
ADB = os.path.join(PROJ, "tools", "platform-tools", "adb.exe")
OUT = os.path.join(PROJ, "devtools", "calib", "uiprobe")


def sh(*args):
    return subprocess.run([ADB, "-s", SERIAL, *args], capture_output=True,
                          text=True, timeout=30, encoding="utf-8", errors="replace").stdout


def parse_nodes(xml):
    out = []
    for m in re.finditer(r'<node\b[^>]*>', xml):
        tag = m.group(0)
        g = lambda k: (re.search(k + r'="([^"]*)"', tag) or [None, ""])[1]
        text, rid, desc = g("text"), g("resource-id"), g("content-desc")
        if not (text or rid or desc):
            continue
        b = g("bounds")
        mm = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b)
        if not mm:
            continue
        l, t, r, bo = map(int, mm.groups())
        out.append({"text": text, "id": rid, "desc": desc, "click": g("clickable"),
                    "rect": (l, t, r, bo)})
    return out


def dump(idx, app_pkg):
    xml = sh("exec-out", "uiautomator", "dump", "/dev/tty")  # fallback below
    xml = sh("exec-out", "cat", "/sdcard/window_dump.xml") if False else xml
    # 用 u2 更稳：shell uiautomator dump 输出到 stdout 需要 /dev/tty 支持
    p = subprocess.run([ADB, "-s", SERIAL, "shell", "uiautomator", "dump",
                        "/sdcard/_probe.xml"], capture_output=True, text=True, timeout=60)
    xml = subprocess.run([ADB, "-s", SERIAL, "exec-out", "cat", "/sdcard/_probe.xml"],
                         capture_output=True, timeout=30).stdout.decode("utf-8", "replace")
    os.makedirs(os.path.join(OUT, app_pkg), exist_ok=True)
    with open(os.path.join(OUT, app_pkg, f"{idx:02d}.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    png = subprocess.run([ADB, "-s", SERIAL, "exec-out", "screencap", "-p"],
                         capture_output=True, timeout=30).stdout
    with open(os.path.join(OUT, app_pkg, f"{idx:02d}.png"), "wb") as f:
        f.write(png)
    return xml


def main():
    global SERIAL
    SERIAL, app_name, app_pkg = sys.argv[1], sys.argv[2], sys.argv[3]
    sh("shell", "am", "force-stop", app_pkg)
    sh("shell", "monkey", "-p", app_pkg, "-c", "android.intent.category.LAUNCHER", "1")
    import time; time.sleep(5)
    idx = 0
    while True:
        xml = dump(idx, app_pkg)
        nodes = parse_nodes(xml)
        clickable = [n for n in nodes if n["click"] == "true"]
        print(f"\n===== 屏 {idx} | 可点元素 {len(clickable)} 个 =====")
        for i, n in enumerate(clickable[:40]):
            lab = n["text"] or n["desc"] or n["id"]
            l, t, r, b = n["rect"]
            print(f"  [{i:2d}] {lab!r} id={n['id'].split('/')[-1]} cx={(l+r)//2} cy={(t+b)//2}")
        cmd = input("点击序号 / d=重dump / n=下一屏 / q=退出: ").strip()
        if cmd == "q":
            break
        if cmd in ("d", "n"):
            idx += int(cmd == "n")
            continue
        try:
            i = int(cmd)
            l, t, r, b = clickable[i]["rect"]
            sh("shell", "input", "tap", str((l + r) // 2), str((t + b) // 2))
            idx += 1
            import time; time.sleep(2.5)
        except (ValueError, IndexError):
            print("无效输入")


if __name__ == "__main__":
    main()
