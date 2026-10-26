# -*- coding: utf-8 -*-
"""probe_path_u2.py - 用 uiautomator2 按文案路径走屏 dump 锚点（走项目真实链路）

用法: python probe_path_u2.py <serial> <pkg> <app_name> <text1> <text2> ...
每屏 dump_xml，按 text/desc/id 精确->包含匹配点击；未命中打印本屏可点元素。
"""
import os
import sys
import time

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJ)
OUT = os.path.join(PROJ, "devtools", "calib", "uiprobe")


def parse_nodes(xml):
    import re
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
                    "clickable": g("clickable") == "true", "rect": (l, t, r, bo)})
    return out


def find_and_tap(d, label):
    xml = d.dump_hierarchy()
    nodes = parse_nodes(xml)
    cands = [n for n in nodes if (n["text"] or n["desc"] or "").strip() == label]
    if not cands:
        cands = [n for n in nodes if label and label in (n["text"] or n["desc"] or "")]
    if not cands:
        return None, nodes
    cands.sort(key=lambda n: (not n["clickable"], -len(n["text"] or n["desc"] or "")))
    n = cands[0]
    l, t, r, b = n["rect"]
    d.click((l + r) // 2, (t + b) // 2)
    return n, nodes


def dump(d, idx, pkg, app_name):
    xml = d.dump_hierarchy()
    dd = os.path.join(OUT, pkg.replace(".", "_"))
    os.makedirs(dd, exist_ok=True)
    open(os.path.join(dd, f"{idx:02d}.xml"), "w", encoding="utf-8").write(xml)
    png = d.screenshot()
    png.save(os.path.join(dd, f"{idx:02d}.png"))
    return xml


def has_text(xml, kw):
    return kw in xml


def skip_splash(d, max_rounds=10):
    """开屏广告处理：优先文案节点，其次右下角坐标(1080x2340基准按比例)。"""
    for i in range(max_rounds):
        xml = d.dump_hierarchy()
        nodes = parse_nodes(xml)
        hit = None
        for n in nodes:
            lab = (n["text"] or n["desc"] or "").strip()
            if lab in ("跳过", "跳过广告", "skip", "Skip", "关闭广告"):
                hit = n
                break
        if hit:
            l, t, r, b = hit["rect"]
            print(f"   [splash] 文案命中 {hit['text'] or hit['desc']!r} @{hit['rect']}")
            d.click((l + r) // 2, (t + b) // 2)
        elif "广告" in xml and "跳过" in xml:
            pass  # 上面的循环已覆盖
        elif has_text(xml, "广告") or len(nodes) < 5:
            # 自定义绘制广告：XML 不可点，按右下角比例点击
            w, h = d.info["displayWidth"], d.info["displayHeight"]
            print(f"   [splash] 自定义广告，点击右下角 x={int(w*.93)} y={int(h*.915)}")
            d.click(int(w * 0.93), int(h * 0.915))
        else:
            return True  # 无广告特征
        time.sleep(2)
    return False


def main():
    import uiautomator2 as u2
    serial, pkg, app_name, *labels = sys.argv[1:]
    d = u2.connect(serial)
    d.app_stop(pkg)
    d.app_start(pkg)
    time.sleep(5)
    if not skip_splash(d):
        print("!! 开屏广告未跳过")
    time.sleep(2)
    xml = dump(d, 0, pkg, app_name)
    for i, label in enumerate(labels, 1):
        hit, _ = find_and_tap(d, label)
        if hit:
            lab = hit["text"] or hit["desc"] or hit["id"]
            print(f"--- [{i}] {label!r} -> 命中 {lab!r} @{hit['rect']}")
            time.sleep(3)
            xml = dump(d, i, pkg, app_name)
        else:
            print(f"--- [{i}] {label!r} -> 未命中!")
            nodes = parse_nodes(xml)
            shown = [x for x in nodes if (x["text"] or x["desc"] or "").strip()]
            if not shown:
                shown = nodes
            for n in shown[:60]:
                lab = n["text"] or n["desc"] or n["id"]
                print(f"   {'C' if n['clickable'] else '-'} {lab!r} id={n['id'].split('/')[-1]} rect={n['rect']}")
            break
    print(f"DONE -> devtools/calib/uiprobe/{pkg.replace('.', '_')}/")


if __name__ == "__main__":
    main()
