# -*- coding: utf-8 -*-
"""
miniyaml.py - 零第三方依赖的 YAML 子集解析器（PyYAML 缺失时的兜底）

仅支持本项目 YAML 配置实际用到的语法子集：
  - 块映射（缩进嵌套）、块序列（`- item`）
  - 行注释与行内注释（`#`，引号内不算）、空行
  - 标量：双/单引号字符串（含 \\ 转义）、int、float、bool、null、裸字符串
  - 流式序列 `[a, b]`、流式映射 `{k: v, k2: v2}`
  - 序列项内联映射 `- key: value`（后接更缩进的行视为该映射的其余键）

接口对齐 PyYAML：`safe_load(text_or_file) -> obj`，`safe_dump(obj, stream=None) -> str`。
完整 YAML（锚点/别名/多行块/复杂标签等）不支持时抛 ValueError，调用方应提示安装 PyYAML。
safe_dump 输出块风格（default_flow_style=False），仅支持 dict/list/标量，输出可被本模块 safe_load 正确回读。
"""

import json
import re

_COMMENT_RE = re.compile(r"^\s*#")
_NUM_INT = re.compile(r"^-?\d+$")
_NUM_FLOAT = re.compile(r"^-?\d+\.\d+(?:[eE][+-]?\d+)?$|^-?\.\d+(?:[eE][+-]?\d+)?$")
_NULLS = {"", "null", "Null", "NULL", "~"}
_TRUES = {"true", "True", "TRUE"}
_FALSES = {"false", "False", "FALSE"}


def _strip_comment(s):
    """去掉行内注释：只在引号外、且 '#' 前为空白或行首时截断。"""
    in_d = in_s = False
    for i, ch in enumerate(s):
        if ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "'" and not in_d:
            in_s = not in_s
        elif ch == "#" and not in_d and not in_s:
            if i == 0 or s[i - 1] in " \t":
                return s[:i].rstrip()
    return s.rstrip()


def _tokenize(text):
    tokens = []
    for raw in text.splitlines():
        stripped = raw.expandtabs(4).rstrip()
        if not stripped.strip():
            continue
        body = _strip_comment(stripped)
        if _COMMENT_RE.match(body):
            continue
        if not body.strip():
            continue
        indent = len(body) - len(body.lstrip(" "))
        tokens.append((indent, body.strip()))
    return tokens


def _find_top_colon(s):
    """返回引号外的第一个冒号下标；无则 -1。"""
    in_d = in_s = False
    for i, ch in enumerate(s):
        if ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "'" and not in_d:
            in_s = not in_s
        elif ch == ":" and not in_d and not in_s:
            return i
    return -1


def _strip_quotes(raw):
    """剥离键/值的包裹引号，返回原始字符串（不做类型推断）。"""
    if len(raw) >= 2 and raw[0] == "'" and raw[-1] == "'":
        return raw[1:-1]
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"' and raw.count('"') >= 2:
        try:
            return _unescape_dq(raw)
        except Exception:
            return raw[1:-1]
    return raw


def _split_pair(s):
    """拆 `key: value`（key 为引号外首个冒号前）。无冒号返回 (None, None)。"""
    idx = _find_top_colon(s)
    if idx <= 0:
        return (None, None)
    key = _strip_quotes(s[:idx].strip())
    val = s[idx + 1:].strip()
    return (key, val)


def _split_top(inner, sep):
    """按顶层分隔符切分流式容器内容（引号/括号内不被切）。"""
    parts, buf = [], []
    depth = 0
    in_d = in_s = False
    for ch in inner:
        if ch == '"' and not in_s:
            in_d = not in_d
            buf.append(ch)
            continue
        if ch == "'" and not in_d:
            in_s = not in_s
            buf.append(ch)
            continue
        if not in_d and not in_s:
            if ch in "[{(":
                depth += 1
            elif ch in "]})":
                depth -= 1
            elif ch == sep and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
                continue
        buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    return parts


def _unescape_dq(s):
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                out.append("\r")
            elif nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            elif nxt == "u" and i + 5 < len(s):
                try:
                    out.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    out.append("\\u")
            else:
                out.append(nxt)
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _parse_scalar(t):
    t = t.strip()
    if not t:
        return None
    # 流式容器
    if t.startswith("[") and t.endswith("]"):
        inner = t[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p) for p in _split_top(inner, ",")]
    if t.startswith("{") and t.endswith("}"):
        inner = t[1:-1].strip()
        if not inner:
            return {}
        d = {}
        for part in _split_top(inner, ","):
            k, v = _split_pair(part)
            if k is None:
                raise ValueError(f"流式映射项缺少 ':'：{part!r}")
            d[k] = _parse_scalar(v) if v else None
        return d
    # 引号字符串
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        return _unescape_dq(t[1:-1])
    if len(t) >= 2 and t[0] == "'" and t[-1] == "'":
        return t[1:-1].replace("''", "'")
    # 基本标量
    if t in _NULLS:
        return None
    if t in _TRUES:
        return True
    if t in _FALSES:
        return False
    if _NUM_INT.match(t):
        return int(t)
    if _NUM_FLOAT.match(t):
        return float(t)
    return t  # 裸字符串


