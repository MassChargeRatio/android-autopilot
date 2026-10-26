# -*- coding: utf-8 -*-
"""test_zone_pick.py - 第3步：位置先验 zone 权重（AUTOP-SELFSEARCH-2026-10-20 第3步）

用户原话：「按钮名称、按钮位置、常用步骤的共性」——候选文案在多处匹配时，
位置本身就是先验：底部导航带的 tab 类按钮、右上角/右缘的浮球类按钮都应加分。

三区（常量在 pick_locate.py）：
  * tab_zone   ：bottom band（top >= ZONE_BOTTOM_BAND*screen_h），+150/-150；
  * top_right  ：顶部右上（top <= ZONE_TOP_BAND*screen_h 且 x 中心靠右），+150/-150；
  * right_edge ：右缘（x 中心 >= ZONE_RIGHT_RATIO*screen_w），+100/-100。

规则：
  * 未知屏高/屏宽（0）→ 该 zone 不做任何加分（不猜位置）；
  * 条目缺坐标（left/right 或 top 缺失）→ 该条目 zone 加分跳过（中性，不惩罚）；
  * 未知 zone 值 → 忽略（不影响既有 nav 带加分与拒配）；
  * 纯函数旧签名兼容：pick_best(entries, target, kind, screen_h, log) 仍可用。

运行：
    python -m pytest tests/test_zone_pick.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pick_locate import (pick_best, ZONE_BOTTOM_BAND, ZONE_TOP_BAND,  # noqa: E402
                         ZONE_RIGHT_RATIO)
from executor import Executor  # noqa: E402


class _Info(dict):
    pass


class _Obj:
    def __init__(self, info):
        self.info = _Info(info)


class _Objs:
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


SCREEN_H, SCREEN_W = 2340, 1080


def t_tab_zone_prefers_bottom():
    """tab_zone：底部带条目（含 +150）胜过中部可点击条目（-150）。"""
    entries = [
        {"label": "任务", "clickable": True, "top": 600,
         "left": 0, "right": 300},
        {"label": "任务", "clickable": False, "top": 2300,
         "left": 0, "right": 300},
    ]
    idx = pick_best(entries, "任务", "text", SCREEN_H, zone="tab_zone")
    assert idx == 1, f"应选底部带条目，实际 {idx}"
    assert int(ZONE_BOTTOM_BAND * SCREEN_H) <= 2300, "fixture 应落在底部带内"
    print("OK  tab_zone 底部带条目胜出")


def t_tab_zone_no_zone_tie_keeps_first():
    """无 zone：两完全相等可点击节点平局取先（旧行为回归保护）。"""
    entries = [
        {"label": "任务", "clickable": True, "top": 600},
        {"label": "任务", "clickable": True, "top": 2260},
    ]
    assert pick_best(entries, "任务", "text", SCREEN_H) == 0
    print("OK  无 zone 时平局取先（不引入位置偏见）")


def t_top_right_prefers_corner():
    """top_right：右上角条目胜过左上角同文案。"""
    entries = [
        {"label": "领现金", "clickable": True, "top": 300,
         "left": 900, "right": 1060},
        {"label": "领现金", "clickable": True, "top": 300,
         "left": 100, "right": 260},
    ]
    idx = pick_best(entries, "领现金", "text", SCREEN_H,
                    screen_w=SCREEN_W, zone="top_right")
    assert idx == 0, f"应选右上角条目，实际 {idx}"
    print("OK  top_right 右上角条目胜出")


def t_right_edge_prefers_right():
    """right_edge：右缘条目胜过左侧同文案。"""
    entries = [
        {"label": "红包", "clickable": True, "top": 1200,
         "left": 900, "right": 1060},
        {"label": "红包", "clickable": True, "top": 1200,
         "left": 100, "right": 260},
    ]
    idx = pick_best(entries, "红包", "text", SCREEN_H,
                    screen_w=SCREEN_W, zone="right_edge")
    assert idx == 0, f"应选右缘条目，实际 {idx}"
    print("OK  right_edge 右缘条目胜出")


def t_zone_ignored_when_screen_unknown():
    """未知屏高/屏宽：zone 不做加分，平局取先。"""
    entries = [
        {"label": "任务", "clickable": True, "top": 600,
         "left": 0, "right": 300},
        {"label": "任务", "clickable": True, "top": 2260,
         "left": 0, "right": 300},
    ]
    assert pick_best(entries, "任务", "text", 0,
                     screen_w=0, zone="tab_zone") == 0
    assert pick_best(entries, "任务", "text", SCREEN_H,
                     screen_w=0, zone="right_edge") == 0
    print("OK  未知屏高/屏宽时 zone 无加分")


def t_zone_missing_coords_no_crash():
    """条目缺坐标：该条目 zone 加分跳过，不崩、不误惩罚。"""
    entries = [
        {"label": "任务", "clickable": True, "top": 600},
        {"label": "任务", "clickable": True, "top": 2260},
    ]
    assert pick_best(entries, "任务", "text", SCREEN_H, screen_w=SCREEN_W,
                     zone="right_edge") == 0
    assert pick_best(entries, "任务", "text", SCREEN_H, screen_w=SCREEN_W,
                     zone="top_right") == 0
    print("OK  缺坐标条目 zone 加分中性化")


def t_unknown_zone_ignored():
    """未知 zone 值：忽略，不影响既有择优。"""
    entries = [
        {"label": "任务", "clickable": True, "top": 600},
        {"label": "任务", "clickable": True, "top": 2260},
    ]
    assert pick_best(entries, "任务", "text", SCREEN_H, screen_w=SCREEN_W,
                     zone="bogus") == 0
    print("OK  未知 zone 值忽略")


def t_legacy_signature_log_positional():
    """旧签名兼容：pick_best(entries, target, kind, screen_h, log) 仍可用。"""
    lines = []
    entries = [
        {"label": "签到", "clickable": False, "top": 100},
        {"label": "签到", "clickable": True, "top": 100},
    ]
    idx = pick_best(entries, "签到", "text", SCREEN_H,
                    lambda e, app="", level="INFO": lines.append((level, e)))
    assert idx == 1, "可点击条目应胜出（旧签名下位置参数仍解析为 log）"
    assert any("择优" in m for _l, m in lines), lines
    print("OK  旧签名兼容（第5个位置参数仍是 log）")


def t_executor_pick_best_passes_zone_and_screen_w():
    """executor._pick_best 透传 zone/screen_w：tab_zone 选中底部条目。"""
    ex = Executor.__new__(Executor)
    ex.recorder = _Rec()

    class _D:
        info = {"displayHeight": 2340, "displayWidth": 1080}
    ex.d = _D()
    obj = _Objs([
        {"text": "任务", "clickable": True,
         "bounds": {"left": 0, "top": 600, "right": 300, "bottom": 700}},
        {"text": "任务", "clickable": True,
         "bounds": {"left": 0, "top": 2300, "right": 300, "bottom": 2400}},
    ])
    best = ex._pick_best(obj, "任务", "text", zone="tab_zone")
    assert best.info["bounds"]["top"] == 2300, best.info
    print("OK  executor._pick_best 透传 zone/screen_w")


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
