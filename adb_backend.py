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
    """subprocess 包装。测试通过 mock adb_backend.subprocess.run 拦截。

    失败回 **None**（绝不回错误串）：历史实现 `except: return f"[adb err] {e}"`
    返回的是**非空字符串**，于是 `_retry` 的 `if last: return last` 把错误文本
    当成功返回，调用方拿 "[adb err] ..." 当设备输出继续解析（典型症状：
    `shell("wm size")` 的返回被当真值、`.strip()` 得到错误串）。
    现约定：None = 调用失败（可判定），"" = 调用成功但无输出。
    """
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           env=_ENV)
        return (r.stdout or "") + (r.stderr or "")
    except Exception:  # noqa: BLE001 - 统一兜底为 None（失败可判定）
        return None


def _retry(fn, retries=RETRIES, backoff=BACKOFF, label=""):
    """通用重试/退避：失败（返回 falsy 或抛异常）按指数退避重试。

    全失败回 **None**（绝不回异常字符串）：历史实现在 except 里把 `last`
    设成 `f"[{label} err] ..."`，末尾 `return last` 就把错误串当成功返回，
    调用方 `if out:` 判真 -> 把失败当成功。现约定 None = 失败、真值 = 成功；
    异常详情只打日志（print），不进返回值。
    """
    last = None
    for i in range(retries + 1):
        try:
            last = fn()
            if last:
                return last
        except Exception as e:  # noqa: BLE001 - 统一兜底
            last = None
            print(f"  [retry] {label or 'call'} 第 {i + 1} 次失败: "
                  f"{type(e).__name__}: {e}")
        if i < retries:
            time.sleep(backoff * (2 ** i))
    # 归一化：空串等 falsy 也统一回 None，保证「None = 失败」这一条契约唯一
    return last or None


# ---- 轻量原语（复制自 temp/adb_core.py，依赖仅 subprocess/os/re/time） ----
def shell(cmd, timeout=30):
    return _run([ADB, "-s", SERIAL, "shell", cmd], timeout)


def tap(x, y, label=""):
    """点击。返回 True=已下发、False=adb 调用失败（失败可判定，不再静默）。"""
    ok = shell(f"input tap {int(x)} {int(y)}") is not None
    if label:
        print(f"  点击 ({int(x)},{int(y)}) {label}")
    time.sleep(1.2)
    return ok


def swipe(x1, y1, x2, y2, dur=0.4):
    """滑动。返回 True=已下发、False=adb 调用失败。"""
    ok = shell(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} "
               f"{int(dur * 1000)}") is not None
    time.sleep(1.2)
    return ok


def back():
    """返回键。返回 True=已下发、False=adb 调用失败。"""
    ok = shell("input keyevent 4") is not None
    time.sleep(1.2)
    return ok


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


def find(xml, pat, exact=False):
    """按子串返回 [(text, bounds, tag), ...]。

    P2-7 结论（评审降级为设计权衡，**不改默认语义**）：子串是定位特性而非
    缺陷 —— 节点文本常带后缀/前后缀（如文本「签到领100金币」必须能用
    pat="签到" 命中），改成精确匹配会直接打断真实定位。故默认仍走子串，
    仅新增 `exact=True` 供「必须全等」的场景使用（默认行为零变化）。
    """
    out = []
    for m in re.finditer(r'<node[^>]*>', xml):
        tag = m.group(0)
        t = re.search(r'text="([^"]*)"', tag)
        cd = re.search(r'content-desc="([^"]*)"', tag)
        v = (t.group(1) if t and t.group(1) else "") or (cd.group(1) if cd else "")
        hit = (v == pat) if exact else (pat in v)
        if hit:
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
def parse_resumed(dumpsys_activity_output):
    """从 dumpsys activity activities 输出取顶部 ResumedActivity 的 (pkg, activity)。

    2026-11-04 京东签到页 A/B 实测：vivo 智慧多窗下 dumpsys window 的
    mCurrentFocus/mFocusedApp 会残留**幽灵窗口**（抖音 SplashActivity，HOME/
    强杀都不消失）且排在首位，解析它会把前台误判成抖音（启动校验误判跳全量
    行为的根因之一）。真值源是 dumpsys activity activities 的 ResumedActivity
    —— 实测与 u2 app_current() 完全一致（都报 com.jingdong.app.mall）。
    """
    m = re.search(
        r"(?:mResumedActivity|ResumedActivity):\s*ActivityRecord\{[^}]*?\s"
        r"([\w.]+)/([\w.$]+)", dumpsys_activity_output or "")
    if m:
        return m.group(1), m.group(2)
    return "", ""


