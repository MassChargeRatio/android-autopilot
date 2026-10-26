# -*- coding: utf-8 -*-
"""config_loader.py - 配置加载与拆分后路径解析（C9）

背景：
    拆分前 config.yaml 内联全部 apps（非空）——旧单文件原样返回（向后兼容）；
    拆分后主文件 apps: [] + apps_dir 指向 config/apps/ ——逐个 App 文件拼接回 apps。

对外：
    load_config(path)       主入口；apps 非空→原样，否则拼接 apps_dir。
    money_behaviors(cfg)    资金类行为集合；配置缺省 {"withdraw"}。
    app_config_path(name)   写回工具定位 App 级文件用。
    safe_app_name(name)     App 名 → 安全文件名（split_config 与 app_config_path 共用）。
    latest_config_mtime(path)  主文件 + apps 目录最大值（webui 缓存失效用）。
"""
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_APPS_DIR = os.path.join(BASE_DIR, "config", "apps")


def safe_app_name(name):
    """App 名转安全文件名：非字母/数字/下划线/中文字符/连字符 → 下划线。"""
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", str(name).strip())
    return s or "app"


def _apps_dir(cfg, base_dir=None):
    d = cfg.get("apps_dir") or DEFAULT_APPS_DIR
    if base_dir and not os.path.isabs(d):
        d = os.path.join(base_dir, d)
    return d


def _load_yaml(path):
    try:
        import yaml
    except ImportError:  # 无 PyYAML 时用内置零依赖解析器兜底
        import miniyaml as yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(path):
    """加载主配置；apps 段非空 → 旧单文件原样返回；否则拼接 apps_dir。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"配置文件不存在: {path}")
    cfg = _load_yaml(path)
    if cfg.get("apps"):
        return cfg
    apps_dir = _apps_dir(cfg, os.path.dirname(os.path.abspath(path)))
    merged = dict(cfg)
    merged_apps = []
    if os.path.isdir(apps_dir):
        for fn in sorted(os.listdir(apps_dir)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            app = _load_yaml(os.path.join(apps_dir, fn))
            if app:
                merged_apps.append(app)
    merged["apps"] = merged_apps
    return merged


def money_behaviors(cfg):
    """资金类行为集合；配置里给了就用，缺省 {"withdraw"}。"""
    mb = cfg.get("money_behaviors")
    if isinstance(mb, (list, tuple, set)) and mb:
        return set(mb)
    return {"withdraw"}


def extra_candidates(cfg, app_name):
    """读取 App 级 extra_candidates（词表微调，AUTOP-SELFSEARCH-2026-10-20 第1步）。

    在合并态 cfg 中按 name（或别名）定位 App，返回其 extra_candidates dict；
    未配置返回 {}。只读，不改动任何既有加载行为。
    """
    for app in (cfg.get("apps") or []):
        if app.get("name") == app_name or app_name in (app.get("aliases") or []):
            return app.get("extra_candidates") or {}
    return {}


def app_config_path(app_name, cfg=None, base_dir=None):
    """写回工具解析 App 级配置文件路径。

    拆分文件名为 `<序号>_<safe_name>.yaml`：先在 apps_dir 里按 safe_name
    扫描精确匹配；找不到时回退到拼接路径（兼容未拆分的旧文件名）。
    """
    apps_dir = _apps_dir(cfg or {}, base_dir or BASE_DIR)
    safe = safe_app_name(app_name)
    if os.path.isdir(apps_dir):
        for fn in sorted(os.listdir(apps_dir)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            base = fn[:-5]
            if base == safe or base.split("_", 1)[-1] == safe:
                return os.path.join(apps_dir, fn)
    return os.path.join(apps_dir, safe + ".yaml")


def latest_config_mtime(path):
    """主文件 + apps 目录下所有 App 文件的最大 mtime（webui 缓存失效用）。"""
    mtimes = []
    if os.path.exists(path):
        mtimes.append(os.path.getmtime(path))
    try:
        cfg = _load_yaml(path) if os.path.exists(path) else {}
        apps_dir = _apps_dir(cfg, os.path.dirname(os.path.abspath(path)))
        if os.path.isdir(apps_dir):
            for fn in os.listdir(apps_dir):
                fp = os.path.join(apps_dir, fn)
                if os.path.isfile(fp):
                    mtimes.append(os.path.getmtime(fp))
    except Exception:
        # 主文件解析失败时至少回退到文件自身 mtime，不让缓存失效吞掉错误
        pass
    return max(mtimes) if mtimes else 0
