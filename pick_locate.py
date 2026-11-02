# -*- coding: utf-8 -*-
"""pick_locate.py - 定位择优纯函数（无设备依赖）

把 executor._pick_best 的打分逻辑抽成纯函数，供执行器与测试对拍复用。

2026-10-28 改造（#2 打分择优）：旧版在「唯一/最优候选是过长不可点击文案」时
直接一票否决返回 None。实测冤案（records.db WARN 归纳）：

    [text]'领取' 只匹配到 '关闭签到提醒后,可能会错过签到福利领取,确认关闭'（判误命中）
    [desc]'签到' 只匹配到 '京东金融通知：签到即将中断'（真按钮在旁边却选不出来）
    '立即签到 +1000火龙币' —— 这种带营销后缀的文案在很多 App 里**就是可点入口本体**

新语义：**同页所有匹配项打分排序，长度超限只是重罚分，不再整条拒配**。
真短按钮存在时靠分值自然胜出；只有当屏上「除超长文案外无可信候选」时，
才对超长候选做二次甄别（FAQ/通知句式硬拒；其余保守放行交上层 expect 校验）。

打分口径（纯函数 score_entry，便于单测与探针复用）：
    精确相等            +1000
    长度差              -3/字，封顶 -90
    clickable           +50
    导航词落在底部带     ±120（仅 target ∈ NAV_LABELS 且已知屏高）
    zone 位置先验        ±zone_bonus（tab_zone/top_right/right_edge）
    超长非可点          -700（罚分，不是否决）
    FAQ/通知句式        再 -400（"…如何参加？""…即将中断"这类噪声）
可信线 _PLAUSIBLE_FLOOR = 95：长度惩罚封顶 -90 加 clickable +50 后恰好越过，
即「正常长度的可点候选」必然可信，「超长不可点的营销/噪声文案」必然不可信。
"""
import re

try:
    from ui_page import NAV_LABELS, NAV_BAND_Y
except ImportError:  # pragma: no cover - 未拷贝 ui_page.py 时退化为空集
    NAV_LABELS, NAV_BAND_Y = set(), 0.80

# ---------- 位置先验三区（第3步，AUTOP-SELFSEARCH-2026-10-20） ----------
# 用户原话：「按钮名称、按钮位置、常用步骤的共性」——候选文案多处匹配时，
# 位置本身就是先验：底部导航带的 tab 类按钮、右上角/右缘的浮球类按钮。
# 只做加分不做硬过滤（与 nav 带一致），避免误伤特殊布局。
ZONE_BOTTOM_BAND = 0.92     # 底部导航带：top >= screen_h*0.92
ZONE_TOP_BAND = 0.18        # 顶部区域：top <= screen_h*0.18
ZONE_RIGHT_RATIO = 0.70     # 右缘：x 中心 >= screen_w*0.70
# 命中/未命中的加权分（未命中扣分仅用于「多匹配择优」，不硬过滤）
_ZONE_BONUS = {
    "tab_zone": 150,
    "top_right": 150,
    "right_edge": 100,
}

# ---------- 打分常量（新旧对照见模块 docstring） ----------
_LEN_DIFF_STEP = 3          # 长度差线性罚：每字 -3
_LEN_DIFF_CAP = 60          # 长度差罚分封顶（旧版 90 会把正常长文案压到线下）
_CONTAINS_BONUS = 80        # 含目标词加分：可信池入场券（公理 A1，见 score_entry）
_OVERLEN_PENALTY = 700      # 超长且不可点的罚分（旧版为整条否决）
_NOISE_PENALTY = 400        # FAQ/通知句式的追加罚分
_NO_TARGET_PENALTY = 90     # 标签不含目标词的降档分（公理 A2：恒不可信）
_PLAUSIBLE_FLOOR = 95       # 「可信候选」线：含词非超长候选恒 >=120 过线；
                            #   不含词候选最高 100-0+50-90=60 恒落线外；
                            #   超长非可点 -6xx 必然进兜底甄别分支

# 疑似噪声文案特征：FAQ / 推送通知标题 / 说明性长句。
# 踩坑来源：一淘 FAQ「什么是签到领钱，如何参加？」被 textContains='签到'
# 命中后当按钮点 —— 这类句子无论多短都不该是点击目标。
# 克制原则（2026-10-28 校准）：**只收问句/通知类强信号**。动词字面
# （查看/详情/更多…）在入口文案里无处不在（'查看更多福利'就是真入口），
# 收进来会批量制造新冤案 —— 长度罚分已经让它们沉底，无须句式层再杀。
_NOISE_MARKERS = ("？", "?", "什么是", "如何", "怎样", "吗", "呢",
                  "规则", "解释", "即将", "中断", "提醒您")
