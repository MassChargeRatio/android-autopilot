# -*- coding: utf-8 -*-
"""record_flow.py - 引导式录制：NL 指令 → 执行 → 记录 → YAML（AUTOP-NL-2026-10-22-B）

为什么不用 getevent 抓物理触摸：
    1. 无语义：raw ABS_MT 只给 slot/tracking_id/pressure，拿不到「点的是哪个元素」；
    2. 坐标空间不同：event 是触摸屏原始量程，需 `getevent -p` 读 `0035/0036` 的 max
       自行换算，多指 slot 还要解析 `SYN_REPORT` 分帧；
    3. 无法归因：录制期脚本注入的点击与用户物理点击混在同一事件流；
    4. 阻塞流收尾差：`adb shell getevent -lt` 是长驻流，Windows 下易留僵尸 adb；
    5. H5 场景坐标本身不可信（星图金融打卡按钮被透明层遮挡就是证据）。

结论：录制输入是「一句 NL 指令」，坐标由 `d.dump_hierarchy()` 的 bounds 反算。

工作流：
    用户逐句输入 NL 指令（点签到 / 点右下角 / 上滑 / 等2秒 / 返回），
    脚本执行并记录每步（命中方式、归一化坐标、执行前后 activity、页面差分），
    结束时给一句命名 + 指定 app/behavior，渲染成 YAML 片段交给 yaml_writer 写回（缺省预览）。

用法：
    python devtools/record_flow.py --app 七猫免费小说 [--serial 192.168.1.54:5555] \\
           [--behavior sign] [--entry auto] [--max-steps 20] [--allow-money] [--apply]

    > 点右下角我的
    > 点福利中心
    > 点签到
    > trace / undo / done
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 只读复用 calibrate 的节点解析/匹配/包判断（不修改其任何逻辑）
from devtools import calibrate  # noqa: E402
from devtools import yaml_writer as yw  # noqa: E402

# ---- 软依赖：A 卡 nl_to_steps.py（可能稍后出现）；未就绪时用极简兜底 ----
NL_TO_STEPS_READY = False
try:  # pragma: no cover - 由 A 卡是否就绪决定
    from nl_to_steps import (  # type: ignore[import-not-found]
        parse_line,
        render_hop,
        render_steps,
        to_yaml_fragment,
    )
    NL_TO_STEPS_READY = True
except ImportError:
    pass

# 兜底（A 卡未就绪）：仅剥最朴素的动词前缀，全句当文案；不复制 A 卡 parse_line 的动词表/切分逻辑
def _fallback_parse_line(cmd: str) -> dict:
    c = (cmd or "").strip()
    if c.startswith("点"):
        return {"verb": "tap", "target": c[1:].strip()}
    if c.startswith("上滑") or c.startswith("下滑") or c.startswith("左滑") \
            or c.startswith("右滑") or c.startswith("滑动"):
        return {"verb": "swipe", "target": c}
    if c.startswith("等"):
        return {"verb": "wait", "target": c}
    if c.startswith("返回"):
        return {"verb": "back", "target": ""}
    return {"verb": "tap", "target": c}


def _split_cmd(cmd: str) -> tuple[str, str, str | tuple | None]:
    """统一把 NL 指令拆成 (verb, target, pos)；A 卡就绪时走真 parse_line。

    A 卡结构：parse_line(cmd) -> (steps: list[dict], warnings: list)。
    单条指令通常只有 1 步；多于 1 步时取首步并打印提示（本工具按单步录制）。
    """
    try:
        info = parse_line(cmd) if NL_TO_STEPS_READY else _fallback_parse_line(cmd)
    except Exception:  # noqa: BLE001 - A 卡结构变化时兜底不阻断录制
        info = _fallback_parse_line(cmd)

    steps: list | None = None
    if isinstance(info, tuple) and info and isinstance(info[0], list):
        steps = info[0]
    elif isinstance(info, list) and info and isinstance(info[0], dict):
        steps = info
    if steps:
        if len(steps) > 1:
            print(f"[warn] 指令拆出 {len(steps)} 步，仅取首步：{steps[0]}")
        first = steps[0] if isinstance(steps[0], dict) else {}
        verb = str(first.get("verb") or "tap")
        target = first.get("target")
        pos = first.get("pos")          # A 卡可能是 (x,y) tuple 或方位词 str
        return verb, (str(target) if target else ""), pos

    if isinstance(info, dict):
        verb = str(info.get("verb") or "tap")
        target = str(info.get("target") or "")
        pos = info.get("pos")
        return verb, target, pos
    if isinstance(info, (tuple, list)):
        parts = tuple(info) + (None, None)
        return str(parts[0] or "tap"), str(parts[1] or ""), parts[2]
    return "tap", str(cmd), None


# ---- 方位词 → 归一化坐标（点右下角 / 点右上…） ----
_POS: dict[str, tuple[float, float]] = {
    "右下角": (0.90, 0.88),
    "右下": (0.90, 0.88),
    "右上角": (0.90, 0.10),
    "右上": (0.90, 0.10),
    "左下角": (0.10, 0.88),
    "左下": (0.10, 0.88),
    "左上角": (0.10, 0.10),
    "左上": (0.10, 0.10),
    "中间偏上": (0.50, 0.35),
    "中间偏下": (0.50, 0.65),
    "中间": (0.50, 0.50),
    "中心": (0.50, 0.50),
    "中部": (0.50, 0.50),
    "上部": (0.50, 0.20),
    "下部": (0.50, 0.80),
}


def _match_pos(target: str) -> tuple[float, float] | None:
    """target 是否以方位词开头（或本身就是方位词）。返回归一化坐标。"""
    if not target:
        return None
    for key in sorted(_POS, key=len, reverse=True):
        if target == key or target.startswith(key):
            return _POS[key]
    return None


def _parse_seconds(target: str) -> float:
    """从「等2秒/等 2.5 秒/等两秒」里取秒数；取不到默认 1.0。"""
    m = re.search(r"(\d+(?:\.\d+)?)", target or "")
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return 1.0


# ---- 纯函数（可单测，无设备） ----

@dataclass
class Step:
    seq: int
    cmd: str
    verb: str
    target: str | None
    pos: str | tuple | None
    hit_kind: str | None      # text|desc|id|point|None
    hit_value: str | None
    bounds: tuple | None      # (l,t,r,b) 像素
    point_norm: tuple | None  # (x,y) round(4)
    act_before: str
    act_after: str
    delta: float
    confirmed: bool
    note: str = ""


def ui_digest(xml: str) -> frozenset:
    """可点节点的 (text, desc, id, bounds) 集合；对节点顺序不敏感。

    可点 = clickable=="true"，或带非空 text/desc 的节点。
    bounds 归一为 (l,t,r,b) int 元组，保证可哈希、可差分。
    """
    items: set[tuple] = set()
    try:
        root = ET.fromstring(xml or "")
    except ET.ParseError:
        return frozenset()
    for el in root.iter("node"):
        a = el.attrib
        m = calibrate.BOUNDS_RE.match(a.get("bounds", ""))
        if not m:
            continue
        x1, y1, x2, y2 = (int(v) for v in m.groups())
        text = a.get("text", "") or ""
        desc = a.get("content-desc", "") or ""
        rid = a.get("resource-id", "") or ""
        clickable = a.get("clickable", "") == "true"
        if not (clickable or text or desc):
            continue
        items.add((text, desc, rid, (x1, y1, x2, y2)))
    return frozenset(items)


def page_delta(a: frozenset, b: frozenset) -> float:
    """页面差分：1 - Jaccard(a, b)。同页=0.0，全换=1.0，双空=0.0。"""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return 1.0 - len(a & b) / len(union)


def step_to_action(step: Step) -> dict | None:
    """把已确认 Step 映射成引擎动作 dict；未确认/未命中返回 None。

    text/desc/id 命中 → click_first；point 命中 → click_point；
    swipe → swipe_natural；wait → wait；back → back。
    """
    if not step.confirmed:
        return None
    kind = step.hit_kind
    if kind in ("text", "desc", "id") and step.hit_value:
        return {
            "type": "click_first",
            "candidates": [{"type": kind, "value": step.hit_value}],
            "timeout": 8,
            "optional": True,
        }
    if kind == "point" and step.point_norm:
        x, y = step.point_norm
        return {
            "type": "click_point",
            "x": x,
            "y": y,
            "vision": False,
            "desc": step.hit_value or step.cmd,
        }
    if step.verb == "swipe":
        return {"type": "swipe_natural"}
    if step.verb == "wait":
        return {"type": "wait", "seconds": _parse_seconds(step.target)}
    if step.verb == "back":
        return {"type": "back"}
    return None


def steps_to_actions(steps: list[Step]) -> tuple[list[dict], list[str]]:
    """遍历 trace，丢弃未确认步，返回 (动作链, warnings)。"""
    actions: list[dict] = []
    warnings: list[str] = []
    for s in steps:
        if not s.confirmed:
            warnings.append(f"step#{s.seq} {s.cmd!r} 未确认，已丢弃")
            continue
        act = step_to_action(s)
        if act is None:
            reason = ("未定位到元素且无坐标兜底"
                      if (s.verb == "tap" and not s.hit_kind and not s.point_norm)
                      else "无可映射动作")
            warnings.append(f"step#{s.seq} {s.cmd!r} {reason}，已丢弃"
                            f"（note={s.note or '-'}）")
            continue
        actions.append(act)
    return actions, warnings


def guess_entry(steps: list[Step]) -> str:
    """从 trace 里猜入口锚点：第一个 text/desc/id 命中值；无则 'auto'。"""
    for s in steps:
        if s.hit_kind in ("text", "desc", "id") and s.hit_value:
            return s.hit_value
    return "auto"


def is_money_step(step: Step, money_words: set[str]) -> bool:
    """资金红线：指令/目标/命中值是否触碰资金类词。"""
    blob = " ".join(filter(None, [step.cmd, step.target, step.hit_value]))
    return any(w and w in blob for w in money_words)


def assemble_actions(steps: list[Step], entry_hops: list[dict]) -> tuple[list[dict], list[str]]:
    """finish 组装：entry hops 在前、录制步在后。"""
    step_actions, warnings = steps_to_actions(steps)
    return list(entry_hops) + list(step_actions), warnings


# ---- 设备层 ----

MONEY_WORDS = frozenset({
    "提现", "立即提现", "收款", "转账", "充值", "支付", "付款", "银行卡", "余额宝",
})


class FlowRecorder:
    """交互式录制器：连接设备 → 逐步执行 → 记录 Step → finish 渲染 YAML。"""

    def __init__(self, app: str, package: str, serial: str | None = None,
                 out_dir: str | None = None, max_steps: int = 20,
                 allow_money: bool = False):
        self.app = app
        self.package = package
        self.serial = serial
        self.out_dir = out_dir
        self.max_steps = max_steps
        self.allow_money = allow_money
        self.money_words: set[str] = set(MONEY_WORDS)
        self.trace: list[Step] = []
        self.d = None            # u2 设备（测试可注入 fake）
        self._session_dir: str | None = None
        self._seq = 0
        self._closed = False
        self._screen: tuple[int, int] | None = None

    # ---- 连接 / 生命周期 ----
    def _connect(self):  # 测试 monkeypatch 点
        if self.serial:
            return calibrate.connect_device(self.serial)
        raise RuntimeError("未提供 serial，且未注入设备")

    def start(self) -> None:
        """连接设备、启动 App、建快照会话目录。"""
        if self._closed:
            raise RuntimeError("recorder 已关闭")
        if self.d is None:
            self.d = self._connect()
        base = self.out_dir or os.path.join(ROOT, "devtools", "calib", "record",
                                            calibrate.safe_name(self.package))
        self._session_dir = os.path.join(base, datetime.now().strftime("%Y%m%d_%H%M%S"))
        os.makedirs(self._session_dir, exist_ok=True)
        try:
            self.d.press("home")
            time.sleep(1.2)
            self.d.app_start(self.package, stop=True)
            self._wait_app_ready()
        except Exception as exc:  # noqa: BLE001 - 设备差异不阻断录制
            print(f"[warn] 启动 App 失败（{type(exc).__name__}: {exc}），继续")

    def _wait_app_ready(self, timeout: float = 10.0) -> None:
        """等 App 离开启动页（真机修正：七猫 LoadingActivity 可持续数秒，
        早期只睡 1.5s 导致首屏只有系统导航节点，文案全部定位不到）。"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                dom = calibrate.dominant_package(self._dump())
            except Exception:  # noqa: BLE001
                return
            if dom and dom == self.package:
                return
            time.sleep(1.0)

    def close(self) -> None:
        self._closed = True

    # ---- 设备辅助 ----
    def _screen_size(self) -> tuple[int, int]:
        if self._screen is None:
            try:
                w, h = self.d.window_size()
                self._screen = (int(w), int(h))
            except Exception:  # noqa: BLE001
                self._screen = (1080, 2340)
        return self._screen

    def _activity(self) -> str:
        try:
            cur = self.d.app_current()
            if isinstance(cur, dict):
                return str(cur.get("activity") or cur.get("package") or "?")
        except Exception:  # noqa: BLE001
            pass
        return "?"

    def _dump(self) -> str:
        try:
            return str(self.d.dump_hierarchy() or "")
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] dump 失败（{type(exc).__name__}: {exc}）")
            return ""

    def _snapshot(self, seq: int, phase: str, xml: str) -> None:
        if not self._session_dir:
            return
        tag = f"{seq:02d}_{phase}"
        try:
            with open(os.path.join(self._session_dir, f"{tag}.xml"),
                      "w", encoding="utf-8") as f:
                f.write(xml)
        except Exception:  # noqa: BLE001
            pass
        try:
            self.d.screenshot(os.path.join(self._session_dir, f"{tag}.png"))
        except Exception:  # noqa: BLE001 - 无截图能力时只留 XML
            pass

    # ---- 执行 ----
    def _execute(self, verb: str, target: str,
                 pos: str | tuple | None = None
                 ) -> tuple[str | None, str | None, tuple | None, tuple | None]:
        """按 verb 执行动作，返回 (hit_kind, hit_value, bounds, point_norm)。"""
        xml = self._dump()
        nodes = calibrate.parse_nodes(xml)
        if verb == "tap":
            # text → desc → id 顺序定位（与 match_selector 工程语义一致）
            if target:
                for kind in ("text", "desc", "id"):
                    hits = calibrate.match_selector(nodes, kind, target)
                    if hits:
                        n = hits[0]
                        cx, cy = n["center"]
                        w, h = self._screen_size()
                        self.d.click(cx, cy)
                        return kind, target, n["bounds"], \
                            (round(cx / w, 4), round(cy / h, 4))
            # 坐标兜底：A 卡已给 (x,y) 归一化坐标，或方位词
            p = pos if isinstance(pos, (tuple, list)) else _match_pos(str(pos) if pos else "")
            if p is not None:
                px, py = float(p[0]), float(p[1])
                w, h = self._screen_size()
                self.d.click(int(px * w), int(py * h))
                return "point", target or (pos if isinstance(pos, str) else "坐标点击"), \
                    None, (round(px, 4), round(py, 4))
            # 文案没命中、又没有坐标兜底：不静默空转，给出可点击文案建议
            self._suggest_targets()
            return None, None, None, None
        if verb == "swipe":
            w, h = self._screen_size()
            self.d.swipe(int(w * 0.5), int(h * 0.8), int(w * 0.5), int(h * 0.3),
                         duration=0.4)
            return None, None, None, None
        if verb == "wait":
            time.sleep(_parse_seconds(target))
            return None, None, None, None
        if verb == "back":
            self.d.press("back")
            return None, None, None, None
        return None, None, None, None

    def _suggest_targets(self, limit: int = 8) -> None:
        """tap 未命中时打印当前屏可点击文案，便于改口述词（真机调试关键）。"""
        try:
            nodes = calibrate.parse_nodes(self._dump())
        except Exception:  # noqa: BLE001
            return
        seen, texts = set(), []
        for n in nodes:
            for key in ("text", "desc"):
                v = (n.get(key) or "").strip()
                if v and v not in seen and len(v) <= 12:
                    seen.add(v)
                    texts.append(v)
            if len(texts) >= limit:
                break
        if texts:
            print("    [提示] 未定位到元素且无坐标兜底，未执行点击。当前屏可点文案："
                  + " / ".join(texts))

    # ---- 机器校验（先于人工，防误触） ----
    def _machine_check(self, step: Step, after_xml: str, act_before: str
                       ) -> tuple[bool, str, bool]:
        """返回 (ok, note, fatal)。fatal=True 表示直接拒绝、不可人工 override（资金红线）。"""
        if not self.allow_money and is_money_step(step, self.money_words):
            return False, "资金红线: 触碰资金类词且未开启 --allow-money", True
        dom = calibrate.dominant_package(after_xml)
        if dom and dom != self.package:
            return False, f"跳转/误触: 主导包 {dom} != {self.package}", False
        # 2026-10-22 真机实跑修正：文案未命中且无坐标时 _execute 根本不点击，
        # 但 App 自身加载会造成高 delta / activity 变化，旧判据把它误判为"有效点击"。
        # 这里显式拦住：没定位到东西就不算一步。
        if step.verb == "tap" and not step.hit_kind and not step.point_norm:
            return False, "未定位到元素且无坐标兜底（未执行点击）", False
        if step.delta < 0.02 and step.act_before == step.act_after:
            return False, "疑似无效点击: delta<0.02 且 activity 未变", False
        return True, "", False

    # ---- 单步录制 ----
    def record_step(self, cmd: str) -> Step | None:
        """执行一条 NL 指令并记录；直接拒绝/丢弃返回 None。"""
        if self._closed:
            raise RuntimeError("recorder 已关闭")
        if self.d is None:
            self.start()
        if len(self.trace) >= self.max_steps:
            print(f"[warn] 已达 max_steps={self.max_steps}")
            return None
        cmd = (cmd or "").strip()
        if not cmd:
            return None
        verb, target, pos = _split_cmd(cmd)

        before_xml = self._dump()
        act_before = self._activity()
        hit_kind, hit_value, bounds, point_norm = self._execute(verb, target, pos)
        time.sleep(1.2)
        after_xml = self._dump()
        act_after = self._activity()

        seq = self._seq + 1
        delta = page_delta(ui_digest(before_xml), ui_digest(after_xml))
        step = Step(seq=seq, cmd=cmd, verb=verb, target=target, pos=pos,
                    hit_kind=hit_kind, hit_value=hit_value, bounds=bounds,
                    point_norm=point_norm, act_before=act_before,
                    act_after=act_after, delta=delta, confirmed=False)
        ok, note, fatal = self._machine_check(step, after_xml, act_before)
        if fatal:
            print(f"[reject] {note}")
            return None
        step.confirmed = ok
        step.note = note
        self._seq = seq
        self._snapshot(seq, "before", before_xml)
        self._snapshot(seq, "after", after_xml)
        self._show_step(step)

        # 人工确认：y=收下（可 override 机器拒绝） n=丢弃 e=改文案后重记
        # r=重试 u=撤销上一步
        ans = input("y=收下 n=丢弃 e=改文案后重记 r=重试 u=撤销上一步 > ").strip().lower()
        if ans == "u":
            self.undo()
            return None
        if ans == "r":
            return self.record_step(cmd)
        if ans in ("", "y"):
            step.confirmed = True
            self.trace.append(step)
            return step
        return None  # n / e / 其他 → 丢弃，不入 trace

    def _show_step(self, step: Step) -> None:
        print(f"--- step#{step.seq} {step.cmd!r} verb={step.verb} "
              f"hit={step.hit_kind}:{step.hit_value} "
              f"bounds={step.bounds} point={step.point_norm}")
        print(f"    activity {step.act_before} -> {step.act_after} "
              f"delta={step.delta:.3f} confirmed={step.confirmed} "
              f"note={step.note or '-'}")

    # ---- 撤销 / 展示 ----
    def undo(self) -> Step | None:
        if not self.trace:
            return None
        return self.trace.pop()

    def show_trace(self) -> None:
        if not self.trace:
            print("(trace 为空)")
            return
        for s in self.trace:
            print(f"  #{s.seq} {s.cmd!r} -> {s.hit_kind}:{s.hit_value} "
                  f"@{s.point_norm} delta={s.delta:.3f} ok={s.confirmed}")

    # ---- 收尾渲染 ----
    def _render_hops(self, entry: str) -> list[dict]:
        if not entry or entry == "auto":
            return []
        try:
            hops = render_hop(entry, {}) if NL_TO_STEPS_READY else []
        except Exception:  # noqa: BLE001
            hops = []
        return list(hops or [])

    def _resolve_entry(self, entry: str) -> str:
        if entry == "auto":
            guessed = guess_entry(self.trace)
            return guessed if guessed != "auto" else ""
        return entry

    def finish(self, name: str, behavior: str, entry: str = "auto",
               apply: bool = False, force: bool = False,
               comments: list[str] | None = None) -> object:
        """组装动作链并交给 yaml_writer 写回（缺省预览）。

        name 是 **App 名**（对应 config/apps/<app>.yaml），不是行为命名；
        行为命名请走 comments，会作为 YAML 注释写进配置。
        """
        if not self.trace:
            return yw.WriteResult("", "error", None, "", ["trace 为空，无内容可写"])
        entry = self._resolve_entry(entry)
        hops = self._render_hops(entry)
        actions, warnings = assemble_actions(self.trace, hops)
        if not actions:
            detail = "；".join(warnings) if warnings else "所有步骤都未产出动作"
            return yw.WriteResult("", "error", None, "",
                                  [f"无可用动作：{detail}",
                                   "建议：用屏上实际文案（如「福利」）或方位词"
                                   "（如「点右下角」）重录，必要时加 --xy 坐标兜底"])
        try:
            path = yw.app_path(name, base_dir=ROOT)
        except Exception as exc:  # noqa: BLE001
            return yw.WriteResult("", "error", None, "", [f"app 配置定位失败: {exc}"])
        result = yw.insert_behavior(path, behavior, actions, comments=comments,
                                    apply=apply, base_dir=ROOT)
        if result.action == "skipped" and any("已存在" in w for w in result.warnings):
            result = yw.replace_behavior(path, behavior, actions, comments=comments,
                                         apply=apply, force=force, base_dir=ROOT)
        result.warnings = list(result.warnings) + list(warnings)
        return result


