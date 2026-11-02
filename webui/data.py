# -*- coding: utf-8 -*-
"""webui.data - 控制台的数据访问层

职责单一：把「工程自身的数据源」读成前端能直接用的结构。
  * config.yaml      -> App / 行为 / 锚点摘要、配置体检
  * data/records.db  -> 收益汇总与明细、操作事件
  * devtools/adbkit  -> 设备在线状态、分辨率、前台 App、实时截图

设计约束：
  * **不重复实现业务逻辑**。设备访问走 `devtools/adbkit.resolve_adb/Adb`，
    记账口径与 `recorder.py` 的 `earnings(ts,app,action,amount,unit,detail)`
    表结构保持一致。
  * 纯计算部分（锚点摘要、配置体检、收益聚合）写成**无 IO 的纯函数**，
    便于单测；带 IO 的部分单独一层。
"""
import json
import os
import re
import sqlite3
import sys
import threading
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_YAML = os.path.join(BASE_DIR, "config.yaml")
DB_PATH = os.path.join(BASE_DIR, "data", "records.db")
DEVTOOLS = os.path.join(BASE_DIR, "devtools")

if DEVTOOLS not in sys.path:
    sys.path.insert(0, DEVTOOLS)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config_loader import load_config as _load_config_merged  # noqa: E402
from config_loader import latest_config_mtime as _latest_config_mtime  # noqa: E402
from config_loader import money_behaviors as _money_behaviors  # noqa: E402

# 行为 key -> 自然语言触发词。与 main.py/nlu.py 的意图表保持一致，
# 保证 GUI 勾选行为后拼出的 --task 能被 nlu.parse_intents 正确解析。
KEY_TO_TRIGGER = {
    "sign": "签到",
    "reserve": "预约打卡",
    "watch": "看视频",
    "withdraw": "提现",
    "bonus": "领金币",
    "collect": "收集",
    "growth": "做任务",
}

# 资金类行为：执行前必须由用户显式确认（项目硬约束 —— 提现/支付/转账
# 不得自动执行，必须先说明影响面并取得授权）。
# C9 起来源统一收敛到 config_loader.money_behaviors（配置可覆盖），
# 此处保留兼容别名供 server.py 等旧引用使用。
MONEY_BEHAVIORS = {"withdraw"}

# 锚点动作类型：带「可校验的定位依据」的动作。这是判断一个行为能否被
# verify_live.py 校验的依据。
ANCHOR_TYPES = ("click_text", "click_id", "click_desc", "click_first")

# click_point 是**重载**类型，必须按载荷区分用途（本工程实测分布 68 / 31 / 0）：
#   * 带 images             —— OpenCV 模板匹配锚点（一等定位手段，**算锚点**）
#   * 带「最右侧」vlm_prompt —— 「导航到我的」前置步（比例坐标兜底，不算锚点）
#   * 两者皆无              —— 纯比例坐标兜底（不算锚点，且脆弱，体检时告警）
# 踩过的坑：最初只把 click_text/id/desc/click_first 当锚点，于是把 30 个
# 图像锚点行为误报成「没有可校验的锚点动作」，总览页红字一片假警报。
POINT_TYPE = "click_point"
NAV_MARK = "最右侧"


def is_nav_prelude(action):
    """是不是「导航到我的」前置步（比例坐标兜底，非锚点）。"""
    return (isinstance(action, dict)
            and action.get("type") == POINT_TYPE
            and NAV_MARK in str(action.get("vlm_prompt", "")))


def is_anchor(action):
    """是不是「可校验的锚点」动作。"""
    if not isinstance(action, dict):
        return False
    t = action.get("type")
    if t in ANCHOR_TYPES:
        return True
    if t == POINT_TYPE:
        # 只有配了参考图才算锚点；比例坐标兜底不算。
        return bool(action.get("images"))
    return False


def anchor_via(action):
    """锚点的定位依据，用于前端展示与体检文案。"""
    t = (action or {}).get("type")
    if t == POINT_TYPE:
        return "图像"
    if t == "click_id":
        return "rid"
    if t == "click_first":
        return "候选"
    return "文案"


