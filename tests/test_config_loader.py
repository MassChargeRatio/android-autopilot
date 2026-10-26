# -*- coding: utf-8 -*-
"""test_config_loader.py - config_loader 单元测试（C9）

覆盖：旧单文件原样返回 / 拆分后拼接 / 顺序保持 / money_behaviors /
app_config_path 定位 / latest_config_mtime 覆盖 apps 目录。

运行：
    python tests/test_config_loader.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import yaml
except ImportError:  # noqa: E402
    import miniyaml as yaml  # noqa: E402

from config_loader import (  # noqa: E402
    load_config, money_behaviors, app_config_path,
    safe_app_name, latest_config_mtime,
)


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def t_old_single_file_returns_as_is():
    """apps 非空 → 旧单文件原样返回（向后兼容），不碰 apps_dir。"""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "config.yaml")
        _write(p, {"device": {"serial": "x"}, "apps": [{"name": "A"}]})
        cfg = load_config(p)
        assert cfg["apps"] == [{"name": "A"}], cfg["apps"]
        assert cfg["device"]["serial"] == "x"
    print("OK  旧单文件（apps 非空）原样返回")


def t_split_dir_merged_in_order():
    """apps 空 + apps_dir → 按文件名序拼接（序号前缀保序）。"""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "config.yaml")
        ad = os.path.join(td, "apps")
        _write(os.path.join(ad, "01_B.yaml"), {"name": "B"})
        _write(os.path.join(ad, "02_A.yaml"), {"name": "A"})
        _write(p, {"apps_dir": "apps", "apps": []})
        cfg = load_config(p)
        assert [a["name"] for a in cfg["apps"]] == ["B", "A"], cfg["apps"]
        assert cfg["apps_dir"] == "apps"  # 顶层透传
    print("OK  拆分后按文件名序拼接（保序）")


def t_money_behaviors_default_and_custom():
    assert money_behaviors({}) == {"withdraw"}
    assert money_behaviors({"money_behaviors": ["withdraw", "cash"]}) == \
        {"withdraw", "cash"}
    print("OK  money_behaviors 缺省/自定义")


def t_app_config_path_resolves_prefixed_file():
    """app_config_path 在带序号前缀的文件名里按 safe_name 定位。"""
    with tempfile.TemporaryDirectory() as td:
        ad = os.path.join(td, "apps")
        os.makedirs(ad)
        with open(os.path.join(ad, "03_趣头条.yaml"), "w", encoding="utf-8") as f:
            f.write("name: 趣头条\n")
        got = app_config_path("趣头条", {"apps_dir": ad}, td)
        assert os.path.basename(got) == "03_趣头条.yaml", got
    print("OK  app_config_path 定位带序号前缀的 App 文件")


def t_safe_app_name_strips_bad_chars():
    assert safe_app_name("抖音极速版") == "抖音极速版"
    assert safe_app_name("A/B:C") == "A_B_C"
    assert safe_app_name("") == "app"
    print("OK  safe_app_name 清洗")


def t_latest_config_mtime_covers_apps_dir():
    """拆分后主文件 mtime 变化不再等于缓存键——必须覆盖 apps 目录。"""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "config.yaml")
        ad = os.path.join(td, "apps")
        _write(os.path.join(ad, "01_A.yaml"), {"name": "A"})
        _write(p, {"apps_dir": "apps", "apps": []})
        m0 = latest_config_mtime(p)
        assert m0 >= os.path.getmtime(os.path.join(ad, "01_A.yaml"))
        # 只动 apps 文件，缓存键也应变化
        os.utime(os.path.join(ad, "01_A.yaml"), (m0 + 100, m0 + 100))
        m1 = latest_config_mtime(p)
        assert m1 > m0, "apps 目录文件变更应推高 latest_config_mtime"
    print("OK  latest_config_mtime 覆盖 apps 目录")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("t_")]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} 通过")
    sys.exit(1 if failed else 0)
