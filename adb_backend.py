# -*- coding: utf-8 -*-
"""adb_backend.py - 纯 adb 后端（AndroidAutopilot u2 评估阶段 A 前半）

依据 docs/u2稳定性与adb引擎评估_2026-11-03.md §3 缺口表补齐 7 项缺口：
  1. foreground()          - dumpsys window -> parse_foreground 移植
  2. dump() stale 防护     - 3 连相同字节数判 stale -> 重试
  3. cold_start() 精确启动 - resolve-activity + am start -n（弃 monkey）
  4. click_text()          - find + center 组合封装
  5. scroll_to_find()      - 滑动直到 find 命中
  6. window_size()         - wm size -> parse_wm_size 移植
  7. 重试/退避             - retry + backoff（对齐 u2 rpc_retries=2, rpc_backoff=0.8）

设计原则：
- 纯实现，不连设备；subprocess 调用统一走 _run（内部 subprocess.run），
  便于测试 mock subprocess。
- 返回类型对齐 device_session.py 语义：window_size 回 plain tuple、dump 回 str、
  foreground 取不到回 "" 不回 "?"。
- 复用 temp/adb_core.py 既有原语：以「复制」方式引入（adb_core 顶部依赖
  numpy/cv2，import 会拉重依赖；此处复制其轻量原语），adb_core.py 本体不改。
"""
import os
import re
import subprocess
import time

# ---- 常量（复制自 temp/adb_core.py，adb_core.py 本体不改） ----
ROOT = os.path.dirname(os.path.abspath(__file__))  # 本文件在仓库根（原 temp/ 草稿上移）
ADB = os.path.join(ROOT, "tools", "platform-tools", "adb.exe")
SERIAL = "192.168.1.54:5555"
OUT = os.path.join(ROOT, "temp")
# 关键：禁用 Git Bash 路径转换（/sdcard 会被改写成 Windows 路径）
_ENV = dict(os.environ, MSYS_NO_PATHCONV="1")


def set_serial(serial):
    """设置当前设备序列号（从 config.yaml device.serial 读入，勿再硬编码）。"""
    global SERIAL
    if serial:
        SERIAL = serial
    return SERIAL

# 对齐 u2 语义：rpc_retries=2 / rpc_backoff=0.8
RETRIES = 2
BACKOFF = 0.8

# stale dump 判定：连续 3 次 dump 字节数相同 => 旧 _p.xml 工件，判 stale
STALE_LIMIT = 3
MIN_DUMP_BYTES = 500


def _run(args, timeout=30):
    """subprocess 包装。测试通过 mock adb_backend.subprocess.run 拦截。"""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           env=_ENV)
        return (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return f"[adb err] {e}"


def _retry(fn, retries=RETRIES, backoff=BACKOFF, label=""):
    """通用重试/退避：失败（返回 falsy 或抛异常）按指数退避重试。"""
    last = None
    for i in range(retries + 1):
        try:
            last = fn()
            if last:
                return last
        except Exception as e:  # noqa: BLE001 - 统一兜底
            last = f"[{label} err] {type(e).__name__}: {e}"
        if i < retries:
            time.sleep(backoff * (2 ** i))
    return last


# ---- 轻量原语（复制自 temp/adb_core.py，依赖仅 subprocess/os/re/time） ----
def shell(cmd, timeout=30):
    return _run([ADB, "-s", SERIAL, "shell", cmd], timeout)


def tap(x, y, label=""):
    shell(f"input tap {int(x)} {int(y)}")
    if label:
        print(f"  点击 ({int(x)},{int(y)}) {label}")
    time.sleep(1.2)


def swipe(x1, y1, x2, y2, dur=0.4):
    shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(dur*1000)}")
    time.sleep(1.2)


def back():
    shell("input keyevent 4")
    time.sleep(1.2)


def texts(xml):
    """返回去重后的 (text 或 desc) 列表。"""
    seen = []
    for m in re.finditer(r'<node[^>]*>', xml):
        tag = m.group(0)
        t = re.search(r'text="([^"]*)"', tag)
        cd = re.search(r'content-desc="([^"]*)"', tag)
        v = (t.group(1) if t and t.group(1) else "") or (cd.group(1) if cd else "")
        if v and v not in seen:
            seen.append(v)
    return seen


def find(xml, pat):
    """按子串返回 [(text, bounds, tag), ...]。"""
    out = []
    for m in re.finditer(r'<node[^>]*>', xml):
        tag = m.group(0)
        t = re.search(r'text="([^"]*)"', tag)
        cd = re.search(r'content-desc="([^"]*)"', tag)
        v = (t.group(1) if t and t.group(1) else "") or (cd.group(1) if cd else "")
        if pat in v:
            b = re.search(r'bounds="([^"]*)"', tag)
            out.append((v, b.group(1) if b else "?", tag))
    return out