_CJK = re.compile(r"[一-鿿]")
# 兜底放行排序用的次级降权词：推送/通知标题句式（含目标词但多半不是入口本体）。
_PUSH_WORDS = ("通知", "提醒")


def _has_marker_standalone(label, m):
    """标记是否以「独立词语」身份出现（而非营销文案的构词成分）。

    ASCII 标记（'?'）直接子串判定。中文标记看邻字：
      - 多字疑问/说明词（'什么是'/'如何'/'规则'…）本身即强信号，
        仅当它同时是 target 的一部分时豁免；
      - '知'/'断' 这类单字级易撞标记要求至少一侧非汉字粘连，
        排除「…早知道」「…不断领」等构词误伤。
    """
    if m.isascii():
        return m in label
    start = 0
    while True:
        i = label.find(m, start)
        if i < 0:
            return False
        prev_c = label[i - 1] if i > 0 else ""
        next_c = label[i + len(m)] if i + len(m) < len(label) else ""
        glued = (bool(_CJK.match(prev_c)) if prev_c else False) and \
                (bool(_CJK.match(next_c)) if next_c else False)
        if not (len(m) == 1 and glued):   # 单字被两侧汉字夹住 -> 构词成分
            return True
        start = i + 1


def overlen_limit(target):
    """旧版长度阈值的等价函数（保留口径：max(len+6, len*3)）。"""
    return max(len(str(target)) + 6, len(str(target)) * 3)


def is_noise_label(label, target=""):
    """超长候选里甄别「绝不可能是按钮」的句式。

    判定：含疑问/说明/通知标记（独立成词才算，target 自带的字符豁免）；
    或不含目标词且以标点收尾的说明性长句。
    """
    label = str(label or "")
    t = str(target or "")
    if any(_has_marker_standalone(label, m) for m in _NOISE_MARKERS
           if m not in t):
        return True
    if t not in label and label[-1:] in ("，", ",", "。", "."):
        return True
    return False


def score_entry(entry, target, kind, screen_h=0, screen_w=0, zone=None):
    """单条目打分（纯函数）。entry = {label, clickable, top, left?, right?}。

    返回 (score, overlong_nonclickable)。overlong 标志供上层甄别兜底用，
    不影响分值语义。kind 目前只对 text/desc 做长度惩罚（id 无长度概念）。
    """
    label = str(entry.get("label") or "")
    t = str(target)
    clickable = bool(entry.get("clickable"))
    try:
        top = int(entry.get("top") or 0)
    except (TypeError, ValueError):
        top = 0

    if label == t:
        score = 1000
    else:
        # 旧版：100 - min(90, |Δlen|*3)，且含词/不含词候选同池混排。
        # 新版两条公理（由 test_plausible_floor_excludes_salvage_zone 锁定）：
        #   A1 含目标词的候选恒可信：最差 100-60+80=120 > floor；
        #   A2 不含目标词的非可点候选恒不可信：最高 100-0-90=10 < floor，
        #      即便 clickable(+50)=60 仍 < floor —— u2 contains 匹配到的
        #      不含词节点几乎总是说明句/背景文字，保守拒配符合旧版倾向。
        score = 100 - min(_LEN_DIFF_CAP, abs(len(label) - len(t)) * _LEN_DIFF_STEP)
        if t and t in label:
            score += _CONTAINS_BONUS
        else:
            score -= _NO_TARGET_PENALTY
    if clickable:
        score += 50

    # 导航词位置合理性：中部假命中扣分、底部带内加分（软先验，不硬过滤）
    if str(t).strip() in NAV_LABELS and screen_h:
        score += 120 if top >= NAV_BAND_Y * screen_h else -120

    # 第3步：位置先验 zone 加分（缺坐标/未知屏尺寸 -> 该条目中性）
    zone_bonus = _ZONE_BONUS.get(zone)
    if zone_bonus and screen_h and (zone != "right_edge" or screen_w):
        try:
            if zone in ("tab_zone", "top_right"):
                ok_zone = (top >= ZONE_BOTTOM_BAND * screen_h
                           if zone == "tab_zone"
                           else top <= ZONE_TOP_BAND * screen_h)
            else:
                ok_zone = True
            xc = None
            if zone in ("top_right", "right_edge"):
                if entry.get("left") is not None and entry.get("right") is not None:
                    xc = (int(entry["left"]) + int(entry["right"])) / 2.0
            if zone in ("top_right", "right_edge") and xc is None:
                pass                            # 缺 x 坐标：中性
            elif ok_zone and (xc is None or
                              xc >= ZONE_RIGHT_RATIO * screen_w):
                score += zone_bonus
            elif zone != "right_edge" or xc is not None:
                score -= zone_bonus
        except Exception:
            pass

    # 超长非可点：重罚但不否决（旧版此处 return None 整条拒配）。
    # **降档不淘汰**：overlong 候选从可信池摘出（进兜底甄别分支），
    # 但仍参与排序 —— 若它含目标词且句式无辜（营销后缀入口），放行；
    # 若不含目标词，兜底层按长句噪声处理，与旧版"优先选短"倾向一致。
    overlong = (kind in ("text", "desc")
                and len(label) > overlen_limit(t) and not clickable)
    if overlong:
        score -= _OVERLEN_PENALTY
        if is_noise_label(label, t):
            score -= _NOISE_PENALTY
    return score, overlong


