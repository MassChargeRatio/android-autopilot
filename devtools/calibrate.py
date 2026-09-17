# -*- coding: utf-8 -*-
"""calibrate.py - 单 App 实跑校准

做什么：
  1. 启动目标 App，等开屏/广告自然结束（不按 BACK，按交接文档坑5）；
  2. 尝试点掉常见弹窗（青少年模式/隐私政策/更新提示等）；
  3. dump UI 层级 + 截图，落盘到 devtools/calib/<app>/；
  4. 用**工程真实的选择器语义**逐条校验 config.yaml 里该 App 的每个行为动作能否命中；
  5. 抽取页面上的"候选锚点"（签到/提现/金币/看视频/我的…）及其坐标，供补配置用。

用法：
    python devtools/calibrate.py --app 红果免费短剧
    python devtools/calibrate.py --apps 星图金融,微博移动版,一淘
    python devtools/calibrate.py --app 抖音 --wait 25 --no-launch   # 只 dump 当前画面
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

ADB_PATH = None
try:
    from adbkit import resolve_adb
    ADB_PATH = resolve_adb()
    os.environ.setdefault("ADBUTILS_ADB_PATH", ADB_PATH)
except Exception:
    pass

CALIB_DIR = os.path.join(HERE, "calib")

# 常见拦截弹窗的按钮文案（按顺序尝试点击）
POPUP_TEXTS = ["同意并继续", "同意", "我知道了", "知道了", "我已知晓", "继续",
               "以后再说", "暂不", "暂不开启", "稍后再说", "跳过", "关闭",
               "取消", "不再提醒", "允许", "仅在使用中允许", "始终允许"]

# 抽取候选锚点用的兴趣关键词
INTEREST_KEYWORDS = [
    "签到", "每日签到", "立即签到", "打卡", "提现", "立即提现", "去提现",
    "领", "领取", "领取奖励", "领金币", "领红包", "金币", "元", "现金",
    "看视频", "看广告", "看剧", "去完成", "去逛逛", "任务", "福利", "红包",
    "我的", "赚钱", "开宝箱", "抽奖", "转盘", "新人",
]

BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")


def safe_name(name: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff.-]", "_", name)


def load_apps(config_path):
    try:
        import yaml
    except ImportError:
        import miniyaml as yaml  # type: ignore
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def parse_nodes(xml_text, drop_statusbar=True):
    """解析 UI dump，返回节点列表（含 text/desc/rid/clickable/center）。

    drop_statusbar：丢弃状态栏区域（y 底部 < 120）的节点。
    否则系统通知文案（"XX通知：现金提现倒计时"）会污染候选锚点列表，
    造成"提现/签到 锚点已存在"的假象。
    """
    nodes = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return nodes
    for el in root.iter("node"):
        a = el.attrib
        m = BOUNDS_RE.match(a.get("bounds", ""))
        if not m:
            continue
        x1, y1, x2, y2 = (int(v) for v in m.groups())
        if drop_statusbar and y2 < 120:
            continue
        nodes.append({
            "text": a.get("text", "") or "",
            "desc": a.get("content-desc", "") or "",
            "rid": a.get("resource-id", "") or "",
            "cls": a.get("class", "") or "",
            "clickable": a.get("clickable", "") == "true",
            "bounds": (x1, y1, x2, y2),
            "center": ((x1 + x2) // 2, (y1 + y2) // 2),
            "size": (x2 - x1, y2 - y1),
        })
    return nodes


PKG_ATTR_RE = re.compile(r'package="([^"]+)"')
# 系统 UI 包不算"页面属于谁"的依据
SYS_PKGS = {"com.android.systemui", "com.vivo.upslide", "android",
            "com.android.launcher3", "com.bbk.launcher2"}


def package_profile(xml_text):
    """统计 dump 里各 package 出现的节点数，排除系统 UI。返回 {pkg: count}。"""
    from collections import Counter
    c = Counter(m for m in PKG_ATTR_RE.findall(xml_text or "")
                if m not in SYS_PKGS)
    return dict(c)


def dominant_package(xml_text):
    """返回 dump 里出现次数最多的 App 包名（即"屏幕上实际是谁"）。

    用途：跨 App 污染检测。目标 App 启动失败/崩溃时，前台会停留在上一个 App，
    两个 App 会得到完全相同的坐标（看似合理、实为垃圾数据）。
    uiautomator2 的 currentPackageName 在这种时序下可能已报新包名，
    所以必须从 dump 本身判断。
    """
    prof = package_profile(xml_text)
    return max(prof, key=prof.get) if prof else ""


def page_belongs_to(xml_text, pkg, ratio=0.5):
    """判断 dump 出来的页面是否确实属于 pkg。

    允许目标包不是"唯一"的（WebView 内嵌、系统控件），
    只要目标包出现、且其节点数不低于主导包的 ratio 倍即可。
    返回 (是否属于, 主导包名, 目标包节点数, 主导包节点数)
    """
    prof = package_profile(xml_text)
    if not prof:
        return False, "", 0, 0
    dom = max(prof, key=prof.get)
    mine = prof.get(pkg, 0)
    dom_n = prof[dom]
    if dom == pkg:
        return True, dom, mine, dom_n
    return (mine > 0 and mine >= dom_n * ratio), dom, mine, dom_n


def match_selector(nodes, kind, value):
    """按工程语义匹配：text=textContains / id=resourceId(精确) / desc=descContains"""
    hits = []
    for n in nodes:
        if kind == "text" and value and value in n["text"]:
            hits.append(n)
        elif kind == "id" and value and value == n["rid"]:
            hits.append(n)
        elif kind == "desc" and value and value in n["desc"]:
            hits.append(n)
    return hits


def parse_sel(sel):
    sel = str(sel)
    if "=" in sel:
        k, _, v = sel.partition("=")
        if k.strip().lower() in ("text", "id", "desc"):
            return k.strip().lower(), v.strip()
    return "text", sel


def check_actions(app_cfg, nodes):
    """逐行为/逐动作校验，返回 [(behavior, idx, action, status, detail)]"""
    out = []
    behaviors = app_cfg.get("behaviors") or {}
    for bid, actions in behaviors.items():
        if not actions:
            continue
        # 行为支持「多候选模板」[[..],[..]]
        variants = actions if all(isinstance(a, list) for a in actions) else [actions]
        for vi, variant in enumerate(variants):
            for i, act in enumerate(variant or []):
                if not isinstance(act, dict):
                    continue
                t = act.get("type")
                if t == "click_text":
                    hits = match_selector(nodes, "text", act.get("text", ""))
                    out.append((bid, vi, i, act, "命中" if hits else "未命中",
                                f"text={act.get('text')!r} "
                                f"候选数={len(hits)}" +
                                (f" 首个坐标={hits[0]['center']}" if hits else "")))
                elif t == "click_id":
                    hits = match_selector(nodes, "id", act.get("res_id", ""))
                    out.append((bid, vi, i, act, "命中" if hits else "未命中",
                                f"id={act.get('res_id')!r} 候选数={len(hits)}"))
                elif t == "click_desc":
                    hits = match_selector(nodes, "desc", act.get("desc", ""))
                    out.append((bid, vi, i, act, "命中" if hits else "未命中",
                                f"desc={act.get('desc')!r} 候选数={len(hits)}"))
                elif t == "click_first":
                    cands = act.get("candidates") or []
                    found = None
                    for c in cands:
                        if not isinstance(c, dict):
                            continue
                        hits = match_selector(nodes, c.get("type", "text"),
                                              c.get("value", ""))
                        if hits:
                            found = (c, hits[0])
                            break
                    out.append((bid, vi, i, act, "命中" if found else "未命中",
                                f"candidates={[c.get('value') for c in cands if isinstance(c, dict)]} "
                                + (f"-> {found[0].get('value')!r} @{found[1]['center']}"
                                   if found else "")))
                elif t == "any_of":
                    # 条件分支：任一分支里的锚点命中即算命中
                    choices = act.get("choices") or []
                    found = None
                    tried = []
                    for ci, ch in enumerate(choices):
                        steps = ch if isinstance(ch, list) else [ch]
                        for a in steps:
                            if not isinstance(a, dict):
                                continue
                            at = a.get("type")
                            if at == "click_first":
                                for c in a.get("candidates") or []:
                                    if not isinstance(c, dict):
                                        continue
                                    hits = match_selector(
                                        nodes, c.get("type", "text"),
                                        c.get("value", ""))
                                    tried.append(c.get("value"))
                                    if hits:
                                        found = (f"分支#{ci + 1}", c.get("value"),
                                                 hits[0])
                                        break
                            elif at == "click_text":
                                hits = match_selector(nodes, "text",
                                                      a.get("text", ""))
                                tried.append(a.get("text"))
                                if hits:
                                    found = (f"分支#{ci + 1}", a.get("text"),
                                             hits[0])
                            elif at == "click_id":
                                hits = match_selector(nodes, "id",
                                                      a.get("res_id", ""))
                                tried.append(a.get("res_id"))
                                if hits:
                                    found = (f"分支#{ci + 1}", a.get("res_id"),
                                             hits[0])
                            elif at == "click_desc":
                                hits = match_selector(nodes, "desc",
                                                      a.get("desc", ""))
                                tried.append(a.get("desc"))
                                if hits:
                                    found = (f"分支#{ci + 1}", a.get("desc"),
                                             hits[0])
                            if found:
                                break
                        if found:
                            break
                    out.append((bid, vi, i, act, "命中" if found else "未命中",
                                f"any_of 分支数={len(choices)} 试过={tried} "
                                + (f"-> {found[0]} {found[1]!r} @{found[2]['center']}"
                                   if found else "")))
                elif t == "click_point":
                    imgs = act.get("images") or ([act["template"]]
                                                 if act.get("template") else [])
                    out.append((bid, vi, i, act, "图片模板",
                                f"需 OpenCV 模板匹配，图数={len(imgs)}: {imgs[:2]}"))
                elif t in ("wait", "think", "swipe", "swipe_natural", "back",
                           "home", "random", "ensure", "scroll_to"):
                    out.append((bid, vi, i, act, "无需锚点", t))
                elif t == "reward":
                    pat = act.get("pattern", "")
                    hit = re.search(pat, " ".join(n["text"] for n in nodes)) \
                        if pat else None
                    out.append((bid, vi, i, act, "命中" if hit else "未命中",
                                f"pattern={pat!r} 当前页文本"
                                + (f" -> {hit.group(0)!r}" if hit else "无匹配")))
                else:
                    out.append((bid, vi, i, act, "跳过", f"type={t}"))
    return out


def extract_anchors(nodes):
    """抽取页面上的候选锚点（可点击或带关键词的节点）。"""
    seen, out = set(), []
    for n in nodes:
        label = (n["text"] or n["desc"]).strip()
        if not label:
            continue
        hit_kw = [k for k in INTEREST_KEYWORDS if k in label]
        if not hit_kw and not n["clickable"]:
            continue
        key = (label, n["center"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "label": label[:40],
            "rid": n["rid"],
            "center": n["center"],
            "size": n["size"],
            "clickable": n["clickable"],
            "kw": hit_kw,
        })
    # 关键词命中的优先
    out.sort(key=lambda x: (len(x["kw"]) == 0, -len(x["kw"]), x["center"][1]))
    return out[:60]


def dismiss_popups(d, nodes, log):
    """按文案点掉常见弹窗；不按 BACK（交接文档坑5）。"""
    for txt in POPUP_TEXTS:
        for n in nodes:
            label = (n["text"] or n["desc"]).strip()
            if label == txt and n["clickable"]:
                log.append(f"点掉弹窗按钮: {txt} @{n['center']}")
                d.click(*n["center"])
                time.sleep(1.2)
                return True
    return False


def entry_hit_rate(checks):
    """入口命中率：每个行为**第一个带锚点的动作**是否命中。

    静态单次 dump 只能校验"落在落地页上的动作"，即各行为的入口步；
    后续步骤依赖前一步跳转后的页面，必须实跑才能校验。
    因此入口命中率才是本次校准的可信指标。
    """
    firsts = {}
    for c in checks:
        if c[4] not in ("命中", "未命中"):
            continue
        firsts.setdefault(c[0], c)
    total = len(firsts)
    hit = sum(1 for c in firsts.values() if c[4] == "命中")
    return hit, total, firsts


def wait_ready(d, pkg, max_wait, min_nodes, log, poll=3.0):
    """自适应等待 App 就绪。

    为什么不用固定 sleep：重型 App（抖音/头条系）冷启动常超过 18s，
    固定等待会 dump 到启动页（只有 15 个节点），校准结果全是"未命中"。
    这里轮询 dump，满足任一条件即认为就绪：
      - 节点数 >= min_nodes 且前台包名是目标包（或包含目标包）
      - dump 中出现任一兴趣关键词（说明内容页已渲染）
    上限 max_wait 秒。返回最终 (xml, nodes, 实际等待秒数)。
    """
    t0 = time.time()
    last_nodes, last_xml = [], ""
    while True:
        try:
            last_xml = d.dump_hierarchy()
            last_nodes = parse_nodes(last_xml)
            fg = ""
            try:
                fg = d.info.get("currentPackageName") or ""
            except Exception:
                pass
            text_blob = " ".join(n["text"] for n in last_nodes)
            kw_hit = any(k in text_blob for k in INTEREST_KEYWORDS)
            pkg_ok = (not pkg) or (fg == pkg) or (pkg in fg)
            elapsed = time.time() - t0
            if len(last_nodes) >= min_nodes and pkg_ok:
                log.append(f"就绪判定: 节点={len(last_nodes)} 前台={fg} "
                           f"耗时={elapsed:.1f}s（节点数达标）")
                return last_xml, last_nodes, elapsed
            if kw_hit and pkg_ok and len(last_nodes) >= 10:
                log.append(f"就绪判定: 节点={len(last_nodes)} 前台={fg} "
                           f"耗时={elapsed:.1f}s（命中兴趣关键词）")
                return last_xml, last_nodes, elapsed
        except Exception as e:
            log.append(f"等待中就绪探测异常: {type(e).__name__}: {e}")
        if time.time() - t0 >= max_wait:
            log.append(f"达到最大等待 {max_wait}s 仍未就绪，"
                       f"节点={len(last_nodes)}，按当前页继续")
            return last_xml, last_nodes, time.time() - t0
        time.sleep(poll)


def probe_after(d, prompt, wait, log, vision_cfg):
    """用 VLM 定位并点击一个入口，然后 dump 跳转后的页面。

    为什么需要：签到/提现这类入口几乎都在二级页（"我的"/"赚钱"），
    落地页 dump 里根本没有这些锚点，只校验落地页必然全"未命中"。
    这里用已校准好的 VLM 兜底（0~1000 归一化，实测误差 ~10px）点进去，
    再 dump 一页，才能拿到二级页的真实锚点。

    提示词回退：各 App 底栏标签写法不一（"我的"/"我"/"个人中心"），
    只用一个提示词会在部分 App 上全部未命中，故按顺序尝试多个写法。
    """
    try:
        import vision as vs
    except ImportError:
        log.append("probe: 无法导入 vision 模块，跳过探针")
        return None, [], None
    loc = vs.VisionLocator(vision_cfg or {}, base_dir=ROOT)
    if not loc.enabled or not loc.vlm_available:
        log.append("probe: VLM 未启用/不可用，跳过探针")
        return None, [], None

    prompts = [prompt,
               "定位屏幕底部导航栏最右侧的『我』标签中心",
               "定位屏幕底部导航栏的个人中心（我的）标签中心",
               "定位屏幕右下角的个人中心头像/图标中心"]
    hit = None
    used = None
    for p in prompts:
        try:
            img = d.screenshot()
        except Exception as e:
            log.append(f"probe: 截图失败 {e}")
            return None, [], None
        hit = loc.locate_on_screen(prompt=p, screen_img=img,
                                   app="calibrate", tag="probe")
        if hit is not None:
            used = p
            break
        log.append(f"probe: 提示词未命中，尝试下一个 -> {p}")
    if hit is None:
        log.append("probe: 全部提示词均未命中")
        return None, [], None
    log.append(f"probe: VLM 命中『{used}』-> ({hit.x},{hit.y})，点击并等待 {wait}s")
    d.click(hit.x, hit.y)
    time.sleep(wait)
    xml = d.dump_hierarchy()
    return xml, parse_nodes(xml), (hit.x, hit.y)


def connect_device(serial, retries=3):
    """连接设备，带自愈重试。

    本机环境特有坑：每条独立 shell 命令结束后 adb daemon 会被回收，
    uiautomator2/adbutils 若正好连到"将死的" daemon，会抛
    ConnectionResetError(WinError 10054)。这里先用 adbkit 显式
    start-server + connect，失败则 kill-server 重来。
    """
    import uiautomator2 as u2
    last = None
    for i in range(retries):
        try:
            if ADB_PATH:
                os.environ["ADBUTILS_ADB_PATH"] = ADB_PATH
            try:
                from adbkit import Adb
                Adb(serial=serial, adb_path=ADB_PATH).ensure()
            except Exception as e:
                print(f"  adb 预连接失败（{type(e).__name__}: {e}），继续尝试 u2")
            d = u2.connect(serial)
            _ = d.info  # 触发一次真实通信，确认链路可用
            return d
        except Exception as e:
            last = e
            print(f"  连接失败（第 {i + 1}/{retries} 次）: "
                  f"{type(e).__name__}: {e}")
            try:
                from adbkit import Adb
                a = Adb(serial=serial, adb_path=ADB_PATH)
                a.run(["kill-server"], timeout=20)
                time.sleep(1.5)
                a.ensure()
            except Exception:
                pass
            time.sleep(2)
    raise RuntimeError(f"设备连接失败（已重试 {retries} 次）: {last}")


def calibrate(app_cfg, args, d):
    name = app_cfg.get("name") or "?"
    pkg = app_cfg.get("package") or ""
    outdir = os.path.join(CALIB_DIR, safe_name(name))
    os.makedirs(outdir, exist_ok=True)
    log = []

    if not args.no_launch:
        d.press("home")
        time.sleep(1.5)
        try:
            d.app_start(pkg, stop=True)
            log.append(f"已启动 {name} ({pkg})")
        except Exception as e:
            log.append(f"启动失败: {type(e).__name__}: {e}")
        if args.fixed_wait:
            log.append(f"固定等待 {args.wait}s（不按 BACK）")
            time.sleep(args.wait)
            xml = nodes = None
        else:
            log.append(f"自适应等待就绪（上限 {args.max_wait}s，"
                       f"最小节点数 {args.min_nodes}；不按 BACK）")
            xml, nodes, waited = wait_ready(
                d, pkg, args.max_wait, args.min_nodes, log)

    # 弹窗处理最多 3 轮
    for rnd in range(3):
        xml = d.dump_hierarchy()
        nodes = parse_nodes(xml)
        if not dismiss_popups(d, nodes, log):
            break
        time.sleep(2)

    xml = d.dump_hierarchy()
    nodes = parse_nodes(xml)
    shot = os.path.join(outdir, "screen.png")
    try:
        d.screenshot(shot)
    except Exception as e:
        log.append(f"截图失败: {e}")
    with open(os.path.join(outdir, "ui.xml"), "w", encoding="utf-8") as f:
        f.write(xml)

    cur_pkg = ""
    try:
        cur_pkg = d.info.get("currentPackageName") or ""
    except Exception:
        pass
    # 归属判定以 dump 自身为准：崩溃/切换时序下 currentPackageName 会失真，
    # 会把「上一个 App 的页面」当成目标 App 的落地页，产出垃圾锚点。
    page_ok, dom_pkg, mine_n, dom_n = page_belongs_to(xml, pkg)
    if not page_ok:
        log.append(f"⚠ 页面归属校验失败: dump 主导包={dom_pkg}（{dom_n} 节点），"
                   f"目标包 {pkg} 仅 {mine_n} 节点，前台={cur_pkg or '?'}"
                   f" -> 本份 dump 判定为**污染**，锚点结论不可用")

    checks = check_actions(app_cfg, nodes)
    anchors = extract_anchors(nodes)
    e_hit, e_total, e_firsts = entry_hit_rate(checks)

    # ---- 可选：二级页探针 ----
    after = None
    if args.probe_vlm:
        axml, anodes, acoord = probe_after(
            d, args.probe_vlm, args.probe_wait, log, args.vision_cfg)
        if anodes:
            with open(os.path.join(outdir, "ui_after.xml"), "w",
                      encoding="utf-8") as f:
                f.write(axml)
            try:
                d.screenshot(os.path.join(outdir, "screen_after.png"))
            except Exception:
                pass
            a_checks = check_actions(app_cfg, anodes)
            a_anchors = extract_anchors(anodes)
            a_hit, a_total, a_firsts = entry_hit_rate(a_checks)
            after = {
                "prompt": args.probe_vlm, "click": acoord,
                "nodes": len(anodes),
                "entry_hit": a_hit, "entry_total": a_total,
                "entry_detail": {k: {"type": v[3].get("type"), "status": v[4],
                                     "detail": v[5]} for k, v in a_firsts.items()},
                "candidate_anchors": a_anchors,
            }
            log.append(f"二级页: 节点={len(anodes)} 入口命中={a_hit}/{a_total}")

    hits = sum(1 for c in checks if c[4] == "命中")
    anchor_req = [c for c in checks if c[4] in ("命中", "未命中")]
    summary = {
        "app": name, "package": pkg, "foreground": cur_pkg,
        "page_owner_ok": page_ok, "dominant_package": dom_pkg,
        "nodes": len(nodes), "anchors": len(anchors),
        "anchor_actions_total": len(anchor_req),
        "anchor_actions_hit": hits,
        "entry_hit": e_hit, "entry_total": e_total,
        "entry_detail": {k: {"type": v[3].get("type"), "status": v[4],
                             "detail": v[5]} for k, v in e_firsts.items()},
        "after": after,
        "log": log,
        "checks": [
            {"behavior": c[0], "variant": c[1], "step": c[2],
             "type": c[3].get("type"), "status": c[4], "detail": c[5]}
            for c in checks],
        "candidate_anchors": anchors,
    }
    with open(os.path.join(outdir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    md = [f"# 校准报告 · {name}", "",
          f"- 包名: `{pkg}`",
          f"- 前台包名: `{cur_pkg or '未知'}`",
          f"- 页面归属: {'✅ 属于目标 App' if page_ok else '❌ **污染**'}"
          f"（dump 主导包 `{dom_pkg or '?'}`，目标包 {mine_n} 节点 / "
          f"主导包 {dom_n} 节点）",
          f"- UI 节点数: {len(nodes)}（已剔除状态栏通知）",
          f"- **入口命中率: {e_hit}/{e_total}**"
          f"（每个行为首个锚点动作是否在落地页命中）",
          f"- 全部锚点类动作命中: {hits}/{len(anchor_req)}"
          f"（后续步骤需跳转后页面，静态 dump 校验不了）", ""]
    if log:
        md += ["## 过程日志", ""] + [f"- {x}" for x in log] + [""]
    md += ["## 入口校验（关键）", "",
           "| 行为 | 类型 | 结果 | 详情 |", "|---|---|---|---|"]
    for k, v in e_firsts.items():
        md.append(f"| {k} | {v[3].get('type')} | {v[4]} | {v[5]} |")
    md += ["", "## 全部动作校验", "",
           "| 行为 | 模板 | 步 | 类型 | 结果 | 详情 |",
           "|---|---|---|---|---|---|"]
    for c in checks:
        md.append(f"| {c[0]} | {c[1]+1} | {c[2]} | {c[3].get('type')} | "
                  f"{c[4]} | {c[5]} |")
    md += ["", "## 页面候选锚点（前 40）", "",
           "| 文案 | resource-id | 中心坐标 | 尺寸 | 可点击 | 关键词 |",
           "|---|---|---|---|---|---|"]
    for a in anchors[:40]:
        md.append(f"| {a['label']} | `{a['rid'][:48]}` | {a['center']} | "
                  f"{a['size']} | {a['clickable']} | {','.join(a['kw'])} |")

    if after:
        md += ["", f"## 二级页（点击『{after['prompt']}』后）", "",
               f"- VLM 命中坐标: {after['click']}",
               f"- 节点数: {after['nodes']}",
               f"- **二级页入口命中: {after['entry_hit']}/{after['entry_total']}**",
               "", "| 行为 | 类型 | 结果 | 详情 |", "|---|---|---|---|"]
        for k, v in after["entry_detail"].items():
            md.append(f"| {k} | {v.get('type')} | {v.get('status')} | "
                      f"{v.get('detail')} |")
        md += ["", "| 二级页候选锚点 | resource-id | 中心坐标 | 可点击 | 关键词 |",
               "|---|---|---|---|---|"]
        for a in after["candidate_anchors"][:40]:
            md.append(f"| {a['label']} | `{a['rid'][:48]}` | {a['center']} | "
                      f"{a['clickable']} | {','.join(a['kw'])} |")

    with open(os.path.join(outdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print(f"[{name}] 前台={cur_pkg or '?'} 节点={len(nodes)} "
          + ("" if page_ok else f"[污染 主导={dom_pkg}] ")
          + f"入口命中={e_hit}/{e_total} 锚点动作命中={hits}/{len(anchor_req)}"
          + (f" 二级页命中={after['entry_hit']}/{after['entry_total']}"
             if after else "") + f" 报告={outdir}")
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default=None)
    ap.add_argument("--apps", default=None, help="逗号分隔多个 App 名")
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--serial", default=None)
    ap.add_argument("--wait", type=float, default=18.0,
                    help="固定等待秒数（配合 --fixed-wait 使用）")
    ap.add_argument("--fixed-wait", action="store_true",
                    help="改用固定等待而非自适应等待")
    ap.add_argument("--max-wait", type=float, default=70.0,
                    help="自适应等待上限秒数（默认 70s）")
    ap.add_argument("--min-nodes", type=int, default=40,
                    help="判定就绪的最小 UI 节点数（默认 40）")
    ap.add_argument("--probe-vlm", default=None,
                    help="二级页探针：用 VLM 定位并点击该描述的目标后，"
                         "再 dump 一页（如「定位底部导航栏最右侧的『我的』标签中心」）")
    ap.add_argument("--probe-wait", type=float, default=6.0,
                    help="探针点击后等待秒数（默认 6s）")
    ap.add_argument("--no-launch", action="store_true",
                    help="不启动 App，只 dump 当前画面")
    args = ap.parse_args()

    cfg = load_apps(args.config)
    apps = cfg.get("apps") or []
    serial = args.serial or (cfg.get("device") or {}).get("serial")
    args.vision_cfg = cfg.get("vision") or {}

    want = []
    if args.apps:
        want = [x.strip() for x in args.apps.split(",") if x.strip()]
    elif args.app:
        want = [args.app]
    if want:
        picked = []
        for w in want:
            for a in apps:
                if a.get("name") == w or w in (a.get("aliases") or []):
                    picked.append(a)
                    break
            else:
                print(f"!! 配置中找不到 App: {w}")
        apps = picked

    if not apps:
        print("没有要校准的 App")
        return 1

    import uiautomator2 as u2  # noqa: F401
    d = connect_device(serial)
    print(f"设备已连接: {d.info.get('displayWidth')}x"
          f"{d.info.get('displayHeight')}  待校准 {len(apps)} 个 App")

    results = []
    for i, a in enumerate(apps, 1):
        print(f"\n===== [{i}/{len(apps)}] {a.get('name')} =====")
        try:
            results.append(calibrate(a, args, d))
        except Exception as e:
            print(f"!! {a.get('name')} 校准异常: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("汇总（入口命中率 = 每个行为首个锚点动作是否在落地页命中）")
    print("=" * 60)
    tot_h = tot_t = bad = 0
    for r in results:
        tot_h += r["entry_hit"]
        tot_t += r["entry_total"]
        flag = ""
        if not r.get("page_owner_ok", True):
            bad += 1
            flag = f"  ❌污染(主导={r.get('dominant_package') or '?'})"
        print(f"  {r['app']:16} 入口 {r['entry_hit']:2}/{r['entry_total']:2}  "
              f"节点 {r['nodes']:5}  前台 {r['foreground'] or '?'}{flag}")
    if tot_t:
        print(f"\n  合计入口命中率: {tot_h}/{tot_t} = {tot_h / tot_t * 100:.0f}%")
    if bad:
        print(f"  ⚠ 其中 {bad} 个 App 的 dump 页面不属于目标 App，结论不可用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
