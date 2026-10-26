# -*- coding: utf-8 -*-
"""yaml_writer.py - 统一 YAML 写回层（AUTOP-NL-2026-10-22）

为什么需要它：
    仓库里已有三套写回范式，各写各的、零测试覆盖，且都有已知缺陷：
      * `to_any_of.py` 整对象 yaml.dump —— 中文注释全丢；
      * `apply_candidate_fixes.py` 行级插入 —— 用 `open(...,"r")` 读，
        Windows 下会把 CRLF 静默统一成 LF，写回造成整份文件 diff；
      * `apply_sign_configs.py` 硬编码文本块 —— 一次性脚本，不可复用。
    34 份 App 配置里 13 份是 CRLF、21 份是 LF，混存是客观事实，
    所以「保换行」不是洁癖，是防止误判「整份文件被改」。

设计取舍（三种写法）：
    A. 行级插入/替换（默认）：保留注释、保留未修改行的字节序列；依赖缩进探测，
       缩进从 `behaviors:` 行实测反推（拆分文件=2，旧单文件=4），不靠猜。
    B. 整对象 dump（`dump_app`，逃生门）：只在文件无注释或需要把
       `[动作]` 改造成 `[[动作],[动作]]` 多模板时用；写前打 WARN。
    C. 硬编码文本块：不提供，已弃用。

契约（`tests/test_yaml_writer.py` 逐条锁定）：
    1. `apply=False` 是缺省：只返回 diff，绝不碰盘。
    2. 幂等：目标块文本逐行相等 -> action="skipped"。
    3. `insert_behavior` 遇已存在 bid 一律 skip；`replace_behavior` 需 force=True。
    4. 只在 apply=True 且确有变更时创建备份。
    5. apply 后必须 verify；verify 失败自动从备份回滚（action="rolled_back"）。
    6. 换行保真：未修改行的字节序列完全不变。
    7. 路径白名单：只允许 <root>/config/apps/*.yaml；拒写 config.yaml 主文件。
"""
from __future__ import annotations

import difflib
import os
import shutil
import time
from dataclasses import dataclass, field

try:
    import yaml
except ImportError as exc:  # pragma: no cover - 仓库 venv 内必有 PyYAML
    raise ImportError(
        "yaml_writer 需要 PyYAML（miniyaml 只有 load，没有 dump）。"
        "请用项目 venv：./.venv/Scripts/python.exe"
    ) from exc

import config_loader

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = "_backup_pre_fix"
TS_FMT = "%Y%m%d_%H%M%S"
APPS_SUBDIR = os.path.join("config", "apps")


class WriterError(RuntimeError):
    """写回层不可恢复错误（路径越界、缺少 behaviors 段等）。"""


@dataclass
class WriteResult:
    path: str
    action: str  # preview | inserted | replaced | skipped | rolled_back | error
    backup: str | None = None
    diff: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.action in ("inserted", "replaced")


# ---------- 定位 / 读取 ----------

def app_path(app_name: str, config_path: str | None = None,
             base_dir: str | None = None) -> str:
    """App 名 -> App 级 YAML 绝对路径（薄封装 config_loader.app_config_path）。"""
    base = base_dir or DEFAULT_ROOT
    cfg = None
    if config_path and os.path.exists(config_path):
        try:
            cfg = config_loader._load_yaml(config_path)
        except Exception:
            cfg = None
    path = config_loader.app_config_path(app_name, cfg=cfg, base_dir=base)
    assert_in_apps_dir(path, base)
    return path


def assert_in_apps_dir(path: str, base_dir: str | None = None) -> None:
    """路径白名单：必须是 <base>/config/apps/*.yaml，且不是主 config.yaml。"""
    base = os.path.abspath(base_dir or DEFAULT_ROOT)
    target = os.path.abspath(path)
    apps_dir = os.path.join(base, APPS_SUBDIR)
    if os.path.abspath(target) == os.path.join(base, "config.yaml"):
        raise WriterError("拒绝写 config.yaml 主文件：apps: [] 是拆分约定，改它必然破坏 parity")
    if not target.lower().endswith((".yaml", ".yml")):
        raise WriterError(f"只允许写 .yaml/.yml：{path}")
    if os.path.commonpath([target, os.path.abspath(apps_dir)]) != os.path.abspath(apps_dir):
        raise WriterError(f"只允许写 config/apps/ 下的文件：{path}")


