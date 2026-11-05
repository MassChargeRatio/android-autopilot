# -*- coding: utf-8 -*-
"""behavior_runner.py - 行为执行层（D 批从 executor.py 三分拆）

搬迁来源：executor.py 的 Executor 类。

⚠️ 2026-10-25 整理：这里原先抄了一份「executor.py 旧行号索引」，代码几经
搬迁后行号全部失效，反而误导定位。现改为**按职责列目录，不写行号**——
找方法请用 IDE 符号导航 / grep，不要信任何写死行号的注释。

职责目录：
  顶层流程   run_app_flow / _resolve / _pick_variant / _run_actions
  分派       _exec_step / _dispatch_step / _dispatch_probe / _run_kind
             / _dispatch（兼容薄包装）
  分支       _step_any_of / _step_random
  点击       _step_click（统一点击，by=text/id/desc；2026-10-25 合并）
             + _step_click_text / _step_click_id / _step_click_desc（别名）
             + _step_click_point / _step_click_first
  滚动滑动   _step_swipe（natural:true 已修：尊重 from/to）
             + _step_swipe_natural（别名）/ _step_scroll_to
  导航       _step_back / _step_home / _step_dismiss_popups
  等待拟人   _step_wait / _step_think
  收益断言   _step_reward / _reward_candidates / _step_ensure
  验证码     _step_captcha
  内部件     _locate_with_kb / _kb_candidates / _expand_kb_pool / _click_tracked
             / _click_obj / _verify_landing / _vision_or_miss
  模块级     StepError / _VISION_GATED_STEPS / DEFAULT_POPUP_TEXTS 等

坑位注释原文照搬，禁止润色（见各方法 docstring）。

方法体内通过 `self._xxx` 同名可覆盖入口互相调用：本类被 executor.py 门面
多继承后，self 是 Executor 实例，tests 对 Executor 实例打桩仍然生效。
"""
import hashlib
import json
import os
import random
import re
import time

from reward_pick import rank_reward_candidates, _TEXT_ATTR_RE, _BALANCE_HINTS  # noqa: E402
from locator import _parse_sel  # noqa: E402
from device_session import win_wh  # noqa: E402
from candidates import candidates_for, category_for_intent  # noqa: E402
# v6 S1：统一编译层。只用于**编译期校验**（把配置错误提前暴露成日志），
# 执行仍走原始 dict —— 这是"老配置一行不改、行为零变化"的实现方式。
from step_model import Step, compile_step  # noqa: E402


class StepError(Exception):
    """单步失败且不可恢复（仅 ensure/captcha/swipe 缺坐标/缺依赖/scroll_to 无果等保留）"""
    pass


# B7：接受 allow_vision 显式门控的 step 原语集合（其余 step 签名不变）。
# 教训：早期用 `self._probe_no_vision` 实例标志位做门控，any_of 循环里
# "临时改写再还原"，异常/新增直调点会留下脏状态；现改为参数链贯穿。
# 2026-10-25：新增统一点击原语 "click"（by=text/id/desc），旧三个名字是它的别名。
_VISION_GATED_STEPS = {"click", "click_text", "click_id", "click_desc",
                       "click_first", "any_of", "random"}

# ---------- 动作分类与返回值契约（2026-10-29） ----------
# 19 个平铺的 type，问题不是"没分类"，而是**同一类的返回值语义不一致**：
# `_run_kind` 只能统一 `None -> True` 兜底，于是"没做任何判断"和"判断通过"
# 在调用方看来完全一样。三个真实后果（本次一并修）：
#   ① _step_click_point 丢掉 _verify_landing 的返回值 -> 落地失败也算成功；
#   ② _step_any_of 的 optional 全 miss 分支日志写"放行"、却 return False；
#   ③ _step_random 不汇总子步骤 -> 子步骤全失败，整步仍算成功。
#
# 分类口径：**它需要什么能力 + 返回值是什么**，不是名字好不好看。
# 规范名与别名分离：click_text/click_id/click_desc 是 click 的别名，
# swipe_natural 是 swipe 的别名，方法名与 dispatch 表一律不动。
ACTION_CATEGORY = {
    # 元素点击：True=点中元素，False=未找到
    "click": "click",
    "click_first": "click",
    "click_text": "click",      # 别名 -> click(by=text)
    "click_id": "click",        # 别名 -> click(by=id)
    "click_desc": "click",      # 别名 -> click(by=desc)
    # 坐标点击：True=落地通过，False=落地失败，None=无可判信号（盲点无法验证）
    "click_point": "point",
    # 手势：True=已执行，缺坐标抛 StepError
    "swipe": "gesture",
    "swipe_natural": "gesture",  # 别名 -> swipe(natural=true)
    # 系统键：True/False
    "back": "key",
    "home": "key",
    # 时序：永远成功，None 是合法返回值
    "wait": "timing",
    "think": "timing",
    # 分支编排：True=某分支命中 / False=全 miss
    "any_of": "flow",
    "random": "flow",
    # 复合动作（内部含多次尝试，对外仍是单个 bool）
    "scroll_to": "compound",
    "dismiss_popups": "compound",
    "captcha": "compound",
    # 断言/读取
    "ensure": "assert",          # True / StepError
    "reward": "read",            # 只记录，None 是合法返回值
}

# 每类允许的返回值。"none" = 允许返回 None（且视为成功），
# 不在允许集里的 None 一律记 WARN 并按失败处理 —— 这就是"不再统一兜底"。
_RETURN_CONTRACT = {
    "click": {"bool"},
    "point": {"bool", "none"},
    "gesture": {"bool"},
    "key": {"bool"},
    "timing": {"none"},
    "flow": {"bool"},
    "compound": {"bool"},
    "assert": {"bool"},
    "read": {"none"},
}

# ---------- F1 全局弹窗清扫（AUTOP-FEAT-2026-10-20） ----------
# 用户原话：「遇到各种不是程序自身引起的弹窗，都可以看到就关闭」+
# 「关闭弹窗的方式还可以尝试系统的回退键」+「不是主动观看的广告，也可以跳过」。
# 关闭顺序（每轮只做一个动作，最多 max_rounds 轮）：
#   文案精确匹配 -> 关闭按钮 id -> 右上角坐标兜底 -> 系统返回键。
# 两条硬护栏：
#   ① 资金类黑名单文案命中 -> 本轮熔断：停扫且禁用 BACK
#      （按 BACK 消化提现确认=跳过用户确认，踩项目资金二次确认红线）；
#   ② corner/back 只在屏上有「广告特征」标记时才动 —— 干净屏上按 BACK
#      可能直接退出 App 或返回上一级，属破坏性操作。
DEFAULT_POPUP_TEXTS = [
    "关闭", "跳过", "暂不", "暂不开启", "以后再说", "稍后再说", "稍后",
    "我知道了", "知道了", "不再提醒", "下次再说", "暂不升级", "取消",
]
POPUP_CLOSE_IDS = []  # 常见关闭按钮 id（各 App iv_close 类），配置可追加
POPUP_BLACKLIST_TEXTS = [
    "提现", "确认提现", "立即提现", "去提现",
    "支付", "确认支付", "付款", "银行卡", "实名", "验证码", "身份验证",
]
POPUP_AD_MARKERS = ("广告", "跳过", "跳转", "打开", "下载", "安装")
# watch 流程保护：这些文案关掉的就是正在看的广告
AD_CLOSE_TEXTS = ("跳过", "跳过广告", "关闭广告")


