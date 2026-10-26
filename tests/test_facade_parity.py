# -*- coding: utf-8 -*-
"""test_facade_parity.py - D 批「门面等价性」测试

D 批把 executor.py 1010 行三分拆为 device_session.py / locator.py /
behavior_runner.py，executor.py 收缩为 ~160 行门面（多继承 mixin）。

本测试对 A/B 终态方法清单逐一断言 Executor 门面 hasattr + callable，
防止搬迁漏方法或改名；同时抽查三个部件类的方法归属，防止职责漂移。

运行：
    python -m pytest tests/test_facade_parity.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import executor  # noqa: E402
from device_session import DeviceSession  # noqa: E402
from locator import Locator, LocateResult, _parse_sel  # noqa: E402
from behavior_runner import BehaviorRunner, StepError  # noqa: E402


# A/B 终态方法清单（三分拆前 executor.py 中 Executor 的全部可调用方法）
FACADE_METHODS = [
    # 设备会话（device_session）
    "connect", "_at_top_level", "_reset_to_landing", "_open_app",
    "_close_app", "_wait_page_ready", "_dump_safe",
    # 元素定位（locator）
    "_locate", "_label_of", "_pick_best", "_click_obj",
    "_kb_candidates", "_kb_mark_fail", "_locate_with_kb",
    "_click_tracked", "_vision_or_miss", "_vision_click",
    # 行为执行（behavior_runner）
    "run_app_flow", "_resolve", "_pick_variant", "_run_actions",
    "_exec_step", "_dispatch_step", "_dispatch_probe", "_run_kind",
    "_dispatch",
    "_step_any_of", "_step_random", "_step_wait", "_step_think",
    "_step_click_text", "_step_click_id", "_step_click_desc",
    "_step_click_point", "_step_click_first",
    "_step_swipe", "_step_swipe_natural", "_step_captcha",
    "_step_scroll_to", "_step_back", "_step_home",
    "_step_reward", "_reward_candidates", "_step_ensure",
]

# 各部件的专属方法（MRO 归属抽查：门面多继承后仍应可经 Executor 调用）
SESSION_METHODS = ["connect", "_at_top_level", "_reset_to_landing",
                   "_open_app", "_close_app", "_wait_page_ready", "_dump_safe"]
LOCATOR_METHODS = ["_locate", "_pick_best", "_click_obj", "_kb_candidates",
                   "_kb_mark_fail", "_locate_with_kb", "_click_tracked",
                   "_vision_or_miss", "_vision_click"]
RUNNER_METHODS = ["run_app_flow", "_resolve", "_pick_variant", "_run_actions",
                  "_exec_step", "_dispatch_step", "_dispatch_probe",
                  "_run_kind", "_dispatch", "_step_any_of", "_step_random",
                  "_step_wait", "_step_think", "_step_click_text",
                  "_step_click_id", "_step_click_desc", "_step_click_point",
                  "_step_click_first", "_step_swipe", "_step_swipe_natural",
                  "_step_captcha", "_step_scroll_to", "_step_back",
                  "_step_home", "_step_reward", "_reward_candidates",
                  "_step_ensure"]


def t_facade_has_all_methods():
    """门面 Executor 对 A/B 终态方法清单逐一 hasattr + callable。"""
    ex = executor.Executor.__new__(executor.Executor)
    missing = [m for m in FACADE_METHODS if not hasattr(ex, m)]
    assert not missing, f"门面缺失方法: {missing}"
    not_callable = [m for m in FACADE_METHODS
                    if hasattr(ex, m) and not callable(getattr(ex, m))]
    assert not not_callable, f"门面方法不可调用: {not_callable}"
    print(f"OK  门面方法齐全且可调用（{len(FACADE_METHODS)} 个）")


def t_components_exist():
    """三个新部件类存在且方法可调用（防职责漂移）。"""
    for cls, methods in ((DeviceSession, SESSION_METHODS),
                         (Locator, LOCATOR_METHODS),
                         (BehaviorRunner, RUNNER_METHODS)):
        inst = cls.__new__(cls)
        missing = [m for m in methods if not callable(getattr(inst, m, None))]
        assert not missing, f"{cls.__name__} 缺失方法: {missing}"
    print("OK  三个部件类方法齐全")


def t_re_exports():
    """executor 门面 re-export：StepError / LocateResult / _parse_sel。"""
    assert executor.StepError is StepError, "StepError 未 re-export"
    assert executor.LocateResult is LocateResult, "LocateResult 未 re-export"
    assert executor._parse_sel is _parse_sel, "_parse_sel 未 re-export"
    assert _parse_sel("text=签到") == ("text", "签到")
    assert _parse_sel("签到") == ("text", "签到")
    print("OK  re-export 齐备（StepError/LocateResult/_parse_sel）")


def t_top_level_labels_global_available():
    """executor 模块级 TOP_LEVEL_LABELS 保留（test_executor_reset 打桩依赖）。"""
    assert hasattr(executor, "TOP_LEVEL_LABELS")
    print("OK  executor.TOP_LEVEL_LABELS 保留")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"门面等价性测试: {len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
