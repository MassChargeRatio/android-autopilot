# -*- coding: utf-8 -*-
"""locator.py - 元素定位层（D 批从 executor.py 三分拆）

搬迁来源：executor.py 的 Executor 类 —— _locate（L480-525）、_label_of
（L527-535）、_pick_best（L537-575）、_click_obj（L577-586）、_kb_candidates
（L588-610）、_kb_mark_fail（L612-623）、_locate_with_kb（L625-655）、
_click_tracked（L657-666）、_vision_or_miss（L668-675）、_vision_click
（L677-716）；模块级 LocateResult（L56-68）、_parse_sel（L36-44）。

坑位注释原文照搬，禁止润色（见各方法 docstring）。

方法体内通过 `self._xxx` 同名可覆盖入口互相调用：本类被 executor.py 门面
多继承后，self 是 Executor 实例，tests 对 Executor 实例打桩仍然生效。
"""
import time
from dataclasses import dataclass

try:
    from pick_locate import pick_best
except ImportError:  # pragma: no cover - 未拷贝 pick_locate.py 时退化为本地兜底
    pick_best = None

# RPC 栈溢出（2026-11-01 微博实崩定位）：RPCError 族继承 BaseException 而非 Exception，
# 所以现有 `except Exception` 全部漏接，溢出会直接穿出崩掉整条流程。这里惰性导入异常类。
# 无 uiautomator2 的环境（tests）退回空元组 —— `except ()` 合法且永不匹配，行为零变化。
try:
    from uiautomator2.exceptions import RPCStackOverflowError as _RPCStackOverflowError
except Exception:  # pragma: no cover - 测试环境无 uiautomator2 依赖
    _RPCStackOverflowError = ()


def _parse_sel(sel):
    """把知识库 selector 拆成 (kind, value)：'text=每日签到' -> ('text','每日签到')。"""
    sel = str(sel)
    if "=" in sel:
        kind, _, value = sel.partition("=")
        if kind.strip().lower() in ("text", "id", "desc"):
            return kind.strip().lower(), value.strip()
    return "text", sel


@dataclass
class LocateResult:
    """元素定位结果（B6 显式化）。

    - hit=False 表示「未命中」：等待超时、pick_best 拒配、kind 非法等；
      定位类动作**永不**因未找到而抛异常，由上层据 hit 记「步骤失败」。
    - detail 复用原 raise 消息文本（零日志漂移），供 `_run_actions` 记录。
    """
    hit: bool
    obj: object = None
    detail: str = "未找到元素"


