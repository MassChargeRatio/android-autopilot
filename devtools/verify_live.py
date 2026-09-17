#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""实机锚点验证：对已修补的行为做「真机回归」。

与 calibrate.py 的区别：
  calibrate.py 只校验**落地页**，而签到/看视频/提现这类入口几乎都在二级页
  （底部导航「我的」之后）。本次修补的核心就是「前置导航步 + 追加候选」，
  因此验证必须走完整链路：

      启动 App -> 自适应等待就绪 -> 关闭弹窗 -> dump(落地页)
        -> 校验锚点
          命中  -> 首屏命中
          未命中且该行为有前置步 -> VLM/比例坐标点『我的』-> dump(二级页)
                                   -> 再校验 -> 导航后命中 / 导航后仍未命中
          未命中且无前置步 -> 首屏未命中

用法：
    python devtools/verify_live.py                        # 全部有校准数据的 App
    python devtools/verify_live.py --apps 一淘,河马剧场
    python devtools/verify_live.py --behaviors watch,collect
    python devtools/verify_live.py --out devtools/calib/LIVE_VERIFY.md
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

from calibrate import (  # noqa: E402
    parse_nodes, match_selector, wait_ready, dismiss_popups,
    connect_device, safe_name,
    dominant_package, page_belongs_to,
)
# 页面结构判据与执行器共用同一份实现（度量与执行必须同口径）
from ui_page import NAV_LABELS, NAV_BAND_Y, at_top_level_nodes  # noqa: E402

ANCHOR_TYPES = ("click_text", "click_id", "click_desc", "click_first")
NAV_MARK = "最右侧"

# 底部导航标签（NAV_LABELS）与底部带阈值（NAV_BAND_Y）单一来源在 ui_page.py，
# 上面已 import；此处不再另立一份，避免与执行器口径漂移。

# 前置步兜底坐标。实测各 App『我的』中心 y 分布在 2106~2192，
# 取中位数附近 (0.90, 0.915) 比原来的 0.908 更稳。
MINE_XY = (0.90, 0.915)

NAV_PROMPTS = [
    "定位屏幕底部导航栏最右侧的『我的』标签中心",
    "定位屏幕底部导航栏最右侧的『我』标签中心",
    "定位屏幕底部导航栏的个人中心（我的）标签中心",
]


def _variant_of(actions):
    if not actions:
        return []
    if all(isinstance(a, list) for a in actions):
        return actions[0] or []
    return actions


def first_anchor_action(actions):
    """返回 (索引, 动作)；行为可能是 [[..],[..]] 变体结构。

    `any_of` 也算锚点动作（真正的锚点在其 choices 里），由 check_anchor 展开。
    """
    for i, act in enumerate(_variant_of(actions)):
        if isinstance(act, dict) and act.get("type") in ANCHOR_TYPES + ("any_of",):
            return i, act
    return None, None


def has_prelude(actions):
    """该行为是否带「导航到我的」前置步（含 any_of 分支内的）。"""
    for act in _variant_of(actions):
        if not isinstance(act, dict):
            continue
        if act.get("type") == "click_point" and NAV_MARK in str(act.get("vlm_prompt", "")):
            return True
        if act.get("type") == "any_of":
            for ch in act.get("choices") or []:
                for a in (ch if isinstance(ch, list) else [ch]):
                    if isinstance(a, dict) and a.get("type") == "click_point" \
                            and NAV_MARK in str(a.get("vlm_prompt", "")):
                        return True
    return False


def _anchor_actions_of_branch(steps):
    return [a for a in steps
            if isinstance(a, dict) and a.get("type") in ANCHOR_TYPES]


def mid_entry_of(act):
    """三级导航的**中间入口**动作（没有则返回 None）。

    三级分支形如 `[我的, think, 福利中心, think, 签到]`：
    末位是目标锚点，**中间**那个锚点类动作就是入口。
    verify_live 只走到「我的」是不够的 —— 必须继续点中间入口，
    否则三级行为会被必然误判为未命中。
    """
    if not isinstance(act, dict) or act.get("type") != "any_of":
        return None
    for ch in act.get("choices") or []:
        steps = ch if isinstance(ch, list) else [ch]
        anchors = _anchor_actions_of_branch(steps)
        if len(anchors) > 1:
            return anchors[-2]          # 末位是目标，倒数第二个是入口
    return None


