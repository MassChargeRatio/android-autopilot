# -*- coding: utf-8 -*-
"""
test_knowledge.py - 元素知识库经验回写 单元自测

覆盖：
  1. 读取 / 按 app+selector 查询；
  2. 执行成功 mark_ok（刷新 last_ok、fail_times 清零、解除 disabled）；
  3. 执行失败 mark_fail 计数递增；
  4. continuous 失败超阈值自动 disabled；
  5. alternative 轮换（candidates 顺序 + disabled 若干元素被跳过）；
  6. 无知识库记录时走原逻辑（candidate_selectors 返回主 selector，has_element=False）；
  7. dry-run 不改盘。

运行：
    python test_knowledge.py            # 直接跑
    python -m unittest test_knowledge   # 或 unittest
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from knowledge import KnowledgeBase  # noqa: E402
from executor import _parse_sel      # noqa: E402

SAMPLE = {
    "apps": [
        {
            "app": "示例阅读App",
            "elements": [
                {
                    "selector": "text=每日签到",
                    "kind": "text",
                    "desc": "签到按钮",
                    "usage": "点它签到",
                    "alternatives": ["text=签到", "id=com.x:id/btn"],
                    "last_ok": "2020-01-01",
                    "fail_times": 0,
                    "disabled": False,
                },
                {
                    "selector": "text=看视频",
                    "kind": "text",
                    "desc": "视频tab(旧)",
                    "usage": "看视频入口",
                    "alternatives": ["text=视频"],
                    "last_ok": "2020-01-01",
                    "fail_times": 5,
                    "disabled": True,
                },
            ],
        }
    ]
}

import yaml  # noqa: E402


def make_kb(dry_run=False, threshold=3):
    """在每个测试的独立临时目录里建一个知识库实例，互不污染。"""
    tmp = tempfile.TemporaryDirectory()
    kb = KnowledgeBase(
        path=os.path.join(tmp.name, "element_knowledge.yaml"),
        recorder=None, threshold=threshold, dry_run=dry_run,
        base_dir=tmp.name,
    )
    # 直接写入样例数据文件，让 load() 读取
    with open(kb.path, "w", encoding="utf-8") as f:
        yaml.safe_dump(SAMPLE, f, allow_unicode=True, sort_keys=False)
    kb.load()
    kb.tmp = tmp  # 记录临时目录，teardown 时清理
    return kb


class TestBasic(unittest.TestCase):
    def test_read_and_lookup(self):
        kb = make_kb()
        self.assertTrue(kb.has_element("示例阅读App", "text=每日签到"))
        e = kb.get("示例阅读App", "text=每日签到")
        self.assertIsNotNone(e)
        self.assertEqual(e["desc"], "签到按钮")
        self.assertEqual(e["alternatives"], ["text=签到", "id=com.x:id/btn"])
        # 不存在的元素
        self.assertFalse(kb.has_element("示例阅读App", "text=不存在"))
        self.assertIsNone(kb.get("其它app", "text=每日签到"))
        kb.tmp.cleanup()

    def test_no_knowledge_falls_back_to_original(self):
        """无知识库记录时走原逻辑：has_element=False、候选即主 selector。"""
        kb = make_kb()
        self.assertFalse(kb.has_element("示例阅读App", "text=从未记录的按钮"))
        # executor._kb_candidates 语义：无记录 -> ([primary], False)
        cands = kb.candidate_selectors("示例阅读App", "text=从未记录的按钮")
        self.assertEqual(cands, ["text=从未记录的按钮"])
        kb.tmp.cleanup()

    def test_candidates_with_alternatives_rotation(self):
        kb = make_kb()
        cands = kb.candidate_selectors("示例阅读App", "text=每日签到")
        # 主 selector 优先，alternatives 依次（去重保留顺序）
        self.assertEqual(cands,
                         ["text=每日签到", "text=签到", "id=com.x:id/btn"])
        kb.tmp.cleanup()

    def test_disabled_element_returns_empty_candidates(self):
        """disabled 元素：candidates 返回空列表，由上层转视觉兜底。"""
        kb = make_kb()
        cands = kb.candidate_selectors("示例阅读App", "text=看视频")
        self.assertEqual(cands, [])
        kb.tmp.cleanup()


class TestWriteback(unittest.TestCase):
    def test_mark_ok_refresh(self):
        kb = make_kb()
        e = kb.get("示例阅读App", "text=每日签到")
        e["fail_times"] = 2
        e["disabled"] = True
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        ok = kb.mark_ok("示例阅读App", "text=每日签到")
        self.assertTrue(ok)
        e = kb.get("示例阅读App", "text=每日签到")
        self.assertEqual(e["last_ok"], today)
        self.assertEqual(e["fail_times"], 0)
        self.assertFalse(e["disabled"])
        kb.tmp.cleanup()

    def test_mark_fail_counting(self):
        kb = make_kb(threshold=3)
        e = kb.get("示例阅读App", "text=每日签到")
        self.assertEqual(e["fail_times"], 0)
        kb.mark_fail("示例阅读App", "text=每日签到")
        self.assertEqual(e["fail_times"], 1)
        kb.mark_fail("示例阅读App", "text=每日签到")
        self.assertEqual(e["fail_times"], 2)
        kb.tmp.cleanup()

    def test_mark_fail_hit_threshold_disables(self):
        kb = make_kb(threshold=3)
        # 已有 2 次，再失败 1 次即达阈值
        e = kb.get("示例阅读App", "text=每日签到")
        e["fail_times"] = 2
        disabled_now = kb.mark_fail("示例阅读App", "text=每日签到")
        self.assertTrue(disabled_now)
        self.assertTrue(e.get("disabled"))
        self.assertEqual(e["fail_times"], 3)
        # 停用后候选为空（转视觉兜底）
        self.assertEqual(
            kb.candidate_selectors("示例阅读App", "text=每日签到"), [])
        kb.tmp.cleanup()

    def test_mark_ok_unregisters_after_disabled(self):
        """被停用后某次成功定位，自动解除 disabled。"""
        kb = make_kb()
        e = kb.get("示例阅读App", "text=每日签到")
        e["disabled"] = True
        e["fail_times"] = 4
        kb.mark_ok("示例阅读App", "text=每日签到")
        self.assertFalse(e["disabled"])
        self.assertEqual(e["fail_times"], 0)
        kb.tmp.cleanup()

    def test_dry_run_does_not_write_file(self):
        kb = make_kb(dry_run=True)
        with open(kb.path, encoding="utf-8") as f:
            before = f.read()
        kb.mark_fail("示例阅读App", "text=每日签到")
        kb.mark_ok("示例阅读App", "text=每日签到")
        with open(kb.path, encoding="utf-8") as f:
            after = f.read()
        self.assertEqual(before, after)  # dry-run 不改盘
        kb.tmp.cleanup()


class TestParseSelector(unittest.TestCase):
    def test_parse_sel(self):
        self.assertEqual(_parse_sel("text=签到"), ("text", "签到"))
        self.assertEqual(_parse_sel("id=com.x:id/btn"), ("id", "com.x:id/btn"))
        self.assertEqual(_parse_sel("desc=返回"), ("desc", "返回"))
        self.assertEqual(_parse_sel("签到"), ("text", "签到"))  # 裸文本默认 text
        self.assertEqual(_parse_sel("  text= 签到  "), ("text", "签到"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