# ---- CLI ----
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="引导式录制：NL 指令 → 执行 → 记录 → YAML")
    ap.add_argument("--app", required=True, help="App 名（对应 config/apps/*.yaml）")
    ap.add_argument("--package", default=None, help="目标包名；缺省从配置推断")
    ap.add_argument("--serial", default=None, help="设备序列号（无线 adb 用 ip:port）")
    ap.add_argument("--behavior", default="sign", help="行为 ID（如 sign/collect）")
    ap.add_argument("--entry", default="auto", help="入口锚点；auto 自动猜")
    ap.add_argument("--max-steps", type=int, default=20)
    ap.add_argument("--allow-money", action="store_true", help="允许录制资金类步骤")
    ap.add_argument("--apply", action="store_true", help="确认后写盘；缺省仅预览")
    args = ap.parse_args(argv)

    package = args.package
    if not package:
        try:
            cfg = yw.load_app(yw.app_path(args.app, base_dir=ROOT))
            package = (cfg.get("package") or "").strip()
        except Exception:  # noqa: BLE001
            package = ""
    if not package:
        print(f"[error] 无法推断包名：{args.app}")
        return 2

    rec = FlowRecorder(args.app, package, serial=args.serial,
                       max_steps=args.max_steps, allow_money=args.allow_money)
    rec.start()
    print(f"开始录制 {args.app}（{package}）。指令示例：点签到 / 点右下角我的 / "
          f"上滑 / 等2秒 / 返回；trace / undo / done")
    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue
            if line in ("done", "退出", "结束"):
                break
            if line in ("trace", "回放"):
                rec.show_trace()
                continue
            if line in ("undo", "撤销"):
                rec.undo()
                print("已撤销上一步")
                continue
            rec.record_step(line)
    except (EOFError, KeyboardInterrupt):
        pass

    rec.show_trace()
    name = input("一句话命名（行为用途，如：每日签到）: ").strip() or "sign"
    try:
        result = rec.finish(args.app, args.behavior, entry=args.entry,
                            apply=args.apply, force=args.force,
                            comments=[f"录制命名：{name}"])
    except yw.WriterError as exc:
        print(f"[error] 写回失败：{exc}")
        rec.close()
        return 1
    rec.close()
    print(f"[result] action={result.action}")
    if result.diff:
        print(result.diff)
    if result.warnings:
        for w in result.warnings:
            print(f"  [warn] {w}")
    if not args.apply:
        print("（预览模式：加 --apply 才写盘）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