def target_anchor_of(act):
    """取「真正的目标锚点」动作（any_of 则取某分支的末位锚点）。"""
    if isinstance(act, dict) and act.get("type") == "any_of":
        for ch in act.get("choices") or []:
            steps = ch if isinstance(ch, list) else [ch]
            anchors = _anchor_actions_of_branch(steps)
            if anchors:
                return anchors[-1]
        return None
    return act


def find_anchor_node(nodes, act, screen_h=None):
    """返回 (node, detail)；node 为命中的节点（可直接点击），未命中为 None。"""
    t = act.get("type")
    if t == "click_first":
        for c in act.get("candidates") or []:
            if not isinstance(c, dict):
                continue
            kind = c.get("type", "text")
            val = c.get("value", "")
            hits = [h for h in match_selector(nodes, kind, val)
                    if _ok_len(h, val, kind)]
            good = [h for h in hits if _nav_ok(h, val, screen_h)]
            if good:
                return good[0], f"{kind}={val!r} @{good[0]['center']}"
        return None, "candidates 全部未命中"
    if t in ("click_text", "click_desc"):
        kind = "text" if t == "click_text" else "desc"
        val = act.get("text" if kind == "text" else "desc", "")
        hits = [h for h in match_selector(nodes, kind, val)
                if _ok_len(h, val, kind)]
        good = [h for h in hits if _nav_ok(h, val, screen_h)]
        return (good[0], f"{kind}={val!r} @{good[0]['center']}") if good \
            else (None, f"{kind}={val!r} 未命中")
    if t == "click_id":
        hits = match_selector(nodes, "id", act.get("res_id", ""))
        return (hits[0], f"id={act.get('res_id')!r}") if hits else (None, "id 未命中")
    return None, f"非锚点动作 type={t}"


def check_anchor(nodes, act, screen_h=None):
    """按执行器语义校验单个锚点动作，返回 (hit, detail)。

    screen_h 给出时，对**底部导航标签**做位置合理性校验：命中的 y 必须落在
    屏幕底部带（y >= NAV_BAND_Y * screen_h），否则判为假命中。
    """
    t = act.get("type")
    if t == "any_of":
        # 一个分支是否命中，取决于该分支的**最后一个**锚点动作（真正的目标），
        # 而不是中途的入口。
        # 踩坑：三级导航分支形如
        #   [我的, think, 福利中心, think, 签到]
        # 中间那步「福利中心」也是锚点类动作；早期实现"分支里任一锚点命中即算命中"，
        # 于是「福利中心」在落地页出现时就报成 `首屏命中 分支#2: text='福利'`
        # —— 看起来命中，实际签到锚点根本没出现（实测污染了 3 个三级行为）。
        #
        # 另注：convert_deep 生成的两条分支**共用同一个目标锚点**，
        # 所以单份 dump 上分支2不会比分支1多命中；分支2 的价值在于
        # 「换一个页面再找」（由 导航后 复校那一步体现）。
        last = "（无分支）"
        for i, ch in enumerate(act.get("choices") or []):
            steps = ch if isinstance(ch, list) else [ch]
            anchors = [a for a in steps
                       if isinstance(a, dict) and a.get("type") in ANCHOR_TYPES]
            if not anchors:
                continue
            hit, det = check_anchor(nodes, anchors[-1], screen_h)
            if hit:
                return True, f"any_of 分支#{i + 1}: {det}"
            last = det
        return False, f"any_of 全部分支未命中（末次: {last}）"
    if t == "click_first":
        first_miss = None
        for c in act.get("candidates") or []:
            if not isinstance(c, dict):
                continue
            kind = c.get("type", "text")
            val = c.get("value", "")
            hits = match_selector(nodes, kind, val)
            hits = [h for h in hits if _ok_len(h, val, kind)]
            if not hits:
                continue
            good = [h for h in hits if _nav_ok(h, val, screen_h)]
            if good:
                return True, f"{kind}={val!r} @{good[0]['center']}"
            if first_miss is None:
                first_miss = (f"{kind}={val!r} @{hits[0]['center']} "
                              f"但不在底部导航带（y={hits[0]['center'][1]}），"
                              f"疑似假命中")
        if first_miss:
            return False, first_miss
        vals = [c.get("value") for c in act.get("candidates") or []
                if isinstance(c, dict)]
        return False, f"candidates={vals} 全部未命中"
    if t == "click_text":
        return _check_single(nodes, "text", act.get("text", ""),
                             act.get("text", ""), screen_h)
    if t == "click_desc":
        return _check_single(nodes, "desc", act.get("desc", ""),
                             act.get("desc", ""), screen_h)
    if t == "click_id":
        hits = match_selector(nodes, "id", act.get("res_id", ""))
        return (bool(hits),
                f"id={act.get('res_id')!r}" + (f" @{hits[0]['center']}" if hits else " 未命中"))
    return False, f"非锚点动作 type={t}"