class BehaviorRunner:
    """行为执行层：顶层流程、动作分派、全部 step 原语、收益识别。"""

    def run_app_flow(self, app_cfg: dict, intents: list):
        """按顺序对某 app 执行一组意图。intents: [(intent_id, keyword), ...]"""
        app_name = app_cfg.get("name") or app_cfg.get("package") or "?"
        pkg = app_cfg.get("package")
        if not pkg:
            self.recorder.log("app 配置缺少 package，跳过", app_name, "WARN")
            return

        # dry-run：只打印执行计划，不触碰设备
        if self.dry_run:
            self.recorder.log(f"[dry-run] 预览计划：{app_name} ({pkg})", app_name)
            last_bid = None
            for intent, kw in intents:
                bid = self._resolve(app_cfg, intent)
                if bid is None:
                    self.recorder.log(
                        f"  意图[{intent}]({kw}) 未配置行为，跳过", app_name, "WARN")
                    continue
                if bid == last_bid:
                    self.recorder.log(
                        f"  意图[{intent}]({kw}) -> 行为[{bid}] 与上一条意图相同，"
                        f"跳过重复执行", app_name, "INFO")
                    continue
                last_bid = bid
                bid_cfg = app_cfg["behaviors"][bid]
                if not self._window_open(bid_cfg, app_name, intent, kw, dry=True):
                    continue
                actions = self._pick_variant(self._behavior_actions(bid_cfg),
                                             app_name, bid)
                self.recorder.log(f"  意图[{intent}]({kw}) -> 行为[{bid}]:", app_name)
                for a in actions:
                    self.recorder.log("      - " + json.dumps(a, ensure_ascii=False),
                                      app_name)
            return

        # 1) 启动 app（即使已有 open 步骤也确保一次）
        #    launch_reset: true → 冷启动，避免恢复上次停留的子页面（tab 类入口必需）
        #    返回 False = 包未安装，必须整单跳过：否则盲点坐标会落到前台别的 App 上
        #    （2026-10-30 趣头条未安装，坐标点进了微信）。注意用 `is False` 判定，
        #    因为测试里 `_open_app` 被 stub 成返回 None 的 lambda。
        # 2026-11-04（AUTOP-火山版-P1 层1/层2）：启动时序可配化。
        # app 配置写了 `launch:` 段 → 走 _open_app_timed（开屏广告等待+确认、
        # 页面就绪预算放宽）；没写 → 原样走 self._open_app，34 份配置零变化。
        if self._open_app_timed(pkg, app_name, app_cfg) is False:
            # 具体原因（未安装 / 前台跑偏）已由 _open_app 记过 ERROR，
            # 这里不再猜原因 —— 2026-10-31 微博实测：前台跳到支付宝被拦，
            # 这行却写成「未安装」，误导排查。
            self.recorder.log(f"{app_name} 启动失败，跳过本次全部行为",
                              app_name, "ERROR")
            return

        # 1b) launch_back：启动后按 BACK 退掉**脏落地页**（无底部导航的全屏内容页/
        #     开屏广告），使首行为从带导航的顶层页起步。不依赖 _at_top_level 确认
        #     （WebView 重页面 dump 不可靠，实测「BACK 未回到顶层页 -> 重启」后仍
        #     落回同一脏页）；已在顶层页则不按（保护正常落地的 App）。
        #     2026-11-01 未找到文本按钮/候选未出现族：悟空浏览器首行为 click_text[赚钱]
        #     因启动落全屏短剧播放页（无底部导航）连败 3 天，launch_back=1 实测
        #     BACK 后「赚钱」tab 进树（bounds [492,2113][588,2170]）。
        launch_back = app_cfg.get("launch_back")
        if launch_back:
            self._back_to_landing_after_launch(pkg, app_name, int(launch_back))

        # 2) 逐意图执行
        # 去重（AUTOP-火山版-2026-11-01）：连续两个意图解析到同一行为时跳过第二个。
        # 起因：抖音火山版 intent_map{sign:reserve} + reserve 同名兜底，任务串同时含
        # 「签到,预约」→ reserve 行为被跑两遍（每遍 ~150-200s），叠加冷启动间隔与
        # watch 后单 app 超 300s 上限 → 三连超时。同行为重复执行在本项目语义下必冗余
        # （每日签到/预约只一次），故收敛为跑一遍。仅影响「同行为连续映射」的 app，
        # 常规 app（sign→sign、reserve→reserve 各不同）行为零变化。
        last_bid = None
        for i, (intent, kw) in enumerate(intents):
            bid = self._resolve(app_cfg, intent)
            if bid is None:
                self.recorder.log(
                    f"意图[{intent}](触发词:{kw}) 在 {app_name} 未定义对应行为，跳过",
                    app_name, "WARN")
                continue
            if bid == last_bid:
                self.recorder.log(
                    f"意图[{intent}](触发词:{kw}) -> 行为[{bid}] 与上一条意图相同，"
                    f"跳过重复执行（同行为只跑一次）", app_name, "INFO")
                continue
            last_bid = bid
            bid_cfg = app_cfg["behaviors"][bid]
            if not self._window_open(bid_cfg, app_name, intent, kw):
                continue
            # 行为之间复位：上一个行为可能已把 App 留在二级/三级页，
            # 不复位则本行为会从脏页面起步（详见 _reset_to_landing 注释）。
            if i > 0:
                self._reset_to_landing(
                    pkg, app_name,
                    launch_reset=bool(app_cfg.get("launch_reset")),
                    launch_back=int(app_cfg.get("launch_back") or 0))
            actions = self._pick_variant(self._behavior_actions(bid_cfg),
                                         app_name, bid)
            # F1：行为执行前全局弹窗清扫（"看到就关"；黑名单熔断仅告警不拦截行为）
            self._maybe_sweep_popups(intent, bid, app_name, app_cfg=app_cfg)
            self.recorder.log(
                f"开始执行行为[{bid}] 动作数={len(actions)}", app_name)
            ok = self._run_actions(actions, app_name, bid)
            if not ok:
                self.recorder.log(
                    f"行为[{bid}] 执行未完成（部分步骤未找到元素已跳过）",
                    app_name, "WARN")
            self.human.think()

        # 3) 自然退场（真人换台/锁屏前的随手操作）
        self._close_app(app_name)

    # ---------- 启动时序参数化（AUTOP-火山版-2026-11-04 层1/层2） ----------
    def _open_app_timed(self, pkg, app_name, app_cfg):
        """按 app 配置 `launch:` 段启动 App；无该段时等价 device_session._open_app。

        为什么另写一份而不是改 device_session._open_app：
          本卡（AUTOP-2026-11-04-P1）红线只允许改 config/apps/抖音火山版.yaml
          与 behavior_runner.py；而 Executor 的 MRO 是
          `(DeviceSession, Locator, BehaviorRunner)`，DeviceSession 在前，
          在本类重写 `_open_app` / `_wait_page_ready` **不生效**。所以只能在
          本类显式复刻启动流程，并用 app 级参数关住风险面：没写 `launch:` 的
          配置一律回落到 self._open_app，行为零变化。

        参数（app yaml `launch:`，全部可选，缺省值 = device_session 现行为）：
          page_ready_max_wait: 页面就绪等待预算秒数（默认 30）
          page_ready_min_nodes: 判定稳定的最小节点数（默认 25）
          splash_wait: 前台不是目标包（开屏广告 deeplink 漂移）时先等这么久
                       再判，而不是立刻 stop+重启（M2 层2 实测重启再吃 30-58s）
          splash_poll: 等待期间前台轮询间隔（默认 2.0）

        返回 True=已启动；False=包未安装 / 两次启动仍漂移（与 _open_app 同口径）。
        """
        cfg = (app_cfg or {}).get("launch") if isinstance(app_cfg, dict) else None
        reset = bool((app_cfg or {}).get("launch_reset"))
        if not isinstance(cfg, dict) or not cfg:
            return self._open_app(pkg, app_name, reset=reset)
        if self.dry_run or self.d is None:
            return self._open_app(pkg, app_name, reset=reset)
        if not self._pkg_installed(pkg):
            # 交给原实现统一记 ERROR「未安装 … 拒绝启动」
            return self._open_app(pkg, app_name, reset=False)
        max_wait = float(cfg.get("page_ready_max_wait") or 30.0)
        min_nodes = int(cfg.get("page_ready_min_nodes") or 25)
        splash_wait = float(cfg.get("splash_wait") or 0.0)
        splash_poll = float(cfg.get("splash_poll") or 2.0)

        if reset:
            self.d.app_start(pkg, stop=True)
            self.recorder.log("冷启动（launch_reset）", app_name, "DEBUG")
        else:
            self.d.app_start(pkg)
        self.human.after_open()
        if splash_wait > 0:
            self._wait_splash_gone(pkg, app_name, splash_wait, splash_poll)
        n, waited, stable, fg = self._wait_page_ready(
            pkg, app_name, max_wait=max_wait, min_nodes=min_nodes)
        self._log_page_ready(n, waited, stable, fg, app_name)
        if pkg and pkg not in (fg or ""):
            self.recorder.log(
                f"开屏等待后前台仍是 {fg or '?'}（不是 {pkg}），"
                f"确认漂移未恢复 -> 重启一次", app_name, "WARN")
            self.d.app_start(pkg, stop=True)
            self.human.after_open()
            n, waited, stable, fg = self._wait_page_ready(
                pkg, app_name, max_wait=max_wait, min_nodes=min_nodes)
            self._log_page_ready(n, waited, stable, fg, app_name, restarted=True)
            if pkg not in (fg or ""):
                self.recorder.log(
                    f"两次启动后前台仍是 {fg or '?'}，跳过本次全部行为"
                    f"（否则盲点坐标会落到别的 App 上）", app_name, "ERROR")
                return False
        self.recorder.log(f"已启动 {app_name}", app_name)
        return True

    def _wait_splash_gone(self, pkg, app_name, splash_wait, splash_poll):
        """开屏广告「等待+确认」（M2 层2 P0）。

        原逻辑（device_session._open_app）：页面就绪判定后只要前台不是目标包
        就立即 stop+重启，重启 = 又一次完整冷启动（M2 11-03 L320-L323 实测
        启动累计 94s）。这里改为先在 splash_wait 秒内轮询前台：广告页自己
        消失、前台回到目标包就直接往下走，不再重启。
        """
        t0 = time.time()
        fg = ""
        while time.time() - t0 < splash_wait:
            try:
                fg = (self.d.info.get("currentPackageName") or "") if self.d else ""
            except Exception:
                fg = ""
            if pkg and pkg in fg:
                self.recorder.log(
                    f"开屏等待 {time.time() - t0:.1f}s 后前台已回到 {pkg}，无需重启",
                    app_name, "DEBUG")
                return True
            time.sleep(splash_poll)
        self.recorder.log(
            f"开屏等待 {splash_wait:g}s 后前台={fg or '?'} 仍未回到 {pkg}",
            app_name, "WARN")
        return False

    def _log_page_ready(self, n, waited, stable, fg, app_name, restarted=False):
        """页面就绪判定日志（与 device_session._open_app 同格式，便于日志比对）。"""
        self.recorder.log(
            f"页面就绪判定{'（重启后）' if restarted else ''}: 节点={n} "
            f"等待={waited:.1f}s "
            f"{'已稳定' if stable else '未稳定（超时，按当前页继续）'}"
            f" 前台={fg or '?'}",
            app_name, "DEBUG" if stable else "WARN")

    # ---------- 第4步：behavior 时间窗（AUTOP-SELFSEARCH-2026-10-20） ----------
    # 用户原话：「常用步骤的共性」——签到/领现金类行为常有时效窗口（凌晨福利、
    # 每日首签等）。behaviors[bid] 兼容两种形态：
    #   * list：旧格式，动作列表；
    #   * dict：新格式 {window: {start, end}, actions: [...]}（window 可选）。
    # 窗口外：记 WARN「跳过(BLOCKED)」跳过本意图，不报错、不打断整条流程。
    @staticmethod
    def _parse_hhmm(s):
        """解析 "HH:MM" / "HH:MM:SS" -> 当日分钟数；失败返回 None。"""
        if s is None:
            return None
        s = str(s).strip()
        m = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?$", s)
        if not m:
            return None
        hh, mm = int(m.group(1)), int(m.group(2))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            return None
        return hh * 60 + mm

    def _in_window(self, win, now=None):
        """行为时间窗判定。返回 True=窗口内/无法判定（放行）；False=窗口外。

        - window 缺失、非 dict、start/end 解析失败 -> True（不因配置问题堵死行为）；
        - start <= end -> 窗口内 = start <= now <= end；
        - start >  end -> 跨午夜窗口：now >= start 或 now <= end 均算窗口内。
        now 形如 "HH:MM"，None 取当前时间。
        """
        if not isinstance(win, dict):
            return True
        start = self._parse_hhmm(win.get("start"))
        end = self._parse_hhmm(win.get("end"))
        if start is None and end is None:
            return True
        if now is None:
            now = time.strftime("%H:%M", time.localtime())
        cur = self._parse_hhmm(now)
        if cur is None:
            return True
        if start is None:
            start = 0
        if end is None:
            end = 23 * 60 + 59
        if start <= end:
            return start <= cur <= end
        return cur >= start or cur <= end

    @staticmethod
    def _behavior_actions(bid_cfg):
        """behaviors[bid] 双形态取动作：list 原样；{window, actions} 取 actions。"""
        if isinstance(bid_cfg, dict) and "actions" in bid_cfg:
            return bid_cfg["actions"]
        return bid_cfg

    @staticmethod
    def _behavior_window(bid_cfg):
        """behaviors[bid] 双形态取 window：无 window 返回 None。"""
        if isinstance(bid_cfg, dict) and isinstance(bid_cfg.get("window"), dict):
            return bid_cfg["window"]
        return None

    def _app_extras(self, app_name):
        """解析 App 级 extra_candidates（词表微调，惰性缓存）。

        candidates_from 自搜寻时，把 config/apps/<app>.yaml 里的
        `extra_candidates` 段并入全局词表。读取失败返回 {}（不中断执行）。
        """
        cache = getattr(self, "_extras_cache", None)
        if cache is None:
            cache = self._extras_cache = {}
        if app_name in cache:
            return cache[app_name]
        extras = {}
        try:
            import config_loader
            path = config_loader.app_config_path(app_name)
            if os.path.isfile(path):
                app = config_loader._load_yaml(path) or {}
                extras = app.get("extra_candidates") or {}
        except Exception:
            extras = {}
        cache[app_name] = extras
        return extras

    def _window_open(self, bid_cfg, app_name, intent, kw, dry=False):
        """行为窗口门控：窗口外记 WARN 跳过(BLOCKED)并返回 False；否则 True。"""
        win = self._behavior_window(bid_cfg)
        if win and not self._in_window(win):
            where = "dry-run" if dry else f"触发词:{kw}"
            self.recorder.log(
                f"意图[{intent}]({where}) 行为不在时间窗内，跳过(BLOCKED)",
                app_name, "WARN")
            return False
        return True

    def _resolve(self, app_cfg, intent):
        behaviors = app_cfg.get("behaviors", {}) or {}
        imap = app_cfg.get("intent_map", {}) or {}
        bid = imap.get(intent)
        if bid and bid in behaviors:
            return bid
        return intent if intent in behaviors else None

    def _pick_variant(self, actions: list, app_name: str, bid: str) -> list:
        """行为序列多样化：behaviors[bid] 支持「多候选模板」[[..],[..]]。

        每次执行以 _diversify_prob 概率从候选模板里随机挑一条，
        并排除上一次用过的，避免连号重复同一套路径（replay 检测点）。
        单模板（旧格式）时原样返回。
        """
        if not actions or not all(isinstance(a, list) for a in actions):
            return actions
        n = len(actions)
        if n == 1:
            return actions[0]
        if random.random() > self._diversify_prob:
            return random.choice(actions)
        try:
            cand = [i for i in range(n) if i != self._variant_last.get(bid, -1)]
            idx = random.choice(cand) if cand else random.randrange(n)
        except ValueError:
            idx = random.randrange(n)
        self._variant_last[bid] = idx
        self.recorder.log(f"  行为[{bid}] 命中候选模板 #{idx+1}/{n}",
                          app_name, "DEBUG")
        return actions[idx]

    # ---------- 动作执行 ----------
    def _run_actions(self, actions: list, app_name: str, bid: str) -> bool:
        # 第3项（AUTOP-NL-2026-10-22）：把当前行为 ID 挂到实例上，
        # 供 click_first 在未写 candidates_from 时自动推断词表类别。
        self._current_bid = bid
        all_ok = True
        for act in actions:
            # v6 S1：编译层只做**校验**，不接管执行。
            # 为什么编译失败也必须继续跑：如果这里 `continue`，一个"新加了但没登记
            # 映射"的 type 会让整条链静默失效，而日志只留一句 WARN —— 那是最难查的
            # 故障形态。所以失败只记 WARN，随后照旧用原 dict 执行，由分派表决定命运
            # （未知 type 仍会被 _run_kind 记「未知动作类型」并返回 False）。
            self._validate_step(act, app_name)
            try:
                ok = self._exec_step(act, app_name)
            except StepError as e:
                # 真人式处理：找不到就挠头一下，继续下一个意图，不硬崩
                self.recorder.log(f"步骤失败: {e}", app_name, "WARN")
                all_ok = False
                self.human.think()
                continue
            if not ok:
                # dismiss_popups 返回 False = 屏幕干净、无弹窗可关，这正是清扫动作
                # 的目标状态，不应算失败（2026-10-25 蛋花实测：干净屏被判「步骤失败」，
                # 把已成功的签到行为整体标成「执行未完成」）。
                if act.get("type") == "dismiss_popups":
                    self.recorder.log("弹窗清扫: 屏幕干净，无需处理", app_name)
                    continue
                # 2026-11-04：顶层 optional 步骤未命中 -> 放行，与 any_of 契约对齐。
                # 但只放行"真未命中"的两种形态，避免掩盖坐标过时/点错：
                #   ① click_point 仅 images 无坐标（飞猪更新弹窗关X / 红果「立即签到」）
                #      —— 模板不命中是**常态**（无弹窗/已签日按钮变灰），不是失败；
                #   ② click_first 候选全未出现（已签态/可选元素）—— 找不到就跳过。
                # 不放行：有坐标的 click_point 落地校验失败 = 点了却没到目标页
                # （坐标过时/点错，如全民K歌 scale 问题），应严格报告。
                # any_of 已在内部放行（返回 True）；any_of/random 分支内走
                # _dispatch_probe，不经这里，分支判定契约不受影响。
                if act.get("optional"):
                    t = act.get("type")
                    no_coord = (act.get("x") is None and act.get("y") is None)
                    miss_kind = self._last_fail or ""
                    passthrough = (
                        (t == "click_point" and no_coord)
                        or (t == "click_first"
                            and "所有候选均未出现" in miss_kind))
                    if passthrough:
                        self.recorder.log(
                            f"步骤未命中（optional 放行）: "
                            f"{miss_kind or '动作未命中'}",
                            app_name, "WARN")
                        continue
                # B6：定位类动作未命中返回 False，按原消息文本记「步骤失败」
                self.recorder.log(
                    f"步骤失败: {self._last_fail or '动作未命中'}",
                    app_name, "WARN")
                all_ok = False
                self.human.think()
        return all_ok

    def _validate_step(self, act, app_name: str) -> None:
        """编译期校验（v6 S1）。**只记日志，不影响执行**。

        能抓到的都是"配置写错、跑起来必然静默失败"的形态：未知 type、
        action 与 type 冲突、click 缺定位字段、flow 既无 branches 也无 candidates_from。
        每条只在**该 step 首次**出现时记一次，避免一次运行刷满日志。
        """
        if not isinstance(act, dict):
            return
        key = id(act)
        seen = getattr(self, "_validated_ids", None)
        if seen is None:
            seen = self._validated_ids = set()
        if key in seen:
            return
        seen.add(key)
        try:
            compile_step(act)
        except ValueError as exc:
            self.recorder.log(f"步骤编译校验失败（仍按原样执行）: {exc}",
                              app_name, "WARN")

    def _exec_step(self, act: dict, app_name: str) -> bool:
        return self._dispatch_step(act, app_name)

    # B7：正常路径与探测路径分拆 —— 视觉门控从实例标志位改为显式参数链。
    # 教训：早期用 `self._probe_no_vision` 在 any_of 循环里"临时改写再还原"，
    # 一旦中途异常或新增直调点就会留下脏状态，且测试只能靠反证用例兜底。
    # 现在 allow_vision 显式贯穿：_dispatch_probe -> _step_click_* / any_of 分支。
    def _dispatch_step(self, act: dict, app_name: str) -> bool:
        """正常路径：动作前 delay+maybe_wander（原 ritual=True 语义）。"""
        self.human.delay()
        # 随机"分心"
        if self.d is not None:
            self.human.maybe_wander(self.d)
        return self._run_kind(act, app_name, allow_vision=True)

    def _dispatch_probe(self, act: dict, app_name: str, allow_vision: bool) -> bool:
        """探测路径：any_of/random 分支内动作，无 ritual，视觉门控显式参数。"""
        return self._run_kind(act, app_name, allow_vision=allow_vision)

    def _run_kind(self, act, app_name: str, allow_vision: bool = True) -> bool:
        """按 type 分派到对应 step 原语，返回 True=成功/命中，False=未命中。

        入参可以是 dict（现有全部调用路径），也可以是 v6 的 Step 对象；
        **执行永远用 `step.raw`** —— 编译层不参与执行，所以行为零变化。
        不做"从 Step 反推 legacy type"这种转换：反推是双向映射，一旦某条
        映射漏了，就会点错坐标或漏点一步，而且很难在测试里被发现。
        """
        raw = act.raw if isinstance(act, Step) else act
        t = raw.get("type")
        fn = {
            "wait": self._step_wait,
            "think": self._step_think,
            "click": self._step_click,
            "click_text": self._step_click_text,
            "click_id": self._step_click_id,
            "click_desc": self._step_click_desc,
            "click_point": self._step_click_point,
            "click_first": self._step_click_first,
            "swipe": self._step_swipe,
            "swipe_natural": self._step_swipe_natural,
            "captcha": self._step_captcha,
            "random": self._step_random,
            "any_of": self._step_any_of,
            "scroll_to": self._step_scroll_to,
            "back": self._step_back,
            "home": self._step_home,
            "dismiss_popups": self._step_dismiss_popups,
            "reward": self._step_reward,
            "ensure": self._step_ensure,
        }.get(t)
        if fn is None:
            self.recorder.log(f"未知动作类型: {t}，已忽略", app_name, "WARN")
            return False
        cat = ACTION_CATEGORY.get(t)
        if cat is None:
            # 分派表有、分类表没有：新增 type 忘了登记分类，属维护错误。
            self.recorder.log(f"动作类型未登记分类: {t}，已按失败处理", app_name, "WARN")
            return False
        if t in _VISION_GATED_STEPS:
            res = fn(raw, app_name, allow_vision=allow_vision)
        else:
            res = fn(raw, app_name)
        return self._check_return(t, cat, res, app_name)

    def _check_return(self, t: str, cat: str, res, app_name: str) -> bool:
        """按类别校验返回值契约。None 只在允许它的类别里算成功。

        为什么不再统一 `None -> True`：那会让"根本没判断"与"判断通过"同义。
        例如 `_step_click_point` 丢了 `_verify_landing` 的返回值时，
        落地失败（False）在调用方看来和成功一样，报告因此长期失真。
        """
        allowed = _RETURN_CONTRACT.get(cat) or {"bool"}
        if res is None:
            if "none" in allowed:
                return True
            self.recorder.log(
                f"返回值契约违反: {t}({cat}) 返回 None，按失败处理", app_name, "WARN")
            return False
        if isinstance(res, bool):
            return res
        self.recorder.log(
            f"返回值契约违反: {t}({cat}) 返回 {type(res).__name__}，已按真值折算",
            app_name, "WARN")
        return bool(res)

    def _dispatch(self, act: dict, app_name: str, ritual: bool) -> bool:
        """兼容薄包装（test_diversify_sensor.py:105 直调；B7 后内部走 step/probe）。"""
        if ritual:
            return self._dispatch_step(act, app_name)
        return self._dispatch_probe(act, app_name, allow_vision=True)

    def _step_any_of(self, act, app_name, allow_vision=True):
        """条件分支：按顺序尝试多组动作，第一组**命中**即停。

        为什么需要：App 落地页不确定（开屏广告/活动弹窗/新手引导/上次退出的
        tab/登录态/灰度活动页都会改变落地页）。同一行为的入口可能在首屏、
        也可能只在二级页 ——
          * 写死前置步 → 堵死首屏那条路径；
          * 只写首屏锚点 → 页面漂移时全灭。
        `any_of` 让两条路径共存：先试首屏，没命中再跳「我的」重试。

        choices 中每个 choice 是一串动作；**该串全部动作都返回成功**才算命中。
        注意：分支内的定位动作应写 `optional: false`（默认），
        否则"没找到"会被当成成功，分支立刻终止。

        B7：视觉门控显式参数链 —— 只有最后一个分支 allow_vision=True，
        前面的分支是"便宜的探测"：本机 VLM 图像请求常 90s 超时，
        若探测分支也走视觉兜底，一次 any_of 可能白等好几分钟。
        嵌套（any_of 内的 any_of）时内层用当前 allow_vision 收窄。

        用法：
            - type: any_of
              choices:
              - - {type: click_first, candidates: [{type: text, value: 签到}]}
              - - {type: click_point, x: 0.9, y: 0.915, optional: true}
                - {type: think}
                - {type: click_first, candidates: [{type: text, value: 签到}]}
              optional: true      # 全部分支都没命中时是否放行
        """
        choices = act.get("choices") or []
        if not choices:
            self.recorder.log("any_of 动作缺少 choices，已忽略", app_name, "WARN")
            return False
        n = len(choices)
        # B1（2026-10-30）：整次 any_of 的总预算。act 显式 total_timeout 优先，
        # 否则用实例默认（_any_of_total，来自 config.timeouts.any_of_total，默认 30 = 现行为）。
        # 注意：预算只在**分支边界**检查，单个分支内部仍可能超预算（不打断进行中的分支，
        # 否则会在点击到一半时中断，留下不确定状态）。
        budget = act.get("total_timeout")
        if budget is None:
            budget = getattr(self, "_any_of_total", 30.0)
        try:
            budget = float(budget)
        except (TypeError, ValueError):
            budget = 30.0
        deadline = (time.time() + budget) if budget > 0 else None
        for i, chosen in enumerate(choices):
            if deadline is not None and time.time() >= deadline:
                self.recorder.log(
                    f"any_of 总预算 {budget:g}s 用尽，跳过剩余 {n - i} 个分支",
                    app_name, "WARN")
                break
            steps = chosen if isinstance(chosen, list) else [chosen]
            branch_vision = (i == n - 1) and allow_vision
            ok = True
            for a in steps:
                try:
                    if not self._dispatch_probe(a, app_name,
                                                allow_vision=branch_vision):
                        ok = False
                        break
                except StepError as e:
                    self.recorder.log(f"any_of 分支#{i + 1} 步骤失败: {e}",
                                      app_name, "DEBUG")
                    ok = False
                    break
            if ok:
                self.recorder.log(f"any_of 分支#{i + 1}/{n} 命中",
                                  app_name, "DEBUG")
                return True
            self.recorder.log(f"any_of 分支#{i + 1}/{n} 未命中", app_name, "DEBUG")
        if act.get("optional", False):
            # 2026-10-29 契约修正：日志一直写"放行"，代码却 return False，
            # 于是 optional 的 any_of 全 miss 仍被外层记成"步骤失败"，
            # 体检报告的红黄绿因此失真。放行就是成功，返回值必须与日志同义。
            self.recorder.log("any_of 全部分支未命中，optional 放行", app_name, "WARN")
            return True
        # B6：全 miss 非 optional 不再抛 StepError，记 WARN 返回 False
        self.recorder.log("any_of 全部分支均未命中", app_name, "WARN")
        return False

    def _step_random(self, act, app_name, allow_vision=True):
        """行为分支随机化：choices 中随机择一执行。
        每个 choice 可以是单个动作 dict，或一串动作 list。

        2026-10-29 契约修正：原实现不返回任何值（None），子步骤失败被静默吞掉，
        整步在 `_run_kind` 里因 None->True 一律算成功。现在汇总子步骤：
        任一子步骤失败即 False；子步骤抛 StepError 也记 False（不向上抛，
        与 any_of 分支内的处理保持一致）。
        """
        choices = act.get("choices") or []
        if not choices:
            self.recorder.log("random 动作缺少 choices，已忽略", app_name, "WARN")
            return False
        chosen = random.choice(choices)
        steps = chosen if isinstance(chosen, list) else [chosen]
        ok = True
        for a in steps:
            try:
                if not self._dispatch_probe(a, app_name, allow_vision=allow_vision):
                    ok = False
            except StepError as e:
                self.recorder.log(f"random 分支步骤失败: {e}", app_name, "DEBUG")
                ok = False
        return ok

    # ---------- 原语实现 ----------
    def _step_wait(self, act, app_name):
        time.sleep(float(act.get("seconds", 1.0)))

    def _step_think(self, act, app_name):
        self.human.think()

    # ---- 统一点击原语（2026-10-25 整理）----
    # click_text / click_id / click_desc 原本是同一段 20 行代码的三份拷贝，
    # 只有 selector 前缀和日志措辞不同 —— 改一处忘两处（B6「未命中不抛
    # StepError」的修正当年就只打进了 click_text）。现合并为 _step_click
    # 一份实现；旧 type 名保留为别名，老配置/老测试无需改写。
    # 每项：(act 字段名, 日志动词, 失败措辞, 视觉兜底 tag 前缀)
    _CLICK_KINDS = {
        "text": ("text", "点击文本", "未找到文本按钮", "click_text"),
        "id":   ("res_id", "点击控件", "未找到控件 id", "click_id"),
        "desc": ("desc", "点击描述", "未找到描述按钮", "click_desc"),
    }

    def _step_click(self, act, app_name, allow_vision=True):
        """统一点击原语：`by` 选选择器（text 默认 / id / desc），点中返回 True。

        知识库候选 + 视觉兜底的行为与旧 click_text 完全一致；
        B6：未命中不再抛 StepError，detail 写入 `_last_fail` 并返回 False。
        """
        by = str(act.get("by") or "text").lower()
        spec = self._CLICK_KINDS.get(by)
        if spec is None:
            self.recorder.log(f"未知 click by: {by}，已忽略", app_name, "WARN")
            self._last_fail = f"未知 click by: {by}"
            return False
        field, verb, fail_word, tag = spec
        value = act.get(field, "")
        primary = f"{by}={value}"
        # back_retry（AUTOP-FAMILY-2026-11-01）：目标文本不在树上时，按 BACK
        # 重新露出底层导航后重试，最多 back_retry 次。应对「全屏内容页盖住底部
        # 导航」的 App（悟空浏览器实测：全屏短剧播放页盖住 tab，「赚钱」不在树上，
        # 按 BACK 后退到带导航页，导航仅短暂可见 ~2s，需在可见窗口内点击）。
        # 只在「未命中」时触发；每次按 BACK 后校验前台，离开目标 App 即冷重启
        # （避免 BACK 把 App 退到桌面后继续盲找）。
        back_retry = int(act.get("back_retry") or 0)
        try:
            _pkg = (self.d.info.get("currentPackageName") or "") if self.d else ""
        except Exception:
            _pkg = ""
        for attempt in range(back_retry + 1):
            obj, has_entry, attempted = self._locate_with_kb(
                app_name, primary, act.get("timeout", 6))
            if obj is not None:
                try:
                    self._click_tracked(
                        obj, app_name, primary, has_entry,
                        f"{verb}: {value}",
                        # StaleObject 自救：点击前元素失效时按同 selector 重定位
                        relocate=lambda: self._locate_with_kb(app_name, primary, 2.0)[0])
                    return True
                except StepError:
                    # 点击前元素失效（stale 重定位失败 / RPC 溢出超限）：
                    # 有余量则按「未命中」处理，交给下方 BACK 重露导航再扫；
                    # 否则透传（与 back_retry=0 时行为一致，上层记「步骤失败」）。
                    self.recorder.log(
                        f"click[{by}={value}] 点击前元素失效，按 BACK 后重试",
                        app_name, "DEBUG")
                    if attempt >= back_retry:
                        raise
            if attempt >= back_retry:
                break
            self.recorder.log(
                f"click[{by}={value}] 第{attempt + 1}次未命中，按 BACK 后重试",
                app_name, "DEBUG")
            try:
                if self.d is not None:
                    self.d.press("back")
            except Exception as e:
                self.recorder.log(
                    f"click[{by}={value}] BACK 重试异常: {type(e).__name__}: {e}",
                    app_name, "DEBUG")
                break
            time.sleep(1.5)
            try:
                fg = (self.d.info.get("currentPackageName") or "") if self.d else ""
            except Exception:
                fg = ""
            if _pkg and fg and fg != _pkg:
                self.recorder.log(
                    f"click[{by}={value}] BACK 后前台={fg}（非目标 {_pkg}）"
                    f"-> 冷重启再试", app_name, "WARN")
                try:
                    self._open_app(_pkg, app_name, reset=True)
                except Exception:
                    break
        if self._vision_or_miss(act, app_name, f"{tag}[{value}]",
                                allow_vision=allow_vision):
            return True
        self._last_fail = f"{fail_word}: {value}"
        return False

    # ---- 兼容别名：老配置/老测试仍写 click_text / click_id / click_desc ----
    def _step_click_text(self, act, app_name, allow_vision=True):
        """别名 → _step_click(by="text")。保留方法名供 facade 直调与测试打桩。"""
        return self._step_click(dict(act, by="text"), app_name, allow_vision)

    def _step_click_id(self, act, app_name, allow_vision=True):
        """别名 → _step_click(by="id")。"""
        return self._step_click(dict(act, by="id"), app_name, allow_vision)

    def _step_click_desc(self, act, app_name, allow_vision=True):
        """别名 → _step_click(by="desc")。"""
        return self._step_click(dict(act, by="desc"), app_name, allow_vision)

    def _step_click_point(self, act, app_name):
        # 若本步绑定了图片/VLM 定位，优先用视觉兜底定位（应对布局/分辨率变化）。
        # `vision: false` 可显式关闭视觉兜底 —— 用于「导航到我的」这类
        # **每个行为都要跑**的固定步骤：本机 VLM 图像请求常 90s 超时，
        # 而比例坐标已被 18 个 App 实机验证可靠，走视觉只会白白拖慢且更不稳。
        if act.get("vision", True) and (
                act.get("images") or act.get("template")
                or act.get("vlm_prompt") or act.get("prompt")):
            # desc 里带的是作者写的人类语义（如「签到弹窗『立即领取』」）。把它带进
            # 视觉兜底日志，才能让「签到按钮确实被点过」这句话在日志里被复核到 ——
            # 否则模板命中只留一句 click_point[visual]，事后无法证明点的是签到按钮
            # （2026-10-25 用户判定规则：复核过点击才算签到成功）。
            vdesc = (f"click_point[{act['desc']}]" if act.get("desc")
                     else "click_point[visual]")
            if self._vision_click(act, app_name, vdesc):
                # 2026-10-24：视觉兜底命中后同样要校验落地（原先直接 return 跳过了 expect）。
                # 2026-10-29：校验结果必须**返回**，不能只调用 —— 落地失败要能传上去。
                if act.get("expect"):
                    return self._verify_landing(act, app_name)
                return True
        wh = win_wh(self.d)
        # 2026-10-30 全量跑实测：`click_point` 只配 images（纯图像锚点、无坐标兜底）时，
        # 视觉一旦 miss 就会掉到这里，float(None) 抛 TypeError **中断整个 App**。
        # 快手 bonus / 飞猪旅行 都是这么崩的。没有坐标就没有可点的地方，
        # 按「未命中」返回，交给 optional / 步骤失败逻辑处理，不要崩。
        if act.get("x") is None or act.get("y") is None:
            self._last_fail = "图像锚点未命中且无坐标兜底"
            return False
        x, y = float(act.get("x")), float(act.get("y"))
        if wh and x <= 1.0 and y <= 1.0:
            x, y = int(wh[0] * x), int(wh[1] * y)
        x, y = self.human.jitter_point(int(x), int(y))
        if self.dry_run:
            return True
        # 2026-10-30：phash 基准是「点击前」那一态，点击后页面必然变样 -> 必然失配。
        # 开启 accept_structure_change 的步骤，点击前先存一份节点集合，
        # 校验失败时用「结构变化」兜底（默认关闭，老配置零影响）。
        nodes_before = None
        if (act.get("expect") or {}).get("accept_structure_change"):
            nodes_before = self._screen_nodes(self._dump_safe())
        # F2：统一点击入口（误触-回退/限流长停），替代裸 d.click
        self.human.tap(self.d, x, y)
        self.recorder.log(f"点击坐标: ({x},{y})", app_name)
        # 2026-10-23 落地校验：坐标是盲点（拼多多圆形入口偏 80px 就静默走错页），
        # 点完必须验证「落到了预期页面」。多信号投票见 landing.py。
        # 2026-10-29：返回值契约 —— True=落地通过，False=落地失败，None=无可判信号。
        if act.get("expect"):
            # 开关没开时保持原来的调用形态（不传 nodes_before）——老配置与既有
            # 测试桩的签名都零影响；只有显式开启的步骤才多传一个参数。
            if nodes_before is None:
                return self._verify_landing(act, app_name, x, y)
            return self._verify_landing(act, app_name, x, y,
                                        nodes_before=nodes_before)
        return True

    @staticmethod
    def _is_target_page_from_dump(xml, expect):
        """B3：用 expect.text_any 判断当前是否已经是目标页。

        只认 text_any —— 它是最稳的语义信号。没有配 text_any 的步骤
        （目前 34 份配置里只有 3 处配了）一律返回 False，即保持原重试行为。
        """
        if not xml:
            return False
        want = [str(w) for w in (expect.get("text_any") or []) if str(w).strip()]
        if not want:
            return False
        joined = " ".join(
            m.group(2) for m in
            re.finditer(r"""(?:text|content-desc)=(["'])(.{1,40}?)\1""", xml))
        return any(w in joined for w in want)

    def _verify_landing(self, act, app_name, x=None, y=None, no_retry=False,
                        nodes_before=None):
        """按 act['expect'] 做多信号落地校验；失败可重试（expect.retry）。

        2026-10-23 真机修正：校验截图必须等页面落定。拼多多实测——点击圆形入口后
        立即（3s 内）截图，整页 dHash 距离 31（过渡动画帧）；等 1.5s 后同一页面距离 3。
        所以每轮先 sleep settle（逐轮加倍），失败再考虑重点击。

        no_retry=True：只探一次、不重复点击（用于 click_first 的「弱命中」探测，
        避免为了验证一个猜测的候选而乱点）。
        """
        import landing
        import time as _time
        expect = act.get("expect") or {}
        retries = 0 if no_retry else int(expect.get("retry", 0) or 0)
        settle = float(expect.get("settle", 1.5))
        for attempt in range(retries + 1):
            if not self.dry_run:
                _time.sleep(settle * (attempt + 1))
            try:
                img = self.d.screenshot()
            except Exception as exc:  # noqa: BLE001
                self.recorder.log(f"落地校验跳过: 截图失败 {type(exc).__name__}",
                                  app_name, "WARN")
                return None
            xml = None
            try:
                xml = self.d.dump_hierarchy()
            except Exception:  # noqa: BLE001 - 节点不可用不影响图形信号
                xml = None
            try:
                pkg = (self.d.app_current() or {}).get("package")
            except Exception:  # noqa: BLE001
                pkg = None
            res = landing.check_landing(img, expect, xml=xml, pkg=pkg)
            tag = landing.describe(res["signals"])
            if res["ok"] is None:
                self.recorder.log(f"落地校验: 无可判信号（{tag}）", app_name, "DEBUG")
                return None
            if res["ok"]:
                self.recorder.log(f"落地校验通过: {tag}", app_name)
                return True
            self.recorder.log(f"落地校验失败（第{attempt + 1}次）: {res['reason']} | {tag}",
                              app_name, "WARN")
            # 结构变化兜底（2026-10-30，默认关闭，按步骤显式开启）：
            # 只救 **phash 失配** 这一种，且要求页面节点结构确实变了。
            # 不救 text_nodes 失配 —— 文案没出现是有效信号，不能靠「页面变了」放行。
            if (nodes_before is not None
                    and expect.get("accept_structure_change")
                    and res["signals"].get("phash") is False):
                diff = self._structure_diff(nodes_before,
                                            self._screen_nodes(xml))
                if diff >= float(expect.get("structure_change_min", 0.15)):
                    self.recorder.log(
                        f"落地校验: phash 失配但页面结构已变化 {diff:.0%}，"
                        f"判为已落地（accept_structure_change，证据等级=结构变化）",
                        app_name)
                    return True
                self.recorder.log(
                    f"落地校验: phash 失配且结构仅变 {diff:.0%}"
                    f"（阈值 {float(expect.get('structure_change_min', 0.15)):.0%}）",
                    app_name, "DEBUG")
            # B3（2026-10-30）：重试前先看同一次 dump 是不是已经是目标页。
            # phash 会因为「签到前/签到后弹窗内容变化」而失配，但终态文案稳定出现；
            # 这种情况再点一次纯属浪费（快手实测一次无效重试 13s）。
            if attempt < retries and self._is_target_page_from_dump(xml, expect):
                self.recorder.log("落地校验失败但已是目标页，跳过重试", app_name)
                return True
            if attempt < retries and x is not None and y is not None and not self.dry_run:
                self.human.tap(self.d, x, y)
                self.recorder.log(f"落地校验重试点击: ({x},{y})", app_name)
        return False

    def _expand_kb_pool(self, app_name, pool, primary):
        """R1：查知识库并把 kb 推荐 selector 展开去重追加到 pool；无可用候选返回 False。

        kb_cands 逐个 _parse_sel，按 (k, v) 去重追加 (k, v, primary if has_entry else None)。
        无知识库记录时 kb_cands=[primary] 正常入池且 primary=None（原语义）；
        记录已 disabled 时 kb_cands=[] 返回 False（调用点跳过该候选）。
        """
        kb_cands, has_entry = self._kb_candidates(app_name, primary)
        if not kb_cands:
            return False
        for sel in kb_cands:
            k, v = _parse_sel(sel)
            if (k, v) not in [(p[0], p[1]) for p in pool]:
                pool.append((k, v, primary if has_entry else None))
        return True

    def _step_click_first(self, act, app_name, allow_vision=True):
        """依次尝试多个候选，点中第一个存在的；每个候选先查知识库（disabled 跳过）。"""
        pool = []           # [(kind, value, primary)]，primary 为知识库主 selector
        for cand in act.get("candidates", []) or []:
            kind, value = cand.get("type"), cand.get("value", "")
            if not value:
                continue
            if not self._expand_kb_pool(app_name, pool, f"{kind}={value}"):
                continue    # 知识库 disabled 的候选直接跳过
        # 记录「作者显式写的候选」数量：合并全局词表后，只有这部分值得给满 2s 定位超时。
        explicit_count = len(pool)
        # 第5步（AUTOP-SELFSEARCH-2026-10-20）：全局词表自搜寻，并入池排在显式之后。
        # 第3项（AUTOP-NL-2026-10-22）：未写 candidates_from 时按当前行为自动推断类别，
        # 使「只写 3 个候选词」的配置也能吃到全 App 共性词表。
        from_ = act.get("candidates_from")
        if not from_:
            from_ = category_for_intent(getattr(self, "_current_bid", ""))
        if from_:
            try:
                merged = candidates_for(from_, {"extra_candidates": self._app_extras(app_name)})
            except ValueError:
                merged = []
                self.recorder.log(f"未知 candidates_from: {from_}，已忽略", app_name, "WARN")
            except Exception:
                merged = []
            for w in merged:
                if not w:
                    continue
                if ("text", w) in [(p[0], p[1]) for p in pool]:
                    continue
                if not self._expand_kb_pool(app_name, pool, "text=" + w):
                    continue
        zone = act.get("zone")
        scroll_left = int(act.get("scroll_retry", 0))
        # back_retry（AUTOP-FAMILY-2026-11-01）：候选全部未出现且 scroll_retry 用尽时，
        # 按 BACK 重新露出底层导航后重扫一遍候选池。与 _step_click 的 back_retry 同理，
        # 应对「全屏内容页盖住底部导航」的 App（悟空浏览器 watch：看剧/任务中心等在
        # 底部导航上，播放页盖住后候选全不可见）。缺省 0 = 行为不变。
        back_left = int(act.get("back_retry") or 0)
        try:
            _pkg = (self.d.info.get("currentPackageName") or "") if self.d else ""
        except Exception:
            _pkg = ""
        # 2026-10-23 真机实测修正（性能回归）：
        # 第 3 项把全局词表并进 pool 后，候选数从 ~12 涨到 ~45，
        # 而每个候选原本各给 2s 定位超时 → 单跳最坏 45×2=90s，
        # 重 App（页面未就绪时全 miss）直接吃满 150s 超时，17 个 App 全 TIMEOUT。
        # 现在：显式候选（作者精选）仍给 2s；合并来的全局词只给 0.35s 探针；
        # 整跳再加一个总预算上限，避免候选池膨胀拖垮整条链。
        explicit_n = explicit_count
        probe_fast = 0.35
        # AUTOP-火山版-2026-11-04（M2 层8 / P0-2）：**预算参数化**。
        # 原先写死 max(30, 显式候选*2+10)：火山版 watch 首分支 4 个显式候选算出
        # 30s，正好等于 any_of 默认总预算 30s —— 分支#1 一 miss 就把预算吃满，
        # 分支#2（底部『我的』坐标兜底）被「any_of 总预算用尽，跳过剩余 1 个分支」
        # 吞掉（M2 11-01 L1479）。现在支持 step 级 `budget:` 覆盖，配合 any_of 的
        # `total_timeout:` 即「每分支独立预算」；不写 budget 时完全同旧行为。
        cfg_budget = act.get("budget")
        if cfg_budget is None:
            budget = max(30.0, explicit_n * 2.0 + 10.0)   # 显式候选要够用，全局词只吃剩余预算
        else:
            try:
                budget = float(cfg_budget)
            except (TypeError, ValueError):
                budget = max(30.0, explicit_n * 2.0 + 10.0)
        t_start = time.time()
        while True:
            for i, (k, v, prim) in enumerate(pool):
                if time.time() - t_start > budget:
                    break
                per = 2.0 if i < explicit_n else probe_fast
                res = self._locate(k, v, timeout=per, **({"zone": zone} if zone else {}))
                if res.hit:
                    # 2026-10-24 修正「全局词表劫持」：
                    # 显式候选（作者精选）命中即算数；合并进来的全局词只是「宽泛猜测」，
                    # 命中不等于语义正确（实测三次踩坑：任务中心→立即签到、任务→首页、
                    # 立即签到→现金）。
                    # 规则：本步声明了 expect（=明确知道该落在哪一页）时，只允许显式候选点击，
                    # 弱命中直接跳过继续找 —— 因为点错页面的代价远大于这一步不点。
                    if act.get("expect") and i >= explicit_n:
                        self.recorder.log(
                            f"跳过弱命中({k}){v}（本步有落地校验，只认显式候选）",
                            app_name, "DEBUG")
                        continue
                    obj = res.obj
                    if prim:
                        self.knowledge.mark_ok(app_name, prim)
                    if not self.dry_run:
                        # StaleObject 自救：按同 (kind, value) 重定位再点。
                        try:
                            self._click_obj(obj, relocate=lambda: self._relocate_candidate(k, v))
                        except StepError:
                            # 点击前元素失效：按「未命中」处理，换下一个候选；
                            # 池尽后由 scroll_retry/back_retry 重扫，否则落
                            # vision/miss 返回 False（不再崩流程）。
                            self.recorder.log(
                                f"多候选命中但点击前失效 ({k}){v}，换下个候选",
                                app_name, "DEBUG")
                            continue
                    self.recorder.log(f"多候选命中并点击: ({k}){v}", app_name)
                    # 2026-10-24：click_first 点中后同样做落地校验（与 click_point 一致），
                    # 否则「点中了 A 却落在 B」仍然无声无息。
                    # 2026-10-29：校验结果必须**返回**，不能只调用 —— 与 _step_click_point
                    # 的同类修复对齐。此前丢了返回值，「点中了 A 却落在 B」仍记成功。
                    if act.get("expect"):
                        return self._verify_landing(act, app_name)
                    return True
            # 本轮全未命中：按 scroll_retry 次数翻页重试（自搜寻拓展）
            if scroll_left > 0:
                scroll_left -= 1
                self.human.natural_swipe(self.d)
                self.human.think()
                continue
            # scroll_retry 用尽仍全未命中：按 back_retry 次数 BACK 重露导航再扫。
            if back_left > 0:
                back_left -= 1
                self.recorder.log(
                    f"click_first 候选全未命中，按 BACK 后重扫（剩 {back_left} 次）",
                    app_name, "DEBUG")
                try:
                    if self.d is not None:
                        self.d.press("back")
                except Exception as e:
                    self.recorder.log(
                        f"click_first BACK 重试异常: {type(e).__name__}: {e}",
                        app_name, "DEBUG")
                    break
                time.sleep(1.5)
                try:
                    fg = (self.d.info.get("currentPackageName") or "") if self.d else ""
                except Exception:
                    fg = ""
                if _pkg and fg and fg != _pkg:
                    self.recorder.log(
                        f"click_first BACK 后前台={fg}（非目标 {_pkg}）-> 冷重启再试",
                        app_name, "WARN")
                    try:
                        self._open_app(_pkg, app_name, reset=True)
                    except Exception:
                        break
                t_start = time.time()   # 重扫给全新预算
                continue
            break
        # 全失败：回写本次尝试过（有知识库记录）的主 selector 失败计数
        self._kb_mark_fail(app_name, [p[2] for p in pool])
        if self._vision_or_miss(act, app_name, "click_first[all-candidates]",
                                allow_vision=allow_vision):
            return True
        if act.get("optional", False):
            # optional：候选全部未出现 —— 这里**必须返回 False**，不能"放行"。
            # 原因：click_first 最常见的用法是当 any_of 的**分支**，而 any_of 判
            # 「分支是否命中」的依据就是这个返回值（见 _step_any_of docstring：
            # 「分支内的定位动作应写 optional: false，否则"没找到"会被当成成功，
            # 分支立刻终止」）。若这里返回 True，any_of 会在第 1 个分支就收工，
            # 后续"跳到我的再试一次"的兜底分支永远不执行 —— any_of 形同虚设。
            # 2026-10-29：原日志写"optional 放行"，与返回值相反，读日志的人会以为
            # 这步没算失败。改成如实描述，避免再次误导体检结论。
            self.recorder.log(
                f"候选全部未出现，optional 仅抑制告警（返回值仍为 False，"
                f"any_of 分支依赖此语义）: {act.get('candidates')}", app_name, "WARN")
            return False
        # B6：非 optional 未命中不再抛 StepError，detail 写入 _last_fail 返回 False
        self._last_fail = f"所有候选均未出现: {act.get('candidates')}"
        return False

    def _step_swipe(self, act, app_name):
        # 2026-10-25 修 bug（抖音火山版校准实测踩到）：natural:true 曾经**忽略
        # from/to** 且永远向下滑 —— human.natural_swipe 内部自己随机起终点，
        # 想把「向上滑回顶」写成 natural:true，结果连滑到底，预约行被推得更远。
        # 现在：给了 from/to 就按坐标走人类轨迹（与普通 swipe 同一条轨迹链）；
        # 只有省略 from/to 时才保留旧的「随机自然滑动」语义（recorder 录制的
        # swipe_natural 走这条，行为不变）。
        f, t = act.get("from"), act.get("to")
        if act.get("natural", False) and self.d and not (f and t):
            self.human.natural_swipe(self.d)
            self.recorder.log("自然滑动(随机)", app_name)
            return True
        wh = win_wh(self.d)
        f, t = act.get("from"), act.get("to")
        if not (f and t and wh):
            raise StepError("swipe 需要 from/to 坐标")
        pct = lambda v: (  # noqa: E731
            int(wh[0] * v[0]), int(wh[1] * v[1])
        ) if v[0] <= 1.0 and v[1] <= 1.0 else (int(v[0]), int(v[1]))
        sx, sy = pct(f)
        ex, ey = pct(t)
        dur = float(act.get("duration", 0.6))
        if not self.dry_run:
            # 曲线轨迹优先：所有 swipe 都走人类轨迹注入（途中小幅抖动 + 变速）
            # 仅当 act 显式要求直线（straight=true）或设备异常时回退原生 swipe
            if not act.get("straight", False):
                points, intervals = self.human.trajectory.generate_gesture(
                    (sx, sy), (ex, ey))
                ok = self.human.trajectory.inject_touch(self.d, points, intervals)
                if ok:
                    self.recorder.log(
                        f"滑动(轨迹) ({sx},{sy})->({ex},{ey})", app_name)
                    return True
            self.d.swipe(sx, sy, ex, ey, duration=dur)
        self.recorder.log(f"滑动 ({sx},{sy})->({ex},{ey})", app_name)
        return True

    def _step_swipe_natural(self, act, app_name):
        """兼容别名（2026-10-25 合并）：等价于 swipe + natural:true。

        省略 from/to → 随机自然滑动（recorder 录制流走这条）；
        带 from/to → 按坐标走人类轨迹（旧实现本就支持，现由 _step_swipe 统一）。
        """
        return self._step_swipe(dict(act, natural=True), app_name)

    def _step_captcha(self, act, app_name):
        """验证码处理原语：检测滑块 -> 缺口识别 -> 拟人拖拽求解。

        act.mode: slider(默认) | 预留。滑块未出现时静默跳过（视为无需处理）。
        """
        if self.captcha is None:
            if not act.get("optional", False):
                self.recorder.log("验证码处理未启用（captcha.enabled=false 或依赖缺失），跳过",
                                  app_name, "WARN")
            return
        if self.dry_run:
            self.recorder.log("[dry-run] 将检测并处理滑块验证码", app_name)
            return
        if self.d is None:
            return
        dump = self._dump_safe()
        screen = self.captcha._screenshot(self.d)
        if not self.captcha.detect_slider(self.d, screen, dump):
            self.recorder.log("未检测到滑块验证码，跳过", app_name, "DEBUG")
            return
        self.recorder.log("检测到滑块验证码，开始求解", app_name)
        ok = self.captcha.solve(self.d, app=app_name, screen_img=screen, dump=dump)
        if not ok:
            # F2 反检测：验证码求解失败 = 风控命中信号。会话级冷却后再让
            # 上层决定去向，期间绝不重试猛点（冷却秒数记入日志）。
            cd = self.human.captcha_cooldown()
            if cd:
                self.recorder.log(
                    f"验证码失败，会话冷却 {cd:.0f}s（期间不重试）",
                    app_name, "WARN")
            raise StepError(f"滑块验证码求解失败（{self.captcha.retry_times} 次尝试）")
        self.human.think()

    def _relocate_candidate(self, k, v):
        """元素失效重定位（StaleObject 竞态自救）：按原 (kind, value) 再找一次。

        返回新元素或 None；任何 RPC 异常都吞掉返回 None（让上层走
        「步骤失败」路径，不崩）。见 locator._click_obj 坑位2。
        """
        try:
            res = self._locate(k, v, timeout=2.0)
            return res.obj if res.hit else None
        except Exception:
            return None

    def _step_scroll_to(self, act, app_name):
        """向下翻页直到出现目标文本/描述后点击（或仅查找）

        坑位（2026-10-21 回归实崩）：B6 起 `_locate` 返回 LocateResult
        （不再返回元素/None），此处旧代码把 LocateResult 当元素传给
        `_click_obj` -> `'LocateResult' object has no attribute 'rect'`。
         scroll_to 一被走到就崩，4 个 App 的回归即死于此。已修为
        res.hit/res.obj 口径。

        2026-11-01 抖音火山版 UI 变更：「预约」行文案从 text 挪到
        content-desc（'今日预约，明日领火苗' / 已预约态 '已预约，…'），
        scroll_to 只搜 text 永远找不到 → 5 页失败。故支持 `desc` 字段
        （与 text 二选一），走 descriptionContains 匹配。
        """
        # 空 desc（desc:""）要让位给 text：`"desc" in act` 对空串也为 True，
        # 曾把 value 定位成空串 -> descriptionContains("") 命中任意元素。
        if act.get("desc"):
            kind, value = "desc", act.get("desc", "")
        else:
            kind, value = "text", act.get("text", "")
        res = self._locate(kind, value, timeout=2.0)
        max_pages = int(act.get("max_pages", 6))
        page = 0
        while not res.hit and page < max_pages:
            self.human.natural_swipe(self.d)
            page += 1
            self.human.think()
            res = self._locate(kind, value, timeout=1.5)
        if not res.hit:
            raise StepError(f"滚动 {max_pages} 页仍未找到: {value}")
        if not self.dry_run:
            # StaleObject 自救：翻页后元素引用易失效，按同文本重定位再点
            self._click_obj(res.obj,
                            relocate=lambda: self._relocate_candidate(kind, value))
        self.recorder.log(f"滚动找到并点击: {value}（翻页{page}）", app_name)
        return True

    def _step_back(self, act, app_name):
        if not self.dry_run:
            self.d.press("back")
        self.recorder.log("返回", app_name)
        return True

    # ---------- F1 全局弹窗清扫 ----------

    def _maybe_sweep_popups(self, intent, bid, app_name, app_cfg=None):
        """run_app_flow 行为执行前自动清扫（全局 popups.enabled 才动）。

        默认关闭（老配置零影响）；config.yaml `popups.enabled: true` 后，
        34 份 App 配置无需任何改动即生效。

        A4（2026-10-30）：支持 per-app `popups.close_points` —— 自绘弹窗
        （dump 里没有可点文案/id）的关闭坐标，归一化 0-1，追加语义。
        """
        if not getattr(self, "_popups_enabled", False):
            return
        cfg = getattr(self, "_popups_cfg", {}) or {}
        if cfg.get("enabled") is False:
            return
        # 表合并口径（派单卡 F1.4）：
        #   texts/blacklist/ids 整表给 -> 替换模块默认表（卡规写法）；
        #   extra_texts/extra_ids/extra_blacklist -> 在默认/替换表基础上追加。
        texts = list(cfg.get("texts") or DEFAULT_POPUP_TEXTS)
        for t in (cfg.get("extra_texts") or []):
            if t not in texts:
                texts.append(t)
        ids = list(cfg.get("ids") or POPUP_CLOSE_IDS)
        for i in (cfg.get("extra_ids") or []):
            if i not in ids:
                ids.append(i)
        blacklist = list(cfg.get("blacklist") or POPUP_BLACKLIST_TEXTS)
        for b in (cfg.get("extra_blacklist") or []):
            if b not in blacklist:
                blacklist.append(b)
        # A4：全局 close_points + App 级追加（dict 整体去重）
        close_points = list(cfg.get("close_points") or [])
        if app_cfg:
            for cp in ((app_cfg.get("popups") or {}).get("close_points") or []):
                if isinstance(cp, dict) and cp not in close_points:
                    close_points.append(cp)
        act = {
            "type": "dismiss_popups",
            "max_rounds": int(cfg.get("max_rounds", 3)),
            "texts": texts,
            "ids": ids,
            "blacklist": blacklist,
            "close_points": close_points,
            "back_key": bool(cfg.get("back_key", True)),
            "corner_fallback": bool(cfg.get("corner_fallback", True)),
            # 用户：「不是主动观看的广告，也可以跳过」→ watch 流程保护在看广告
            "protect_ad": bool(cfg.get("protect_ad_in_watch", True)) and (
                intent == "watch" or "watch" in (bid or "")),
        }
        self._step_dismiss_popups(act, app_name)

    def _step_dismiss_popups(self, act, app_name):
        """弹窗清扫：每轮一个动作，顺序 文案 -> id -> 右上角坐标 -> 系统返回键。

        返回：True=关过东西；False=屏幕干净/未启用；"blocked"=资金黑名单熔断。
        """
        max_rounds = max(1, int(act.get("max_rounds", 3)))
        texts = list(act.get("texts") or DEFAULT_POPUP_TEXTS)
        ids = list(act.get("ids") or POPUP_CLOSE_IDS)
        blacklist = list(act.get("blacklist") or POPUP_BLACKLIST_TEXTS)
        close_points = list(act.get("close_points") or [])
        back_key = bool(act.get("back_key", True))
        corner = bool(act.get("corner_fallback", True))
        protect_ad = bool(act.get("protect_ad", False))
        if protect_ad:
            texts = [t for t in texts if t not in AD_CLOSE_TEXTS]

        if self.dry_run or self.d is None:
            self.recorder.log(
                f"[dry-run] 弹窗清扫（最多{max_rounds}轮，protect_ad={protect_ad}）",
                app_name)
            return False

        for rnd in range(1, max_rounds + 1):
            # A1：本轮只 dump 这一次（原来 _popup_close_one 内部还会再 dump 一次）
            xml = self._dump_safe()
            bad = next((b for b in blacklist if b in xml), None)
            if bad:
                # 资金类页面：停扫且禁用 BACK（提现确认等必须留给人）
                self.recorder.log(
                    f"弹窗清扫熔断: 出现资金类文案[{bad}]，停扫且禁用BACK",
                    app_name, "WARN")
                return "blocked"
            fp_before = self._screen_fingerprint(xml)
            if not self._popup_close_one(texts, ids, corner, back_key,
                                         app_name, rnd, xml=xml,
                                         close_points=close_points):
                return False  # 本屏无弹窗特征
            # A2：给页面一点响应时间，再比一次指纹。
            # 没变 = 点了没反应，立刻退出，不再空转到 max_rounds。
            # （2026-10-30 快手实测：连打 3 轮同一坐标 37s，什么都没关掉）
            self.human.think()
            if self._screen_fingerprint(self._dump_safe()) == fp_before:
                self.recorder.log(
                    f"弹窗清扫: 屏幕无变化，提前结束（第{rnd}轮）", app_name, "WARN")
                return False
            time.sleep(1.0)
        return True

    @staticmethod
    def _screen_nodes(xml: str) -> frozenset:
        """把 dump 压成「可点或带文案的节点」集合，供指纹与结构差异比较。

        引号无关：真机 dump 用双引号，测试桩常用单引号，两种都要认
        （2026-10-30 踩过：只认双引号会让指纹恒等，A2 永远判「没变化」）。
        """
        if not xml:
            return frozenset()
        items = []
        for tag in re.findall(r"<node[^>]*>", xml):
            m_t = re.search(r"""\btext=(["'])(.*?)\1""", tag)
            m_d = re.search(r"""\bcontent-desc=(["'])(.*?)\1""", tag)
            t = m_t.group(2) if m_t else ""
            dc = m_d.group(2) if m_d else ""
            if not t and not dc and 'clickable="true"' not in tag:
                continue
            m_b = re.search(r"""\bbounds=(["'])(.*?)\1""", tag)
            items.append((t, dc, m_b.group(2) if m_b else ""))
        return frozenset(items)

    @staticmethod
    def _structure_diff(a: frozenset, b: frozenset) -> float:
        """两个屏幕节点集合的差异度：1 - |A∩B| / |A∪B|（0=完全相同，1=毫无交集）。"""
        if not a or not b:
            return 0.0
        inter = len(a & b)
        union = len(a | b)
        return 0.0 if union == 0 else 1.0 - inter / union

    @staticmethod
    def _screen_fingerprint(xml: str) -> int:
        """dump 指纹：可点/带文案节点的 (text, desc, bounds) 排序后取确定性哈希。

        A2 用它判断「关闭动作之后屏幕到底变没变」——点了没反应就不该继续下一轮。

        为什么不用 dhash：视频流页面的 dhash 每帧都在抖，会制造假「变化」，让 A2
        失效；而弹窗是**节点结构**变化，dump 指纹对它更敏感。

        为什么不用内置 hash()：每进程随机（PYTHONHASHSEED），跨进程不可复现。
        这里用 md5 前 8 字节，同一屏在任何进程里都得到同一个值，便于日志对拍。
        """
        nodes = BehaviorRunner._screen_nodes(xml)
        if not nodes:
            return 0
        raw = "\x1f".join("\x1e".join(x) for x in sorted(nodes)).encode("utf-8")
        return int.from_bytes(hashlib.md5(raw).digest()[:8], "big")

    def _popup_close_one(self, texts, ids, corner, back_key, app_name, rnd,
                         xml=None, close_points=None):
        """单轮清扫：返回 True=执行了一个关闭动作；False=屏幕干净。

        A1：xml 由调用方传入，本函数不再自己 dump。
        A4：close_points（归一化坐标）在文案/id 之后、corner 之前按序尝试。
        corner 只在第 1 轮允许（整次清扫最多一次）：它是盲点，反复打同一个位置
        在 2026-10-30 快手实测里连打 3 轮 37s 且 0 效果；而且 corner 被禁的那一轮
        绝不能再落到 back —— 在干净屏上按 BACK 会直接退出 App。
        """
        if xml is None:
            xml = self._dump_safe()
        # 粗筛快速通道（2026-11-01 抖音火山版「复位→watch 挂起 300s」定位）：
        # 火山版首页是视频流，天然带「广告/下载/打开」等 AD markers，本函数因此
        # 永不提前返回；而逐个 _locate 会对**每个** popup 文案做一次全量 UI dump
        # （13 文案 × 重页面 3-8s/次），干净屏一轮 25-110s —— 正是 11-01 火山版
        # reserve 前扫掉 110s、复位后扫掉 47-73s、整单超 300s 的主因。
        # 先对已 dump 的 xml 做子串粗筛：**确定不在屏上**的文案/id 直接跳过，
        # 不发起 _locate。粗筛保守：t in xml 为 True 仍走精确 _locate
        # （子串可能横跨属性或只出现在 content-desc 里，多一次查询无害，绝不漏关）。
        # xml 为空（dump 失败/未知屏幕）时不粗筛，退回逐项 _locate —— 宁可慢不可漏。
        xml_s = xml or ""
        scan_texts = texts if not xml_s else [t for t in texts if t in xml_s]
        scan_ids = ids if not xml_s else [rid for rid in ids if rid in xml_s]
        for t in scan_texts:
            res = self._locate("text", t, timeout=0.8)
            if res.hit:
                self._click_obj(res.obj)
                self.recorder.log(f"弹窗清扫: 点文案[{t}]（第{rnd}轮）", app_name)
                return True
        for rid in scan_ids:
            res = self._locate("id", rid, timeout=0.5)
            if res.hit:
                self._click_obj(res.obj)
                self.recorder.log(f"弹窗清扫: 点id[{rid}]（第{rnd}轮）", app_name)
                return True
        if not any(m in xml_s for m in POPUP_AD_MARKERS):
            return False  # 无广告特征：干净屏，不动坐标/返回键
        wh = win_wh(self.d)
        # A4：per-app 关闭坐标优先于盲点 corner
        if close_points and wh:
            for cp in close_points:
                if not isinstance(cp, dict):
                    continue
                try:
                    cx, cy = float(cp["x"]), float(cp["y"])
                except (KeyError, TypeError, ValueError):
                    continue
                px, py = int(wh[0] * cx), int(wh[1] * cy)
                self.d.click(px, py)
                self.recorder.log(
                    f"弹窗清扫: close_points 点击({px},{py})"
                    f"[{cp.get('desc') or f'({cx},{cy})'}]（第{rnd}轮）", app_name)
                return True
        if corner and wh and rnd == 1:
            x, y = int(wh[0] * 0.93), int(wh[1] * 0.11)
            self.d.click(x, y)
            self.recorder.log(
                f"弹窗清扫: 右上角坐标兜底({x},{y})（第{rnd}轮）", app_name)
            return True
        if corner and not wh and back_key:
            # 取不到窗口尺寸 -> corner 打不了，退回系统返回键（用户原始需求②）
            self.d.press("back")
            self.recorder.log(f"弹窗清扫: 系统返回键（第{rnd}轮）", app_name)
            return True
        # corner 未启用（或第 2 轮起已禁用）-> 不做任何盲操作。
        # 2026-10-30：back 必须受 corner 这个「盲操作总开关」约束。否则把
        # corner_fallback 关掉之后，back 会变成 AD_MARKERS 命中就按 BACK ——
        # 而视频流首页天然带「广告/下载」字样，一按 BACK 直接退出 App。
        return False

    def _step_home(self, act, app_name):
        if not self.dry_run:
            self.d.press("home")
        self.recorder.log("回到桌面", app_name)
        return True

    # ---------- 收益识别 ----------
    def _step_reward(self, act, app_name):
        pattern = act.get("pattern")
        unit = act.get("unit", "")
        rname = act.get("name", act.get("type", "收益"))
        detail = act.get("detail", "")
        if self.dry_run:
            self.recorder.log(f"[dry-run] 将识别收益: {rname} ({pattern})", app_name)
            return
        xml = self.d.dump_hierarchy()
        cands = self._reward_candidates(xml, pattern, act)
        if not cands:
            self.recorder.log(f"本次未从页面识别到[{rname}]收益数字", app_name, "WARN")
            return
        src, m = cands[0]
        try:
            if "amount" in m.groupdict():
                amount = float(m.group("amount"))
                unit = m.groupdict().get("unit") or unit
            else:
                amount = float(m.group(1) if m.groups() else 0)
        except (ValueError, IndexError):
            self.recorder.log(f"[{rname}] 数字解析失败: {m.group(0)}", app_name, "WARN")
            return
        if len(cands) > 1:
            self.recorder.log(
                f"[{rname}] 页面有 {len(cands)} 处匹配，取 {src!r} -> {amount}{unit}",
                app_name)
        self.recorder.record_earning(app_name, rname, amount, unit, detail)

    # 只在 text / content-desc 里找收益数字，常量与坑注释已随 B8 迁至 reward_pick.py。
    def _reward_candidates(self, xml, pattern, act):
        """返回 [(来源文案, match), ...]，按「可信度」排序。"""
        out = []
        for m in _TEXT_ATTR_RE.finditer(xml or ""):
            val = m.group(1)
            mm = re.search(pattern, val)
            if mm:
                out.append((val, mm))
        if not out:
            # 退化：整份 XML 兜底（兼容跨标签的旧 pattern）
            mm = re.search(pattern, xml or "")
            if mm:
                out.append(("", mm))
        if len(out) <= 1:
            return out
        return rank_reward_candidates(
            out,
            [str(k) for k in (act.get("context") or [])],
            _BALANCE_HINTS,
            "元",
            act.get("unit") or "",
        )

    # ---------- 页面校验 ----------
    def _step_ensure(self, act, app_name):
        """确认关键页面已出现（如已进入签到页），防止误点

        坑位（2026-10-21 回归排查）：B6 起 `_locate` 返回 LocateResult，
        旧代码 `obj is None` 恒为 False —— `exists: yes` 校验静默放行
        （文本没出现也通过）、`exists: no` 恒误报。已修为 res.hit 口径。
        """
        text = act.get("text", "")
        expect = act.get("exists", "yes")
        res = self._locate("text", text, timeout=float(act.get("timeout", 6)))
        if expect == "yes" and not res.hit:
            raise StepError(f"校验失败，未出现关键文本: {text}")
        if expect == "no" and res.hit:
            raise StepError(f"校验失败，不应出现的文本却在: {text}")
        self.recorder.log(f"校验通过: {text}({expect})", app_name)
