#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""to_any_of 转换器单测。

覆盖两条转换路径：
  * convert_one  —— 二级（首屏直连 / 我的）
  * convert_deep —— 三级（首屏直连 / 我的 / 我的→任务中心）
以及幂等性（已是 any_of 不再转换）。
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "devtools"))

import to_any_of as T  # noqa: E402


ANCHOR = {
    "type": "click_first",
    "candidates": [{"type": "text", "value": "签到"},
                   {"type": "text", "value": "每日签到"}],
    "timeout": 8,
    "optional": True,
}
TAIL = [{"type": "think"},
        {"type": "click_first", "candidates": [{"type": "text", "value": "领取"}],
         "timeout": 6, "optional": True}]


class TestConvertOne(unittest.TestCase):
    def test_plain_anchor_without_nav_is_skipped(self):
        acts = [dict(ANCHOR)] + [dict(x) for x in TAIL]
        new, ch, why = T.convert_one(acts)
        self.assertFalse(ch)
        self.assertIn("无前置步", why)

    def test_add_nav_creates_two_branches(self):
        acts = [dict(ANCHOR)] + [dict(x) for x in TAIL]
        new, ch, why = T.convert_one(acts, add_nav=True)
        self.assertTrue(ch)
        self.assertEqual(new[0]["type"], "any_of")
        self.assertEqual(len(new[0]["choices"]), 2)
        # 分支1：首屏直连（单个锚点，且必须非 optional 才能"报未命中"）
        self.assertEqual(len(new[0]["choices"][0]), 1)
        self.assertIs(new[0]["choices"][0][0]["optional"], False)
        # 分支2：导航 + think + 锚点
        b2 = new[0]["choices"][1]
        self.assertEqual(b2[0]["type"], "click_point")
        self.assertIn("最右侧", b2[0]["vlm_prompt"])
        self.assertEqual(b2[-1]["type"], "click_first")
        # 尾随步骤保留
        self.assertEqual(new[1:], TAIL)

    def test_existing_nav_becomes_branch2(self):
        nav = dict(T.NAV_POINT)
        acts = [nav, {"type": "think"}, dict(ANCHOR)] + [dict(x) for x in TAIL]
        new, ch, _ = T.convert_one(acts)
        self.assertTrue(ch)
        b2 = new[0]["choices"][1]
        self.assertEqual(len(b2), 3)          # 原前置步(2) + 锚点(1)
        self.assertEqual(b2[0]["type"], "click_point")

    def test_idempotent(self):
        acts = [dict(ANCHOR)]
        new1, ch1, _ = T.convert_one(acts, add_nav=True)
        new2, ch2, why2 = T.convert_one(new1, add_nav=True)
        self.assertTrue(ch1)
        self.assertFalse(ch2)
        self.assertIn("已是 any_of", why2)

    def test_optional_flag_inherited(self):
        acts = [{"type": "click_first", "candidates": [{"type": "text", "value": "x"}],
                 "timeout": 5, "optional": True}]
        new, ch, _ = T.convert_one(acts, add_nav=True)
        self.assertTrue(new[0]["optional"])
        acts2 = [{"type": "click_first", "candidates": [{"type": "text", "value": "x"}],
                  "timeout": 5, "optional": False}]
        new2, _, _ = T.convert_one(acts2, add_nav=True)
        self.assertFalse(new2[0]["optional"])

    def test_variant_structure_untouched(self):
        acts = [[dict(ANCHOR)], [dict(ANCHOR)]]
        new, ch, why = T.convert_one(acts)
        self.assertFalse(ch)
        self.assertIn("变体结构", why)


class TestConvertDeep(unittest.TestCase):
    def test_two_level_when_l2_hit_on_mine(self):
        """我的页本身命中 -> 只加一层导航。"""
        acts = [dict(ANCHOR)] + [dict(x) for x in TAIL]
        new, ch, why = T.convert_deep(acts, l2_label=None)
        self.assertTrue(ch)
        b2 = new[0]["choices"][1]
        self.assertEqual([a["type"] for a in b2],
                         ["click_point", "think", "click_first"])
        self.assertIn("二级导航", why)

    def test_three_level_with_l2_entry(self):
        """签到在三级页 -> 我的 → 任务中心 → 签到。"""
        acts = [dict(ANCHOR)] + [dict(x) for x in TAIL]
        new, ch, why = T.convert_deep(acts, l2_label="任务中心")
        self.assertTrue(ch)
        b2 = new[0]["choices"][1]
        self.assertEqual([a["type"] for a in b2],
                         ["click_point", "think", "click_first", "think",
                          "click_first"])
        # 实测到的入口文案排在候选第一位
        self.assertEqual(b2[2]["candidates"][0]["value"], "任务中心")
        self.assertIs(b2[2]["optional"], False)
        # 三级锚点即原锚点
        self.assertEqual(b2[-1]["candidates"][0]["value"], "签到")
        self.assertIn("我的→任务中心", why)

    def test_l2_candidates_deduplicated(self):
        acts = [dict(ANCHOR)]
        new, _, _ = T.convert_deep(acts, l2_label="福利")
        vals = [c["value"] for c in new[0]["choices"][1][2]["candidates"]]
        self.assertEqual(len(vals), len(set(vals)))
        self.assertEqual(vals[0], "福利")

    def test_deep_idempotent(self):
        acts = [dict(ANCHOR)]
        new1, ch1, _ = T.convert_deep(acts, l2_label="任务中心")
        _, ch2, why2 = T.convert_deep(new1, l2_label="任务中心")
        self.assertTrue(ch1)
        self.assertFalse(ch2)
        self.assertIn("已是 any_of", why2)

    def test_extra_steps_for_sidebar_entry(self):
        """抖音系：我的 → ≡更多(desc) → 金币。入口是 desc 不是 text。"""
        acts = [dict(ANCHOR)] + [dict(x) for x in TAIL]
        sidebar = [{"type": "click_desc", "desc": "更多",
                    "timeout": 6, "optional": False}]
        new, ch, why = T.convert_deep(acts, extra_steps=sidebar)
        self.assertTrue(ch)
        b2 = new[0]["choices"][1]
        self.assertEqual([a["type"] for a in b2],
                         ["click_point", "think", "click_desc", "think",
                          "click_first"])
        self.assertEqual(b2[2]["desc"], "更多")
        self.assertIn("自定义入口", why)

    def test_extra_steps_take_precedence_over_label(self):
        acts = [dict(ANCHOR)]
        sidebar = [{"type": "click_desc", "desc": "更多", "optional": False}]
        new, _, why = T.convert_deep(acts, l2_label="任务中心",
                                     extra_steps=sidebar)
        b2 = new[0]["choices"][1]
        self.assertEqual(b2[2]["type"], "click_desc")
        self.assertIn("自定义入口", why)


if __name__ == "__main__":
    unittest.main(verbosity=2)