def _anchor_of(action):
    """把一个锚点动作压成前端要展示的结构。

    `key` = 该锚点真正用来定位的依据，按类型取不同字段 —— 体检要看的是
    「这个锚点到底靠什么找元素」，只盯 text/candidates 会把
    click_id（靠 res_id）和图像锚点（靠参考图）误报成没配置。
    """
    t = action.get("type")
    imgs = action.get("images") or []
    imgs = imgs if isinstance(imgs, list) else []
    cands = [c.get("value") for c in (action.get("candidates") or [])
             if isinstance(c, dict)][:8]
    if t == "click_id":
        key = action.get("res_id") or ""
    elif t == POINT_TYPE:
        key = imgs[0] if imgs else ""
    elif t == "click_first":
        key = cands[0] if cands else (action.get("candidates_from") or "")
    else:
        key = action.get("text") or action.get("desc") or ""
    return {
        "type": t,
        "via": anchor_via(action),
        "key": key,
        "text": action.get("text") or action.get("desc") or "",
        "candidates": cands,
        "images": len(imgs),
    }


def _variant_of(actions):
    """行为可能是 [[..],[..]] 多候选模板，取第一组作为主视图。"""
    if not actions:
        return []
    if all(isinstance(a, list) for a in actions):
        return actions[0] or []
    return actions


def _paths_of(acts):
    """把行为展开成若干条**完整路径**。

    `any_of` 的语义是「按顺序试多组动作，第一组全部成功即停」，它**前后**的
    动作对每条分支都生效，必须拼进每条路径 —— 否则会漏算
    「any_of 之后还有一个锚点」的情况（实测 `一淘.sign` 正是这种：
    `[any_of{[[签到],[我的,think,签到]]}, think, 签到]`，
    展开后第二条路径是 `[我的,think,签到,think,签到]`，才是真正的三级导航）。
    """
    paths = [[]]
    for a in acts:
        if isinstance(a, dict) and a.get("type") == "any_of":
            choices = [ch if isinstance(ch, list) else [ch]
                       for ch in (a.get("choices") or [])]
            expanded = [p + ch for p in paths for ch in choices]
            paths = expanded or paths
        else:
            for p in paths:
                p.append(a)
    return [p for p in paths if p]


def _all_actions(acts):
    """展开后所有路径上的动作（用于全量体检，不重不漏）。"""
    out = []
    for p in _paths_of(acts):
        out.extend(p)
    return out


# verify_live.py 的锚点口径已与 is_anchor() 对齐（含 click_point 图像锚点），
# 见 devtools/verify_live.py 的 is_anchor_action。图像锚点行为现在会被
# stability_run 计入命中率分母，不再算「未度量」。
# ⚠️ 改 verify_live.py 的锚点判断时，这里必须同步，否则覆盖率会显示错。
# VERIFIER_ANCHOR_TYPES 已删除 —— verifier_can_check 直接复用 is_anchor，
# 避免两套口径再次漂移。


def verifier_can_check(actions):
    """该行为能否被**实机验证器**校验到（口径对齐 verify_live.py，图像锚点也算）。"""
    return any(is_anchor(a) or (isinstance(a, dict) and a.get("type") == "any_of")
               for a in _variant_of(actions))


