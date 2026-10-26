# -*- coding: utf-8 -*-
"""test_config_split_parity.py - 拆分前后 apps 深比较对拍（C9 不变式）

拆分前：config.yaml.pre_split_<ts> 备份内的内联 apps；
拆分后：config_loader.load_config 拼接 config/apps/ 的结果。
要求深比较相等（数量、顺序、字段、值全一致）。

基线维护（C9 不变式的活基线）：
  * `_backup_pre_fix/config.yaml.split_baseline` 存在时以其为准；
    否则回退到最后一个 `config.yaml.pre_split_*` 历史快照。
  * 有意变更 App 配置（新增/修改 behavior）后，测试会如实报差异——
    这是设计行为（防误改），确认变更无误后刷新基线：
        python -c "import sys; sys.path.insert(0,'.'); import yaml; from config_loader import load_config; \
cfg=yaml.safe_load(open('config.yaml',encoding='utf-8').read()) or {}; \
cfg['apps']=load_config('config.yaml')['apps']; \
open('_backup_pre_fix/config.yaml.split_baseline','w',encoding='utf-8').write(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))"

运行：
    python tests/test_config_split_parity.py
"""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    import yaml
except ImportError:  # noqa: E402
    import miniyaml as yaml  # noqa: E402

from config_loader import load_config  # noqa: E402

CONFIG = os.path.join(ROOT, "config.yaml")
# 规范基线：有意变更 App 配置（加/改 behavior）后，由人刷新一次，
# 刷新方法见下方 _before_apps 注释；历史 pre_split_* 快照仅作向后兼容回退。
BASELINE = os.path.join(ROOT, "_backup_pre_fix", "config.yaml.split_baseline")
BACKUPS = sorted(glob.glob(os.path.join(ROOT, "_backup_pre_fix",
                                        "config.yaml.pre_split_*")))


def _baseline_path():
    if os.path.exists(BASELINE):
        return BASELINE
    return BACKUPS[-1] if BACKUPS else None


def _before_apps():
    path = _baseline_path()
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("apps") or []


def t_split_parity_deep_equal():
    before = _before_apps()
    if before is None:
        print("SKIP 未找到 pre_split 备份，跳过（首次拆分场景）")
        return
    after = load_config(CONFIG).get("apps") or []
    assert len(after) == len(before), \
        f"apps 数量不一致: before={len(before)} after={len(after)}"
    for i, (b, a) in enumerate(zip(before, after)):
        assert a == b, f"第 {i + 1} 个 app 不一致\nbefore={b}\nafter={a}"
    print(f"OK  拆分前后 apps 深比较相等（{len(after)} 个，顺序一致）")


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