def center(b):
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b)
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return ((x1 + x2) // 2, (y1 + y2) // 2)


# ---------------- 缺口 1：foreground() ----------------
def foreground(timeout=15):
    """当前前台包名。dumpsys window -> parse_foreground（mCurrentFocus 优先）。

    返回包名字符串；取不到回 "" 不回 "?"（对齐 device_session 语义）。
    """
    out = _run([ADB, "-s", SERIAL, "shell", "dumpsys", "window"], timeout=timeout)
    info = parse_foreground(out)
    return info["package"]


def parse_foreground(dumpsys_window_output):
    """从 dumpsys window 输出里取前台 Activity 与包名。纯函数（移植 webui/data.py:327）。"""
    m = re.search(r"mCurrentFocus=Window\{[^}]*?\s([\w.]+)/([\w.$]+)\}",
                  dumpsys_window_output or "")
    if m:
        return {"package": m.group(1), "activity": m.group(2)}
    m = re.search(r"mFocusedApp=.*?\s([\w.]+)/([\w.$]+)", dumpsys_window_output or "")
    if m:
        return {"package": m.group(1), "activity": m.group(2)}
    return {"package": "", "activity": ""}


# ---------------- 缺口 6：window_size() ----------------
def window_size(timeout=10):
    """当前屏幕尺寸。wm size -> parse_wm_size -> (w, h) 或 (None, None)。"""
    out = _run([ADB, "-s", SERIAL, "shell", "wm", "size"], timeout=timeout)
    return parse_wm_size(out)


def parse_wm_size(out):
    """解析 wm size 输出 -> (w, h) 或 (None, None)。纯函数（移植 webui/data.py:342）。"""
    m = re.search(r"Override size:\s*(\d+)x(\d+)", out or "")
    if not m:
        m = re.search(r"Physical size:\s*(\d+)x(\d+)", out or "")
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


# ---------------- 缺口 2：dump() stale 防护 ----------------
# stale 状态跨调用累积：uiautomator dump 失败时 /sdcard/_p.xml 仍是旧工件，
# pull 回来的字节数连续不变；3 连相同即判 stale（不返回旧内容，强制重试）。
_dump_sizes = []


def reset_dump_state():
    """清空 stale 计数状态（测试隔离用）。"""
    global _dump_sizes
    _dump_sizes = []


def dump(name, retry=None):
    """uiautomator dump + pull 回本地，返回 XML 字符串。

    stale 防护：记录连续 dump 字节数，3 连相同判 stale（旧 XML 工件）
    -> 强制重试；最终仍失败回 ""。

    2026-11-04 Q1 §7 族级规则：dump 落 **/data/local/tmp/dy.xml**（勿落
    /sdcard —— 实测 /sdcard 上恒 0 字节，是历史 parity 0 字节 OPEN 根因）；
    pull 走独立 `adb pull` 子进程（勿 shell 内嵌，否则本地拿不到文件）。
    """
    global _dump_sizes
    retry = RETRIES if retry is None else retry
    p = os.path.join(OUT, name)
    dev = "/data/local/tmp/dy.xml"
    for i in range(retry + 1):
        shell(f"uiautomator dump {dev}")
        _run([ADB, "-s", SERIAL, "pull", dev, p], timeout=30)
        if os.path.exists(p) and os.path.getsize(p) > MIN_DUMP_BYTES:
            size = os.path.getsize(p)
            _dump_sizes.append(size)
            _dump_sizes = _dump_sizes[-10:]
            # 3 连相同（含本次）=> 旧 XML 工件，判 stale，不返回，重试
            if (len(_dump_sizes) >= STALE_LIMIT
                    and len(set(_dump_sizes[-STALE_LIMIT:])) == 1):
                time.sleep(BACKOFF)
                continue
            try:
                return open(p, encoding="utf-8").read()
            except Exception:
                pass
        time.sleep(BACKOFF)
    return ""


# ---------------- 缺口 3：精确冷启动 ----------------
def resolve_activity(pkg, timeout=15):
    """cmd package resolve-activity --brief 取启动组件。返回组件串或 ""。"""
    out = _run([ADB, "-s", SERIAL, "shell", "cmd", "package",
                "resolve-activity", "--brief", pkg], timeout=timeout)
    comp = (out or "").strip().splitlines()[-1] if (out or "").strip() else ""
    if not comp or comp.startswith("Error") or "NONE" in comp:
        return ""
    return comp


def cold_start(pkg, wait=7):
    """精确冷启动：resolve-activity 取组件 -> am start -n（弃 monkey）。"""
    comp = resolve_activity(pkg)
    if not comp:
        return False
    shell(f"am force-stop {pkg}")
    time.sleep(1.5)
    shell(f"am start -n {comp}")
    time.sleep(wait)
    return True


# ---------------- 缺口 4：click_text() ----------------
def click_text(xml, pat, label=""):
    """find + center 组合：命中第一个文本即点击，返回 True；未命中返回 False。"""
    hits = find(xml, pat)
    if not hits:
        return False
    c = center(hits[0][1])
    if not c:
        return False
    tap(*c, label=label or pat)
    return True


# ---------------- 缺口 5：scroll_to_find() ----------------
def scroll_to_find(xml, pat, max_swipes=5, direction="up"):
    """滑动直到 find 命中。direction='up' 向上滑（内容上移，找下方内容）。"""
    hits = find(xml, pat)
    if hits:
        return hits
    w, h = window_size() or (1080, 2340)
    for _ in range(max_swipes):
        if direction == "down":
            swipe(w // 2, int(h * 0.3), w // 2, int(h * 0.7), dur=0.4)
        else:
            swipe(w // 2, int(h * 0.7), w // 2, int(h * 0.3), dur=0.4)
        xml = dump("scroll_probe.xml")
        hits = find(xml, pat) if xml else []
        if hits:
            return hits
    return []


# ---------------- 缺口 7：重试/退避 封装原语 ----------------
def tap_retry(x, y, retries=RETRIES, backoff=BACKOFF):
    """带重试/退避的 tap（input 偶发挂起兜底）。"""
    def _t():
        shell(f"input tap {int(x)} {int(y)}")
        return True
    return bool(_retry(_t, retries=retries, backoff=backoff, label="tap"))


def back_retry(retries=RETRIES, backoff=BACKOFF):
    """带重试/退避的 back。"""
    def _b():
        shell("input keyevent 4")
        return True
    return bool(_retry(_b, retries=retries, backoff=backoff, label="back"))


# ---------------- Phase B：u2 d 对象形态适配器 ----------------
class _AdbInfo:
    """以 u2 `.info` 形态暴露前台信息（只实现引擎实际用到的键）。

    键映射：
      currentPackageName -> foreground()（u2 的 currentPackageName 语义）
      displayHeight / displayWidth -> window_size()（locator 兜底取屏幕尺寸）
    其余键回 default（引擎未用到）。
    """
    def __init__(self, backend):
        self._backend = backend

    def get(self, key, default=None):
        if key == "currentPackageName":
            return self._backend.foreground() or ""
        if key in ("displayHeight", "displayWidth"):
            w, h = self._backend.window_size()
            v = h if key == "displayHeight" else w
            return v if v is not None else default
        return default


class AdbDeviceAdapter:
    """把 adb_backend 包装成 u2 `d` 对象形态，供 device_session 原语替换。

    Phase B（docs/u2稳定性与adb引擎评估 §4 步骤5）：原语（window_size /
    dump_hierarchy / press(back,home) / info.get / shell / app_start）走 adb；
    **元素操作**（d(text=..)、click、swipe、screenshot、app_current…）经
    __getattr__ 转发给真实 u2 `d` —— u2 保留为元素引擎 + fallback。

    返回类型对齐 u2 语义：window_size 回 plain tuple、dump 回 str、
    info.get("currentPackageName") 回 str（取不到回 "" 不回 "?"）。
    """
    def __init__(self, u2d, backend, serial=None):
        self._u2 = u2d
        self._backend = backend
        self._serial = serial

    def __getattr__(self, name):
        # 元素操作/未接管方法 -> 转发真实 u2 d（如 d(text="x")、click、swipe）
        return getattr(self._u2, name)

    @property
    def serial(self):
        return self._serial

    @property
    def info(self):
        return _AdbInfo(self._backend)

    def window_size(self):
        return self._backend.window_size()

    def dump_hierarchy(self):
        return self._backend.dump("proxy_dump.xml") or ""

    def press(self, key):
        if key == "back":
            self._backend.back_retry()
        elif key == "home":
            self._backend.shell("input keyevent 3")
        else:
            getattr(self._u2, "press")(key)

    def shell(self, cmd):
        return self._backend.shell(cmd)

    def app_start(self, pkg, stop=False):
        if stop:
            return self._backend.cold_start(pkg)
        comp = self._backend.resolve_activity(pkg)
        if comp:
            self._backend.shell(f"am start -n {comp}")
            return True
        return getattr(self._u2, "app_start")(pkg)
