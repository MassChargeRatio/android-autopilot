# -*- coding: utf-8 -*-
"""test_candidates_auto.py - 第3项：跨 App 共性词表归纳（AUTOP-NL-2026-10-22）

目标（用户原话）：关键词识别在「所有 App」层面具有共性，归纳后不必每个 App 单独写。
即：某条 sign 只写了
    candidates: [连续签到, 今日签到, 签到]
执行器也应自动并入全局表与跨 App 归纳词。

锁定四点（均可红）：
  1. mine_words 把「≥2 个 App 在同一行为下用过」的文案升级为共性词；
  2. 仅 1 个 App 用过的文案不升级（防把个别 App 的特有文案污染全局）；
  3. candidates_for 的结果包含归纳词（顺序：全局表 → 归纳 → App extra）；
  4. click_first 未写 candidates_from 时按 _current_bid 自动推断类别并入池。

运行：
    python -m pytest tests/test_candidates_auto.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import candidates  # noqa: E402
from executor import Executor, LocateResult  # noqa: E402


def _app(name, words, bid="sign"):
    return {
        "name": name,
        "behaviors": {
            bid: [
                {"type": "click_first", "candidates": [{"type": "text", "value": w} for w in words]},
            ]
        },
    }


def t_mine_promotes_words_used_by_two_apps():
    # 注意：连续签到/今日签到/签到 本就在全局 SIGN 表里，归纳层只需覆盖「表外新词」
    apps = [_app("A", ["跨App新词甲", "单App独有词"]), _app("B", ["跨App新词甲"])]
    mined = candidates.mine_words(apps)
    words = mined.get("sign", [])
    assert "跨App新词甲" in words, words
    assert "单App独有词" not in words, f"仅 1 个 App 用过，不应升级: {words}"
    print("OK  支持度 >=2 的文案升级为共性词，单 App 文案不升级")


def t_mine_skips_words_already_in_global_table():
    apps = [_app("A", ["签到"]), _app("B", ["签到"])]
    mined = candidates.mine_words(apps)
    assert "签到" not in mined.get("sign", []), "已在全局表的不重复列出"
    print("OK  已在全局表的文案不重复列出")


def t_candidates_for_includes_mined_words():
    apps = [_app("A", ["特有一号词"]), _app("B", ["特有一号词"])]
    candidates.register_apps(apps)
    merged = candidates.candidates_for("sign", None)
    assert "特有一号词" in merged, merged
    assert merged.index("今日签到") < merged.index("特有一号词"), "全局表应排在归纳词之前"
    candidates.register_apps([])  # 复位，避免污染其他用例
    print("OK  candidates_for 并入归纳词且顺序为 全局表→归纳")


def t_click_first_infers_category_from_current_bid():
    class _Rec:
        def log(self, *a, **k):
            pass

    class _Human:
        def delay(self, *a):
            pass

        def maybe_wander(self, *a):
            pass

        def think(self):
            pass

        def natural_swipe(self, d):
            pass

    apps = [_app("A", ["跨App共性词"]), _app("B", ["跨App共性词"])]
    candidates.register_apps(apps)

    seen = []

    def _locate(k, v, timeout=2.0, zone=None, screen_w=0):
        seen.append(v)
        return LocateResult(False, None, "测试未命中")

    ex = Executor("fake-serial", _Human(), _Rec(), dry_run=True, config={})
    ex.dry_run = False
    ex._locate = _locate
    ex._kb_candidates = lambda app, primary: ([primary], False)
    ex._kb_mark_fail = lambda app, prims: None
    ex._click_obj = lambda obj, relocate=None: None
    ex._app_extras = lambda app: {}

    ex._current_bid = "sign"
    ex._step_click_first({"type": "click_first", "timeout": 0.1}, "A", allow_vision=False)

    assert "跨App共性词" in seen, f"未按行为自动并入共性词，实际探测: {seen}"
    candidates.register_apps([])
    print("OK  未写 candidates_from 时按 _current_bid 自动并入共性词")


def t_stopwords_never_promoted():
    """弹窗关闭词/导航词绝不能被升级成 sign 共性词（否则会去点「关闭」）。"""
    apps = [_app("A", ["关闭", "暂不", "以后再说", "我", "我的", "签到页"]),
            _app("B", ["关闭", "暂不", "以后再说", "我", "我的", "签到页"])]
    mined = candidates.mine_words(apps)
    words = set(mined.get("sign", []))
    leaked = words & candidates.STOPWORDS
    assert not leaked, f"停用词泄漏进共性词表: {leaked}"
    assert "签到页" in words, words
    print("OK  停用词不进归纳结果")


def t_category_for_intent():
    assert candidates.category_for_intent("sign") == "sign"
    assert candidates.category_for_intent("reserve") == "sign"
    assert candidates.category_for_intent("unknown_behavior") is None
    print("OK  行为→词表类别映射")
