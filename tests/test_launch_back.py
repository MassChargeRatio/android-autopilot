# -*- coding: utf-8 -*-
"""test_launch_back.py - launch_back 配置的启动后 BACK 接线（无需真机）

背景（AUTOP-FAMILY-2026-11-01，未找到文本按钮/候选未出现族）：
    某些 App 启动落在**无底部导航的全屏内容页**（悟空浏览器=全屏短剧播放页、
    飞猪旅行=开屏广告页），冷/温启动都落同一页。首行为（如 click_text[赚钱]）
    因目标文本不在树上而失败，连败 3 天；`_reset_to_landing` 的 `_at_top_level`
    在 WebView 重页面上 dump 不可靠（实测「BACK 未回到顶层页 -> 重启」，重启又
    落回同一脏页）。

正确行为：
    1. `launch_back: N` 时，`_open_app` 成功后调用 `_back_to_landing_after_launch`；
    2. 未配置时**不得**调用（零行为变化）；
    3. 已在顶层页时不按 BACK（保护正常落地的 App）；
    4. dry_run 下不得触碰设备。

运行：
    python tests/test_launch_back.py
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


def _mk_app(launch_back=None):
    app = {
        "name": "测试App",
        "package": "com.test.app",
        "behaviors": {
            "sign": [{"type": "click_text", "text": "签到"}],
            "watch": [{"type": "click_text", "text": "看视频"}],
        },
    }
    if launch_back is not None:
        app["launch_back"] = launch_back
    return app


def t_launch_back_calls_helper_when_configured():
    """配置 launch_back=1 时，_open_app 成功后必须调用启动 BACK 助手。"""
    ex = _mk(dry_run=False)
    calls = []
    ex._open_app = lambda pkg, name, reset=False: True
    ex._back_to_landing_after_launch = lambda pkg, name, n: calls.append((pkg, n)) or True
    ex._reset_to_landing = lambda pkg, name, max_back=3: None
    ex._run_actions = lambda actions, name, bid: True
    ex.run_app_flow(_mk_app(launch_back=1), [("sign", "签到")])
    assert calls == [("com.test.app", 1)], calls
    print("OK  launch_back=1 -> 启动后调用 1 次 BACK 助手")


def t_launch_back_not_called_without_config():
    """未配置 launch_back 时不得调用（零行为变化）。"""
    ex = _mk(dry_run=False)
    calls = []
    ex._open_app = lambda pkg, name, reset=False: True
    ex._back_to_landing_after_launch = lambda pkg, name, n: calls.append((pkg, n)) or True
    ex._reset_to_landing = lambda pkg, name, max_back=3: None
    ex._run_actions = lambda actions, name, bid: True
    ex.run_app_flow(_mk_app(), [("sign", "签到")])
    assert calls == [], calls
    print("OK  未配置 launch_back 不调用 BACK 助手")


def t_launch_back_dry_run_no_device():
    """dry_run 下 _back_to_landing_after_launch 直接返回，不触碰设备。"""
    ex = _mk(dry_run=True)
    joined_before = "\n".join(m for _l, m in ex.recorder.lines)
    ex._back_to_landing_after_launch("com.test.app", "测试App", 1)
    assert ex.d is None, "dry_run 不应连设备"
    joined = "\n".join(m for _l, m in ex.recorder.lines)
    assert "[dry-run]" in joined or joined == joined_before or "launch_back" not in joined
    print("OK  dry_run 下 BACK 助手不触碰设备")


class _FakeD:
    """伪造设备：记录 BACK 次数，可切换是否已在顶层页 / 是否离开 App。

    注意 `.info` 必须是**属性**（返回 dict），与真实 uiautomator2 Device 一致：
    `self.d.info.get("currentPackageName")` 依赖 dict 接口。
    """

    def __init__(self):
        self.back_presses = 0
        self.at_top = False
        self._fg = "com.test.app"

    @property
    def info(self):
        return {"currentPackageName": self._fg}

    def press(self, key):
        self.back_presses += 1
        # 按一次 BACK 后模拟回到顶层页（如悟空短剧播放页 -> 带导航页）
        self.at_top = True

    def window_size(self):
        return (1080, 2340)


class _DumpD(_FakeD):
    """在顶层页时可 dump 出底部导航，非顶层页返回空。"""

    def dump_hierarchy(self):
        if self.at_top:
            return (
                '<hierarchy rotation="0" width="1080" height="2340">'
                '<node text="首页" content-desc="" bounds="[0,2113][216,2170]"/>'
                '<node text="赚钱" content-desc="" bounds="[432,2113][648,2170]"/>'
                '<node text="我的" content-desc="" bounds="[864,2113][1080,2170]"/>'
                '</hierarchy>'
            )
        return ""


def t_helper_presses_back_when_dirty():
    """非顶层页时按 BACK（最多 max_back 次）。"""
    ex = _mk(dry_run=False)
    d = _DumpD()
    ex.d = d
    ex._back_to_landing_after_launch("com.test.app", "测试App", 1)
    assert d.back_presses == 1, f"脏落地页应按 1 次 BACK，实际 {d.back_presses}"
    print("OK  脏落地页按 1 次 BACK")


def t_helper_no_back_when_already_top():
    """已在顶层页时一个 BACK 都不按。"""
    ex = _mk(dry_run=False)
    d = _DumpD()
    d.at_top = True
    ex.d = d
    ex._back_to_landing_after_launch("com.test.app", "测试App", 1)
    assert d.back_presses == 0, f"顶层页不应按 BACK，实际 {d.back_presses}"
    print("OK  顶层页不按 BACK")


def t_helper_stops_when_leaves_app():
    """BACK 后前台离开目标 App 时停手（避免退到桌面）。"""
    ex = _mk(dry_run=False)
    d = _FakeD()
    d.at_top = False
    d._fg = "com.other.app"   # BACK 后跳到别的 App
    ex.d = d
    ex._back_to_landing_after_launch("com.test.app", "测试App", 3)
    assert d.back_presses == 1, f"离开 App 应停手（1 次），实际 {d.back_presses}"
    print("OK  离开目标 App 时停手")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    failed = 0
    for fn in tests:
        try:
            if fn() is False:
                failed += 1
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