def summarize_behavior(actions):
    """把一个行为的动作列表压成前端要展示的摘要。

    返回 {anchors, levels, has_prelude, branches, vias, optional_all}：
      * anchors     —— 去重后的锚点动作（跨 any_of 各分支合并）
      * levels      —— 最长路径的可达层数（1=首屏可达，2=需导航，3=需二级入口）
      * has_prelude —— 是否带「导航到我的」前置步
      * branches    —— 候选路径条数（>1 表示有多路径覆盖）
      * vias        —— 去重后的定位依据（文案/图像/rid/候选）
    """
    acts = _variant_of(actions)
    paths = _paths_of(acts)

    anchors, seen = [], set()
    has_prelude = False
    levels = 0
    for p in paths:
        prelude = any(is_nav_prelude(a) for a in p)
        has_prelude = has_prelude or prelude
        n = 0
        for a in p:
            if not is_anchor(a):
                continue
            n += 1
            an = _anchor_of(a)
            sig = (an["type"], an["key"])
            if sig not in seen:
                seen.add(sig)
                anchors.append(an)
        if n:
            # 1=首屏可达；+1=需先导航到「我的」；再+1=还需穿透一层二级入口。
            levels = max(levels, 1 + (1 if prelude else 0) + (1 if n > 1 else 0))

    branches = len(paths) if len(paths) > 1 else (1 if anchors else 0)
    vias = []
    for an in anchors:
        if an["via"] not in vias:
            vias.append(an["via"])
    return {
        "anchors": anchors,
        "levels": levels,
        "has_prelude": has_prelude,
        "branches": branches,
        "vias": vias,
        "optional_all": all(isinstance(a, dict) and a.get("optional")
                            for a in acts if isinstance(a, dict)) and bool(acts),
    }


def validate_config(cfg):
    """配置体检：返回问题列表 [{level, app, msg}]。纯函数。"""
    issues = []
    apps = (cfg or {}).get("apps") or []
    seen = {}
    for i, a in enumerate(apps):
        name = (a.get("name") or "").strip()
        pkg = (a.get("package") or "").strip()
        if not name:
            issues.append({"level": "ERROR", "app": f"#{i + 1}",
                           "msg": "缺少 name"})
            continue
        if not pkg:
            issues.append({"level": "ERROR", "app": name, "msg": "缺少 package"})
        if name in seen:
            issues.append({"level": "ERROR", "app": name,
                           "msg": f"App 名重复（第 {seen[name] + 1} 与第 {i + 1} 项）"})
        seen.setdefault(name, i)
        beh = a.get("behaviors") or {}
        if not beh:
            issues.append({"level": "WARN", "app": name, "msg": "未配置任何行为"})
        for bid, actions in beh.items():
            s = summarize_behavior(actions)
            if not s["anchors"]:
                issues.append({"level": "ERROR", "app": name,
                               "msg": f"行为 {bid} 没有可校验的锚点动作"
                                      "（文案/rid/图像都没有）"})
            for an in s["anchors"]:
                if not an["key"]:
                    issues.append({"level": "WARN", "app": name,
                                   "msg": f"行为 {bid} 的 {an['via']} 锚点"
                                          "未配置定位依据"})
            # 纯比例坐标兜底：能跑但很脆（换机型/改版即失效），值得提醒。
            # 要展开 any_of 分支后再扫，否则分支里的兜底点会被漏掉。
            for a in _all_actions(actions):
                if (isinstance(a, dict) and a.get("type") == POINT_TYPE
                        and not a.get("images") and not is_nav_prelude(a)):
                    issues.append({"level": "WARN", "app": name,
                                   "msg": f"行为 {bid} 用纯比例坐标兜底（无参考图）"})
    return issues


def aggregate_earnings(rows, today=None):
    """按单位聚合收益明细。

    rows: [(ts, app, action, amount, unit, detail)]
    返回 {summary:[{unit,total,count}], by_app:[{app,unit,total,count}], total_rows}
    """
    today = today or datetime.now().strftime("%Y-%m-%d")
    by_unit, by_app = {}, {}
    for ts, app, action, amount, unit, _detail in rows:
        unit = unit or ""
        try:
            amt = float(amount or 0)
        except (TypeError, ValueError):
            amt = 0.0
        u = by_unit.setdefault(unit, {"unit": unit, "total": 0.0, "count": 0,
                                      "today": 0.0})
        u["total"] += amt
        u["count"] += 1
        if str(ts).startswith(today):
            u["today"] += amt
        k = (app or "-", unit)
        g = by_app.setdefault(k, {"app": app or "-", "unit": unit,
                                  "total": 0.0, "count": 0})
        g["total"] += amt
        g["count"] += 1
    return {
        "summary": sorted(by_unit.values(), key=lambda x: -x["total"]),
        "by_app": sorted(by_app.values(), key=lambda x: -x["total"]),
        "total_rows": len(rows),
    }


