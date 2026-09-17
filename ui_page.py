# -*- coding: utf-8 -*-
"""ui_page.py - 页面结构判据（纯函数，无设备依赖）

为什么单独抽出来：**执行器（executor.py）和验证器（devtools/verify_live.py）
必须用同一套「页面长什么样」的判据**。两边判据不一致时，离线统计出的命中率
就不能代表真机执行结果 —— 度量与执行脱钩，校准就失去意义。

当前只收敛一件事：**判断当前页是不是 App 的顶层页（带底部导航栏）**。

背景（真实缺陷）：
    行为之间不复位会串味。实测喜番免费短剧 sign 走三级导航
    （我的 → 福利中心 → 签到）后停在「签到」二级页，紧随的 watch 从脏页面
    起步，比例坐标 (972,2141) 点飞到了 com.eggflower.read（蛋花免费小说）——
    一个 App 的数据被另一个 App 污染。执行器和验证器都有这个问题。

判据：底部导航标签必须落在**屏幕底部带**（y >= NAV_BAND_Y × 屏高）。
      页面中部出现同名文字不算 —— 实测蛋花二级页命中过 text='我的' @(575,627)，
      y=627 在 1080x2340 上属页面中部，是假命中。
"""

# 底部导航标签（用于**锚点**的底部带校验）。刻意保守：只收明确的导航名，
# 避免把内容区的普通文字误判成导航。
NAV_LABELS = {"我的", "我", "首页", "个人中心", "我的 ", "个人中心 "}

# 顶层页识别用的标签集（更宽）。顶部/底部 tab 的常见命名都算，
# 只要求「落在底部带」即可 —— 这里放宽是安全的，因为判据不是「是导航栏」，
# 而是「页面底部有一排 tab」，放宽只会让复位少按几次 BACK。
TOP_LEVEL_LABELS = NAV_LABELS | {
    "推荐", "视频", "任务", "赚钱", "福利", "发现", "关注", "广场", "消息",
    "直播", "商城", "小说", "短剧", "放映厅", "书城", "听书",
}

NAV_BAND_Y = 0.80          # 底部 20% 视为导航带

# 「明确的首页类标签」：单独出现也足以证明这是顶层页。
HOME_TABS = {"首页", "推荐", "我的", "我"}


def _bounds_of(node):
    b = node.get("bounds")
    if isinstance(b, (list, tuple)) and len(b) == 4:
        return b
    return None


def _label_of(node):
    return ((node.get("text") or "").strip(),
            (node.get("content-desc") or "").strip())


def band_labels(nodes, screen_h=None):
    """返回落在底部导航带里的标签集合。"""
    out = set()
    if not nodes:
        return out
    h = screen_h
    if not h:
        ys = [b[3] for b in (_bounds_of(n) for n in nodes) if b]
        h = max(ys) if ys else None
    if not h:
        return out
    band = NAV_BAND_Y * h
    for n in nodes:
        txt, desc = _label_of(n)
        for lab in (txt, desc):
            if lab not in TOP_LEVEL_LABELS:
                continue
            b = _bounds_of(n)
            if b and (b[1] >= band or b[3] >= band):
                out.add(lab)
    return out


def at_top_level_nodes(nodes, screen_h=None):
    """当前 dump 是否呈现「顶层页」（带底部 tab 栏）。

    判据刻意做硬，避免把二级页误判成顶层页（误判会导致该复位时不复位）：
      * 底部带里出现 **>=2 个不同**的 tab 名  -> 顶层页（真 tab 栏一般 4~5 个）
      * 或底部带里出现 HOME_TABS 中的标签     -> 顶层页（首页/推荐/我的）

    反例：喜番免费短剧的「签到」二级页底部只有一个「签到」，既不足 2 个、
    也不含首页类标签 -> 判为**非**顶层页 -> 继续 BACK，直到真的退回去。
    """
    labs = band_labels(nodes, screen_h)
    if len(labs) >= 2:
        return True
    return bool(labs & HOME_TABS)

