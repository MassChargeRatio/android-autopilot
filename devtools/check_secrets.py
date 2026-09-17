#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_secrets.py - 提交前拦下明文密钥

背景（真实踩过）：本工程的 VLM API Key 曾经**硬编码在源码里** ——
`devtools/vlm_probe.py` 与 3 个 `handover/02_适配脚本/*.py` 各写了一份明文。
只要把工程推上 GitHub，Key 就跟着走了。这类东西靠「记得别提交」是守不住的，
必须有一条**自动化的**检查。

用法：
    python devtools/check_secrets.py              # 扫 git 暂存区（pre-commit 用）
    python devtools/check_secrets.py --tracked    # 扫全部已跟踪文件
    python devtools/check_secrets.py <文件...>    # 只扫指定文件
    python devtools/check_secrets.py --all        # 扫工作区全部文件（忽略 .gitignore）

退出码：0 = 干净；1 = 发现疑似密钥（会打印 file:line）。
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 疑似密钥的形态。宁可误报也别漏报 —— 误报只是多看一眼，漏报是不可逆的泄露。
PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
     "疑似 API Key（sk- 前缀）"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
     "私钥文件内容"),
    (re.compile(r"(?i)\b(?:api[_-]?key|apikey|access[_-]?key|secret|"
                r"passwd|password|auth[_-]?token)\b\s*[:=]\s*[\"']?"
                r"([A-Za-z0-9_\-+/]{20,})"),
     "赋值式密钥（字段名 + 长字面量）"),
]

# 命中行里出现这些词就放行：说明不是硬编码的真值。
ALLOW = re.compile(
    r"(?i)(environ|getenv|os\.environ|"
    r"example|placeholder|sample|dummy|fake|redacted|"
    r"your[_-]|change[_-]?me|xxx+|\*\*\*|<[^>]*>|\{\{?[^}]*\}?\})")

SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz",
            ".tar", ".db", ".pyc", ".woff", ".woff2", ".ttf", ".mp4", ".exe",
            ".dll", ".so", ".bin"}

MAX_BYTES = 2 * 1024 * 1024      # 单文件超过 2MB 不扫（几乎不会是源码）


def _git(*args):
    try:
        out = subprocess.run(["git", "-C", ROOT] + list(args),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def list_staged():
    out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [x for x in (out or "").splitlines() if x.strip()]


def list_tracked():
    out = _git("ls-files")
    return [x for x in (out or "").splitlines() if x.strip()]


def scan(path):
    """返回 [(行号, 说明, 命中片段), ...]。"""
    full = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.isfile(full):
        return []
    if os.path.splitext(full)[1].lower() in SKIP_EXT:
        return []
    try:
        if os.path.getsize(full) > MAX_BYTES:
            return []
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        return []

    hits = []
    for n, line in enumerate(lines, 1):
        if ALLOW.search(line):
            continue
        for rx, why in PATTERNS:
            m = rx.search(line)
            if m:
                got = m.group(0)
                # 命中片段也做遮蔽，避免把密钥又打印到 CI 日志里
                shown = got if len(got) <= 12 else got[:8] + "…（已遮蔽）"
                hits.append((n, why, shown))
                break
    return hits


def main():
    ap = argparse.ArgumentParser(description="提交前扫明文密钥")
    ap.add_argument("files", nargs="*", help="只扫这些文件")
    ap.add_argument("--staged", action="store_true",
                    help="扫 git 暂存区（默认行为）")
    ap.add_argument("--tracked", action="store_true", help="扫全部已跟踪文件")
    ap.add_argument("--all", action="store_true",
                    help="扫工作区全部文件（无视 .gitignore，含未跟踪）")
    args = ap.parse_args()

    if args.files:
        targets = args.files
    elif args.all:
        targets = []
        for base, dirs, names in os.walk(ROOT):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__", "node_modules")]
            targets += [os.path.relpath(os.path.join(base, n), ROOT)
                        for n in names]
    elif args.tracked:
        targets = list_tracked()
    else:
        targets = list_staged()

    bad = 0
    for p in targets:
        for n, why, shown in scan(p):
            print(f"  ✗ {p}:{n}  {why}  ->  {shown}")
            bad += 1

    if bad:
        print(f"\n发现 {bad} 处疑似明文密钥 —— 已阻止提交。")
        print("修法：改成从环境变量或 config.yaml 读，"
              "真实配置加进 .gitignore（参考 config.example.yaml）。")
        return 1
    print(f"OK  未发现明文密钥（扫描 {len(targets)} 个文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
