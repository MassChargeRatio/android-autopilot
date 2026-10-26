# -*- coding: utf-8 -*-
"""test_miniyaml_nested_seq.py - 嵌套块序列解析回归（`- - key: v`）

2026-10-20 真机回归 0/12 的根因之一：miniyaml 的 _parse_seq 不处理
「序列项本身是序列」的写法（`choices:` 下每个分支 `- - type: click_first`），
把整段 any_of 解析成 {"- type": "click_first", ...} —— _run_kind 看到
type=None，any_of 静默全灭。webui 契约测试同时抓到 vias 为空。

PyYAML 语义：外层 '-' 占一项，内层 '-' 开出子序列。
    choices:
    - - type: click_first        # 分支1 = [ {type: click_first, ...} ]
        timeout: 3
    - - type: click_point        # 分支2 = [ {type: click_point, ...} ]
        x: 0.9

运行：
    python tests/test_miniyaml_nested_seq.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import miniyaml  # noqa: E402


def t_choices_nested_seq():
    """any_of choices 的双层序列：每个分支是 list，动作键名干净。"""
    text = """behaviors:
  sign:
  - type: any_of
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 签到
        timeout: 3
    - - type: click_point
        x: 0.9
        y: 0.915
        optional: true
"""
    d = miniyaml.safe_load(text)
    act = d["behaviors"]["sign"][0]
    assert act["type"] == "any_of", act
    ch = act["choices"]
    assert isinstance(ch, list) and len(ch) == 2, ch
    # 分支1
    assert isinstance(ch[0], list) and ch[0][0]["type"] == "click_first", ch[0]
    assert ch[0][0]["timeout"] == 3
    assert ch[0][0]["candidates"] == [{"type": "text", "value": "签到"}]
    # 分支2
    assert ch[1][0]["type"] == "click_point", ch[1]
    assert ch[1][0]["x"] == 0.9 and ch[1][0]["optional"] is True
    # 关键回归点：不允许出现 "- type" 这种拼错键
    flat = repr(d)
    assert '"- type"' not in flat and "'- type'" not in flat, flat
    print("t_choices_nested_seq OK")


def t_inner_multi_item_seq():
    """内层序列多个项：`- - a` 后跟 `  - b` 同在分支里。"""
    text = """choices:
- - type: click_first
    candidates:
    - type: text
      value: 我的
  - type: think
"""
    d = miniyaml.safe_load(text)
    ch = d["choices"]
    assert len(ch) == 1, ch
    branch = ch[0]
    assert [s["type"] for s in branch] == ["click_first", "think"], branch
    assert branch[0]["candidates"][0]["value"] == "我的"
    print("t_inner_multi_item_seq OK")


def t_triple_nested():
    """三层嵌套 `- - - x`：逐层脱壳成 [[[x]]]。"""
    text = """a:
- - - scalar
"""
    d = miniyaml.safe_load(text)
    assert d["a"] == [[["scalar"]]], d
    print("t_triple_nested OK")


def t_flat_seq_unaffected():
    """普通单层序列不受影响。"""
    text = """cands:
- type: text
  value: A
- type: desc
  value: B
"""
    d = miniyaml.safe_load(text)
    assert d["cands"] == [
        {"type": "text", "value": "A"},
        {"type": "desc", "value": "B"},
    ], d
    print("t_flat_seq_unaffected OK")


def t_flow_style_inner():
    """内层流式风格 `- - {type: x}`：按标量容器解析。"""
    text = """choices:
- - {type: click_point, x: 0.5}
- - {type: think}
"""
    d = miniyaml.safe_load(text)
    assert d["choices"] == [
        [{"type": "click_point", "x": 0.5}],
        [{"type": "think"}],
    ], d
    print("t_flow_style_inner OK")


def t_roundtrip_real_config():
    """真配置趣头条 sign：safe_dump -> safe_load 语义等价。"""
    path = os.path.join(ROOT, "config", "apps", "01_趣头条.yaml")
    with open(path, encoding="utf-8") as f:
        orig = miniyaml.safe_load(f.read())
    dumped = miniyaml.safe_dump(orig)
    back = miniyaml.safe_load(dumped)
    assert back == orig, "round-trip 后语义漂移"
    # 显式核对 any_of 分支结构
    sign = back["behaviors"]["sign"]
    anyof = [a for a in sign if a.get("type") == "any_of"]
    assert anyof, "sign 应含 any_of"
    for a in anyof:
        for branch in a["choices"]:
            assert isinstance(branch, list) and branch, branch
            assert all(isinstance(s, dict) and s.get("type") for s in branch), branch
    print("t_roundtrip_real_config OK")


if __name__ == "__main__":
    t_choices_nested_seq()
    t_inner_multi_item_seq()
    t_triple_nested()
    t_flat_seq_unaffected()
    t_flow_style_inner()
    t_roundtrip_real_config()
    print("ALL miniyaml nested-seq TESTS PASSED")