def pick_best(entries, target, kind, screen_h=0, log=None, screen_w=0,
              zone=None):
    """从多匹配候选里择优（打分排序 + 超长甄别兜底）。

    entries : [{label, clickable, top, left?, right?}]（保序，最多取前 12 条）
    target  : 目标文本
    kind    : text / desc / id
    screen_h: 屏幕高度像素（0 = 未知，跳过 nav 带/zone 位置判断）
    log     : 可选回调 log(event, app="", level="INFO")
    screen_w: 屏幕宽度像素（0 = 未知，跳过 zone 右缘/右上角加分）
    zone    : tab_zone / top_right / right_edge / None（未知值忽略）
    返回    : 选中下标（平局取先）；无任何可信候选时返回 None
    """
    n = len(entries)
    if n == 0:
        return None
    scored = []                               # [(idx, score, overlong), ...]
    for i in range(min(n, 12)):
        s, ov = score_entry(entries[i], target, kind, screen_h, screen_w, zone)
        scored.append((i, s, ov))

    # 可信候选（score > floor）参与择优；全部不可信时进入超长甄别分支。
    # 兜底池排序**短者优先**：旧版「可点击优先 + 短文本优先」的倾向保留，
    # 不含目标词的说明长句与含词营销入口同池时，靠 _rank 分层再按长度收口。
    plausible = [t for t in scored if t[1] > _PLAUSIBLE_FLOOR]
    if plausible:
        best_i, best_score = plausible[0][0], plausible[0][1]
        for i, s, _ov in plausible[1:]:
            if s > best_score:                # 严格大于 -> 平局取先
                best_i, best_score = i, s
        if log is not None:
            log(f"  [{kind}]'{target}' 命中 {n} 处，择优 {best_score} 分",
                "", "DEBUG")
        return best_i

    # 兜底：只剩超长/低分候选 —— 逐条甄别，噪声句式维持拒绝（旧行为）。
    # 顺序纪律（2026-10-28 实测修正）：**优先含目标词的超长文案**，其次才是不含目标词的长句
    # —— 「立即签到 +1000火龙币」这类营销后缀在很多 App 里就是可点入口本体；
    # 「闲鱼通知：闲鱼币今日签到提醒」虽也含「签到」但属推送标题，降权靠后。
    # 同级内**短者优先**（旧版 len 升序倾向），放行后由上层 expect/落地校验把关。
    survivors = [t for t in scored if not is_noise_label(
        entries[t[0]].get("label"), target)]
    if survivors:
        def _rank(t):
            lab = str(entries[t[0]].get("label") or "")
            return (
                0 if str(target) in lab else 1,       # 含目标词优先
                1 if any(w in lab for w in _PUSH_WORDS) else 0,  # 推送标题靠后
                len(lab),                              # 短者靠前（旧倾向）
                -t[1],                                 # 分数高者优先
                t[0],                                  # 平局取先（保序）
            )
        idx = min(survivors, key=_rank)[0]
        if log is not None:
            log(f"  [{kind}]'{target}' 无常规可信候选，放行超长文案 "
                f"{str(entries[idx].get('label'))[:24]!r}（打分择优兜底，"
                f"交落地校验把关）", "", "WARN")
        return idx
    if log is not None:
        worst = str(entries[scored[0][0]].get("label"))[:24]
        log(f"  [{kind}]'{target}' 候选均为超长噪声文案（如 {worst!r}），"
            f"判为误命中", "", "WARN")
    return None