def _nav_ok(node, label, screen_h):
    """底部导航标签的位置合理性校验。"""
    if screen_h is None or str(label).strip() not in NAV_LABELS:
        return True
    return node["center"][1] >= NAV_BAND_Y * screen_h


def _check_single(nodes, kind, value, label, screen_h):
    hits = match_selector(nodes, kind, value)
    hits = [h for h in hits if _ok_len(h, value, kind)]
    if not hits:
        return False, f"{kind}={label!r} 未命中"
    good = [h for h in hits if _nav_ok(h, label, screen_h)]
    if good:
        return True, f"{kind}={label!r} @{good[0]['center']}"
    return False, (f"{kind}={label!r} @{hits[0]['center']} "
                   f"但不在底部导航带（y={hits[0]['center'][1]}），疑似假命中")


def _ok_len(node, target, kind):
    """复刻执行器的「长文案拒配」。"""
    if kind not in ("text", "desc"):
        return True
    label = node["text"] if kind == "text" else node["desc"]
    limit = max(len(str(target)) + 6, len(str(target)) * 3)
    if len(label) > limit and not node["clickable"]:
        return False
    return True


def goto_mine(d, vision_cfg, log, use_vlm=True):
    """导航到『我的』：优先 VLM 定位，失败用比例坐标兜底。返回新 dump 的 nodes。

    use_vlm=False 时直接走比例坐标 —— 探路跑批时用，因为本机 VLM 图像请求
    常 90s 超时（一次导航可能耗 9~27 分钟），而比例坐标兜底已被实机验证可靠
    （多数 App 的『我的』就在 x≈0.90 / y≈0.91）。
    """
    x, y = None, None
    if use_vlm:
        try:
            import vision as vs
            loc = vs.VisionLocator(vision_cfg or {}, base_dir=ROOT)
            if loc.enabled and loc.vlm_available:
                img = d.screenshot()
                for p in NAV_PROMPTS:
                    hit = loc.locate_on_screen(prompt=p, screen_img=img,
                                               app="verify", tag="nav")
                    if hit is not None:
                        x, y = hit.x, hit.y
                        log.append(f"导航: VLM 命中『{p}』-> ({x},{y})")
                        break
                if x is None:
                    log.append("导航: VLM 全部提示词未命中，回退比例坐标")
            else:
                log.append("导航: VLM 不可用，用比例坐标")
        except Exception as e:
            log.append(f"导航: VLM 异常 {type(e).__name__}: {e}，用比例坐标")
    else:
        log.append("导航: --nav-fast 跳过 VLM，直接用比例坐标")
    if x is None:
        w, h = d.window_size()
        x, y = int(MINE_XY[0] * w), int(MINE_XY[1] * h)
        log.append(f"导航: 比例坐标 -> ({x},{y})")
    d.click(x, y)
    time.sleep(3.5)
    xml = d.dump_hierarchy()
    return parse_nodes(xml), (x, y), xml


def at_top_level(nodes, screen_h=None):
    """判断当前页是否是 App 的**顶层页**（带底部导航栏）。

    实现见 ui_page.at_top_level_nodes —— 与执行器共用同一份判据，
    否则「离线统计说能命中、真机执行却失败」这类脱钩问题无法被发现。

    行为之间必须复位，否则会串味：实测喜番 sign 走三级导航
    （我的 → 福利中心 → 签到）后被留在「签到」二级页，紧随的 watch
    从脏页面起步，比例坐标 (972,2141) 点飞到了 com.eggflower.read（蛋花）。
    """
    return at_top_level_nodes(nodes, screen_h)


