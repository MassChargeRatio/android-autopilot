# -*- coding: utf-8 -*-
"""test_selfsearch_candidates.py - 第1步：全局分类候选词表（AUTOP-SELFSEARCH-2026-10-20）

数据源 = 派单卡 P3 按钮文案族 + dispatch/AUTOP-SELFSEARCH-2026-10-20/APP_PATHS.md
12 条用户描述。要求：
  * APP_PATHS 中每个按钮文案必须被四张表之一覆盖（未覆盖即红）；
  * App 级 extra_candidates 追加/去重/保序（config/apps/*.yaml 可微调）；
  * config_loader.extra_candidates 只读读取（含别名），不破坏既有加载行为。

运行：
    python -m pytest tests/test_selfsearch_candidates.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import candidates  # noqa: E402
import config_loader  # noqa: E402

# APP_PATHS.md 12 条描述中的按钮文案（提现组暂略，但仍入表，供后续提现行为启用）
APP_WORDS = [
    # 01 趣头条
    "我的", "任务", "今日签到", "提现兑换", "立即提现",
    # 02 拼多多
    "多多视频", "提现", "签到",
    # 03 京东
    "逛", "连续签到", "去提现",
    # 04 美团
    "视频", "今日签到", "提现",
    # 05 快手
    "任务中心", "签到",
    # 06 百度地图
    "首页", "我的", "现金签到",
    # 07 海马畅听
    "我的", "领现金", "签到",
    # 08 UC浏览器极速版
    "任务", "签到领元宝",
    # 09 飞猪旅行
    "能量红包", "里程签到",
    # 10 米读小说
    "任务", "我的", "福利中心", "立即签到",
    # 11 米读极速版
    "我的", "福利", "立即签到",
    # 13 大众点评
    "签到", "得金币", "立即签到",
]


def _all_words():
    return (candidates.SIGN + candidates.TASK_CENTER + candidates.NAV_TAB
            + candidates.WITHDRAW)


def t_tables_exist_and_nonempty():
    for name in ("SIGN", "TASK_CENTER", "NAV_TAB", "WITHDRAW"):
        words = getattr(candidates, name)
        assert isinstance(words, list) and words, f"{name} 表缺失或为空"
    print("OK  四张表存在且非空")


def t_app_paths_words_covered():
    """APP_PATHS 每个按钮文案必须被四张表之一覆盖（未覆盖即红）。"""
    allw = set(_all_words())
    miss = [w for w in APP_WORDS if w not in allw]
    assert not miss, f"APP_PATHS 文案未覆盖: {miss}"
    print(f"OK  APP_PATHS 共 {len(set(APP_WORDS))} 个独立文案全部覆盖")


def t_candidates_for_returns_global_without_app():
    got = candidates.candidates_for("sign")
    assert got == candidates.SIGN, "无 app_cfg 时应原样返回全局表"
    print("OK  candidates_for 无 App 配置返回全局表")


def t_candidates_for_appends_extra_and_dedup():
    app_cfg = {"extra_candidates": {"sign": ["独家签到", "今日签到"]}}
    got = candidates.candidates_for("sign", app_cfg)
    assert "独家签到" in got, "App 特有词应追加"
    assert got.count("今日签到") == 1, "与全局重复的词不应重复出现"
    assert got.index("今日签到") == got.index(candidates.SIGN[0]), "保序：全局在前"
    print("OK  candidates_for 追加 App 特有词且去重保序")


def t_unknown_category_raises():
    try:
        candidates.candidates_for("bogus")
    except ValueError:
        return
    raise AssertionError("未知词表应抛 ValueError")


def t_loader_reads_app_extra_candidates():
    cfg = {"apps": [
        {"name": "拼多多", "extra_candidates": {"sign": ["独家签到"]}},
        {"name": "京东"},
    ]}
    assert config_loader.extra_candidates(cfg, "拼多多") == {"sign": ["独家签到"]}
    assert config_loader.extra_candidates(cfg, "京东") == {}
    assert config_loader.extra_candidates(cfg, "不存在") == {}
    # 别名命中
    cfg2 = {"apps": [{"name": "趣头条", "aliases": ["趣看天下"],
                      "extra_candidates": {"nav_tab": ["逛逛"]}}]}
    assert config_loader.extra_candidates(cfg2, "趣看天下") == {"nav_tab": ["逛逛"]}
    print("OK  config_loader.extra_candidates 只读读取（含别名）")


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
