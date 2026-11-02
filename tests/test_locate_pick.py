# -*- coding: utf-8 -*-
"""test_locate_pick.py - Executor._pick_best 单元测试

覆盖两个真实踩坑场景（无需真机）：
  1. textContains 命中多处时，应择优（优先完全相等 / 更短 / 可点击）；
  2. 只命中"长文案里恰好包含关键词"的不可点击节点时，应判为误命中返回 None
     —— 否则 executor 会点错（实测一淘"我的"页里候选 `签到` 唯一命中的是
     FAQ 链接「什么是签到领钱，如何参加？」）。

运行：
    python -m pytest tests/test_locate_pick.py -q
    或直接 python tests/test_locate_pick.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor  # noqa: E402


class _Info(dict):
    pass


class _Obj:
    """模拟 UiObject 单元素"""

    def __init__(self, info):
        self.info = _Info(info)


class _Objs:
    """模拟 UiObject 多匹配（支持 .count 与 [i]）"""

    def __init__(self, infos):
        self._infos = [_Info(i) for i in infos]

    @property
    def count(self):
        return len(self._infos)

    def __getitem__(self, i):
        return _Obj(self._infos[i])

    @property
    def info(self):
        return self._infos[0]


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, event, app="", level="INFO"):
        self.lines.append(f"[{level}] {event}")


def _mk():
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()
    return ex


def t_pick_shortest_clickable():
    ex = _mk()
    obj = _Objs([
        {"text": "约返0.13元", "clickable": False},
        {"text": "元", "clickable": True},
        {"text": "元", "clickable": False},
    ])
    best = ex._pick_best(obj, "元", "text")
    assert best.info["text"] == "元" and best.info["clickable"] is True, best.info
    print("OK  多匹配择优：选中可点击的短文本")


def t_exact_beats_clickable():
    ex = _mk()
    obj = _Objs([
        {"text": "每日签到", "clickable": True},
        {"text": "签到", "clickable": False},
    ])
    best = ex._pick_best(obj, "签到", "text")
    assert best.info["text"] == "签到", best.info
    print("OK  完全相等优先于可点击加分")


def t_reject_long_text():
    """FAQ 问句是超长唯一候选 -> 仍判误命中（打分改造后此行为必须保持）。

    2026-10-28：文案从「过长文案」改为「噪声文案」——旧版按长度阈值拒，
    新版按句式甄别拒；判定结果不变，日志措辞更新。
    """
    ex = _mk()
    obj = _Objs([{"text": "什么是签到领钱，如何参加？", "clickable": False}])
    best = ex._pick_best(obj, "签到", "text")
    assert best is None, f"应判为误命中，实际返回 {best.info if best else None}"
    assert any("噪声" in l for l in ex.recorder.lines), ex.recorder.lines
    print("OK  长文案误命中被拒配（返回 None）")


def t_accept_moderate_text():
    ex = _mk()
    obj = _Objs([{"text": "每日签到领金币", "clickable": False}])
    best = ex._pick_best(obj, "签到", "text")
    assert best is not None, "长度在阈值内的文本应被接受"
    print("OK  阈值内的较长文本仍接受")


def t_long_text_but_clickable_ok():
    ex = _mk()
    obj = _Objs([{"text": "看视频领金币任务中心入口", "clickable": True}])
    best = ex._pick_best(obj, "看视频", "text")
    assert best is not None, "可点击节点不因文案长而被拒"
    print("OK  可点击节点不受长文案拒配影响")


def t_single_match_short():
    ex = _mk()
    obj = _Objs([{"text": "红包签到", "clickable": False}])
    best = ex._pick_best(obj, "签到", "text")
    assert best is not None, "短文本单匹配应接受"
    print("OK  单匹配短文本接受（红包签到）")


if __name__ == "__main__":
    tests = [t_pick_shortest_clickable, t_exact_beats_clickable,
             t_reject_long_text, t_accept_moderate_text,
             t_long_text_but_clickable_ok, t_single_match_short]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