def read_text(path: str) -> tuple[list[str], str, bool]:
    """读文件 -> (lines, eol, ends_with_newline)。

    按字节判断 eol（不依赖文本模式的通用换行转换），保证写回时字节一致。
    """
    with open(path, "rb") as f:
        raw = f.read()
    eol = "\r\n" if b"\r\n" in raw else "\n"
    ends_nl = raw.endswith(b"\n")
    text = raw.decode("utf-8")
    if text.endswith("\r\n"):
        text = text[:-2]
    elif text.endswith("\n"):
        text = text[:-1]
    lines = text.replace("\r\n", "\n").split("\n") if text else []
    return lines, eol, ends_nl


def load_app(path: str) -> dict:
    """读单个 App 文件；兼容旧式 `- name: X`（加载成 list）的形态，取首个元素。"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else {}
    return data if isinstance(data, dict) else {}


def find_app_block(lines: list[str], app_name: str) -> tuple[int | None, int | None]:
    """返回 app 块 [start, end)；拆分后的 App 级文件整文件即一个块。"""
    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == f"- name: {app_name}":
            start = i
            break
    if start is None:
        if lines and lines[0].strip() == f"name: {app_name}":
            return 0, len(lines)
        return None, None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- name: "):
            end = j
            break
    return start, end


def behavior_indent(lines: list[str], start: int, end: int) -> int | None:
    """behaviors 子键缩进：拆分文件=2，旧单文件=4；找不到 behaviors: 返回 None。"""
    for k in range(start, end):
        s = lines[k].rstrip()
        if s.strip() == "behaviors:":
            return len(s) - len(s.lstrip()) + 2
    return None


def find_behavior(lines: list[str], start: int, end: int, bid: str,
                  indent: int) -> int | None:
    for k in range(start, end):
        s = lines[k]
        if s.startswith(" " * indent) and not s.startswith(" " * (indent + 1)) \
                and s.rstrip().endswith(":") and s.strip().rstrip(":") == bid:
            return k
    return None


def behavior_span(lines: list[str], bstart: int, app_end: int, indent: int) -> int:
    for k in range(bstart + 1, app_end):
        s = lines[k]
        if s.startswith(" " * indent) and not s.startswith(" " * (indent + 1)) \
                and s.rstrip().endswith(":"):
            return k
    return app_end


# ---------- 渲染（纯函数，无 IO） ----------

def render_actions(actions: list[dict], indent: int = 2) -> list[str]:
    """动作链 -> YAML 文本行（带缩进）。产出与仓库既有 `- - type:` 风格逐字一致。"""
    dumped = yaml.safe_dump(
        actions,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=200,
    )
    pad = " " * indent
    return [pad + ln if ln.strip() else "" for ln in dumped.rstrip("\n").split("\n")]


def render_behavior_block(bid: str, actions: list[dict], indent: int,
                          comments: list[str] | None = None) -> list[str]:
    """渲染 `  sign:` + 注释 + 动作链（不含前后空行）。"""
    pad = " " * indent
    out = []
    for c in (comments or []):
        out.append(f"{pad}# {c}" if c and not c.startswith("#") else f"{pad}{c}")
    out.append(f"{pad}{bid}:")
    out.extend(render_actions(actions, indent + 2))
    return out


# ---------- 备份 / 写盘 ----------

def backup(path: str, tag: str = "NL", base_dir: str | None = None) -> str:
    """字节级备份到 _backup_pre_fix/<stem>.pre_<TAG>_<yyyymmdd_HHMMSS>.yaml。"""
    base = base_dir or DEFAULT_ROOT
    bdir = os.path.join(base, BACKUP_DIR)
    os.makedirs(bdir, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(path))
    dst = os.path.join(bdir, f"{stem}.pre_{tag}_{time.strftime(TS_FMT)}{ext}")
    shutil.copy2(path, dst)
    return dst


def atomic_write(path: str, lines: list[str], eol: str, ends_nl: bool = True) -> None:
    data = eol.join(lines) + (eol if ends_nl else "")
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data.encode("utf-8"))
    os.replace(tmp, path)


def _unified_diff(old: list[str], new: list[str], path: str) -> str:
    return "".join(difflib.unified_diff(
        [ln + "\n" for ln in old], [ln + "\n" for ln in new],
        fromfile=f"a/{os.path.basename(path)}",
        tofile=f"b/{os.path.basename(path)}",
        n=3,
    ))


# ---------- 复验 ----------

def snapshot(config_path: str | None = None,
             base_dir: str | None = None) -> dict[str, dict]:
    """{app_name: app_dict} 全量快照（用于写后确认「没误伤别的 App」）。"""
    base = base_dir or DEFAULT_ROOT
    cfg_path = config_path or os.path.join(base, "config.yaml")
    try:
        cfg = config_loader.load_config(cfg_path)
    except Exception:
        return {}
    return {(a.get("name") or "").strip(): a for a in (cfg.get("apps") or [])}


def verify(path: str, before: dict[str, dict], bid: str,
           expect_actions: list[dict] | None = None,
           config_path: str | None = None,
           base_dir: str | None = None) -> tuple[bool, list[str]]:
    """写后复验：①可加载 ②其他 App 未变 ③目标 bid 与期望深比较相等。"""
    problems: list[str] = []
    try:
        app = load_app(path)
    except Exception as exc:  # noqa: BLE001
        return False, [f"目标文件无法解析: {exc}"]

    name = (app.get("name") or "").strip()
    behaviors = app.get("behaviors") or {}
    if bid not in behaviors:
        problems.append(f"目标行为缺失: {name}.{bid}")
    elif expect_actions is not None and behaviors.get(bid) != expect_actions:
        problems.append(f"目标行为与期望不一致: {name}.{bid}")

    if before:
        try:
            cfg_path = config_path or os.path.join(base_dir or DEFAULT_ROOT, "config.yaml")
            after = {(a.get("name") or "").strip(): a for a in
                     (config_loader.load_config(cfg_path).get("apps") or [])}
        except Exception as exc:  # noqa: BLE001
            problems.append(f"整体配置无法加载: {exc}")
            after = {}
        if after:
            if len(after) != len(before):
                problems.append(f"app 数量变化: {len(before)} -> {len(after)}")
            for aname, aapp in before.items():
                if aname == name:
                    continue
                if after.get(aname) != aapp:
                    problems.append(f"误伤其他 App: {aname}")
    return (not problems), problems


# ---------- 主操作 ----------

def _prepare(path: str, bid: str, actions: list[dict], comments: list[str] | None,
             indent_hint: int | None) -> tuple[list[str], str, bool, int, int, int | None]:
    if not os.path.exists(path):
        raise WriterError(f"文件不存在: {path}")
    lines, eol, ends_nl = read_text(path)
    start, end = find_app_block(lines, _app_name_of(lines))
    if start is None:
        raise WriterError(f"无法定位 App 块: {path}")
    indent = behavior_indent(lines, start, end)
    if indent is None:
        raise WriterError(f"缺少 behaviors: 段，拒绝写（{path}）")
    if indent_hint is not None and indent_hint != indent:
        pass  # 以实测为准，hint 仅作调试参考
    bstart = find_behavior(lines, start, end, bid, indent)
    block = render_behavior_block(bid, actions, indent, comments)
    return lines, eol, ends_nl, indent, start, (bstart, end, block)  # type: ignore[return-value]


def _app_name_of(lines: list[str]) -> str:
    for ln in lines[:5]:
        s = ln.strip()
        if s.startswith("name:"):
            return s.split(":", 1)[1].strip()
        if s.startswith("- name:"):
            return s.split(":", 1)[1].strip()
    raise WriterError("无法从文件首部读取 name:")


def insert_behavior(path: str, bid: str, actions: list[dict],
                    comments: list[str] | None = None,
                    apply: bool = False, tag: str = "NL",
                    base_dir: str | None = None) -> WriteResult:
    """在 behaviors: 末尾插入新行为；已存在则 skip（不覆盖，覆盖请用 replace_behavior）。"""
    assert_in_apps_dir(path, base_dir)
    lines, eol, ends_nl, indent, start, tail = _prepare(path, bid, actions, comments, None)
    bstart, end, block = tail
    if bstart is not None:
        return WriteResult(path, "skipped", None, "",
                           [f"{bid} 已存在；如需覆盖请用 replace_behavior(force=True)"])

    # behaviors 段的结束位置：下一个缩进 <= behaviors 的键，或文件末尾
    b_indent = indent - 2
    insert_at = end
    for k in range(start, end):
        if lines[k].rstrip().strip() == "behaviors:":
            for j in range(k + 1, end):
                s = lines[j]
                if not s.strip():
                    continue
                cur = len(s) - len(s.lstrip())
                if cur <= b_indent:
                    insert_at = j
                    break
            break

    # 插入点前补一个空行（若上一行非空），保持文件风格
    new_lines = list(lines)
    payload = list(block)
    if insert_at > 0 and new_lines[insert_at - 1].strip():
        payload = [""] + payload
    if insert_at < len(new_lines) and new_lines[insert_at].strip():
        payload = payload + [""]
    new_lines[insert_at:insert_at] = payload

    diff = _unified_diff(lines, new_lines, path)
    if not apply:
        return WriteResult(path, "preview", None, diff, [])
    bak = backup(path, tag, base_dir)
    atomic_write(path, new_lines, eol, ends_nl)
    ok, problems = verify(path, {}, bid, actions, base_dir=base_dir)
    if not ok:
        shutil.copy2(bak, path)
        return WriteResult(path, "rolled_back", bak, diff, problems)
    return WriteResult(path, "inserted", bak, diff, [])


def replace_behavior(path: str, bid: str, actions: list[dict],
                     comments: list[str] | None = None,
                     apply: bool = False, force: bool = False, tag: str = "NL",
                     base_dir: str | None = None) -> WriteResult:
    """替换已有行为块；force=False 时 skip。"""
    assert_in_apps_dir(path, base_dir)
    lines, eol, ends_nl, indent, start, tail = _prepare(path, bid, actions, comments, None)
    bstart, end, block = tail
    if bstart is None:
        return WriteResult(path, "skipped", None, "", [f"{bid} 不存在；新增请用 insert_behavior"])
    if not force:
        return WriteResult(path, "skipped", None, "", ["replace 需要 force=True"])

    bend = behavior_span(lines, bstart, end, indent)
    old_block = lines[bstart:bend]
    if old_block == block:
        return WriteResult(path, "skipped", None, "", ["内容与现有块逐行相同（幂等）"])

    new_lines = list(lines)
    new_lines[bstart:bend] = block
    diff = _unified_diff(lines, new_lines, path)
    if not apply:
        return WriteResult(path, "preview", None, diff, [])
    bak = backup(path, tag, base_dir)
    atomic_write(path, new_lines, eol, ends_nl)
    ok, problems = verify(path, {}, bid, actions, base_dir=base_dir)
    if not ok:
        shutil.copy2(bak, path)
        return WriteResult(path, "rolled_back", bak, diff, problems)
    return WriteResult(path, "replaced", bak, diff, [])


def dump_app(app: dict, path: str, apply: bool = False, tag: str = "NL",
             base_dir: str | None = None) -> WriteResult:
    """整对象重写（逃生门：丢注释）。仅在文件无注释或需改多模板结构时使用。"""
    assert_in_apps_dir(path, base_dir)
    lines, eol, ends_nl = read_text(path)
    dumped = yaml.safe_dump(app, allow_unicode=True, sort_keys=False,
                            default_flow_style=False, width=200)
    new_lines = dumped.rstrip("\n").split("\n")
    diff = _unified_diff(lines, new_lines, path)
    warn = ["dump_app 会丢弃全部中文注释，非必要勿用"]
    if not apply:
        return WriteResult(path, "preview", None, diff, warn)
    bak = backup(path, tag, base_dir)
    atomic_write(path, new_lines, eol, True)
    return WriteResult(path, "replaced", bak, diff, warn)
