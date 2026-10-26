# -*- coding: utf-8 -*-
"""g_scan.py - 带跑辅助：扫描当前页文本节点（含 bounds），可按关键词过滤。

用法：
    python devtools/g_scan.py                # 全部文本节点
    python devtools/g_scan.py 打卡 签到       # 只看含这些关键词的节点
    python devtools/g_scan.py --click 打卡   # 点第一个文本恰为「打卡」的节点
"""
import sys
import time

import uiautomator2 as u2
import xml.etree.ElementTree as ET

SERIAL = "192.168.1.54:5555"


def walk(node, out):
    text = (node.get("text") or "").strip()
    desc = (node.get("content-desc") or "").strip()
    bounds = node.get("bounds") or ""
    if text or desc:
        out.append({
            "text": text,
            "desc": desc,
            "bounds": bounds,
            "clickable": node.get("clickable"),
        })
    for child in node:
        walk(child, out)


def center(bounds):
    try:
        left_top, right_bottom = bounds.split("][")
        x1, y1 = [int(v) for v in left_top.strip("[]").split(",")]
        x2, y2 = [int(v) for v in right_bottom.strip("[]").split(",")]
        return (x1 + x2) // 2, (y1 + y2) // 2
    except Exception:
        return None


def main():
    args = [a for a in sys.argv[1:]]
    do_click = "--click" in args
    args = [a for a in args if a != "--click"]
    keywords = args

    d = u2.connect(SERIAL)
    print("activity:", d.app_current().get("activity"))
    root = ET.fromstring(d.dump_hierarchy())
    nodes = []
    walk(root, nodes)
    print("total nodes:", len(nodes))

    hits = nodes
    if keywords:
        hits = [n for n in nodes if any(k in (n["text"] + n["desc"]) for k in keywords)]

    for n in hits[:60]:
        c = center(n["bounds"])
        print(f"{n['text'][:30]:32s}| {n['desc'][:16]:18s}| {n['bounds']:24s}| cl={n['clickable']} c={c}")

    if do_click and keywords:
        target = None
        for n in hits:
            if n["text"] == keywords[0]:
                target = n
                break
        if target is None and hits:
            target = hits[0]
        if target:
            c = center(target["bounds"])
            print("clicking", target["text"], c)
            d.click(*c)
            time.sleep(2)


if __name__ == "__main__":
    main()
