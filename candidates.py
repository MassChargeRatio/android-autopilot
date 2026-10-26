# -*- coding: utf-8 -*-
"""candidates.py - 全局分类候选词表（AUTOP-SELFSEARCH-2026-10-20 第1步）

用户原话：「应该总结这些app的领现金过程中，按钮名称、按钮位置、常用步骤的
共性，使程序自己有一套思路，不用依赖外部描述而能自己搜寻。」

数据源：
  * 派单卡 P3 按钮文案族（签到族 / 任务容器族 / tab 族 / 提现族）；
  * dispatch/AUTOP-SELFSEARCH-2026-10-20/APP_PATHS.md 12 条用户人工勘察描述
    （词表覆盖度测试 fixture，未覆盖即红）。

机制：
  * 全局四张表 + App 级微调（config/apps/*.yaml 的 `extra_candidates` 段，
    经 config_loader.extra_candidates 读取，**追加**语义、去重保序）；
  * `candidates_for(category, app_cfg)` 返回合并后的候选词列表；
  * 引擎 click_first 用 `candidates_from: <category>` 触发自搜寻
    （见第2步：候选池 = 显式 candidates + 全局词表按序追加）。

为何独立成模块而不是并入 knowledge.py：元素知识库（knowledge.py）管的是
"某个 App 某 selector 的历史命中/失败经验回写"，数据是执行期动态积累的；
而这里是"领现金路径按钮文案的静态共性词表"，数据来自用户勘察 + 派单卡 P3，
两类数据的来源、生命周期、回写方式都不同，拆开避免 knowledge 语义被稀释。
"""
# 签到族（P3 签到族 + APP_PATHS 各 App 签到入口文案）
SIGN = [
    "今日签到", "立即签到", "签到", "签到领元宝", "签到领金币",
    "连续签到", "得金币", "直接领取", "去签到",
    # APP_PATHS 补全：百度地图「现金签到」、飞猪「里程签到」、通用「立即领取/领取」
    "现金签到", "里程签到", "立即领取", "领取",
]

# 任务容器族（P3 任务容器族 + 飞猪「能量红包」签到入口）
TASK_CENTER = [
    "任务", "任务中心", "福利", "福利中心", "领现金", "钱包", "赚金币",
    "能量红包",
]

# tab 族（P3 tab 族 + APP_PATHS：百度地图/大众点评「首页」tab）
NAV_TAB = [
    "我的", "任务", "福利", "逛", "视频", "多多视频", "领现金",
    "首页",
]

# 提现族（P3；本期只建表不配行为，供后续提现组启用时使用）
WITHDRAW = [
    "提现", "提现兑换", "去提现", "立即提现",
]

_TABLES = {
    "sign": SIGN,
    "task_center": TASK_CENTER,
    "nav_tab": NAV_TAB,
    "withdraw": WITHDRAW,
}
CATEGORIES = tuple(_TABLES.keys())


def candidates_for(category, app_cfg=None):
    """返回 category 的候选词：全局表 + 跨 App 归纳词 + App 级 extra_candidates（去重保序）。

    category : sign / task_center / nav_tab / withdraw
    app_cfg  : App 配置 dict（可含 extra_candidates 段）或 None。

    顺序即优先级：全局表（人工勘察） > 跨 App 归纳（自动） > App 专属追加。
    """
    if category not in _TABLES:
        raise ValueError(f"未知候选词表: {category}（可选 {CATEGORIES}）")
    merged = list(_TABLES[category])
    for w in mine_words().get(category, []):
        if w not in merged:
            merged.append(w)
    extras = ((app_cfg or {}).get("extra_candidates") or {}).get(category) or []
    for w in extras:
        if w not in merged:
            merged.append(w)
    return merged


# ---------- 第 3 项：跨 App 共性归纳（AUTOP-NL-2026-10-22） ----------
# 目标：候选词在「所有 App」层面归纳，App 配置里不必重复写
#     candidates: [连续签到, 今日签到, 签到]
# 只要写了 click_first，执行器就自动并入 全局表 + 跨 App 归纳词 + App extra。
# 归纳口径：同一条行为（sign/watch/...）下出现的文本候选，被 >= MIN_APP_SUPPORT 个
# App 使用过 → 升级为该行为的共性词。只增不减，不影响人工维护的全局表顺序。

