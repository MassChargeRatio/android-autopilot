# -*- coding: utf-8 -*-
"""test_anchor_anyof.py - any_of 锚点校验语义（无需真机）

背景（真实测量缺陷）：
    三级导航的 any_of 分支形如
        [click_point(我的), think, click_first(福利中心), think, click_first(签到)]
    中间那步「福利中心」也是锚点类动作。早期 `check_anchor` 遍历分支时
    **把分支里任何一个锚点类动作命中都当成整个分支命中**，
    于是「福利中心」在落地页被找到时，就报成
        `首屏命中 any_of 分支#2: text='福利'`
    —— 看起来像命中，实际上签到锚点根本没出现过。

    实测影响：天天快讯极速版.sign / 河马剧场.sign / 喜番免费短剧.sign
    三个三级行为在 3 轮统计里全被记成「首屏命中」，全是假命中。

正确语义：
    一个分支是否命中，取决于该分支的**最后一个**锚点动作（真正的目标），
    而不是中途的入口。执行器本身就是按顺序执行、最后一步才落到目标锚点。

运行：
    python tests/test_anchor_anyof.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "devtools"))

from verify_live import (  # noqa: E402
    check_anchor, mid_entry_of, target_anchor_of, find_anchor_node,
    at_top_level,
)

H = 2340
NAV = {"type": "click_point",
       "vlm_prompt": "定位屏幕底部导航栏最右侧的『我的』标签中心",
       "x": 0.9, "y": 0.915, "vision": False, "optional": True}


def _n(text="", cx=500, cy=1200, clickable=True):
    return {"text": text, "desc": "", "rid": "", "center": (cx, cy),
            "size": (100, 100), "clickable": clickable,
            "bounds": (cx - 50, cy - 50, cx + 50, cy + 50)}


def _three_level_anyof(anchor_values=("签到", "每日签到")):
    return {"type": "any_of", "optional": True, "choices": [
        [{"type": "click_first",
          "candidates": [{"type": "text", "value": v} for v in anchor_values],
          "optional": False}],
        [dict(NAV), {"type": "think"},
         {"type": "click_first",
          "candidates": [{"type": "text", "value": "福利中心"},
                         {"type": "text", "value": "福利"}],
          "optional": False},
         {"type": "think"},
         {"type": "click_first",
          "candidates": [{"type": "text", "value": v} for v in anchor_values],
          "optional": False}],
    ]}


def t_mid_entry_alone_is_not_a_hit():
    """落地页只有「福利中心」（中间入口）-> 不应判为命中。"""
    nodes = [_n("福利中心", 540, 2187)]
    hit, det = check_anchor(nodes, _three_level_anyof(), H)
    assert not hit, f"中间入口命中被误判为整体命中: {det}"
    print("OK  中间入口「福利中心」单独出现不算命中")


def t_real_anchor_is_a_hit():
    """落地页有真正的签到锚点 -> 命中（走分支1）。"""
    nodes = [_n("签到", 720, 2093)]
    hit, det = check_anchor(nodes, _three_level_anyof(), H)
    assert hit, det
    assert "分支#1" in det, det
    print("OK  真正的签到锚点出现即命中（分支#1）")


def t_second_branch_anchor_also_counts():
    """分支2 的最终锚点也要被检查到（不是只看分支1）。

    `convert_deep` 生成的两条分支**共用同一个目标锚点**，所以单份 dump 上
    分支1 先命中 —— 这里断言的是「命中被正确识别」，并说明分支2 的价值在
    『换页面再找』（由 导航后 复校体现）。
    """
    nodes = [_n("每日签到", 300, 800)]
    hit, det = check_anchor(nodes, _three_level_anyof(), H)
    assert hit, det
    assert "分支#" in det, det
    # 分支2 的末步（目标锚点）确实被纳入检查范围
    act = _three_level_anyof()
    b2_anchors = [a for a in act["choices"][1]
                  if a.get("type") == "click_first"]
    assert b2_anchors, "分支2 应包含锚点动作"
    assert check_anchor([_n("签到")], {"type": "any_of", "optional": True,
                                      "choices": [act["choices"][1]]}, H)[0]
    print("OK  分支2 的最终锚点被纳入检查（命中识别正确）")


def t_branch2_alone_still_needs_real_anchor():
    """只给分支2（导航+中间入口+锚点）时，中间入口不算命中、锚点才算。"""
    act = _three_level_anyof()
    only_b2 = {"type": "any_of", "optional": True,
               "choices": [act["choices"][1]]}
    assert check_anchor([_n("福利中心", 540, 2187)], only_b2, H)[0] is False
    assert check_anchor([_n("签到", 720, 2093)], only_b2, H)[0] is True
    print("OK  仅分支2 时：中间入口不算命中，目标锚点才算")


def t_two_level_anyof_unchanged():
    """二级 any_of（无中间入口）行为不变：末步就是锚点。"""
    act = {"type": "any_of", "optional": True, "choices": [
        [{"type": "click_first", "candidates": [{"type": "text", "value": "签到"}],
          "optional": False}],
        [dict(NAV), {"type": "think"},
         {"type": "click_first", "candidates": [{"type": "text", "value": "签到"}],
          "optional": False}],
    ]}
    assert check_anchor([_n("签到")], act, H)[0] is True
    assert check_anchor([_n("福利")], act, H)[0] is False
    print("OK  二级 any_of 语义不变")


def t_nav_point_is_not_treated_as_anchor():
    """导航 click_point 不是锚点，不能靠它"命中"。"""
    act = {"type": "any_of", "optional": True, "choices": [[dict(NAV)]]}
    hit, det = check_anchor([_n("我的", 918, 2130)], act, H)
    assert not hit, f"导航步不应算锚点命中: {det}"
    print("OK  导航 click_point 不算锚点命中")


def t_all_branches_miss():
    nodes = [_n("首页"), _n("推荐")]
    hit, det = check_anchor(nodes, _three_level_anyof(), H)
    assert not hit, det
    assert "未命中" in det, det
    print("OK  全部分支未命中")


def t_mid_entry_detected_for_three_level():
    act = _three_level_anyof()
    mid = mid_entry_of(act)
    assert mid is not None, "三级 any_of 应能识别出中间入口"
    vals = [c["value"] for c in mid["candidates"]]
    assert vals[0] == "福利中心", vals
    tgt = target_anchor_of(act)
    assert tgt is not None
    tvals = [c["value"] for c in tgt["candidates"]]
    assert "签到" in tvals, tvals
    assert mid is not tgt, "中间入口不能等于目标锚点"
    print("OK  三级 any_of：中间入口与目标锚点被正确区分")


def t_no_mid_entry_for_two_level():
    act = {"type": "any_of", "optional": True, "choices": [
        [{"type": "click_first", "candidates": [{"type": "text", "value": "签到"}],
          "optional": False}],
        [dict(NAV), {"type": "think"},
         {"type": "click_first", "candidates": [{"type": "text", "value": "签到"}],
          "optional": False}],
    ]}
    assert mid_entry_of(act) is None, "二级 any_of 不应有中间入口"
    assert target_anchor_of(act) is not None
    print("OK  二级 any_of 无中间入口")


def t_mid_entry_none_for_plain_anchor():
    assert mid_entry_of({"type": "click_first",
                         "candidates": [{"type": "text", "value": "签到"}]}) is None
    print("OK  非 any_of 动作无中间入口")


def t_target_anchor_of_plain_anchor_is_itself():
    plain = {"type": "click_text", "text": "提现"}
    assert target_anchor_of(plain) is plain
    print("OK  普通锚点的目标就是它自己")


def t_find_anchor_node_returns_clickable_node():
    nodes = [_n("福利中心", 540, 2187)]
    mid = mid_entry_of(_three_level_anyof())
    node, det = find_anchor_node(nodes, mid, H)
    assert node is not None, det
    assert node["center"] == (540, 2187)
    print("OK  find_anchor_node 返回可点击节点（供真机点中间入口）")


def t_find_anchor_node_none_when_absent():
    node, det = find_anchor_node([_n("首页")], mid_entry_of(_three_level_anyof()), H)
    assert node is None, det
    print("OK  中间入口不存在时返回 None")


def t_find_anchor_node_respects_nav_band():
    """中间入口若是导航标签，也要过底部带校验。"""
    act = {"type": "click_first", "candidates": [{"type": "text", "value": "我的"}]}
    node, _ = find_anchor_node([_n("我的", 575, 627)], act, H)
    assert node is None, "页面中部的『我的』不应作为入口"
    node2, _ = find_anchor_node([_n("我的", 918, 2130)], act, H)
    assert node2 is not None
    print("OK  find_anchor_node 继承底部导航带校验")


# ---------------------------------------------------------------- 行为间复位
def t_at_top_level_true_when_nav_in_bottom_band():
    """底部带有导航标签 -> 顶层页。"""
    nodes = [_n("首页", 100, 2140), _n("我的", 960, 2145)]
    assert at_top_level(nodes, H) is True
    print("OK  底部带导航标签 -> 判为顶层页")


def t_at_top_level_false_when_label_in_middle():
    """页面中部的『我的』不算顶层页（假命中防线）。"""
    nodes = [_n("我的", 575, 627)]
    assert at_top_level(nodes, H) is False
    print("OK  页面中部同名文字 -> 不判为顶层页")


def t_at_top_level_false_for_sub_page():
    """二级页（签到列表）无底部导航 -> 不是顶层页，必须继续 BACK。"""
    nodes = [_n("签到", 188, 1993), _n("每日签到", 400, 1200),
             _n("立即领取", 900, 1500)]
    assert at_top_level(nodes, H) is False
    print("OK  二级页无导航栏 -> 不判为顶层页")


def t_at_top_level_infers_height_when_unknown():
    """未传屏高时用节点最大 y 兜底推断，仍能识别底部带。"""
    nodes = [_n("首页", 100, 2200), _n("我的", 960, 2230)]
    assert at_top_level(nodes, None) is True
    print("OK  屏高未知时按最大 y 推断")


def t_at_top_level_single_non_home_label_is_not_enough():
    """底部只有一个非首页类标签（如『福利』）-> 不足以判为顶层页。

    这条防的是「二级页底部恰有个『福利』字样就被当成顶层页、于是不复位」。
    """
    nodes = [_n("福利", 500, 2140), _n("立即领取", 900, 1500)]
    assert at_top_level(nodes, H) is False
    print("OK  底部单个非首页类标签不足以判为顶层页")


def t_at_top_level_home_tab_alone_is_enough():
    """底部出现『我的』这类首页标签，单独一个即可判为顶层页。"""
    nodes = [_n("我的", 960, 2145), _n("签到", 400, 1200)]
    assert at_top_level(nodes, H) is True
    print("OK  底部出现首页类标签即判为顶层页")


def t_at_top_level_real_tab_bar():
    """典型 5 个 tab 的顶层页。"""
    nodes = [_n("首页", 100, 2140), _n("视频", 400, 2140),
             _n("任务", 700, 2140), _n("福利", 900, 2140),
             _n("我的", 1000, 2145)]
    assert at_top_level(nodes, H) is True
    print("OK  典型多 tab 顶层页识别正确")


def t_void_status_is_excluded_from_denominator():
    """新增的作废状态必须能被统计脚本识别（前缀契约）。"""
    sys.path.insert(0, os.path.join(ROOT, "devtools"))
    from stability_run import is_void, is_hit
    st = "数据作废(导航后页面非目标App)"
    assert is_void(st) is True, "作废状态必须排除出分母"
    assert is_hit(st) is False
    assert is_void("导航后仍未命中") is False
    assert is_hit("导航后命中") is True
    print("OK  作废状态前缀契约成立（不进分母、不算命中）")


# ---------------------------------------------------------- reset_to_landing
class _FakeDev:
    """只记录 press 调用次数的最小假设备。"""

    def __init__(self, pages=None):
        self.presses = []
        self.pages = list(pages or [])

    def dump_hierarchy(self):
        if len(self.pages) > 1:
            return self.pages.pop(0)
        return self.pages[0] if self.pages else "<x/>"

    def press(self, key):
        self.presses.append(key)


def _with_stubs(pages, fn):
    """临时替换 page_belongs_to / parse_nodes，避免测试依赖真机 dump。"""
    import verify_live as V
    orig_pb, orig_pn = V.page_belongs_to, V.parse_nodes
    V.page_belongs_to = lambda xml, pkg: (True, pkg, 1, 1)
    V.parse_nodes = lambda xml: pages.pop(0)
    try:
        return fn(V)
    finally:
        V.page_belongs_to, V.parse_nodes = orig_pb, orig_pn


def t_reset_skips_back_when_already_top_level():
    """已在顶层页 -> 一个 BACK 都不按。

    实测教训：多数 App 在「我的」tab 按 BACK 会**直接退出 App**。
    早期实现「先按 BACK 再判」导致一按就退到桌面，白吃一次冷启动。
    """
    dev = _FakeDev()

    def run(V):
        log = []
        V.reset_to_landing(dev, "com.x", log, H)
        return log

    log = _with_stubs([[_n("首页", 100, 2140), _n("我的", 960, 2145)]], run)
    assert dev.presses == [], f"已在顶层页不该按 BACK，实际 {dev.presses}"
    assert any("已在顶层页" in x for x in log), log
    print("OK  已在顶层页时不按 BACK（先判断后动作）")


def t_reset_backs_until_top_level():
    """二级页 -> 按 BACK，退到顶层页即停（不多按）。"""
    dev = _FakeDev()

    def run(V):
        log = []
        V.reset_to_landing(dev, "com.x", log, H)
        return log

    # 第 1 次 dump（判前）= 签到二级页；BACK 后第 2 次 dump = 顶层页
    pages = [[_n("签到", 188, 1993)],
             [_n("首页", 100, 2140), _n("我的", 960, 2145)]]
    log = _with_stubs(pages, run)
    assert dev.presses == ["back"], dev.presses
    assert any("回到顶层页" in x for x in log), log
    print("OK  二级页按一次 BACK 回到顶层页后即停")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