def _parse_seq(tokens, i, item_level):
    """解析一列块序列项（缩进 == item_level 且以 '-' 开头）。

    兼容两种风格：
      - miniyaml dump / 常规：序列项缩进 == 父键缩进 + 2；
      - PyYAML dump：块序列项与父键同列。
    返回 (items, 下一个未消费 token 下标)。
    """
    items = []
    n = len(tokens)
    while i < n:
        indent, body = tokens[i]
        if indent != item_level or not body.startswith("-"):
            break
        rest = body[1:].lstrip()
        if rest == "":
            if i + 1 < n and tokens[i + 1][0] > item_level:
                child, ni = _build(tokens, i + 1, tokens[i + 1][0])
                items.append(child)
                i = ni
            else:
                items.append(None)
                i += 1
            continue
        # 嵌套块序列（`- - key: v`）：本项本身又是一个序列。
        # PyYAML 语义：外层 '-' 占一项，内层 '-' 开出子序列；choices 的每个
        # 分支就是这样写的。2026-10-20 实测不处理会把整段 any_of 解析成
        # {"- type": "click_first", ...}——运行时 any_of 静默全灭（0/12 回归
        # 的根因之一），webui 契约测试同时抓到 vias 为空。
        if rest.startswith("-"):
            inner_col = item_level + (len(body) - len(rest))
            tokens[i] = (inner_col, rest)
            sub, ni = _parse_seq(tokens, i, inner_col)
            items.append(sub)
            i = ni
            continue
        # 序列项本身是流式容器（{...} / [...]）时，整体作为一个标量，不再拆键值
        if rest.startswith("{") or rest.startswith("["):
            items.append(_parse_scalar(rest))
            i += 1
            continue
        key, vtext = _split_pair(rest)
        if key is None:
            items.append(_parse_scalar(rest))
            i += 1
            continue
        item = {}
        i += 1
        if vtext:
            item[key] = _parse_scalar(vtext)
            if i < n and tokens[i][0] > item_level:
                deeper, ni = _build(tokens, i, tokens[i][0])
                if isinstance(deeper, dict):
                    # 保持源文本键序：首键在前，deeper 其余键随后
                    item = {key: item[key], **deeper}
                i = ni
        else:
            if i < n and tokens[i][0] > item_level:
                child, ni = _build(tokens, i, tokens[i][0])
                item[key] = child
                i = ni
            else:
                item[key] = None
        # 合并同层兄弟键（miniyaml dump 布局：`- key:` 挂块子节点后跟 timeout/type 等兄弟键）
        sib_indent = item_level + 2
        while i < n:
            ind2, body2 = tokens[i]
            if ind2 != sib_indent or body2.startswith("-"):
                break
            k2, vt2 = _split_pair(body2)
            if k2 is None:
                break
            i += 1
            if vt2:
                item[k2] = _parse_scalar(vt2)
                if i < n and tokens[i][0] > sib_indent:
                    d2, ni2 = _build(tokens, i, tokens[i][0])
                    if isinstance(d2, dict):
                        # 保持源文本键序：当前兄弟键在前，d2 其余键随后
                        item = {k2: item[k2], **d2}
                    i = ni2
            else:
                if i < n and tokens[i][0] > sib_indent:
                    c2, ni2 = _build(tokens, i, tokens[i][0])
                    item[k2] = c2
                    i = ni2
                else:
                    item[k2] = None
        items.append(item)
    return items, i


def _build(tokens, i, level):
    """解析缩进为 level 的一块。返回 (value, 下一token下标)。"""
    value = None
    n = len(tokens)
    while i < n:
        indent, body = tokens[i]
        if indent < level:
            break
        if indent > level:
            # 防御：理论上不会到达（深层已由上层消费）
            i += 1
            continue
        # ---- 序列项 ----
        if body.startswith("-"):
            if value is None:
                value = []
                value, i = _parse_seq(tokens, i, level)
            else:
                # 理论不会到达：同缩进 '-' 应已被所属键的前瞻消费
                i += 1
            continue
        # ---- 映射项 ----
        key, vtext = _split_pair(body)
        if key is None:
            # 出现在块级但无冒号：罕见，按独立标量处理
            if value is None:
                value = _parse_scalar(body)
            i += 1
            continue
        if value is None:
            value = {}
        i += 1
        if vtext:
            value[key] = _parse_scalar(vtext)
        else:
            if i < n and tokens[i][0] > level:
                child, ni = _build(tokens, i, tokens[i][0])
                value[key] = child
                i = ni
            elif i < n and tokens[i][0] == level and tokens[i][1].startswith("-"):
                # PyYAML 风格：块序列项与键同列，序列属于该键的值
                seq, ni = _parse_seq(tokens, i, level)
                value[key] = seq
                i = ni
            else:
                value[key] = None
    return value, i