def foreground(timeout=15):
    """当前前台包名。优先 dumpsys activity activities 的 ResumedActivity
    （抗多窗幽灵窗），失败回退 dumpsys window -> parse_foreground。

    返回包名字符串；取不到回 "" 不回 "?"（对齐 device_session 语义）。
    """
    out = _run([ADB, "-s", SERIAL, "shell", "dumpsys", "activity", "activities"],
               timeout=timeout)
    pkg, _act = parse_resumed(out)
    if pkg:
        return pkg
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
        # 2026-11-04 修正（京东签到页 A/B 实测）：先 rm 设备端旧文件，再 dump。
        # 否则「uiautomator dump 在动画页 could not get idle state 失败、不写
        # 新文件」时，adb pull 仍会把上一 app 的旧树拉回来（实测拉到抖音残留
        # 树 103999B），落地校验 text_nodes 拿错页文案 -> 签到误判失败（9 app
        # 回归根因）。rm 后失败即无文件，pull 失败回 ""，交由上层 u2 兜底。
        shell(f"rm -f {dev}")
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
    """精确冷启动：resolve-activity 取组件 -> am start -n（弃 monkey）。

    返回 True=启动命令**已下发成功**、False=组件解析失败或 adb 调用失败
    （_run 失败回 None -> 判 False，不再无条件 True 让上层以为已启动）。
    """
    comp = resolve_activity(pkg)
    if not comp:
        return False
    shell(f"am force-stop {pkg}")
    time.sleep(1.5)
    ok = shell(f"am start -n {comp}") is not None
    time.sleep(wait)
    return ok


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

    # u2 info 语义对齐：支持 d.info["displayWidth"] 与 d.info.displayWidth 两种
    # 访问形态（devtools/probe_path_u2.py 用下标，历史代码用属性），
    # 否则 Phase B 下会 AttributeError/KeyError，与 d(...) 同类 latent crash。
    def __getitem__(self, key):
        v = self.get(key)
        if v is None:
            raise KeyError(key)
        return v

    def __getattr__(self, name):
        if name.startswith("_"):  # 防 _backend 等私有名递归
            raise AttributeError(name)
        v = self.get(name)
        if v is None:
            raise AttributeError(name)
        return v


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

    def __call__(self, *args, **kwargs):
        # u2 选择器惯用法 d(text=..)/d(className=..)/d(resourceId=..)... 是
        # 「调用 d 本身」，__getattr__ 只拦属性访问、拦不到调用 —— 必须显式
        # __call__ 转发到真实 u2 d。返回的是真实 u2 UiObject，其后
        # .click()/.exists()/.info 等走 u2 元素引擎（2026-11-04 全量回归首
        # 个 app 就爆 TypeError: 'AdbDeviceAdapter' object is not callable）。
        return self._u2(*args, **kwargs)

    @property
    def serial(self):
        return self._serial

    @property
    def info(self):
        return _AdbInfo(self._backend)

    def window_size(self):
        return self._backend.window_size()

    def dump_hierarchy(self):
        # 2026-11-04 京东签到页 A/B 实测（两败俱伤）：uiautomator dump CLI 在
        # 内容 dump 上**不可靠**，两种失败模式都已复现 ——
        #   (1) 持续动画页（视频流/金币计数器/自动播下一条）=> 等 idle 超时
        #       "could not get idle state"，设备端无新文件；
        #   (2) vivo 智慧多窗下前台是京东但 uiautomator「活动窗口」指向残留的
        #       抖音 Splash => dump 成功但写入**抖音树**（103999B 非当前屏）。
        # 两种都让落地校验 text_nodes 拿不到当前页文案 -> 签到误判失败
        # （9 app 回归根因）。u2 的 jsonrpc dump 实测 3 轮均可靠、无需 idle、
        # 且抓对窗口。故 **内容 dump 恒走 u2**；adb 只替换真正脆弱的原语
        # （window_size/press/shell/app_start/info）。这是阶段B结论修正点。
        try:
            return self._u2.dump_hierarchy() or ""
        except Exception:  # noqa: BLE001 - 节点不可用不冒泡
            return ""

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
            # adb 下发失败（_run 回 None）时回 False，可判定
            return self._backend.shell(f"am start -n {comp}") is not None
        return getattr(self._u2, "app_start")(pkg)
