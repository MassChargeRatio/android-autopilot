# -*- coding: utf-8 -*-
"""dump 当前屏(桌面/文件夹)可点击节点, 提取图标名与 bounds → 供包名枚举与文件夹判断。
用法: python adb_dump_icons.py [输出xml]
背景: 桌面图标节点常见 text="" bounds=...; 文件夹为 clickable 大节点; "没写/运行未通过"多为文件夹误判。
补充: 需结合截图(裁剪 bounds)+VLM 交叉确认, 避免仅凭 XML 臆断包名。
"""
import subprocess, sys, os, re, xml.etree.ElementTree as ET

ADB = r"C:\Users\Administrator\platform-tools\platform-tools\adb.exe"
DEV = "192.168.1.54:5555"
TMP = r"C:\Users\Administrator\AppData\Roaming\Tencent\Marvis\User\oAN1i2QfS5SbEiQu-VJk4vqp2ZnI\workspace\conv_277511131d59420bac41e2e16244f382\temp"


def adb(args, t=60):
    return subprocess.run([ADB, "-s", DEV, "shell"] + args, capture_output=True, timeout=t)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TMP, "ui_dump.xml")
    r = adb(["uiautomator", "dump", "/sdcard/ui_tmp.xml"])
    if r.returncode != 0:
        print("[FAIL] uiautomator dump:", r.stderr[:300]); return
    pull = subprocess.run([ADB, "-s", DEV, "pull", "/sdcard/ui_tmp.xml", out_path], capture_output=True, timeout=60)
    print("pull exit", pull.returncode)
    tree = ET.parse(out_path)
    # 可点击/可聚焦的叶子节点作为候选图标
    rows = []
    for node in tree.iter("node"):
        if node.get("clickable") == "true":
            text = node.get("text") or ""
            desc = node.get("content-desc") or ""
            label = (text or desc).strip()
            rows.append((node.get("bounds"), label, node.get("package")))
    for b, label, pkg in rows:
        print(b, "|", label, "|", pkg)


if __name__ == "__main__":
    main()
