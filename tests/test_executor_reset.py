# -*- coding: utf-8 -*-
"""test_executor_reset.py - 执行器的「行为间复位」接线（无需真机）

背景（真实缺陷）：
    一个 App 上要跑多个行为（签到 / 看视频 / 提现），它们**共享同一个 App
    实例**。`run_app_flow` 原本是「一个 App 只 `_open_app` 一次，然后行为
    串行执行」，第 N 个行为跑到二级/三级页后留下的页面会污染第 N+1 个行为。

    实测：喜番免费短剧 sign 三级导航（我的 → 福利中心 → 签到）后停在
    「签到」页，紧随的 watch 比例坐标点飞到了 com.eggflower.read
    （蛋花免费小说，序列里的上一个 App）—— 一个 App 的收益被另一个 App 污染。

正确行为：
    1. 第 2 个及以后的行为开始前必须调用复位；
    2. 已经在顶层页时**不能按 BACK**（多数 App 在「我的」tab 按 BACK 会直接
       退出 App，白吃一次冷启动）；
    3. dry_run 下不得触碰设备。

运行：
    python tests/test_executor_reset.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import executor as E  # noqa: E402


class _Rec:
    def __init__(self):
        self.lines = []

    def log(self, msg, app=None, level="INFO"):
        self.lines.append((level, str(msg)))


class _Human:
    def think(self):
        pass

    def after_open(self):
        pass

    def close_naturally(self, d):
        pass


def _mk(dry_run=True):
    return E.Executor("serial", _Human(), _Rec(), dry_run=dry_run,
                      config={}, base_dir=ROOT)


APP = {
    "name": "测试App",
    "package": "com.test.app",
    "behaviors": {
        "sign": [{"type": "click_text", "text": "签到"}],
        "watch": [{"type": "click_text", "text": "看视频"}],
        "withdraw": [{"type": "click_text", "text": "提现"}],
    },
}


def t_dry_run_does_not_touch_device():
    """dry_run 下跑完三个行为，不得有任何设备交互。"""
    ex = _mk(dry_run=True)
    ex.run_app_flow(APP, [("sign", "签到"), ("watch", "看视频"),
                          ("withdraw", "提现")])
    assert ex.d is None, "dry_run 不应连设备"
    joined = "\n".join(m for _l, m in ex.recorder.lines)
    assert "[dry-run]" in joined, joined
    assert "行为[sign]" in joined and "行为[watch]" in joined
    print("OK  dry_run 下不触碰设备且计划完整")


def t_reset_is_noop_in_dry_run():
    """_reset_to_landing 在 dry_run 下必须直接返回。"""
    ex = _mk(dry_run=True)
    ex._reset_to_landing("com.test.app", "测试App")
    joined = "\n".join(m for _l, m in ex.recorder.lines)
    assert "复位" not in joined, f"dry_run 不该执行复位: {joined}"
    print("OK  dry_run 下复位为空操作")


def t_reset_called_between_behaviors():
    """第 2 个及以后的行为前必须复位（用计数替身验证接线）。

    注意：dry_run 会在进入循环前就返回，所以这里必须走**真实**循环路径，
    把设备相关方法换成替身。
    """
    ex = _mk(dry_run=False)
    calls = []
    ran = []
    ex._open_app = lambda pkg, name, reset=False: None
    ex._run_actions = lambda actions, name, bid: ran.append(bid) or True
    ex._reset_to_landing = lambda pkg, name, max_back=3, launch_reset=False, launch_back=0: calls.append(pkg)
    ex.run_app_flow(APP, [("sign", "签到"), ("watch", "看视频"),
                          ("withdraw", "提现")])
    assert ran == ["sign", "watch", "withdraw"], ran
    assert len(calls) == 2, f"3 个行为应复位 2 次，实际 {len(calls)}"
    assert all(c == "com.test.app" for c in calls), calls
    print("OK  行为之间复位接线正确（3 个行为 -> 2 次复位）")


def t_reset_not_called_for_single_behavior():
    """只有一个行为时不需要复位。"""
    ex = _mk(dry_run=False)
    calls = []
    ex._open_app = lambda pkg, name, reset=False: None
    ex._run_actions = lambda actions, name, bid: True
    ex._reset_to_landing = lambda pkg, name, max_back=3, launch_reset=False, launch_back=0: calls.append(pkg)
    ex.run_app_flow(APP, [("sign", "签到")])
    assert calls == [], calls
    print("OK  单行为不复位")


def t_at_top_level_true_when_ui_page_missing():
    """ui_page 缺失时关闭复位功能，退化为旧行为而不是崩溃。"""
    ex = _mk(dry_run=True)
    saved = E.TOP_LEVEL_LABELS
    try:
        E.TOP_LEVEL_LABELS = set()
        assert ex._at_top_level() is True
    finally:
        E.TOP_LEVEL_LABELS = saved
    print("OK  ui_page 缺失时优雅降级（关闭复位，不崩）")


def t_reset_propagates_launch_flags():
    """复位调用点把 launch_reset/launch_back 从 app_cfg 传给 _reset_to_landing。"""
    ex = _mk(dry_run=False)
    calls = []
    ex._open_app = lambda pkg, name, reset=False: None
    ex._run_actions = lambda actions, name, bid: True
    ex._reset_to_landing = (
        lambda pkg, name, max_back=3, launch_reset=False, launch_back=0:
        calls.append((launch_reset, launch_back)))
    app = dict(APP, launch_reset=True, launch_back=2)
    ex.run_app_flow(app, [("sign", "签到"), ("watch", "看视频")])
    assert calls == [(True, 2)], f"应传 (launch_reset=True, launch_back=2)，实际 {calls}"
    print("OK  复位调用点传递 launch_reset/launch_back")


def t_reopen_clean_cold_starts_when_launch_reset():
    """复位重启：launch_reset=True 时冷启动（reset=True）；launch_back>0 时退脏页。"""
    ex = _mk(dry_run=False)
    got = []
    ex._open_app = lambda pkg, name, reset=False: got.append(("open", reset)) or True
    ex._back_to_landing_after_launch = lambda pkg, name, n: got.append(("back", n)) or True
    ex._reopen_clean("com.test.app", "测试App", launch_reset=True, launch_back=2)
    assert got == [("open", True), ("back", 2)], f"应冷启动+退脏页，实际 {got}"
    print("OK  复位重启冷启动+退脏页")


def t_reopen_clean_resumes_when_no_launch_reset():
    """复位重启：无 launch_reset 时 resume（reset=False），无 launch_back 时不退脏页。"""
    ex = _mk(dry_run=False)
    got = []
    ex._open_app = lambda pkg, name, reset=False: got.append(("open", reset)) or True
    ex._back_to_landing_after_launch = lambda pkg, name, n: got.append(("back", n)) or True
    ex._reopen_clean("com.test.app", "测试App", launch_reset=False, launch_back=0)
    assert got == [("open", False)], f"默认应 resume，实际 {got}"
    print("OK  复位重启默认 resume 不退脏页")


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