def daily_series(rows, days=7, today=None):
    """近 N 日按天聚合（用于趋势图）。返回 [{date,total,count}]，按日期升序。"""
    today_d = datetime.strptime(today, "%Y-%m-%d") if today else datetime.now()
    buckets = {}
    for i in range(days - 1, -1, -1):
        d = (today_d - timedelta(days=i)).strftime("%Y-%m-%d")
        buckets[d] = {"date": d, "total": 0.0, "count": 0}
    for ts, _app, _action, amount, _unit, _d in rows:
        d = str(ts)[:10]
        if d in buckets:
            try:
                buckets[d]["total"] += float(amount or 0)
            except (TypeError, ValueError):
                pass
            buckets[d]["count"] += 1
    return list(buckets.values())


def parse_foreground(dumpsys_window_output):
    """从 `dumpsys window` 输出里取前台 Activity 与包名。纯函数。

    踩坑：`d.info.currentPackageName` 在崩溃/切换时序下会先报新包名，
    而屏幕还是旧 App。这里用 dumpsys 的 mCurrentFocus 作为交叉参考。
    """
    m = re.search(r"mCurrentFocus=Window\{[^}]*?\s([\w.]+)/([\w.$]+)\}", dumpsys_window_output or "")
    if m:
        return {"package": m.group(1), "activity": m.group(2)}
    m = re.search(r"mFocusedApp=.*?\s([\w.]+)/([\w.$]+)", dumpsys_window_output or "")
    if m:
        return {"package": m.group(1), "activity": m.group(2)}
    return {"package": "", "activity": ""}


def parse_wm_size(out):
    """解析 `wm size` 输出 -> (w, h) 或 (None, None)。纯函数。"""
    m = re.search(r"Override size:\s*(\d+)x(\d+)", out or "")
    if not m:
        m = re.search(r"Physical size:\s*(\d+)x(\d+)", out or "")
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def behavior_task_text(behaviors):
    """把行为 key 列表拼成 main.py --task 能解析的自然语言。纯函数。"""
    parts = [KEY_TO_TRIGGER.get(b, b) for b in (behaviors or [])]
    return "，然后".join(parts) or "签到"


