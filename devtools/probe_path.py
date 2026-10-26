# -*- coding: utf-8 -*-
"""probe_path.py - 按文案路径自动走屏并 dump 每屏锚点

用法: python probe_path.py <serial> <pkg> <app_name> <text1> <text2> ...
每屏解析可点元素，按文案匹配(text/desc/id 精确优先、包含次之)点击；
未命中则把该屏可点元素全打印出来(便于补候选)。
"""
import os
import re
import subprocess
import sys
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADB = os.path.join(PROJ, "tools", "platform-tools", "adb.exe")
OUT = os.path.join(PROJ, "devtools", "calib", "uiprobe")
SERIAL = None


def sh(*args):
    return subprocess.run([ADB, "-s", SERIAL, *args], capture_output=True,
                          text=True, timeout=60, encoding="utf-8", errors="replace").stdout


def sh_bin(*args):
    return subprocess.run([ADB, "-s", SERIAL, *args], capture_output=True, timeout=60).stdout


def parse_nodes(xml):
    out = []
    for m in re.finditer(r'<node\b[^>]*>', xml):
        tag = m.group(0)
        g = lambda k: (re.search(k + r'="([^"]*)"', tag) or [None, ""])[1]
        text, rid, desc = g("text"), g("resource-id"), g("content-desc")
        b = g("bounds")
        mm = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b)
        if not mm:
            continue
        l, t, r, bo = map(int, mm.groups())
        out.append({"text": text, "id": rid, "desc": desc, "click": g("clickable"),
                    "rect": (l, t, r, bo)})
    return out


def dump(idx, pkg, app_name):
    subprocess.run([ADB, "-s", SERIAL, "shell", "uiautomator", "dump",
                    "/sdcard/_probe.xml"], capture_output=True, timeout=60)
    xml = sh_bin("exec-out", "cat", "/sdcard/_probe.xml").decode("utf-8", "replace")
    d = os.path.join(OUT, pkg.replace(".", "_"))
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"{idx:02d}.xml"), "w", encoding="utf-8").write(xml)
    open(os.path.join(d, f"{idx:02d}.png"), "wb").write(
        sh_bin("exec-out", "screencap", "-p"))
    return xml


def find_and_tap(nodes, label):
    cands = [n for n in nodes if (n["text"] or n["desc"] or n["id"]).strip() == label]
    if not cands:
        cands = [n for n in nodes if label in (n["text"] or n["desc"] or "")]
    if not cands:
        return None
    # 优先可点击、短的文案（同 _pick_best 精神）
    cands.sort(key=lambda n: (n["click"] != "true",
                              -len(n["text"] or n["desc"] or "")))
    n = cands[0]
    l, t, r, b = n["rect"]
    sh("shell", "input", "tap", str((l + r) // 2), str((t + b) // 2))
    return n


def main():
    global SERIAL
    SERIAL, pkg, app_name, *labels = sys.argv[1:]
    sh("shell", "am", "force-stop", pkg)
    sh("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(5)
    xml = dump(0, pkg, app_name)
    for i, label in enumerate(labels, 1):
        nodes = parse_nodes(xml)
        hit = find_and_tap(nodes, label)
        if hit:
            lab = hit['text'] or hit['desc'] or hit['id']
            msg = f"\n--- 目标[{i}] {label!r} -> 命中 {lab!r} @{hit['rect']}"
        else:
            msg = f"\n--- 目标[{i}] {label!r} -> 未命中!"
        print(msg)
        if not hit:
            print("本屏可点元素(前40):")
            for n in [x for x in nodes if x["click"] == "true"][:40]:
                lab = n["text"] or n["desc"] or n["id"]
                print(f"   {lab!r} id={n['id'].split('/')[-1]} rect={n['rect']}")
            break
        time.sleep(3)
        xml = dump(i, pkg, app_name)
    print(f"\nDONE dumps -> devtools/calib/uiprobe/{pkg.replace('.', '_')}/")


if __name__ == "__main__":
    main()