def reset_to_landing(d, pkg, log, screen_h=None, max_back=3):
    """把 App 退回顶层页并返回新的 (xml, nodes)。

    策略：**先判断、后动作** ——
      1) 已经在顶层页且页面属于目标 App -> 直接返回，一个 BACK 都不按；
      2) 否则按 BACK（快、不触发开屏广告），每次都校验页面仍属于目标 App；
      3) 退不回去 -> stop + start（确定但慢，约 20~30s）。

    为什么必须先判断：多数 App 在顶层页（如「我的」tab）按 BACK 会**直接退出
    App**。实测复位前不看一眼就按，喜番 withdraw 那次一按就退到桌面
    （主导包 com.vivo.vtouch），白白多吃一次冷启动。

    踩坑（铁律）：开屏广告期按 BACK 会直接退出 App，故 BACK 后一旦发现
    已不在目标 App，立刻改走重启，不再继续按。
    """
    xml = d.dump_hierarchy()
    nodes = parse_nodes(xml)
    ok, dom, _m, _n = page_belongs_to(xml, pkg)
    if ok and at_top_level(nodes, screen_h):
        log.append("复位: 已在顶层页，无需 BACK")
        return xml, nodes
    for i in range(1, max_back + 1):
        try:
            d.press("back")
        except Exception as e:
            log.append(f"复位: BACK 异常 {type(e).__name__}: {e}")
            break
        time.sleep(1.5)
        xml = d.dump_hierarchy()
        nodes = parse_nodes(xml)
        ok, dom, _m, _n = page_belongs_to(xml, pkg)
        if not ok:
            log.append(f"复位: 第{i}次 BACK 后已不在目标 App（主导包 {dom}）"
                       f"-> 改走重启")
            break
        if at_top_level(nodes, screen_h):
            log.append(f"复位: 第{i}次 BACK 回到顶层页")
            return xml, nodes
    log.append("复位: BACK 未能回到顶层页 -> 重启 App")
    try:
        d.app_stop(pkg)
    except Exception as e:
        log.append(f"复位: stop 异常 {type(e).__name__}: {e}")
    try:
        d.app_start(pkg, wait=True)
    except Exception as e:
        log.append(f"复位: 重启异常 {type(e).__name__}: {e}")
    xml, nodes, waited = wait_ready(d, pkg, max_wait=75, min_nodes=25, log=log)
    dismiss_popups(d, nodes, log)
    return xml, nodes


