# -*- coding: utf-8 -*-
"""test_yaml_writer.py - 统一写回层（AUTOP-NL-2026-10-22）

锁定 7 条契约，重点是三条容易静默出错的：
  * 换行保真：CRLF 文件写回后仍是 CRLF，未修改行字节不变；
  * 幂等 + 不覆盖：已存在行为一律 skip，replace 需 force；
  * 写后复验与自动回滚。

全部用 tempfile 造 apps_dir，不碰真实 config/apps/。

运行：
    ./.venv/Scripts/python.exe -m pytest tests/test_yaml_writer.py -q
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import yaml  # noqa: E402

import devtools.yaml_writer as yw  # noqa: E402

LF_BODY = """name: A
package: com.example.a
behaviors:
  collect:
  - type: click_point
    x: 0.5
    y: 0.5
    timeout: 6
    optional: true
    desc: 图像-收集
"""

CRLF_BODY = LF_BODY.replace("\n", "\r\n")


def _mkroot(body: str = LF_BODY, extra_app: str | None = None) -> str:
    root = tempfile.mkdtemp(prefix="yw_")
    apps = os.path.join(root, "config", "apps")
    os.makedirs(apps)
    with open(os.path.join(root, "config.yaml"), "w", encoding="utf-8") as f:
        f.write("apps: []\napps_dir: config/apps\n")
    with open(os.path.join(apps, "01_A.yaml"), "w", encoding="utf-8", newline="") as f:
        f.write(body)
    if extra_app:
        with open(os.path.join(apps, "02_B.yaml"), "w", encoding="utf-8") as f:
            f.write(extra_app)
    return root


ACTIONS = [
    {"type": "click_first", "candidates_from": "sign", "timeout": 8, "optional": True},
    {"type": "think"},
]


def t_read_text_detects_eol():
    root = _mkroot(CRLF_BODY)
    lines, eol, ends_nl = yw.read_text(os.path.join(root, "config", "apps", "01_A.yaml"))
    assert eol == "\r\n", repr(eol)
    assert ends_nl is True
    assert lines[0] == "name: A"
    print("OK  读文件能识别 CRLF")


def t_insert_preserves_crlf_and_comments():
    root = _mkroot(CRLF_BODY)
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    before = open(path, "rb").read()
    res = yw.insert_behavior(path, "sign", ACTIONS, comments=["测试注释"], apply=True,
                             base_dir=root)
    assert res.action == "inserted", (res.action, res.warnings)
    after = open(path, "rb").read()
    assert b"\r\n" in after and after.count(b"\n") == after.count(b"\r\n"), "写回把 CRLF 改成了 LF"
    assert "测试注释".encode("utf-8") in after
    # 未修改行的字节序列必须原样保留
    for ln in before.split(b"\r\n"):
        if ln.strip():
            assert ln in after, f"原行丢失或被改写: {ln!r}"
    print("OK  插入后 CRLF 保持、注释保留、原行字节不变")


def t_insert_is_idempotent():
    root = _mkroot()
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    r1 = yw.insert_behavior(path, "sign", ACTIONS, apply=True, base_dir=root)
    assert r1.action == "inserted", r1.warnings
    r2 = yw.insert_behavior(path, "sign", ACTIONS, apply=True, base_dir=root)
    assert r2.action == "skipped", r2.action
    print("OK  重复插入 -> skipped（幂等）")


def t_insert_skips_existing_behavior():
    root = _mkroot()
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    res = yw.insert_behavior(path, "collect", ACTIONS, apply=True, base_dir=root)
    assert res.action == "skipped", res.action
    print("OK  已存在行为不覆盖，提示改用 replace")


def t_replace_requires_force():
    root = _mkroot()
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    res = yw.replace_behavior(path, "collect", ACTIONS, apply=True, base_dir=root)
    assert res.action == "skipped" and "force" in res.warnings[0], res.warnings
    res2 = yw.replace_behavior(path, "collect", ACTIONS, apply=True, force=True, base_dir=root)
    assert res2.action == "replaced", (res2.action, res2.warnings)
    print("OK  replace 需 force；force 后替换成功")


def t_replace_span_does_not_swallow_next_behavior():
    body = LF_BODY + "  watch:\n  - type: think\n"
    root = _mkroot(body)
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    yw.replace_behavior(path, "collect", [{"type": "think"}], apply=True, force=True, base_dir=root)
    app = yaml.safe_load(open(path, encoding="utf-8"))
    assert app["behaviors"]["collect"] == [{"type": "think"}], app["behaviors"]["collect"]
    assert app["behaviors"]["watch"] == [{"type": "think"}], "替换吞掉了下一个行为"
    print("OK  替换不越界，后续行为完好")


def t_backup_naming_and_location():
    root = _mkroot()
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    res = yw.insert_behavior(path, "sign", ACTIONS, apply=True, base_dir=root)
    assert res.backup and os.path.exists(res.backup)
    name = os.path.basename(res.backup)
    assert name.startswith("01_A.pre_NL_") and name.endswith(".yaml"), name
    assert os.path.basename(os.path.dirname(res.backup)) == "_backup_pre_fix"
    print("OK  备份落在 _backup_pre_fix/，命名含 pre_NL_<ts>")


def t_preview_does_not_touch_disk():
    root = _mkroot()
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    before = open(path, "rb").read()
    res = yw.insert_behavior(path, "sign", ACTIONS, apply=False, base_dir=root)
    assert res.action == "preview"
    assert open(path, "rb").read() == before, "预览模式不应写盘"
    assert not os.path.exists(os.path.join(root, "_backup_pre_fix"))
    assert "- type: click_first" in res.diff
    print("OK  缺省预览：不写盘、不产生备份、返回 diff")


def t_verify_detects_missing_bid():
    root = _mkroot()
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    ok, problems = yw.verify(path, {}, "sign", ACTIONS, base_dir=root)
    assert not ok and any("缺失" in p for p in problems), problems
    print("OK  verify 检出目标行为缺失")


def t_verify_detects_collateral_damage():
    root = _mkroot(extra_app="name: B\npackage: com.example.b\nbehaviors:\n  sign:\n  - type: think\n")
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    before = yw.snapshot(os.path.join(root, "config.yaml"), base_dir=root)
    assert "A" in before and "B" in before, before.keys()
    # 人为改动 B，模拟误伤
    pb = os.path.join(root, "config", "apps", "02_B.yaml")
    with open(pb, "w", encoding="utf-8") as f:
        f.write("name: B\npackage: com.example.b\nbehaviors:\n  sign:\n  - type: wait\n")
    ok, problems = yw.verify(path, before, "collect", None,
                             config_path=os.path.join(root, "config.yaml"), base_dir=root)
    assert not ok and any("误伤" in p for p in problems), problems
    print("OK  verify 检出误伤其他 App")


def t_rollback_when_verify_fails():
    root = _mkroot()
    path = os.path.join(root, "config", "apps", "01_A.yaml")
    original = open(path, "rb").read()
    real_verify = yw.verify
    yw.verify = lambda *a, **k: (False, ["模拟复验失败"])
    try:
        res = yw.insert_behavior(path, "sign", ACTIONS, apply=True, base_dir=root)
    finally:
        yw.verify = real_verify
    assert res.action == "rolled_back", res.action
    assert open(path, "rb").read() == original, "复验失败后未回滚"
    print("OK  复验失败自动回滚，文件恢复原字节")


def t_rejects_config_yaml_and_outside_paths():
    root = _mkroot()
    try:
        yw.insert_behavior(os.path.join(root, "config.yaml"), "sign", ACTIONS, base_dir=root)
    except yw.WriterError as e:
        assert "config.yaml" in str(e)
    else:
        raise AssertionError("应拒绝写 config.yaml")
    try:
        yw.insert_behavior(os.path.join(root, "elsewhere.yaml"), "sign", ACTIONS, base_dir=root)
    except yw.WriterError:
        pass
    else:
        raise AssertionError("应拒绝写 config/apps 之外的路径")
    print("OK  路径白名单生效")


def t_render_roundtrip_with_tricky_chars():
    actions = [
        {"type": "click_first",
         "candidates": [{"type": "text", "value": "连续签到：领+50%"}, {"type": "text", "value": "签到"}],
         "timeout": 8, "optional": False},
        {"type": "any_of", "optional": True,
         "choices": [[{"type": "click_point", "x": 0.5, "y": 0.641, "vision": False}]]},
    ]
    lines = yw.render_actions(actions, indent=2)
    text = "\n".join(ln[2:] if ln.startswith("  ") else ln for ln in lines)
    back = yaml.safe_load(text)
    assert back == actions, back
    assert any(ln.strip().startswith("- - type:") for ln in lines), "any_of 嵌套应为 `- - type:`"
    print("OK  渲染 round-trip 一致，全角冒号/+/% 不炸")


def t_indent4_old_single_file():
    body = ("- name: C\n  package: com.example.c\n  behaviors:\n"
            "    collect:\n    - type: think\n")
    root = tempfile.mkdtemp(prefix="yw4_")
    apps = os.path.join(root, "config", "apps")
    os.makedirs(apps)
    with open(os.path.join(root, "config.yaml"), "w", encoding="utf-8") as f:
        f.write("apps: []\napps_dir: config/apps\n")
    path = os.path.join(apps, "03_C.yaml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    res = yw.insert_behavior(path, "sign", ACTIONS, apply=True, base_dir=root)
    assert res.action == "inserted", (res.action, res.warnings)
    app = yw.load_app(path)  # 旧式 `- name:` 会加载成 list，用 load_app 归一化
    assert app["behaviors"]["sign"] == ACTIONS
    assert app["behaviors"]["collect"] == [{"type": "think"}]
    print("OK  旧单文件 ind=4 结构插入正确")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} 通过")
    sys.exit(1 if failed else 0)
