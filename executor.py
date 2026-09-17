# -*- coding: utf-8 -*-
"""
executor.py - 执行引擎
用 uiautomator2 在 Windows 侧控制 Android 设备/模拟器，
按配置的 app 行为模板逐步执行：启动 app、找元素、模拟点击/滑动、
识别收益并交给 Recorder 记账。所有点击经 Human 模块做真人化处理。
"""
import json
import os
import random
import re
import time

try:
    from vision import VisionLocator
except ImportError:  # pragma: no cover - 允许只拷走部分文件的极端场景
    VisionLocator = None

try:
    from captcha_slider import SliderCaptchaSolver
except ImportError:  # pragma: no cover - 未拷贝 captcha_slider.py 时降级
    SliderCaptchaSolver = None

try:
    from knowledge import KnowledgeBase
except ImportError:  # pragma: no cover - 未拷贝 knowledge.py 时降级为原逻辑
    KnowledgeBase = None

try:
    from ui_page import TOP_LEVEL_LABELS, NAV_BAND_Y
except ImportError:  # pragma: no cover - 未拷贝 ui_page.py 时关闭复位功能
    TOP_LEVEL_LABELS, NAV_BAND_Y = set(), 0.80


def _parse_sel(sel):
    """把知识库 selector 拆成 (kind, value)：'text=每日签到' -> ('text','每日签到')。"""
    sel = str(sel)
    if "=" in sel:
        kind, _, value = sel.partition("=")
        if kind.strip().lower() in ("text", "id", "desc"):
            return kind.strip().lower(), value.strip()
    return "text", sel


class StepError(Exception):
    """单步失败且不可恢复"""
    pass


# 底部导航标签。锚点是这些词时，定位择优会优先取落在屏幕**底部带**的匹配 ——
# 实测页面中部也会出现同名标签（蛋花免费小说二级页 text='我的' @(575,627)，
# 而底部导航在 y≈2100+），不做区分就会点到错的元素。
NAV_LABELS = {"我的", "我", "首页", "个人中心", "我的 ", "个人中心 "}
NAV_BAND_Y = 0.80          # 底部 20% 视为导航带


