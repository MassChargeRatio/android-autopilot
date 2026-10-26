# -*- coding: utf-8 -*-
"""pick_locate.py - 定位择优纯函数（无设备依赖）

把 executor._pick_best 的打分逻辑抽成纯函数，供执行器与测试对拍复用。
打分规则、日志文案与 executor 原实现逐字一致，后续 B/D 批可直接复用。
"""
try:
    from ui_page import NAV_LABELS, NAV_BAND_Y
except ImportError:  # pragma: no cover - 未拷贝 ui_page.py 时退化为空集
    NAV_LABELS, NAV_BAND_Y = set(), 0.80

# ---------- 位置先验三区（第3步，AUTOP-SELFSEARCH-2026-10-20） ----------
# 用户原话：「按钮名称、按钮位置、常用步骤的共性」——候选文案多处匹配时，
# 位置本身就是先验：底部导航带的 tab 类按钮、右上角/右缘的浮球类按钮。
# 只做加分不做硬过滤（与 nav 带一致），避免误伤特殊布局。
ZONE_BOTTOM_BAND = 0.92     # 底部导航带：top >= screen_h*0.92
ZONE_TOP_BAND = 0.18        # 顶部区域：top <= screen_h*0.18
ZONE_RIGHT_RATIO = 0.70     # 右缘：x 中心 >= screen_w*0.70
# 命中/未命中的加权分（未命中扣分仅用于「多匹配择优」，不硬过滤）
_ZONE_BONUS = {
    "tab_zone": 150,
    "top_right": 150,
    "right_edge": 100,
}


def pick_best(entries, target, kind, screen_h=0, log=None, screen_w=0,
              zone=None):
    """从多匹配候选里择优；对"长文案误命中"做拒配。

    entries : [{label, clickable, top, left?, right?}]（保序，最多传前 12 条）
    target  : 目标文本
    kind    : text / desc / id
    screen_h: 屏幕高度像素（0 = 未知，跳过 nav 带内加分）
    log     : 可选回调 log(event, app="", level="INFO")，复刻原 DEBUG/WARN 文案
    screen_w: 屏幕宽度像素（0 = 未知，跳过 zone 右缘/右上角加分）
    zone    : tab_zone / top_right / right_edge / None（未知值忽略）
    返回    : 选中下标（平局取先）；误命中返回 None
    """
    n = len(entries)
    if n == 0:
        return None
    if n <= 1:
        best_i = 0
    else:
        # 底部导航标签的位置合理性：实测页面中部也会出现「我的」这类
        # 标签文本（蛋花免费小说二级页 text='我的' @(575,627)，而底部
        # 导航在 y≈2100+）。若目标词是导航标签，优先取落在屏幕底部带的
        # 匹配 —— 只做加分，不做硬过滤，避免误伤特殊布局。
        nav_label = str(target).strip() in NAV_LABELS
        zone_bonus = _ZONE_BONUS.get(zone)
        best_i, best_score = 0, None
        for i in range(min(n, 12)):
            ent = entries[i]
            label = ent["label"]
            clickable = bool(ent.get("clickable"))
            if label == target:
                score = 1000
            else:
                score = 100 - min(90, abs(len(label) - len(target)) * 3)
            if clickable:
                score += 50
            if nav_label and screen_h:
                try:
                    top = int(ent.get("top") or 0)
                    if top >= NAV_BAND_Y * screen_h:
                        score += 120
                    else:
                        score -= 120
                except Exception:
                    pass
            # 第3步：位置先验 zone 加分（缺坐标/未知屏尺寸 -> 该条目中性）
            if zone_bonus and screen_h and (zone != "right_edge" or screen_w):
                try:
                    top = int(ent.get("top") or 0)
                    if zone in ("tab_zone", "top_right"):
                        ok_zone = (top >= ZONE_BOTTOM_BAND * screen_h
                                   if zone == "tab_zone"
                                   else top <= ZONE_TOP_BAND * screen_h)
                    else:
                        ok_zone = True
                    xc = None
                    if zone in ("top_right", "right_edge"):
                        if "left" in ent and "right" in ent:
                            xc = (int(ent["left"]) + int(ent["right"])) / 2.0
                    if zone in ("top_right", "right_edge") and xc is None:
                        pass                            # 缺 x 坐标：中性
                    elif ok_zone and (xc is None or
                                      xc >= ZONE_RIGHT_RATIO * screen_w):
                        score += zone_bonus
                    elif zone != "right_edge" or xc is not None:
                        score -= zone_bonus
                except Exception:
                    pass
            if best_score is None or score > best_score:
                best_score, best_i = score, i
        if log is not None:
            log(f"  [{kind}]'{target}' 命中 {n} 处，择优 {best_score} 分",
                "", "DEBUG")
    # 长文案拒配：明显过长的非可点击文本视为误命中
    try:
        best = entries[best_i]
        label = best["label"]
        limit = max(len(target) + 6, len(target) * 3)
        if (kind in ("text", "desc") and len(label) > limit
                and not bool(best.get("clickable"))):
            if log is not None:
                log(f"  [{kind}]'{target}' 只匹配到过长文案 {label[:24]!r}"
                    f"（{len(label)} 字 > 阈值 {limit}）且不可点击，判为误命中",
                    "", "WARN")
            return None
    except Exception:
        pass
    return best_i