class Locator:
    """元素定位层：_locate/_pick_best、元素知识库辅助、视觉兜底回退链。"""

    def _locate(self, kind, value, timeout=6.0, zone=None, screen_w=0, poll=0.25):
        """定位元素，返回 LocateResult(hit, obj, detail)。

        坑位记录：`textContains` 会命中"长文案里恰好包含关键词"的节点。
        实测一淘"我的"页里，候选 `签到` 唯一命中的是 FAQ 链接
        「什么是签到领钱，如何参加？」——若直接点下去就点错了。
        因此这里做两步：先取全部匹配并按"更短/可点击/完全相等"择优，
        再把明显过长的非可点击文本判为"未命中"，交给下一个候选或视觉兜底。

        B6：定位失败不再抛异常，统一返回 hit=False 的 LocateResult。
        第3步：zone/screen_w 位置先验透传 _pick_best（多匹配时按区加分）。

        B2（2026-10-30）：把「一次 wait(timeout=6.0) 阻塞 6 秒」拆成 poll 粒度轮询。
        命中即返回（语义不变）；差别在**未命中**时——原来必须睡满 timeout 才返回，
        现在每 poll 秒重查一次，元素中途出现就立刻返回。
        这条直接影响弹窗清扫：它要顺序试 13 个关闭文案，每次 timeout=0.8，
        原实现干净屏一轮就是 13×0.8=10.4s（快手实测 3 轮 37s 的主因之一）。
        """
        # dry-run / 未连接设备：不 import uiautomator2，直接返回未命中
        if self.d is None or self.dry_run:
            return LocateResult(False, None, "dry-run 或未连接设备，跳过定位")
        d = self.d
        value = str(value)
        deadline = time.time() + max(0.0, float(timeout))
        poll = max(0.02, float(poll))
        rpc_failures = 0
        while True:
            try:
                if kind == "text":
                    obj = d(textContains=value)
                elif kind == "id":
                    obj = d(resourceId=value)
                elif kind == "desc":
                    obj = d(descriptionContains=value)
                else:
                    return LocateResult(False, None, f"未知定位类型: {kind}")
                remain = deadline - time.time()
                if obj.wait(timeout=min(poll, max(0.0, remain))):
                    best = self._pick_best(obj, value, kind,
                                           zone=zone, screen_w=screen_w)
                    if best is not None:
                        return LocateResult(True, best, "")
                    # 命中但被拒配（长文案误命中）：不提前返回，继续找
            except _RPCStackOverflowError:
                # 微博实崩（2026-11-01）：Android 侧 java.lang.StackOverflowError 发生在
                # 层级 dump 瞬间（动态树过深）。瞬态 —— Java 栈 unwind 后下一次 dump
                # 往往就恢复。重试上限内退避重来；超限返回未命中（B6 契约：定位永不因
                # 未命中抛异常，上层记「步骤失败」继续跑，不崩整条流程）。
                rpc_failures += 1
                if rpc_failures > self.rpc_retries or time.time() >= deadline:
                    return LocateResult(
                        False, None,
                        f"RPC 栈溢出持续 {rpc_failures} 次，定位放弃")
                time.sleep(self.rpc_backoff)
                continue
            if time.time() >= deadline:
                return LocateResult(False, None, "等待超时，元素未出现")

    @staticmethod
    def _label_of(info, kind):
        if kind == "text":
            return info.get("text") or ""
        if kind == "desc":
            return info.get("contentDescription") or ""
        return info.get("resourceId") or ""

    def _pick_best(self, obj, target, kind, zone=None, screen_w=0):
        """从多匹配里择优；对"长文案误命中"做拒配。

        第3步：zone/screen_w 位置先验 —— 多匹配时按底部带/右上/右缘加分，
        未命中者扣分（仅用于择优，不硬过滤）；缺坐标或未知屏尺寸则中性。
        """
        try:
            n = int(getattr(obj, "count", 1))
        except Exception:
            return obj
        try:
            if n <= 1:
                info = obj.info
                entries = [{
                    "label": self._label_of(info, kind),
                    "clickable": bool(info.get("clickable")),
                    "top": int(info["bounds"]["top"]) if info.get("bounds") else 0,
                    "left": int(info["bounds"]["left"]) if info.get("bounds") else None,
                    "right": int(info["bounds"]["right"]) if info.get("bounds") else None,
                }]
                screen_h = 0
            else:
                try:
                    d_info = self.d.info or {}
                    screen_h = int(d_info.get("displayHeight") or 0)
                    if not screen_w:
                        screen_w = int(d_info.get("displayWidth") or 0)
                except Exception:
                    screen_h = 0
                entries = []
                for i in range(min(n, 12)):
                    try:
                        info = obj[i].info
                        entries.append({
                            "label": self._label_of(info, kind),
                            "clickable": bool(info.get("clickable")),
                            "top": int(info["bounds"]["top"]) if info.get("bounds") else 0,
                            "left": int(info["bounds"]["left"]) if info.get("bounds") else None,
                            "right": int(info["bounds"]["right"]) if info.get("bounds") else None,
                        })
                    except Exception:
                        continue
        except Exception:
            return obj
        if pick_best is None:
            return obj
        idx = pick_best(entries, str(target), kind, screen_h, self.recorder.log,
                        screen_w=screen_w, zone=zone)
        if idx is None:
            return None
        return obj if n <= 1 else obj[idx]

    def _click_obj(self, obj, relocate=None):
        """点击元素中心（经 human.tap：抖动+误触回退+限流）。

        坑位1（2026-10-21 回归实崩）：u2 的 UiObject **没有 `.rect` 属性**，
        正确 API 是 `.bounds()` -> `(lx, ly, rx, ry)` plain tuple。旧代码
        `obj.rect` + `.left/.right` 双重错误 —— 只要文案命中走到真实点击
        （click_first/scroll_to）就必崩 `AttributeError`。一轮回归 7 个「命中」
        全是坐标兜底（文案先 miss 所以没走到这里），把此坑完全遮住了。

        坑位2（2026-10-21 三轮回归实崩）：`StaleObjectException` ——
        元素定位后页面变化，`obj.bounds()` 抛 RPCUnknownError 直接崩掉
        整条流程。u2 元素引用是定位时快照，点击前必须容忍失效：
        relocate 回调重定位一次再点；仍失效抛 StepError（上层记
        「步骤失败」继续跑，不崩）。

        坑位3（2026-11-01 微博实崩）：点击瞬间的第二次 dump 遇 Android 侧
        java.lang.StackOverflowError（RPCStackOverflowError）。元素本身仍有效
        （_locate 刚命中），只是 dump 递归过深 —— 瞬态，Java 栈 unwind 后即恢复。
        与「元素失效」不同，这里**不 relocate**，而是退避重试 rpc_retries 次；
        超限抛 StepError（上层记「步骤失败」继续跑，不崩流程）。

        兼容分支：测试/探针里的假元素带 `.rect` 属性对象。
        """
        lx = ly = rx = ry = None
        rpc_attempts = 0
        stale_attempts = 0
        rpc_retries = getattr(self, "rpc_retries", 2)
        rpc_backoff = getattr(self, "rpc_backoff", 0.8)
        while True:
            try:
                rect = getattr(obj, "rect", None)
                if rect is not None and hasattr(rect, "left"):
                    lx, ly, rx, ry = rect.left, rect.top, rect.right, rect.bottom
                else:
                    lx, ly, rx, ry = obj.bounds()
                break
            except _RPCStackOverflowError:
                # 微博实崩：点击瞬间 dump 又溢出，瞬态。退避重试（Java 栈 unwind
                # 需要时间），不 relocate（元素仍有效）；超限抛 StepError 继续跑。
                rpc_attempts += 1
                if rpc_attempts <= rpc_retries:
                    time.sleep(rpc_backoff)
                    continue
                from behavior_runner import StepError
                raise StepError("点击前 RPC 栈溢出（元素已失效）")
            except Exception as e:  # noqa: BLE001 - u2 RPC 错误族统一按失效处理
                if stale_attempts == 0 and relocate is not None:
                    fresh = relocate()
                    if fresh is not None and fresh is not obj:
                        obj = fresh
                        stale_attempts += 1
                        continue
                from behavior_runner import StepError
                raise StepError(
                    f"点击前元素已失效（{e.__class__.__name__}，页面可能已变化）")
        cx = (lx + rx) // 2
        cy = (ly + ry) // 2
        x, y = self.human.jitter_point(cx, cy)
        if self.dry_run:
            return
        self.human.tap(self.d, x, y)

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

    def _locate_with_kb(self, app_name, primary, timeout=6):
        """查知识库并尝试候选定位；返回 (obj, has_entry, attempted)。

        - 无知识库记录           -> 只用主 selector 定位，has_entry=False；
        - 记录已 disabled        -> cands 为空，attempted=False，跳过元素定位；
        - 有记录且启用           -> 依次尝试主 + 启用 alternatives。
        失败回写 mark_fail 遵循「仅当 has_entry and cands（实际尝试过才计数）」。
        """
        cands, has_entry = self._kb_candidates(app_name, primary)
        attempted = bool(cands)
        if cands:  # 空列表=知识库已 disabled，跳过元素定位直接转视觉
            for sel in cands:
                k, v = _parse_sel(sel)
                res = self._locate(k, v, timeout)
                if res.hit:
                    return res.obj, has_entry, attempted
        if has_entry and attempted:
            self.knowledge.mark_fail(app_name, primary)
        return None, has_entry, attempted

    def _click_tracked(self, obj, app_name, primary, has_entry, log_text,
                       relocate=None):
        """命中分支共享件：知识库 mark_ok + 真人化点击 + 日志。

        relocate：元素失效（StaleObject）时的重定位回调，透传 _click_obj。
        """
        if has_entry:
            self.knowledge.mark_ok(app_name, primary)
        if not self.dry_run:
            self._click_obj(obj, relocate=relocate)
        self.recorder.log(log_text, app_name)

    def _vision_or_miss(self, act, app_name, desc, allow_vision=True):
        """未命中分支共享件：按开关尝试视觉兜底，命中返回 True。"""
        if allow_vision and self._vision_click(act, app_name, desc):
            return True
        return False

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
            screen_img=img, app=app_name, tag=desc,
            threshold=act.get("template_threshold"))
        if hit is None:
            self.recorder.log(f"视觉兜底全部未命中，放弃该步: {desc}", app_name, "WARN")
            return False
        x, y = self.human.jitter_point(int(hit.x), int(hit.y))
        self.d.click(x, y)
        self.recorder.log(f"视觉兜底点击成功: {desc} -> ({x},{y})", app_name)
        return True