def safe_load(text):
    """对齐 PyYAML.safe_load：接受字符串或文件对象，返回 Python 对象。"""
    if hasattr(text, "read"):
        text = text.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8")
    tokens = _tokenize(text)
    if not tokens:
        return None
    obj, _ = _build(tokens, 0, tokens[0][0])
    return obj


# ---------------------------------------------------------------------------
# safe_dump：块风格导出（对齐 PyYAML safe_dump 的常见用法）
# ---------------------------------------------------------------------------

def _dump_quoted(s):
    """生成引号包裹的字符串字面量：优先单引号，含单引号时退回双引号转义。"""
    if "'" not in s:
        return "'" + s + "'"
    # 双引号 + 转义（复用 json.dumps 的转义规则，safe_load 的 _unescape_dq 可读回）
    return json.dumps(s, ensure_ascii=False)


def _needs_quote(s):
    """判断裸字符串是否需要加引号（避免被 safe_load 误解为其他类型或破坏结构）。"""
    # YAML 1.1 布尔/空情面量：PyYAML 会把裸 yes/no/on/off/y/n 解析成 bool，需加引号保字符串
    if s.lower() in ("y", "n", "yes", "no", "on", "off"):
        return True
    if s == "":
        return True
    if s in _NULLS or s in _TRUES or s in _FALSES:
        return True
    if _NUM_INT.match(s) or _NUM_FLOAT.match(s):
        return True
    # 日期/时间样式：PyYAML 会把裸 2026-09-10 解析成 datetime.date，需加引号保字符串
    if re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}([T ].*)?$", s):
        return True
    # 含结构字符 / 引号 / 控制字符 / 首尾空白 / 以 '-' 开头
    if any(ch in s for ch in ":#{}[],\n\t"):
        return True
    if "\r" in s or '"' in s:
        return True
    if s != s.strip():
        return True
    if s.startswith("-") or s.startswith("?") or s.startswith(" "):
        return True
    return False


def _dump_scalar(v):
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return _dump_quoted(v) if _needs_quote(v) else v
    if isinstance(v, (dict, list)):
        raise ValueError("嵌套容器请使用块级导出路径，不要作为叶标量")
    raise TypeError(f"无法序列化的类型: {type(v)!r}")


def _dump_sequence(node, indent):
    """导出块序列（indent 为序列项自身的缩进层级）。"""
    pad = " " * indent
    lines = []
    for item in node:
        if isinstance(item, dict):
            if not item:
                lines.append(pad + "- {}")
                continue
            first = True
            for k, v in item.items():
                ks = _dump_scalar(k)
                prefix = "- " if first else "  "
                first = False
                if isinstance(v, dict):
                    if not v:
                        lines.append(f"{pad}{prefix}{ks}: {{}}")
                    else:
                        lines.append(f"{pad}{prefix}{ks}:")
                        lines.extend(_dump_block(v, indent + 4))
                elif isinstance(v, list):
                    if not v:
                        lines.append(f"{pad}{prefix}{ks}: []")
                    else:
                        lines.append(f"{pad}{prefix}{ks}:")
                        lines.extend(_dump_sequence(v, indent + 4))
                else:
                    lines.append(f"{pad}{prefix}{ks}: {_dump_scalar(v)}")
        elif isinstance(item, list):
            lines.append(pad + "-")
            lines.extend(_dump_sequence(item, indent + 2))
        else:
            lines.append(pad + "- " + _dump_scalar(item))
    return lines


def _dump_block(node, indent):
    """导出块映射或根节点。返回行列表。"""
    pad = " " * indent
    if isinstance(node, dict):
        if not node:
            return [pad + "{}"]
        lines = []
        for k, v in node.items():
            ks = _dump_scalar(k)
            if isinstance(v, dict):
                if not v:
                    lines.append(f"{pad}{ks}: {{}}")
                else:
                    lines.append(f"{pad}{ks}:")
                    lines.extend(_dump_block(v, indent + 2))
            elif isinstance(v, list):
                if not v:
                    lines.append(f"{pad}{ks}: []")
                else:
                    lines.append(f"{pad}{ks}:")
                    lines.extend(_dump_sequence(v, indent + 2))
            else:
                lines.append(f"{pad}{ks}: {_dump_scalar(v)}")
        return lines
    if isinstance(node, list):
        return _dump_sequence(node, indent) if node else [pad + "[]"]
    return [pad + _dump_scalar(node)]


def safe_dump(obj, stream=None, default_flow_style=False, sort_keys=False,
              allow_unicode=True):
    """对齐 PyYAML.safe_dump 常用签名：块风格导出 dict/list/标量。

    返回字符串（stream 为 None）或写入 stream 后返回 None。
    输出保证可被本模块 safe_load 重新解析为语义等价的 dict/list。
    """
    if isinstance(obj, dict):
        lines = _dump_block(obj, 0) if obj else ["{}"]
    elif isinstance(obj, list):
        lines = _dump_sequence(obj, 0) if obj else ["[]"]
    else:
        lines = [str(obj)]
    text = "\n".join(lines) + "\n"
    if stream is not None:
        stream.write(text)
        return None
    return text
