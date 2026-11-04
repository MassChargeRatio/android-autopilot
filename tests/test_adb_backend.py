# -*- coding: utf-8 -*-
"""test_adb_backend.py - 纯 adb 后端（AUTOP-2026-11-03-M1）单元测试

覆盖 temp/adb_backend.py 7 缺口：
  foreground / dump stale 防护 / resolve 冷启动 / click_text /
  scroll_to_find / window_size / 重试退避。
全部 mock subprocess（patch adb_backend._run / adb_backend.subprocess.run），
不依赖设备。

运行：
    python -m pytest tests/test_adb_backend.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)  # adb_backend.py 在仓库根（tracked，克隆即可测）

import pytest  # noqa: E402

import adb_backend  # noqa: E402

DUMPSYS_SAMPLE = (
    "mCurrentFocus=Window{abc123 u0 com.tencent.mm/com.tencent.mm.ui.LauncherUI}\n"
)
DUMPSYS_FALLBACK = (
    "mFocusedApp=Window{xyz u0 com.ss.android.ugc.aweme/.main.MainActivity}\n"
)
WM_OVERRIDE = "Physical size: 1080x2340\nOverride size: 1080x2400\n"
WM_PHYSICAL = "Physical size: 1080x2340\n"
RESOLVE_SAMPLE = "com.tencent.mm\ncom.tencent.mm/com.tencent.mm.ui.LauncherUI\n"
XML_HIT = ('<hierarchy><node text="赚钱" content-desc="" bounds="[492,2113][588,2170]"/>'
           '<node text="首页" content-desc="" bounds="[0,0][100,100]"/></hierarchy>')


def fake_run(args, timeout=30):
    """按命令内容返回模拟输出（对应真实 adb 返回）。"""
    joined = " ".join(str(a) for a in args)
    if "dumpsys" in joined:
        return DUMPSYS_SAMPLE
    if "wm" in joined and "size" in joined:
        return WM_OVERRIDE
    if "resolve-activity" in joined:
        return RESOLVE_SAMPLE
    if "pull" in joined:
        return ""
    return ""


@pytest.fixture(autouse=True)
def _clean_dump_state():
    adb_backend.reset_dump_state()
    yield
    adb_backend.reset_dump_state()


# ---------------- 缺口 1：foreground() ----------------
def test_parse_foreground_current_focus():
    info = adb_backend.parse_foreground(DUMPSYS_SAMPLE)
    assert info == {"package": "com.tencent.mm",
                    "activity": "com.tencent.mm.ui.LauncherUI"}


def test_parse_foreground_focused_app_fallback():
    info = adb_backend.parse_foreground(DUMPSYS_FALLBACK)
    assert info == {"package": "com.ss.android.ugc.aweme",
                    "activity": ".main.MainActivity"}


def test_parse_foreground_empty():
    assert adb_backend.parse_foreground("no focus line here") == \
        {"package": "", "activity": ""}


def test_foreground_ok(monkeypatch):
    monkeypatch.setattr(adb_backend, "_run", fake_run)
    assert adb_backend.foreground() == "com.tencent.mm"


def test_foreground_missing_returns_empty(monkeypatch):
    """前台取不到必须回 "" 不回 "?"（对齐 device_session 语义）。"""
    monkeypatch.setattr(adb_backend, "_run", lambda *a, **k: "")
    assert adb_backend.foreground() == ""


def test_run_uses_subprocess(monkeypatch):
    """_run 确实走 subprocess.run，命令构造正确（mock subprocess 层）。"""
    class FakeProc:
        stdout = DUMPSYS_SAMPLE
        stderr = ""

    called = {}

    def fake_subprocess_run(args, **kw):
        called["args"] = args
        return FakeProc()

    monkeypatch.setattr(adb_backend.subprocess, "run", fake_subprocess_run)
    out = adb_backend._run(["adb", "-s", "x", "shell", "dumpsys", "window"])
    assert out == DUMPSYS_SAMPLE
    assert "dumpsys" in called["args"]
    assert called["args"][1] == "-s" and called["args"][2] == "x"


# ---------------- 缺口 6：window_size() ----------------
def test_parse_wm_size_override_priority():
    assert adb_backend.parse_wm_size(WM_OVERRIDE) == (1080, 2400)


def test_parse_wm_size_physical_fallback():
    assert adb_backend.parse_wm_size(WM_PHYSICAL) == (1080, 2340)


def test_parse_wm_size_missing():
    assert adb_backend.parse_wm_size("") == (None, None)


def test_window_size_ok(monkeypatch):
    monkeypatch.setattr(adb_backend, "_run", fake_run)
    assert adb_backend.window_size() == (1080, 2400)


def test_window_size_physical(monkeypatch):
    monkeypatch.setattr(adb_backend, "_run", lambda *a, **k: WM_PHYSICAL)
    assert adb_backend.window_size() == (1080, 2340)


def test_window_size_missing(monkeypatch):
    monkeypatch.setattr(adb_backend, "_run", lambda *a, **k: "")
    assert adb_backend.window_size() == (None, None)


# ---------------- 缺口 3：resolve-activity 精确冷启动 ----------------
def test_resolve_activity_ok(monkeypatch):
    monkeypatch.setattr(adb_backend, "_run", fake_run)
    assert adb_backend.resolve_activity("com.tencent.mm") == \
        "com.tencent.mm/com.tencent.mm.ui.LauncherUI"


def test_resolve_activity_none(monkeypatch):
    monkeypatch.setattr(adb_backend, "_run", lambda *a, **k: "NONE")
    assert adb_backend.resolve_activity("com.foo.bar") == ""


def test_cold_start_ok(monkeypatch):
    calls = []
    monkeypatch.setattr(
        adb_backend, "resolve_activity",
        lambda pkg: "com.tencent.mm/com.tencent.mm.ui.LauncherUI")
    monkeypatch.setattr(adb_backend, "shell", lambda cmd: calls.append(cmd))
    monkeypatch.setattr(adb_backend.time, "sleep", lambda *a, **k: None)
    assert adb_backend.cold_start("com.tencent.mm") is True
    assert calls[0] == "am force-stop com.tencent.mm"
    assert calls[1] == "am start -n com.tencent.mm/com.tencent.mm.ui.LauncherUI"


def test_cold_start_fail_no_resolve(monkeypatch):
    monkeypatch.setattr(adb_backend, "resolve_activity", lambda pkg: "")

    def _boom(cmd):
        raise AssertionError("resolve 失败不应调 shell")

    monkeypatch.setattr(adb_backend, "shell", _boom)
    assert adb_backend.cold_start("com.foo") is False


# ---------------- 缺口 4：click_text() ----------------
def test_click_text_hit(monkeypatch):
    calls = []
    monkeypatch.setattr(
        adb_backend, "tap",
        lambda x, y, label="": calls.append((x, y, label)))
    assert adb_backend.click_text(XML_HIT, "赚钱") is True
    assert calls == [(540, 2141, "赚钱")]


def test_click_text_miss(monkeypatch):
    monkeypatch.setattr(
        adb_backend, "tap",
        lambda x, y, label="": (_ for _ in ()).throw(AssertionError("未命中不应点击")))
    assert adb_backend.click_text(XML_HIT, "不存在的文本") is False


# ---------------- 缺口 5：scroll_to_find() ----------------
def test_scroll_to_find_first_hit(monkeypatch):
    monkeypatch.setattr(
        adb_backend, "find",
        lambda xml, pat: [("赚钱", "[0,0][5,5]", "<node/>")])
    monkeypatch.setattr(
        adb_backend, "swipe",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("首屏命中不应滑动")))
    hits = adb_backend.scroll_to_find(XML_HIT, "赚钱")
    assert len(hits) == 1


def test_scroll_to_find_after_swipe(monkeypatch):
    seq = iter([[], [], [("奖励", "[0,0][5,5]", "<node/>")]])
    monkeypatch.setattr(adb_backend, "find", lambda xml, pat: next(seq))
    monkeypatch.setattr(adb_backend, "swipe", lambda *a, **k: None)
    monkeypatch.setattr(adb_backend, "window_size", lambda: (1080, 2340))
    monkeypatch.setattr(adb_backend, "dump", lambda name: "<hierarchy/>")
    hits = adb_backend.scroll_to_find(XML_HIT, "奖励", max_swipes=3)
    assert len(hits) == 1


def test_scroll_to_find_exhausted(monkeypatch):
    monkeypatch.setattr(adb_backend, "find", lambda xml, pat: [])
    monkeypatch.setattr(adb_backend, "swipe", lambda *a, **k: None)
    monkeypatch.setattr(adb_backend, "window_size", lambda: (1080, 2340))
    monkeypatch.setattr(adb_backend, "dump", lambda name: "<hierarchy/>")
    assert adb_backend.scroll_to_find(XML_HIT, "没有的", max_swipes=2) == []


# ---------------- 缺口 2：dump() stale 防护 ----------------
def _big_xml(tag):
    return ("<hierarchy>" + "<!--padding-->" * 60 +
            f'<node text="{tag}" bounds="[0,0][10,10]"/></hierarchy>')


def test_dump_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(adb_backend, "OUT", str(tmp_path))
    monkeypatch.setattr(adb_backend, "shell", lambda *a, **k: "")
    monkeypatch.setattr(adb_backend, "_run", lambda *a, **k: "")
    xml = _big_xml("新内容")
    (tmp_path / "probe.xml").write_text(xml, encoding="utf-8")
    assert adb_backend.dump("probe.xml") == xml


def test_dump_stale_three_same(tmp_path, monkeypatch):
    """连续 3 次 dump 字节数相同 => 旧 _p.xml 工件，判 stale 回 ""。"""
    monkeypatch.setattr(adb_backend, "OUT", str(tmp_path))
    monkeypatch.setattr(adb_backend, "shell", lambda *a, **k: "")
    monkeypatch.setattr(adb_backend, "_run", lambda *a, **k: "")
    monkeypatch.setattr(adb_backend.time, "sleep", lambda *a, **k: None)
    xml = _big_xml("旧工件")
    (tmp_path / "probe.xml").write_text(xml, encoding="utf-8")
    # 前两次：不足 3 连，无法断定 stale，返回内容
    assert adb_backend.dump("probe.xml") == xml
    assert adb_backend.dump("probe.xml") == xml
    # 第三次：3 连相同 -> 判 stale，重试仍相同 -> 回 ""
    assert adb_backend.dump("probe.xml") == ""


def test_dump_recovers_after_size_change(tmp_path, monkeypatch):
    """stale 后 size 变化 => 新内容，恢复正常返回。"""
    monkeypatch.setattr(adb_backend, "OUT", str(tmp_path))
    monkeypatch.setattr(adb_backend, "shell", lambda *a, **k: "")
    monkeypatch.setattr(adb_backend, "_run", lambda *a, **k: "")
    monkeypatch.setattr(adb_backend.time, "sleep", lambda *a, **k: None)
    old = _big_xml("旧")
    (tmp_path / "probe.xml").write_text(old, encoding="utf-8")
    assert adb_backend.dump("probe.xml") == old   # 1st
    assert adb_backend.dump("probe.xml") == old   # 2nd
    assert adb_backend.dump("probe.xml") == ""    # 3rd: stale
    fresh = _big_xml("新内容变化后字节数不同" * 5)
    (tmp_path / "probe.xml").write_text(fresh, encoding="utf-8")
    assert adb_backend.dump("probe.xml") == fresh  # size 变化 -> 新内容


# ---------------- 缺口 7：重试/退避 ----------------
def test_tap_retry(monkeypatch):
    monkeypatch.setattr(adb_backend, "shell", lambda *a, **k: "")
    assert adb_backend.tap_retry(10, 20) is True


def test_back_retry(monkeypatch):
    monkeypatch.setattr(adb_backend, "shell", lambda *a, **k: "")
    assert adb_backend.back_retry() is True


# ---------------- Phase B：AdbDeviceAdapter 适配器 ----------------
class FakeU2:
    """模拟 u2 d 对象：元素操作走这里，验证转发。"""
    def __init__(self):
        self.clicked = []
        self.pressed = []
    def click(self, x, y):
        self.clicked.append((x, y))
        return None
    def text(self, s):
        return ("u2text", s)
    def press(self, key):
        self.pressed.append(key)
        return None
    def app_start(self, pkg, stop=False):
        return ("u2start", pkg, stop)


class FakeBackend:
    """模拟 adb_backend 模块（只测适配器路由，不真连设备）。"""
    def __init__(self):
        self.calls = []
        self._fg = "com.fake.app"
        self._wh = (1080, 2340)
    def foreground(self):
        self.calls.append("foreground")
        return self._fg
    def window_size(self):
        self.calls.append("window_size")
        return self._wh
    def dump(self, name):
        self.calls.append(("dump", name))
        return "<hierarchy><node/></hierarchy>"
    def back_retry(self):
        self.calls.append("back_retry")
        return True
    def shell(self, cmd):
        self.calls.append(("shell", cmd))
        return "shell-ok"
    def cold_start(self, pkg):
        self.calls.append(("cold_start", pkg))
        return True
    def resolve_activity(self, pkg):
        self.calls.append(("resolve_activity", pkg))
        return f"{pkg}/.MainActivity"


def _adapter(backend="adb"):
    u2 = FakeU2()
    fb = FakeBackend()
    a = adb_backend.AdbDeviceAdapter(u2, fb, "192.168.1.7:5555")
    return u2, fb, a


def test_adapter_serial():
    _, _, a = _adapter()
    assert a.serial == "192.168.1.7:5555"


def test_adapter_window_size_routes_adb():
    u2, fb, a = _adapter()
    assert a.window_size() == (1080, 2340)
    assert "window_size" in fb.calls


def test_adapter_dump_hierarchy_routes_adb():
    u2, fb, a = _adapter()
    assert a.dump_hierarchy() == "<hierarchy><node/></hierarchy>"
    assert ("dump", "proxy_dump.xml") in fb.calls


def test_adapter_press_back_routes_adb():
    u2, fb, a = _adapter()
    a.press("back")
    assert "back_retry" in fb.calls
    assert u2.pressed == []          # 不走 u2


def test_adapter_press_home_routes_adb():
    u2, fb, a = _adapter()
    a.press("home")
    assert ("shell", "input keyevent 3") in fb.calls


def test_adapter_press_other_forwards_u2():
    u2, fb, a = _adapter()
    a.press("menu")
    assert u2.pressed == ["menu"]


def test_adapter_info_current_package_routes_adb():
    u2, fb, a = _adapter()
    assert a.info.get("currentPackageName") == "com.fake.app"
    assert "foreground" in fb.calls


def test_adapter_info_display_size_routes_window_size():
    u2, fb, a = _adapter()
    assert a.info.get("displayHeight") == 2340
    assert a.info.get("displayWidth") == 1080


def test_adapter_info_unknown_key_default():
    u2, fb, a = _adapter()
    assert a.info.get("nonexistent", "dflt") == "dflt"


def test_adapter_shell_routes_adb():
    u2, fb, a = _adapter()
    assert a.shell("pm list packages x") == "shell-ok"
    assert ("shell", "pm list packages x") in fb.calls


def test_adapter_app_start_cold_routes_adb():
    u2, fb, a = _adapter()
    assert a.app_start("com.fake.app", stop=True) is True
    assert ("cold_start", "com.fake.app") in fb.calls


def test_adapter_app_start_warm_routes_adb():
    u2, fb, a = _adapter()
    assert a.app_start("com.fake.app") is True
    assert ("shell", "am start -n com.fake.app/.MainActivity") in fb.calls


def test_adapter_element_ops_forward_u2():
    """元素操作（click/text/app_start 之外的 u2 方法）必须转发给真实 u2。"""
    u2, fb, a = _adapter()
    a.click(100, 200)
    assert u2.clicked == [(100, 200)]
    assert a.text("赚钱") == ("u2text", "赚钱")