# 行为 ID → 词表类别（配置里不写 candidates_from 时，按当前行为自动推断）
INTENT_TO_CATEGORY = {
    "sign": "sign",
    "reserve": "sign",
    "bonus": "sign",
    "growth": "task_center",
    "collect": "task_center",
    "watch": "nav_tab",
    "open": "nav_tab",
    "withdraw": "withdraw",
}

MIN_APP_SUPPORT = 2  # 至少 2 个 App 用过的文案才算共性

# 归纳黑名单（AUTOP-NL-2026-10-22 实测修正）：
# 签到链里常夹带「弹窗清扫」步骤（关闭/暂不/以后再说…）与「导航」步骤（我/我的/首页），
# 这些词一旦被升级成 sign 共性词，click_first 找签到时就会去点「关闭」——
# 实测未加过滤时 sign 池被污染到 48 个，含「关闭/暂不/我知道了/我/我的」。
STOPWORDS = {
    "关闭", "关闭广告", "跳过", "跳过广告", "取消", "暂不", "暂不升级", "暂不开启",
    "以后再说", "稍后再说", "稍后", "我知道了", "知道了", "不再提醒", "下次再说",
    "开", "返回", "我", "我的", "首页", "同意", "允许", "确定", "好的",
}

_registered_apps = []
_auto_cache = {}


def register_apps(apps):
    """登记全量 App 配置（main.py 载入配置后调用）；幂等，重复调用会清缓存。"""
    global _registered_apps, _auto_cache
    _registered_apps = list(apps or [])
    _auto_cache = {}


def category_for_intent(intent):
    """行为 ID → 词表类别；未知行为返回 None（不并入，保持旧行为）。"""
    return INTENT_TO_CATEGORY.get((intent or "").strip())


def _walk_actions(node, sink):
    """递归收集所有动作 dict（行为值可能是 [动作] 或 [[动作...], [动作...]] 多模板）。"""
    if isinstance(node, list):
        for item in node:
            _walk_actions(item, sink)
    elif isinstance(node, dict):
        sink.append(node)
        for value in node.values():
            if isinstance(value, (list, dict)):
                _walk_actions(value, sink)


def mine_words(apps=None):
    """跨 App 归纳共性候选词，返回 {category: [word, ...]}（按支持度降序）。

    apps 缺省用 register_apps() 登记的全量配置；结果为纯函数产物，缓存到 _auto_cache。
    """
    if apps is None and _auto_cache:
        return _auto_cache
    pool = list(apps if apps is not None else _registered_apps)
    all_known = set()
    for words in _TABLES.values():
        all_known.update(words)
    support = {}  # (category, word) -> set(app_name)
    for app in pool:
        name = (app.get("name") or "").strip() or "?"
        behaviors = app.get("behaviors") or {}
        for bid, actions in behaviors.items():
            default_category = category_for_intent(bid)
            if not default_category:
                continue
            acts = []
            _walk_actions(actions, acts)
            for act in acts:
                if act.get("type") != "click_first":
                    continue
                # 步骤自带 candidates_from 时以它为准（那是作者声明的真实语义），
                # 否则才退回「按当前行为推断」。
                category = act.get("candidates_from") or default_category
                if category not in _TABLES:
                    continue
                for cand in act.get("candidates") or []:
                    if (cand.get("type") or "").lower() != "text":
                        continue
                    word = str(cand.get("value") or "").strip()
                    if not word or word in STOPWORDS:
                        continue
                    if word in all_known:  # 已在任何一张人工表里，不重复归纳
                        continue
                    support.setdefault((category, word), set()).add(name)
    grouped = {}
    for (category, word), owners in support.items():
        if len(owners) < MIN_APP_SUPPORT:
            continue
        grouped.setdefault(category, []).append((len(owners), word))
    result = {}
    for category, items in grouped.items():
        known = set(_TABLES.get(category, []))
        ordered = [w for _, w in sorted(items, key=lambda x: (-x[0], x[1])) if w not in known]
        if ordered:
            result[category] = ordered
    if apps is None:
        _auto_cache.update(result)
        return _auto_cache
    return result
