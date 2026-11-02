# -*- coding: utf-8 -*-
"""
executor.py - 执行引擎（D 批三分拆后为门面）

原 1010 行实现已按职责拆分为三个部件，本文件保留为 ~160 行门面：

  - device_session.py  ：设备会话（连接/启停/页面稳定/顶层复位/安全 dump）
  - locator.py         ：元素定位（_locate/_pick_best/元素知识库/视觉兜底/A3 共享件）
  - behavior_runner.py ：行为执行（顶层流程/分派/全部 step 原语/收益识别）

门面 Executor 通过多继承组合三者；`__init__` 负责组装 mixin 状态
（d/vision/knowledge/captcha/_variant_last/_diversify_prob 等）。
方法调用经 `self._xxx` 同名可覆盖入口转发 —— tests 对 Executor 实例的
方法打桩（如 `ex._locate=…`）在 MRO 上优先于部件类，仍然生效。

对外兼容：StepError / LocateResult / _parse_sel 在此 re-export
（tests/test_knowledge.py:26 等依赖）；模块级 TOP_LEVEL_LABELS 保留
（tests/test_executor_reset.py:28 monkeypatch 依赖）。
"""
import os

from reward_pick import rank_reward_candidates, _TEXT_ATTR_RE, _BALANCE_HINTS  # noqa: F401,E402

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
    from ui_page import (TOP_LEVEL_LABELS, NAV_BAND_Y, NAV_LABELS,
                         nodes_from_xml, at_top_level_nodes)
except ImportError:  # pragma: no cover - 未拷贝 ui_page.py 时关闭复位功能
    TOP_LEVEL_LABELS, NAV_BAND_Y, NAV_LABELS = set(), 0.80, set()
    nodes_from_xml, at_top_level_nodes = None, None

from device_session import DeviceSession  # noqa: E402
from locator import Locator, LocateResult, _parse_sel  # noqa: E402
from behavior_runner import BehaviorRunner, StepError, _VISION_GATED_STEPS  # noqa: E402,F401

# 对外兼容 re-export（tests 依赖）
__all__ = ["Executor", "StepError", "LocateResult", "_parse_sel"]


class Executor(DeviceSession, Locator, BehaviorRunner):
    def __init__(self, serial: str, human, recorder, dry_run: bool = False,
                 config: dict = None, base_dir: str = None):
        self.serial = serial
        self.human = human
        self.recorder = recorder
        self.dry_run = dry_run
        self.d = None  # uiautomator2 Device
        # B6：最近一次定位动作未命中的 detail（复用原 raise 消息文本，零日志漂移）
        self._last_fail = ""
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

        # F1 全局弹窗清扫（popups 段缺省=关闭，老配置零影响）
        popups_cfg = (config or {}).get("popups") or {}
        self._popups_cfg = popups_cfg
        self._popups_enabled = bool(popups_cfg.get("enabled", False))

        # B1（2026-10-30）：any_of 整次总预算。默认 30 = 现行为（老配置零影响）；
        # 要收窄的 App 在那一步的 act 里写 total_timeout，或改这里全局默认。
        timeouts_cfg = (config or {}).get("timeouts") or {}
        try:
            self._any_of_total = float(timeouts_cfg.get("any_of_total", 30.0))
        except (TypeError, ValueError):
            self._any_of_total = 30.0

        # RPC 超时（2026-10-31）：u2 库默认 300s，实测两个 App 各卡死 300 秒无日志。
        # 默认 20s —— dump/click 正常在 1.5s 内，20s 足够，异常时能及时抛错重试。
        dev_cfg = (config or {}).get("device") or {}
        try:
            self.rpc_timeout = float(dev_cfg.get("rpc_timeout", 20.0))
        except (TypeError, ValueError):
            self.rpc_timeout = 20.0

        # RPC 栈溢出重试（2026-11-01 微博实崩）：RPCStackOverflowError 对应 Android 侧
        # java.lang.StackOverflowError，瞬态（动态层级过深时 dump 失败，unwind 后即恢复）。
        # 重试上限内退避重来；超限记「步骤失败」继续跑，不让单次溢出崩掉整条 App 流程。
        try:
            self.rpc_retries = int(dev_cfg.get("rpc_retries", 2))
        except (TypeError, ValueError):
            self.rpc_retries = 2
        try:
            self.rpc_backoff = float(dev_cfg.get("rpc_backoff", 0.8))
        except (TypeError, ValueError):
            self.rpc_backoff = 0.8