class Executor:
    def __init__(self, serial: str, human, recorder, dry_run: bool = False,
                 config: dict = None, base_dir: str = None):
        self.serial = serial
        self.human = human
        self.recorder = recorder
        self.dry_run = dry_run
        self.d = None  # uiautomator2 Device
        # any_of 的"探测分支不许走视觉兜底"开关。
        # 必须在 __init__ 里给默认值：`_step_click_text/_click_id/_click_desc/
        # _click_first` 都会**直接读取**它，而 `_step_any_of` 只在进入分支时改它。
        # 若不给默认值，任何不含 any_of 的行为走到"元素没找到 -> 该走视觉兜底"
        # 那一步就会 AttributeError，把正常情况变成崩溃。
        self._probe_no_vision = False
        # 视觉兜底定位层（元素定位失败时启用）
        self.vision = None
        base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        if VisionLocator is not None:
            vision_cfg = (config or {}).get("vision") or {}
            self.vision = VisionLocator(vision_cfg, base_dir, recorder)
            self.vision_enabled = self.vision.enabled
        else:
            self.vision_enabled = False
        # 元素知识库（经验回写）：selector 失败自动轮换 alternatives，
        # 连续失败超阈值自动 disabled，disabled 后用尽则转入视觉兜底。
        self.knowledge = None
        if KnowledgeBase is not None:
            kb_cfg = (config or {}).get("knowledge") or {}
            self.knowledge = KnowledgeBase(
                path=os.path.join(
                    base_dir, kb_cfg.get("file") or "element_knowledge.yaml"),
                recorder=recorder,
                threshold=kb_cfg.get("fail_threshold", 3),
                dry_run=dry_run,
                base_dir=base_dir,
            )
            self.knowledge.load()
            self.recorder.log(f"元素知识库就绪: {self.knowledge.path} "
                              f"(阈值={self.knowledge.threshold}, "
                              f"dry_run={dry_run})", "sys", "DEBUG")
        # 滑块验证码求解器（懒加载，无设备/未启用时保持 None）
        self.captcha = None
        captcha_cfg = (config or {}).get("captcha") or {}
        if SliderCaptchaSolver is not None and captcha_cfg.get("enabled", False):
            self.captcha = SliderCaptchaSolver(
                cfg=captcha_cfg, base_dir=base_dir, recorder=recorder,
                vision=self.vision, trajectory=self.human.trajectory)
            self.recorder.log(f"滑块验证码求解器就绪: mode={self.captcha.gap_mode} "
                              f"retry={self.captcha.retry_times}", "sys", "DEBUG")

        # 行为序列多样化：记录每个行为上次用的候选模板，避免连续重复同一路径
        self._variant_last = {}
        self._diversify_prob = float((config or {}).get(
            "diversify", {}).get("variant_prob", 0.8))

    # ---------- 连接 ----------
    def connect(self):
        if self.d is not None:
            return self.d
        if self.dry_run:
            self.recorder.log("dry-run 模式：跳过设备连接", "sys")
            return None
        try:
            import uiautomator2 as u2
        except ImportError as e:
            raise StepError(
                "缺少依赖 uiautomator2，请先执行: pip install -r requirements.txt"
            ) from e
        self.d = u2.connect(self.serial) if self.serial else u2.connect()
        self.recorder.log(f"设备已连接: {self.d.serial if self.serial else 'auto'}",
                          "sys")
        return self.d

    # ---------- 顶层流程 ----------
    def _at_top_level(self):
        """当前是否在 App 顶层页（底部有 tab 栏）。判据见 ui_page.py。

        与 devtools/verify_live.py 共用同一份实现 —— 两边口径不一致时，
        离线统计的命中率就无法代表真机执行结果。
        """
        if TOP_LEVEL_LABELS is None or not TOP_LEVEL_LABELS:
            return True          # ui_page 缺失：关闭复位，保持旧行为
        try:
            _w, h = self.d.window_size()
        except Exception:
            return True
        band = NAV_BAND_Y * h
        labs = set()
        for lab in TOP_LEVEL_LABELS:
            try:
                el = self.d(text=lab)
                if not el.exists:
                    continue
                b = el.info.get("bounds") or {}
                if (b.get("top", 0) >= band) or (b.get("bottom", 0) >= band):
                    labs.add(lab)
            except Exception:
                continue
        if len(labs) >= 2:
            return True
        return bool(labs & {"首页", "推荐", "我的", "我"})

    def _reset_to_landing(self, pkg, app_name, max_back=3):
        """把 App 退回顶层页。**行为之间必须复位。**

        为什么：一个行为可能已经导航到二级/三级页（我的 → 福利中心 → 签到）。
        不复位的话，下一个行为从脏页面起步，配置里的比例坐标兜底会点到错误
        元素、甚至跳到别的 App —— 实测喜番免费短剧 sign 之后 watch 被带到
        com.eggflower.read（蛋花免费小说），整条链路的收益都记错。

        策略：**先判断、后动作** ——
          1) 已经在顶层页 -> 直接返回，一个 BACK 都不按；
          2) 否则按 BACK（快、不触发开屏广告），每次校验前台仍在目标 App；
          3) 一旦发现已离开目标 App 立刻停手并重启 —— 开屏广告期继续按
             BACK 会直接退出 App；退不回去也走重启（确定但慢）。

        为什么必须先判断：多数 App 在顶层页（如「我的」tab）按 BACK 会**直接
        退出 App**。实测复位前不看一眼就按，一按就退到桌面，白白多吃一次冷启动。
        """
        if self.dry_run or self.d is None:
            return
        if self._at_top_level():
            self.recorder.log("复位: 已在顶层页，无需 BACK", app_name, "DEBUG")
            return
        for i in range(1, max_back + 1):
            try:
                self.d.press("back")
            except Exception as e:
                self.recorder.log(f"复位 BACK 异常: {type(e).__name__}: {e}",
                                  app_name, "DEBUG")
                break
            time.sleep(1.5)
            try:
                fg = self.d.info.get("currentPackageName") or ""
            except Exception:
                fg = ""
            if fg and fg != pkg:
                self.recorder.log(
                    f"复位: 第{i}次 BACK 后前台={fg}（非目标 App）-> 重启",
                    app_name, "WARN")
                self._open_app(pkg, app_name)
                return
            if self._at_top_level():
                self.recorder.log(f"复位: 第{i}次 BACK 回到顶层页",
                                  app_name, "DEBUG")
                return
        self.recorder.log("复位: BACK 未回到顶层页 -> 重启 App", app_name, "WARN")
        self._open_app(pkg, app_name)

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
            for intent, kw in intents:
                bid = self._resolve(app_cfg, intent)
                if bid is None:
                    self.recorder.log(
                        f"  意图[{intent}]({kw}) 未配置行为，跳过", app_name, "WARN")
                    continue
                actions = self._pick_variant(app_cfg["behaviors"][bid], app_name, bid)
                self.recorder.log(f"  意图[{intent}]({kw}) -> 行为[{bid}]:", app_name)
                for a in actions:
                    self.recorder.log("      - " + json.dumps(a, ensure_ascii=False),
                                      app_name)
            return

        # 1) 启动 app（即使已有 open 步骤也确保一次）
        self._open_app(pkg, app_name)

        # 2) 逐意图执行
        for i, (intent, kw) in enumerate(intents):
            bid = self._resolve(app_cfg, intent)
            if bid is None:
                self.recorder.log(
                    f"意图[{intent}](触发词:{kw}) 在 {app_name} 未定义对应行为，跳过",
                    app_name, "WARN")
                continue
            # 行为之间复位：上一个行为可能已把 App 留在二级/三级页，
            # 不复位则本行为会从脏页面起步（详见 _reset_to_landing 注释）。
            if i > 0:
                self._reset_to_landing(pkg, app_name)
            actions = self._pick_variant(app_cfg["behaviors"][bid], app_name, bid)
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
        all_ok = True
        for act in actions:
            try:
                self._exec_step(act, app_name)
            except StepError as e:
                # 真人式处理：找不到就挠头一下，继续下一个意图，不硬崩
                self.recorder.log(f"步骤失败: {e}", app_name, "WARN")
                all_ok = False
                self.human.think()
        return all_ok

    def _exec_step(self, act: dict, app_name: str):
        self._dispatch(act, app_name, ritual=True)

    def _dispatch(self, act: dict, app_name: str, ritual: bool) -> bool:
        """执行一个动作。返回 True=成功/命中，False=未命中（仅 any_of 会用到）。

        约定：`optional: true` 的定位类动作「没找到」时**不抛异常**，
        只记 WARN 放行 —— 这在普通顺序执行里是对的，但在 `any_of`
        条件分支里会被误判成"分支成功"。因此这里统一把结果回传，
        由 `any_of` 依据布尔值判断分支是否真的命中。
        """
        t = act.get("type")
        fn = {
            "wait": self._step_wait,
            "think": self._step_think,
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
            "reward": self._step_reward,
            "ensure": self._step_ensure,
        }.get(t)
        if fn is None:
            self.recorder.log(f"未知动作类型: {t}，已忽略", app_name, "WARN")
            return False
        # 每个动作之前的"人味间隔"（random 分支等内部动作不重复叠加）
        if ritual:
            self.human.delay()
            # 随机"分心"
            if self.d is not None:
                self.human.maybe_wander(self.d)
        res = fn(act, app_name)
        return True if res is None else bool(res)

    def _step_any_of(self, act, app_name):
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
        for i, chosen in enumerate(choices):
            steps = chosen if isinstance(chosen, list) else [chosen]
            # 只有最后一个分支允许触发视觉兜底。
            # 前面的分支是"便宜的探测"：本机 VLM 图像请求常 90s 超时，
            # 若探测分支也走视觉兜底，一次 any_of 可能白等好几分钟。
            prev = getattr(self, "_probe_no_vision", False)
            self._probe_no_vision = (i < n - 1)
            ok = True
            try:
                for a in steps:
                    try:
                        if not self._dispatch(a, app_name, ritual=False):
                            ok = False
                            break
                    except StepError as e:
                        self.recorder.log(f"any_of 分支#{i + 1} 步骤失败: {e}",
                                          app_name, "DEBUG")
                        ok = False
                        break
            finally:
                self._probe_no_vision = prev
            if ok:
                self.recorder.log(f"any_of 分支#{i + 1}/{n} 命中",
                                  app_name, "DEBUG")
                return True
            self.recorder.log(f"any_of 分支#{i + 1}/{n} 未命中", app_name, "DEBUG")
        if act.get("optional", False):
            self.recorder.log("any_of 全部分支未命中，optional 放行", app_name, "WARN")
            return False
        raise StepError("any_of 全部分支均未命中")

    def _step_random(self, act, app_name):
        """行为分支随机化：choices 中随机择一执行。
        每个 choice 可以是单个动作 dict，或一串动作 list。"""
        choices = act.get("choices") or []
        if not choices:
            self.recorder.log("random 动作缺少 choices，已忽略", app_name, "WARN")
            return
        chosen = random.choice(choices)
        if isinstance(chosen, list):
            for a in chosen:
                self._dispatch(a, app_name, ritual=False)
        elif isinstance(chosen, dict):
            self._dispatch(chosen, app_name, ritual=False)

    # ---------- 原语实现 ----------
    def _step_wait(self, act, app_name):
        time.sleep(float(act.get("seconds", 1.0)))

    def _step_think(self, act, app_name):
        self.human.think()

    def _locate(self, kind, value, timeout=6.0):
        """定位元素，返回 UiObject 或 None

        坑位记录：`textContains` 会命中"长文案里恰好包含关键词"的节点。
        实测一淘"我的"页里，候选 `签到` 唯一命中的是 FAQ 链接
        「什么是签到领钱，如何参加？」——若直接点下去就点错了。
        因此这里做两步：先取全部匹配并按"更短/可点击/完全相等"择优，
        再把明显过长的非可点击文本判为"未命中"，交给下一个候选或视觉兜底。
        """
        # dry-run / 未连接设备：不 import uiautomator2，直接返回 None
        if self.d is None or self.dry_run:
            return None
        import uiautomator2 as u2  # noqa
        d = self.d
        value = str(value)
        if kind == "text":
            obj = d(textContains=value)
        elif kind == "id":
            obj = d(resourceId=value)
        elif kind == "desc":
            obj = d(descriptionContains=value)
        else:
            return None
        if not obj.wait(timeout=timeout):
            return None
        return self._pick_best(obj, value, kind)

    @staticmethod
    def _label_of(info, kind):
        if kind == "text":
            return info.get("text") or ""
        if kind == "desc":
            return info.get("contentDescription") or ""
        return info.get("resourceId") or ""

    def _pick_best(self, obj, target, kind):
        """从多匹配里择优；对"长文案误命中"做拒配。"""
        try:
            n = int(getattr(obj, "count", 1))
        except Exception:
            return obj
        if n <= 1:
            best = obj
        else:
            # 底部导航标签的位置合理性：实测页面中部也会出现「我的」这类
            # 标签文本（蛋花免费小说二级页 text='我的' @(575,627)，而底部
            # 导航在 y≈2100+）。若目标词是导航标签，优先取落在屏幕底部带的
            # 匹配 —— 只做加分，不做硬过滤，避免误伤特殊布局。
            nav_label = str(target).strip() in NAV_LABELS
            try:
                screen_h = int((self.d.info or {}).get("displayHeight") or 0)
            except Exception:
                screen_h = 0
            best, best_score = obj, None
            for i in range(min(n, 12)):
                try:
                    cand = obj[i]
                    info = cand.info
                except Exception:
                    continue
                label = self._label_of(info, kind)
                clickable = bool(info.get("clickable"))
                if label == target:
                    score = 1000
                else:
                    score = 100 - min(90, abs(len(label) - len(target)) * 3)
                if clickable:
                    score += 50
                if nav_label and screen_h:
                    try:
                        top = int(info["bounds"]["top"])
                        if top >= NAV_BAND_Y * screen_h:
                            score += 120
                        else:
                            score -= 120
                    except Exception:
                        pass
                if best_score is None or score > best_score:
                    best_score, best = score, cand
            self.recorder.log(
                f"  [{kind}]'{target}' 命中 {n} 处，择优 {best_score} 分",
                "", "DEBUG")
        # 长文案拒配：明显过长的非可点击文本视为误命中
        try:
            info = best.info
            label = self._label_of(info, kind)
            limit = max(len(target) + 6, len(target) * 3)
            if (kind in ("text", "desc") and len(label) > limit
                    and not bool(info.get("clickable"))):
                self.recorder.log(
                    f"  [{kind}]'{target}' 只匹配到过长文案 {label[:24]!r}"
                    f"（{len(label)} 字 > 阈值 {limit}）且不可点击，判为误命中",
                    "", "WARN")
                return None
        except Exception:
            pass
        return best

    def _click_obj(self, obj):
        rect = obj.rect  # left, top, right, bottom
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2
        x, y = self.human.jitter_point(cx, cy)
        if self.dry_run:
            return
        self.d.click(x, y)

    # ---------- 元素知识库辅助 ----------
    def _kb_candidates(self, app_name, primary_selector):
        """先查知识库，返回本元素当前应尝试的候选 selector 列表与是否命中知识库记录。

        返回 (cands, has_entry)：
          - 无知识库记录   -> ([primary_selector], False)，走原逻辑；
          - 记录已 disabled -> ([], True)，跳过元素定位直接转视觉兜底；
          - 有记录且启用   -> ([主] + [启用 alternatives], True)，含替代轮换。
        """
        if self.knowledge is None:
            return [primary_selector], False
        if not self.knowledge.has_element(app_name, primary_selector):
            return [primary_selector], False
        return self.knowledge.candidate_selectors(app_name, primary_selector), True

    def _kb_mark_fail(self, app_name, primaries):
        """对本次实际尝试过、知识库中有记录的主 selector 做失败回写。"""
        if self.knowledge is None:
            return
        seen = []
        for p in primaries:
            if p and p not in seen:
                seen.append(p)
                self.knowledge.mark_fail(app_name, p)

    # ---------- 视觉兜底定位回退链 ----------
    def _vision_click(self, act, app_name, desc) -> bool:
        """在 uiautomator2 元素定位失败/超时后，尝试视觉兜底点击。

        回退顺序：
          1) act 中绑定的 images/template 图片资源 -> OpenCV 模板匹配点击
          2) 若配置开启且 vlm 已配置 -> VisionLocator 的 VLM 后端识别点击
        命中则执行真人化点击并写日志，返回 True；否则返回 False。
        """
        if not self.vision or not self.vision_enabled:
            return False
        templates = act.get("images") or []
        if act.get("template"):
            templates = [act["template"]] + list(templates) if not isinstance(
                act["template"], (list, tuple)) else list(act["template"]) + list(templates)
        prompt = act.get("vlm_prompt") or act.get("prompt") or ""
        if not templates and not prompt:
            return False
        if self.dry_run:
            self.recorder.log(f"[dry-run] 将尝试视觉兜底点击: {desc}", app_name, "DEBUG")
            # dry-run 不截真实设备图，直接视为计划已打印、不执行
            return False
        if self.d is None:
            return False
        img = self.vision.screenshot_from_device(self.d)
        if img is None:
            self.recorder.log(f"视觉兜底截图失败，无法视觉点击: {desc}", app_name, "WARN")
            return False
        hit = self.vision.locate_on_screen(
            templates=templates or None,
            prompt=prompt or None,
            screen_img=img, app=app_name, tag=desc)
        if hit is None:
            self.recorder.log(f"视觉兜底全部未命中，放弃该步: {desc}", app_name, "WARN")
            return False
        x, y = self.human.jitter_point(int(hit.x), int(hit.y))
        self.d.click(x, y)
        self.recorder.log(f"视觉兜底点击成功: {desc} -> ({x},{y})", app_name)
        return True

    def _step_click_text(self, act, app_name):
        primary = "text=" + str(act.get("text", ""))
        cands, has_entry = self._kb_candidates(app_name, primary)
        obj = None
        if cands:  # 空列表=知识库已 disabled，跳过元素定位直接转视觉
            for sel in cands:
                k, v = _parse_sel(sel)
                obj = self._locate(k, v, act.get("timeout", 6))
                if obj is not None:
                    break
        if obj is None:
            if has_entry and cands:  # 实际尝试过但都失败才计数
                self.knowledge.mark_fail(app_name, primary)
            desc = f"click_text[{act.get('text')}]"
            if not self._probe_no_vision and self._vision_click(act, app_name, desc):
                return
            raise StepError(f"未找到文本按钮: {act.get('text')}")
        if has_entry:
            self.knowledge.mark_ok(app_name, primary)
        if not self.dry_run:
            self._click_obj(obj)
        self.recorder.log(f"点击文本: {act.get('text')}", app_name)

    def _step_click_id(self, act, app_name):
        primary = "id=" + str(act.get("res_id", ""))
        cands, has_entry = self._kb_candidates(app_name, primary)
        obj = None
        if cands:
            for sel in cands:
                k, v = _parse_sel(sel)
                obj = self._locate(k, v, act.get("timeout", 6))
                if obj is not None:
                    break
        if obj is None:
            if has_entry and cands:
                self.knowledge.mark_fail(app_name, primary)
            desc = f"click_id[{act.get('res_id')}]"
            if not self._probe_no_vision and self._vision_click(act, app_name, desc):
                return
            raise StepError(f"未找到控件 id: {act.get('res_id')}")
        if has_entry:
            self.knowledge.mark_ok(app_name, primary)
        if not self.dry_run:
            self._click_obj(obj)
        self.recorder.log(f"点击控件: {act.get('res_id')}", app_name)

    def _step_click_desc(self, act, app_name):
        primary = "desc=" + str(act.get("desc", ""))
        cands, has_entry = self._kb_candidates(app_name, primary)
        obj = None
        if cands:
            for sel in cands:
                k, v = _parse_sel(sel)
                obj = self._locate(k, v, act.get("timeout", 6))
                if obj is not None:
                    break
        if obj is None:
            if has_entry and cands:
                self.knowledge.mark_fail(app_name, primary)
            desc = f"click_desc[{act.get('desc')}]"
            if not self._probe_no_vision and self._vision_click(act, app_name, desc):
                return
            raise StepError(f"未找到描述按钮: {act.get('desc')}")
        if has_entry:
            self.knowledge.mark_ok(app_name, primary)
        if not self.dry_run:
            self._click_obj(obj)
        self.recorder.log(f"点击描述: {act.get('desc')}", app_name)

    def _step_click_point(self, act, app_name):
        # 若本步绑定了图片/VLM 定位，优先用视觉兜底定位（应对布局/分辨率变化）。
        # `vision: false` 可显式关闭视觉兜底 —— 用于「导航到我的」这类
        # **每个行为都要跑**的固定步骤：本机 VLM 图像请求常 90s 超时，
        # 而比例坐标已被 18 个 App 实机验证可靠，走视觉只会白白拖慢且更不稳。
        if act.get("vision", True) and (
                act.get("images") or act.get("template")
                or act.get("vlm_prompt") or act.get("prompt")):
            if self._vision_click(act, app_name, "click_point[visual]"):
                return
        info = self.d.window_size() if self.d else None
        x, y = float(act.get("x")), float(act.get("y"))
        if info and x <= 1.0 and y <= 1.0:
            x, y = int(info.width * x), int(info.height * y)
        x, y = self.human.jitter_point(int(x), int(y))
        if self.dry_run:
            return
        self.d.click(x, y)
        self.recorder.log(f"点击坐标: ({x},{y})", app_name)

    def _step_click_first(self, act, app_name):
        """依次尝试多个候选，点中第一个存在的（适合按钮文案会变动的场景）

        每个候选都会先查知识库：有记录则用知识库推荐的 selector（含替代轮换），
        记录已 disabled 的候选被跳过；命中/失败分别回写 last_ok / fail_times。
        """
        pool = []           # [(kind, value, primary)]，primary 为知识库主 selector
        for cand in act.get("candidates", []) or []:
            kind, value = cand.get("type"), cand.get("value", "")
            if not value:
                continue
            primary = f"{kind}={value}"
            kb_cands, has_entry = self._kb_candidates(app_name, primary)
            if not kb_cands:
                continue    # 知识库 disabled 的候选直接跳过
            for sel in kb_cands:
                k, v = _parse_sel(sel)
                if (k, v) not in [(p[0], p[1]) for p in pool]:
                    pool.append((k, v, primary if has_entry else None))
        for k, v, prim in pool:
            obj = self._locate(k, v, timeout=2.0)
            if obj is not None:
                if prim:
                    self.knowledge.mark_ok(app_name, prim)
                if not self.dry_run:
                    self._click_obj(obj)
                self.recorder.log(f"多候选命中并点击: ({k}){v}", app_name)
                return True
        # 全失败：回写本次尝试过（有知识库记录）的主 selector 失败计数
        self._kb_mark_fail(app_name, [p[2] for p in pool])
        # 所有元素候选均超时 -> 视觉兜底（candidates 全部失败）
        if not self._probe_no_vision and self._vision_click(
                act, app_name, "click_first[all-candidates]"):
            return True
        if act.get("optional", False):
            # optional：候选全部未出现时视为"本次无需执行"（如签到类当日已完成），
            # 记 WARN 放行，不算行为失败。
            self.recorder.log(
                f"候选全部未出现，optional 放行: {act.get('candidates')}",
                app_name, "WARN")
            return False
        raise StepError(f"所有候选均未出现: {act.get('candidates')}")

    def _step_swipe(self, act, app_name):
        if act.get("natural", False) and self.d:
            self.human.natural_swipe(self.d)
            self.recorder.log("自然滑动", app_name)
            return
        info = self.d.window_size() if self.d else None
        f, t = act.get("from"), act.get("to")
        if not (f and t and info):
            raise StepError("swipe 需要 from/to 坐标")
        pct = lambda v: (  # noqa: E731
            int(info.width * v[0]), int(info.height * v[1])
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
                    return
            self.d.swipe(sx, sy, ex, ey, duration=dur)
        self.recorder.log(f"滑动 ({sx},{sy})->({ex},{ey})", app_name)

    def _step_swipe_natural(self, act, app_name):
        """显式自然滑动原语：仅起终点可配，轨迹交给 HumanTrajectory。"""
        if not self.d:
            raise StepError("swipe_natural 需要设备")
        f, t = act.get("from"), act.get("to")
        if f and t:
            info = self.d.window_size()
            pct = lambda v: (  # noqa: E731
                int(info.width * v[0]), int(info.height * v[1])
            ) if v[0] <= 1.0 and v[1] <= 1.0 else (int(v[0]), int(v[1]))
            start, end = pct(f), pct(t)
            if not self.dry_run:
                points, intervals = self.human.trajectory.generate_gesture(start, end)
                self.human.trajectory.inject_touch(self.d, points, intervals)
            self.recorder.log(f"自然滑动(轨迹) {f}->{t}", app_name)
        else:
            if not self.dry_run:
                self.human.natural_swipe(self.d)
            self.recorder.log("自然滑动(随机)", app_name)

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
            raise StepError(f"滑块验证码求解失败（{self.captcha.retry_times} 次尝试）")
        self.human.think()

    def _dump_safe(self):
        try:
            return str(self.d.dump_hierarchy())
        except Exception:
            return ""

    def _step_scroll_to(self, act, app_name):
        """向下翻页直到出现目标文本后点击（或仅查找）"""
        text = act.get("text", "")
        obj = self._locate("text", text, timeout=2.0)
        max_pages = int(act.get("max_pages", 6))
        page = 0
        while obj is None and page < max_pages:
            self.human.natural_swipe(self.d)
            page += 1
            self.human.think()
            obj = self._locate("text", text, timeout=1.5)
        if obj is None:
            raise StepError(f"滚动 {max_pages} 页仍未找到: {text}")
        if not self.dry_run:
            self._click_obj(obj)
        self.recorder.log(f"滚动找到并点击: {text}（翻页{page}）", app_name)

    def _step_back(self, act, app_name):
        if not self.dry_run:
            self.d.press("back")
        self.recorder.log("返回", app_name)

    def _step_home(self, act, app_name):
        if not self.dry_run:
            self.d.press("home")
        self.recorder.log("回到桌面", app_name)

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

    # 只在 text / content-desc 里找收益数字。
    # 踩坑：直接在整份 XML 上 re.search，会命中活动横幅、广告位等无关数字
    # （例如「新人 1 元提现」），把横幅数字当成账户余额记进收益表。
    _TEXT_ATTR_RE = re.compile(r'(?:text|content-desc)="([^"]*)"')
    # 金额类收益的语义提示词：多处匹配时优先取带这些词的文案
    _BALANCE_HINTS = ("可提现", "提现", "余额", "钱包", "现金", "账户", "收益")

    def _reward_candidates(self, xml, pattern, act):
        """返回 [(来源文案, match), ...]，按「可信度」排序。"""
        out = []
        for m in self._TEXT_ATTR_RE.finditer(xml or ""):
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
        # 优先：配置里显式给的 context 关键词
        ctx = [str(k) for k in (act.get("context") or [])]
        if ctx:
            for i, (val, _) in enumerate(out):
                if any(k in val for k in ctx):
                    return [out[i]] + out[:i] + out[i + 1:]
        # 其次：金额类收益优先带「提现/余额/钱包」语义的文案
        if (act.get("unit") or "") == "元":
            for i, (val, _) in enumerate(out):
                if any(k in val for k in self._BALANCE_HINTS):
                    return [out[i]] + out[:i] + out[i + 1:]
        return out

    # ---------- 页面校验 ----------
    def _step_ensure(self, act, app_name):
        """确认关键页面已出现（如已进入签到页），防止误点"""
        text = act.get("text", "")
        expect = act.get("exists", "yes")
        obj = self._locate("text", text, timeout=float(act.get("timeout", 6)))
        if expect == "yes" and obj is None:
            raise StepError(f"校验失败，未出现关键文本: {text}")
        if expect == "no" and obj is not None:
            raise StepError(f"校验失败，不应出现的文本却在: {text}")
        self.recorder.log(f"校验通过: {text}({expect})", app_name)

    # ---------- 启停 ----------
    def _wait_page_ready(self, pkg, app_name, max_wait=45.0, min_nodes=25,
                         poll=2.0, stable_samples=2):
        """启动后等页面**稳定**再动手。返回 (节点数, 等待秒数, 是否稳定)。

        为什么需要：App 落地页不确定（开屏广告/活动弹窗/新手引导/上次退出的
        tab/登录态/灰度活动页）。启动后立刻 dump 常抓到启动页或广告页 ——
        实测同一批配置不同轮次锚点命中率差异显著（一淘.sign 三轮三种结果），
        根因就是"在不确定的页面上找确定的锚点"。

        判定：连续 `stable_samples` 次轮询的节点数变化都很小（<=10%）且节点数
        达标，才认为页面已渲染完成。
        注意必须是**连续多次**：单次小变化会误判 —— 实测加载过程中
        节点数会走 5 → 40 → 42 → 200，只看一次小变化会在 42 就提前动手。

        上限 max_wait 秒，超时按当前页继续（不阻塞流程）。
        """
        if self.dry_run or self.d is None:
            return 0, 0.0, True
        t0 = time.time()
        prev, last_n, streak = -1, 0, 0
        while time.time() - t0 < max_wait:
            try:
                xml = self.d.dump_hierarchy()
            except Exception as e:
                self.recorder.log(f"页面稳定探测异常: {type(e).__name__}: {e}",
                                  app_name, "DEBUG")
                streak = 0
                time.sleep(poll)
                continue
            n = xml.count("<node")
            last_n = n
            try:
                fg = self.d.info.get("currentPackageName") or ""
            except Exception:
                fg = ""
            if pkg and pkg not in fg:
                # 还在启动页/别的 App，继续等
                prev, streak = n, 0
                time.sleep(poll)
                continue
            if n >= min_nodes and prev >= 0 and abs(n - prev) <= max(3, prev * 0.1):
                streak += 1
                if streak >= stable_samples:
                    return n, time.time() - t0, True
            else:
                streak = 0
            prev = n
            time.sleep(poll)
        return last_n, time.time() - t0, False

    def _open_app(self, pkg, app_name):
        if self.dry_run:
            self.recorder.log(f"[dry-run] 将启动 {app_name} ({pkg})", app_name)
            return
        self.d.app_start(pkg)
        self.human.after_open()  # 首屏随机停留
        n, waited, stable = self._wait_page_ready(pkg, app_name)
        self.recorder.log(
            f"页面就绪判定: 节点={n} 等待={waited:.1f}s "
            f"{'已稳定' if stable else '未稳定（超时，按当前页继续）'}",
            app_name, "DEBUG" if stable else "WARN")
        self.recorder.log(f"已启动 {app_name}", app_name)

    def _close_app(self, app_name):
        if self.dry_run:
            self.recorder.log(f"[dry-run] 将退出 {app_name}", app_name)
            return
        self.human.close_naturally(self.d)
        self.recorder.log(f"已退出 {app_name}", app_name)