# ===========================================================================
# IO 层
# ===========================================================================
def load_yaml(path):
    try:
        import yaml
    except ImportError:  # 与 main.py 一致：无 PyYAML 时用内置解析器
        sys.path.insert(0, BASE_DIR)
        import miniyaml as yaml
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Store:
    """配置 + 数据库的只读访问（带轻量缓存）。线程安全。"""

    def __init__(self, config_path=CONFIG_YAML, db_path=DB_PATH):
        self.config_path = config_path
        self.db_path = db_path
        self._lock = threading.Lock()
        self._cfg = None
        self._cfg_mtime = None
        self._stab = None
        self._stab_mtime = None

    # ---------- 配置 ----------
    def config(self, reload=False):
        with self._lock:
            try:
                mtime = _latest_config_mtime(self.config_path)
            except OSError:
                mtime = None
            if reload or self._cfg is None or mtime != self._cfg_mtime:
                self._cfg = _load_config_merged(self.config_path)
                self._cfg_mtime = mtime
            return self._cfg

    def apps(self):
        # 2026-10-29 性能修正：config() / _money_behaviors() 原先写在两层循环**里面**，
        # 34 个 App × 平均 3 条 behavior 会调用 config() 近百次。config() 带 mtime 缓存，
        # 命中时很便宜，但一旦缓存未命中（每次冷启动、或配置目录 mtime 抖动）就是
        # 「解析 34 份 YAML」× 99 次 —— 实测包内环境单次 /api/overview 45s，
        # 超过前端 20s 超时，4 个 webui HTTP 用例直接 TimeoutError。
        # 把不随循环变化的量提到循环外，单次耗时从 45s 降到 2s 量级。
        cfg = self.config()
        money = _money_behaviors(cfg)
        out = []
        for i, a in enumerate((cfg.get("apps") or [])):
            beh = a.get("behaviors") or {}
            behaviors = []
            for bid, actions in beh.items():
                s = summarize_behavior(actions)
                behaviors.append({
                    "id": bid,
                    "trigger": KEY_TO_TRIGGER.get(bid, bid),
                    "money": bid in money,
                    "levels": s["levels"],
                    "branches": s["branches"],
                    "has_prelude": s["has_prelude"],
                    "vias": s["vias"],
                    "anchors": s["anchors"],
                })
            out.append({
                "index": i,
                "name": a.get("name") or f"app{i}",
                "package": a.get("package") or "",
                "aliases": list(a.get("aliases") or []),
                "behaviors": behaviors,
            })
        return out

    def device_cfg(self):
        return self.config().get("device") or {}

    def verify_coverage(self):
        """实机验证器的**行为覆盖率**。

        verify_live.py 遇到它认不出的锚点类型会记「无锚点动作」并跳过，
        而 stability_run.py 把该状态当作废、**不计入命中率分母** ——
        所以命中率不会被稀释，但那批行为是**完全没被度量**的。
        这个数字必须让人看得见，否则容易把「70% 命中率」误读成「覆盖了七成」。
        """
        total = checked = 0
        image_only = 0
        for a in self.config().get("apps") or []:
            for _bid, actions in (a.get("behaviors") or {}).items():
                total += 1
                if verifier_can_check(actions):
                    checked += 1
                elif summarize_behavior(actions)["vias"] == ["图像"]:
                    image_only += 1
        return {"total": total, "verifiable": checked,
                "unverifiable": total - checked, "image_only": image_only}

    def overview(self):
        cfg = self.config()
        apps = self.apps()
        return {
            "device": self.device_cfg(),
            "app_count": len(apps),
            "behavior_count": sum(len(a["behaviors"]) for a in apps),
            "money_behavior_count": sum(1 for a in apps for b in a["behaviors"]
                                        if b["money"]),
            "apps": apps,
            "issues": validate_config(cfg),
            "verify_coverage": self.verify_coverage(),
            "human": cfg.get("human") or {},
            "vision_enabled": bool((cfg.get("vision") or {}).get("enabled")),
            "captcha_enabled": bool((cfg.get("captcha") or {}).get("enabled")),
        }

    # ---------- 数据库 ----------
    def _connect(self):
        if not os.path.exists(self.db_path):
            return None
        # 只读打开：控制台不写库，避免与运行中的执行器抢锁
        uri = "file:%s?mode=ro" % self.db_path.replace("?", "%3f").replace("#", "%23")
        conn = sqlite3.connect(uri, uri=True, timeout=3.0)
        conn.row_factory = sqlite3.Row
        return conn

    def earnings(self, days=None, app=None, limit=2000):
        conn = self._connect()
        if conn is None:
            return {"summary": [], "by_app": [], "total_rows": 0,
                    "series": [], "rows": []}
        try:
            where, params = [], []
            if days:
                since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
                where.append("ts >= ?")
                params.append(since)
            if app:
                where.append("app = ?")
                params.append(app)
            sql = "SELECT ts, app, action, amount, unit, detail FROM earnings"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY ts DESC LIMIT ?"
            params.append(int(limit))
            rows = [tuple(r) for r in conn.execute(sql, params).fetchall()]
            agg = aggregate_earnings(rows)
            agg["series"] = daily_series(rows, days=min(days or 7, 30))
            agg["rows"] = [dict(zip(("ts", "app", "action", "amount", "unit",
                                     "detail"), r)) for r in rows[:limit]]
            return agg
        finally:
            conn.close()

    def ops(self, limit=50, level=None):
        conn = self._connect()
        if conn is None:
            return []
        try:
            sql = "SELECT ts, app, event, level FROM ops"
            params = []
            if level:
                sql += " WHERE level = ?"
                params.append(level)
            sql += " ORDER BY id DESC LIMIT ?"
            params.append(int(limit))
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def ops_stats(self):
        conn = self._connect()
        if conn is None:
            return {"total": 0, "by_level": {}, "last_ts": ""}
        try:
            total = conn.execute("SELECT COUNT(*) FROM ops").fetchone()[0]
            by_level = {r[0] or "INFO": r[1] for r in conn.execute(
                "SELECT level, COUNT(*) FROM ops GROUP BY level")}
            last = conn.execute("SELECT MAX(ts) FROM ops").fetchone()[0] or ""
            return {"total": total, "by_level": by_level, "last_ts": last}
        finally:
            conn.close()

    # ---------- 校准 / 稳定性 ----------
    def stability(self):
        """读 `devtools/calib/STABILITY*.json`，供「校准」页展示。

        这是本工程最核心的度量产物（多轮命中率、稳定/波动/从未命中三分类、
        改动的版本对比链），此前只能手工打开 markdown 看。控制台能**运行**
        stability_run，却看不到它的结果 —— 这个接口补上那一半。
        """
        with self._lock:
            try:
                mtime = os.path.getmtime(STABILITY_JSON)
            except OSError:
                return {"available": False,
                        "hint": "尚无稳定性报告 —— 到「诊断工具」页跑一次"
                                "「多轮稳定性统计」，完成后回到本页刷新"}
            if self._stab is None or mtime != self._stab_mtime:
                try:
                    self._stab = load_stability(STABILITY_JSON)
                except Exception as e:  # noqa: BLE001
                    return {"available": False,
                            "hint": f"报告解析失败（{type(e).__name__}: {e}）"}
                self._stab_mtime = mtime
            out = dict(self._stab)
        # 覆盖率口径与 verify_live.py 对齐（见 verify_coverage 的注释）。
        # 放在锁外：verify_coverage -> config() 也要拿同一把锁。
        out["verify_coverage"] = self.verify_coverage()
        return out