def verify_app(app_cfg, behaviors, d, vision_cfg, log, probe_nav=False,
               nav_fast=False):
    name = app_cfg.get("name")
    pkg = app_cfg.get("package")
    rows = []
    # 屏幕高度：用于底部导航标签的位置合理性校验
    try:
        _w, screen_h = d.window_size()
    except Exception:
        screen_h = None
    # 启动 + 归属校验，最多试 2 次（偶发启动失败会停留上一个 App）
    xml, nodes, waited = "", [], 0.0
    ok_page, dom, mine, dom_n, fg = False, "", 0, 0, ""
    for attempt in (1, 2):
        log.append(f"启动 {pkg}（第 {attempt} 次）")
        try:
            d.app_start(pkg, wait=True)
        except Exception as e:
            log.append(f"启动失败: {type(e).__name__}: {e}")
        xml, nodes, waited = wait_ready(d, pkg, max_wait=75, min_nodes=25, log=log)
        log.append(f"就绪: 节点={len(nodes)} 等待={waited:.1f}s")
        dismiss_popups(d, nodes, log)
        try:
            fg = d.info.get("currentPackageName") or ""
        except Exception:
            fg = ""
        # 归属判定以 dump 自身为准：崩溃/切换时序下前台包名会失真
        ok_page, dom, mine, dom_n = page_belongs_to(xml, pkg)
        log.append(f"归属校验: dump 主导包={dom}（{dom_n} 节点） 目标包={mine} 节点"
                   f" 前台={fg} -> {'属于目标 App' if ok_page else '不属于目标 App'}")
        if ok_page:
            break
        log.append("归属校验失败" + ("，重试一次" if attempt == 1 else ""))
        time.sleep(3)

    # 页面归属：dump 到的必须真是目标 App。
    # 踩坑：若目标 App 启动失败/崩溃，前台会停留在**上一个 App**，
    # 于是两个 App 会得到完全相同的坐标（看似合理、实为垃圾数据）。
    # 宁可不给结论，也不要给出错误结论。
    if not ok_page:
        log.append(f"归属校验最终失败 -> 本轮结果作废（dump 主导包 {dom}，前台 {fg}）")
        return [{"behavior": "-", "status": "数据作废(页面非目标App)",
                 "detail": f"期望 {pkg}；dump 主导包 {dom}（{dom_n} 节点），"
                           f"目标包 {mine} 节点；前台 {fg}",
                 "prelude": False}]

    bcfg = app_cfg.get("behaviors") or {}
    targets = [b for b in (behaviors or bcfg.keys()) if bcfg.get(b)]
    # 行为间复位标记：上一个行为导航过（离开顶层页）就置脏，下一个行为
    # 开始前必须先复位，否则量到的是「上一行为留下的页面」。
    dirty = False
    for bid in targets:
        if dirty:
            xml, nodes = reset_to_landing(d, pkg, log, screen_h)
            dirty = False
        actions = bcfg[bid]
        idx, act = first_anchor_action(actions)
        if act is None:
            rows.append({"behavior": bid, "status": "无锚点动作",
                         "detail": "该行为无 click_* 动作", "prelude": has_prelude(actions)})
            continue
        prelude = has_prelude(actions)
        hit, detail = check_anchor(nodes, act, screen_h)
        if hit:
            rows.append({"behavior": bid, "status": "首屏命中",
                         "detail": detail, "prelude": prelude})
            log.append(f"  {bid}: 首屏命中 {detail}")
            continue
        if not prelude and not probe_nav:
            rows.append({"behavior": bid, "status": "首屏未命中",
                         "detail": detail, "prelude": False})
            log.append(f"  {bid}: 首屏未命中（无前置步）{detail}")
            continue
        # 走前置步（probe_nav 时即使配置里没有前置步也试一次，用于判断
        # 「这个未命中能否靠导航到我的救回」）。
        # 实测导航有波动（同一 App 两次跑结果可能不同），故最多试 2 轮。
        dirty = True        # 下面一定会离开顶层页
        log.append(f"  {bid}: 首屏未命中，执行前置导航"
                   + ("（probe-nav 探路）" if not prelude else ""))
        # 三级导航行为（如 sign：我的 → 福利中心 → 签到）：只走到「我的」不够，
        # 必须继续点中间入口，否则三级行为必然被误判为未命中。
        mid = mid_entry_of(act)
        tgt = target_anchor_of(act) or act
        if mid is not None:
            log.append(f"  {bid}: 检测到三级导航，中间入口 = "
                       f"{mid.get('candidates') or mid.get('text') or mid.get('desc')}")
        hit2, detail2, nodes2, xy = False, detail, [], None
        void_rounds = 0
        for attempt in (1, 2):
            hit2 = False
            nodes2, xy, xml2 = goto_mine(d, vision_cfg, log, use_vlm=not nav_fast)
            dismiss_popups(d, nodes2, log)
            ok2, dom2, _mine2, dom2_n = page_belongs_to(xml2, pkg)
            if not ok2:
                void_rounds += 1
                log.append(f"  {bid}: 第{attempt}轮导航后页面不属于目标 App"
                           f"（主导包 {dom2}，{dom2_n} 节点）-> 本轮作废")
                continue
            hit2, detail2 = check_anchor(nodes2, tgt, screen_h)
            log.append(f"  {bid}: 第{attempt}轮导航后 "
                       f"{'命中' if hit2 else '仍未命中'} {detail2}")
            # 二级页没找到目标 -> 再点中间入口，进三级页找
            if not hit2 and mid is not None:
                node, det_mid = find_anchor_node(nodes2, mid, screen_h)
                if node is None:
                    log.append(f"  {bid}: 第{attempt}轮二级页未找到中间入口 {det_mid}")
                else:
                    cx, cy = node["center"]
                    log.append(f"  {bid}: 点中间入口 {det_mid}")
                    d.click(cx, cy)
                    time.sleep(3.5)
                    xml3 = d.dump_hierarchy()
                    nodes3 = parse_nodes(xml3)
                    dismiss_popups(d, nodes3, log)
                    ok3, dom3, _m3, _d3 = page_belongs_to(xml3, pkg)
                    if not ok3:
                        log.append(f"  {bid}: 三级页不属于目标 App（主导包 {dom3}）")
                    else:
                        hit2, detail2 = check_anchor(nodes3, tgt, screen_h)
                        log.append(f"  {bid}: 第{attempt}轮三级页 "
                                   f"{'命中' if hit2 else '仍未命中'} {detail2}")
                        if hit2:
                            detail2 = f"（三级页）{detail2}"
            if hit2:
                break
            if attempt == 1:
                log.append(f"  {bid}: 第1轮未命中，回退首页重试一次")
                try:
                    d.press("back")
                    time.sleep(2)
                except Exception:
                    pass
        if hit2:
            # 原本没前置步、导航后才命中 -> 说明补前置步能救回
            status = "导航后命中" if prelude else "导航可救(建议加前置步)"
        elif void_rounds >= 2:
            # 两轮导航都落在别的 App 上：这是**测量无效**，不是「未命中」。
            # 计入未命中分母会系统性低估命中率（实测喜番 watch 就这样被误判）。
            status = "数据作废(导航后页面非目标App)"
        else:
            status = "导航后仍未命中" if prelude else "导航后也未命中(不可救)"
        rows.append({"behavior": bid, "status": status,
                     "detail": f"{detail} | 二级页: {detail2}",
                     "nav_xy": xy, "prelude": prelude,
                     "nodes_after": len(nodes2)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(ROOT, "config.yaml"))
    ap.add_argument("--apps", default=None, help="逗号分隔，限定 App")
    ap.add_argument("--behaviors", default=None, help="逗号分隔，限定行为")
    ap.add_argument("--out", default=os.path.join(HERE, "calib", "LIVE_VERIFY.md"))
    ap.add_argument("--json", default=os.path.join(HERE, "calib", "LIVE_VERIFY.json"))
    ap.add_argument("--probe-nav", action="store_true",
                    help="所有未命中项都试一次导航到『我的』，"
                         "用于判断能否靠前置步救回")
    ap.add_argument("--nav-fast", action="store_true",
                    help="导航到『我的』时跳过 VLM，直接用比例坐标"
                         "（本机 VLM 图像请求常 90s 超时，跑批时建议开启）")
    args = ap.parse_args()

    import yaml
    cfg = yaml.safe_load(open(args.config, encoding="utf-8")) or {}
    vision_cfg = cfg.get("vision") or {}
    serial = (cfg.get("device") or {}).get("serial")

    only = set(x.strip() for x in args.apps.split(",")) if args.apps else None
    only_b = set(x.strip() for x in args.behaviors.split(",")) if args.behaviors else None

    apps = [a for a in (cfg.get("apps") or [])
            if not only or a.get("name") in only]
    # 只验证有校准数据的 App（无 dump 的说明还没跑过校准）
    apps = [a for a in apps
            if os.path.isdir(os.path.join(HERE, "calib", safe_name(a.get("name", ""))))]

    print(f"待验证 App: {len(apps)} -> {[a['name'] for a in apps]}")
    d = connect_device(serial)

    report = {}
    all_log = {}
    for a in apps:
        name = a.get("name")
        print(f"\n===== {name} =====")
        log = []
        try:
            rows = verify_app(a, only_b, d, vision_cfg, log,
                              probe_nav=args.probe_nav,
                              nav_fast=args.nav_fast)
        except Exception as e:
            log.append(f"验证异常: {type(e).__name__}: {e}")
            rows = [{"behavior": "-", "status": "异常", "detail": str(e)}]
        report[name] = rows
        all_log[name] = log
        for r in rows:
            print(f"  {r['behavior']:10s} {r['status']:14s} {r['detail'][:200]}")

    # 汇总
    stat = {}
    for rows in report.values():
        for r in rows:
            stat[r["status"]] = stat.get(r["status"], 0) + 1
    print("\n===== 汇总 =====")
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    md = ["# 实机锚点回归报告", "",
          f"> 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
          f"> 设备: {serial}", "", "## 汇总", ""]
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        md.append(f"- {k}: **{v}**")
    md.append("")
    for name, rows in report.items():
        md.append(f"## {name}")
        md.append("")
        md.append("| 行为 | 结果 | 明细 | 前置步 |")
        md.append("|---|---|---|---|")
        for r in rows:
            md.append(f"| {r['behavior']} | {r['status']} | {r['detail']} | "
                      f"{'有' if r.get('prelude') else '-'} |")
        md.append("")
        md.append("<details><summary>执行日志</summary>")
        md.append("")
        md.append("```")
        md += all_log.get(name, [])
        md.append("```")
        md.append("")
        md.append("</details>")
        md.append("")
    open(args.out, "w", encoding="utf-8").write("\n".join(md) + "\n")
    json.dump({"report": report, "stat": stat},
              open(args.json, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n报告: {args.out}\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
