# -*- coding: utf-8 -*-
"""
nlu.py - 自然语言行为解析器
把用户的一句自然语言（如 "帮我去XX签到并看视频，然后提现"）
解析成有序的【意图列表】，再在配置阶段绑定到具体 app 的行为模板。
采用关键词规则引擎：可维护、可解释、无需重模型。
"""
import re

# 内置意图 -> 行为 ID 词典（app 配置中若自定义 intent_map 则优先）
# 2026-10-25 整理：
#   ① 新增 gift（快马的「白拿礼物」原是中文自定义 behavior 名，现收编为标准意图）；
#   ② growth 删掉「签到领」—— _ORDERED_ITEMS 长词优先，「签到领」会抢在
#      「签到」之前命中，导致「签到领金币」被解析成 growth 而不是 sign；
#   ③ reserve 正式启用（抖音火山版没有签到只有预约，intent_map: sign→reserve）。
DEFAULT_INTENT_MAP = {
    "sign":    ["签到", "每日签到", "打卡", "签到打卡"],
    "reserve": ["预约打卡", "预约签到", "预约"],
    "watch":   ["看视频", "刷视频", "看广告", "刷广告", "看任务视频", "视频任务"],
    "withdraw": ["提现", "提钱", "兑换红包", "提收益"],
    "bonus":   ["领红包", "领金币", "领取奖励", "领任务奖励", "领积分"],
    "collect": ["收集", "收取能量", "喂鸡", "浇水", "收取金币"],
    "growth":  ["浇花", "施肥", "升级", "做任务"],
    "gift":    ["白拿礼物", "白拿", "免费领", "领礼物"],
    # `open` 是部分 App（百度极速版、海马畅听）唯一/主要的配置行为名，
    # 之前没有对应关键词，导致「百度极速版」只能用回退意图（sign）而被跳过。
    "open":    ["打开", "启动", "开启应用", "开应用"],
}

# 匹配顺序：长词优先，避免"签到"吞掉"预约签到"这类更长词组
_ORDERED_ITEMS = sorted(
    [(kw, intent) for intent, kws in DEFAULT_INTENT_MAP.items() for kw in kws],
    key=lambda x: len(x[0]), reverse=True,
)


def parse_intents(natural_text: str) -> list:
    """从自然语言中提取有序意图。返回 [(intent_id, 命中的关键词), ...]，保持原文出现顺序"""
    text = natural_text or ""
    hits = []
    for kw, intent in _ORDERED_ITEMS:
        if kw in text:
            # 记录关键词在原文中的位置，用于保持顺序
            idx = text.index(kw)
            hits.append((idx, intent, kw))
    # 去重（同一意图只保留命中一次）
    seen = set()
    ordered = []
    for idx, intent, kw in sorted(hits, key=lambda x: x[0]):
        if intent in seen:
            continue
        seen.add(intent)
        ordered.append((intent, kw))
    return ordered


def match_app(text: str, apps_cfg: list):
    """在自然语言或 --app 参数中匹配配置的 app。
    返回 (匹配的 app dict, None) 或 (None, 匹配失败原因)。

    匹配优先级（逐级收窄，避免"京东理财"被"京东"抢先命中）：
      1. 包名精确
      2. 名称精确
      3. 别名精确
      4. 最长子串（名称/别名出现在文本里；或用户输入是名称的片段）
      5. 包名子串
      6. 数字序号

    历史缺陷：旧实现按 apps 配置顺序做「别名 in 文本」判断并立即返回，
    由于"京东"排在"京东理财"之前，`--app 京东理财` 会误命中"京东"，
    任务被发到错误的 app。故改为先精确后最长匹配。
    """
    raw = (text or "").strip()
    t = raw.lower()
    if not apps_cfg:
        return None, "配置中没有定义任何 app"
    if not t:
        return None, "未能识别出 app（请用 --app 指定，或在意向句里带上 app 名）"

    def _name(app):
        return (app.get("name") or "").strip()

    def _aliases(app):
        return [str(a).strip() for a in (app.get("aliases") or []) if str(a).strip()]

    # 1) 包名精确
    for app in apps_cfg:
        pkg = (app.get("package") or "").strip().lower()
        if pkg and pkg == t:
            return app, None

    # 2) 名称精确
    for app in apps_cfg:
        if _name(app).lower() == t:
            return app, None

    # 3) 别名精确
    for app in apps_cfg:
        for alias in _aliases(app):
            if alias.lower() == t:
                return app, None

    # 4) 最长子串匹配
    best_score, best_idx, best_app = -1.0, -1, None
    for i, app in enumerate(apps_cfg):
        tokens = ([_name(app)] if _name(app) else []) + _aliases(app)
        for tok in tokens:
            tl = tok.lower()
            if not tl:
                continue
            if tl in t:
                # 用户输入里包含该 app 名/别名：以命中长度为准，越长越具体
                score = float(len(tl))
            elif t in tl and len(t) >= 2:
                # 用户输入是名称的片段（简称/漏字），弱化计分
                score = len(t) * 0.5
            else:
                continue
            if score > best_score:
                best_score, best_idx, best_app = score, i, app
    if best_app is not None:
        return best_app, None

    # 5) 包名子串
    for app in apps_cfg:
        pkg = (app.get("package") or "").strip().lower()
        if pkg and pkg in t:
            return app, None

    # 6) 数字序号（如 "app 1" / "1号app"）
    m = re.search(r"(\d+)\s*(?:号)?\s*(?:app|应用)?", t)
    if m:
        idx = int(m.group(1)) - 1
        if 0 <= idx < len(apps_cfg):
            return apps_cfg[idx], None
    return None, f"在配置中未找到匹配的 app（当前共 {len(apps_cfg)} 个）"

# 注：意图 → behavior 的解析在 behavior_runner.Executor._resolve（唯一实现）。
# 此处原有一份 resolve_behavior 与它逐行相同且全仓库无人调用（2026-10-25
# 清理死代码时删除）—— 两处相同逻辑必然漂移，只保留执行层那一份。