# ===========================================================================
# 校准 / 稳定性报告
# ===========================================================================
CALIB_DIR = os.path.join(DEVTOOLS, "calib")
STABILITY_JSON = os.path.join(CALIB_DIR, "STABILITY.json")

# 版本对比链的顺序**不能靠文件名排序**：`STABILITY.json` 是当前版，
# `STABILITY_pre_*.json` 是改动前的备份。名字排序恰好把 `STABILITY` 排在
# 最后，但一旦再新增备份就会错位。这里显式声明已知阶段，未知备份按名追加。
STAGE_ORDER = ["STABILITY_pre_fix", "STABILITY_pre_reset", "STABILITY"]
STAGE_LABELS = {
    "STABILITY_pre_fix": "修「中间入口当命中」之前",
    "STABILITY_pre_reset": "修完中间入口 · 未加行为间复位",
    "STABILITY": "当前",
}


def _stage_key(stem):
    try:
        return (0, STAGE_ORDER.index(stem))
    except ValueError:
        return (1, stem)


def _kind_of(valid, hits):
    """逐行为三分类。与 stability_run.classify 同义，只是这里要逐行徽章。"""
    if not valid:
        return "未度量"
    if hits == valid:
        return "稳定"
    if hits == 0:
        return "从未命中"
    return "波动"


def load_stability(path):
    """把一份 STABILITY*.json 归一化成前端直接可用的结构。

    **命中/作废判定直接复用 devtools/stability_run**，不在这里另写一份 ——
    口径一旦分叉，界面上的命中率就会与命令行输出、与 ROUND3_FINDINGS.md
    对不上，而两边单测都还是绿的（这正是本项目踩过的「静默不一致」）。
    """
    import stability_run as SR  # devtools 已在 sys.path（见文件头）

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    rows = raw.get("per_behavior") or []
    behaviors = []
    for x in rows:
        valid = int(x.get("valid") or 0)
        hits = int(x.get("hits") or 0)
        behaviors.append({
            "app": x.get("app") or "",
            "behavior": x.get("behavior") or "",
            "statuses": list(x.get("statuses") or []),
            "valid": valid,
            "void": int(x.get("void") or 0),
            "hits": hits,
            "rate": (hits / valid) if valid else None,
            "kind": _kind_of(valid, hits),
        })

    stable, flaky, never = SR.classify(rows)
    tot = raw.get("total") or {}
    valid = int(tot.get("valid") or 0)
    hits = int(tot.get("hits") or 0)
    return {
        "available": True,
        "path": path,
        "mtime": os.path.getmtime(path),
        "rounds": int(raw.get("rounds") or 0),
        "total": {
            "hits": hits, "valid": valid,
            "void": int(tot.get("void") or 0),
            "rate": (hits / valid) if valid else None,
        },
        "counts": {
            "stable": len(stable), "flaky": len(flaky), "never": len(never),
            "unmeasured": sum(1 for b in behaviors if not b["valid"]),
            "behaviors": len(behaviors),
        },
        "behaviors": behaviors,
    }


def stability_chain():
    """列出 `calib/STABILITY*.json` 备份链，供「版本对比」用。

    每次现算（几个十几 KB 的 JSON），不缓存：用户刚跑完 stability_run
    就会来点刷新，缓存反而会显示旧结果。
    """
    try:
        names = sorted(os.listdir(CALIB_DIR))
    except OSError:
        return []
    stems = []
    for n in names:
        if n.startswith("STABILITY") and n.endswith(".json"):
            stems.append(n[:-5])
    stems.sort(key=_stage_key)

    chain = []
    for stem in stems:
        path = os.path.join(CALIB_DIR, stem + ".json")
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:  # noqa: BLE001 - 坏文件不该让整页挂掉
            continue
        tot = raw.get("total") or {}
        valid = int(tot.get("valid") or 0)
        hits = int(tot.get("hits") or 0)
        chain.append({
            "stage": stem,
            "label": STAGE_LABELS.get(stem, stem),
            "current": stem == "STABILITY",
            "mtime": os.path.getmtime(path),
            "rounds": int(raw.get("rounds") or 0),
            "hits": hits, "valid": valid,
            "rate": (hits / valid) if valid else None,
            "stable": int(raw.get("stable_hit") or 0),
            "flaky": int(raw.get("flaky") or 0),
            "never": int(raw.get("never") or 0),
        })
    return chain


# ===========================================================================
# 设备
# ===========================================================================
def _adbkit():
    import adbkit
    return adbkit


def adb_path():
    try:
        return _adbkit().resolve_adb()
    except Exception as e:  # noqa: BLE001
        return f"(未找到 adb: {type(e).__name__}: {e})"


def device_status(serial=None, deep=True):
    """设备状态。deep=True 时额外取型号/分辨率/前台 App（稍慢）。"""
    k = _adbkit()
    info = {
        "adb_path": adb_path(),
        "serial": serial or "",
        "online": False,
        "model": "", "size": "", "foreground": "",
        "error": "",
    }
    try:
        adb = k.Adb(serial)
        info["serial"] = adb.serial or ""
        addr = adb.ensure(retries=2)
        info["serial"] = addr or info["serial"]
        info["online"] = True
    except Exception as e:  # noqa: BLE001
        info["error"] = f"{type(e).__name__}: {e}"
        return info
    if not deep:
        return info
    try:
        info["model"] = adb.shell("getprop ro.product.model", timeout=15).strip()
    except Exception:
        pass
    try:
        w, h = parse_wm_size(adb.shell("wm size", timeout=15))
        info["size"] = f"{w}x{h}" if w else ""
    except Exception:
        pass
    try:
        fg = parse_foreground(adb.shell("dumpsys window", timeout=30))
        info["foreground"] = fg["package"]
        info["foreground_activity"] = fg["activity"]
    except Exception:
        pass
    return info


def screenshot_png(serial=None, timeout=40):
    """实时截图，返回 PNG bytes（失败抛异常）。"""
    k = _adbkit()
    adb = k.Adb(serial)
    adb.ensure(retries=2)
    p = adb.run(["exec-out", "screencap", "-p"], timeout=timeout, binary=True)
    data = p.stdout or b""
    if not data.startswith(b"\x89PNG"):
        raise RuntimeError("截图失败（未返回 PNG）: "
                           + (p.stderr or b"").decode("utf-8", "replace")[:200])
    return data
