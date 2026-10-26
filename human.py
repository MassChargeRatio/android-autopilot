# -*- coding: utf-8 -*-
"""
human.py - 真人模拟模块
职责：让自动化行为贴近真人，降低被风控识别的概率：
  1. 作息窗口：只在合理时间段执行
  2. 启动时刻随机偏移：避免每天同一秒动作
  3. 动作间隔随机：每次点击/滑动之间加入人类延迟
  4. 点击坐标抖动：不在控件正中心落点
  5. 随机"思考"与"手滑/分心"小动作
  6. 自然滑动：滑动速度与轨迹随机化
  7. F2 反检测增强（AUTOP-FEAT-2026-10-20）：误触-回退 / 限流长停 /
     验证码冷却 / 乱逛扩展 —— 全部 seed 可复现，禁裸 random.*
"""
import math
import random
import time

from human_trajectory import HumanTrajectory


def _win_wh(d):
    """窗口尺寸 (w, h)；d.window_size() 是 plain tuple，禁直接 .width 访问
    （2026-10-20 回归实测的 latent crash 族，统一经 device_session.win_wh 兼容）。"""
    from device_session import win_wh
    return win_wh(d)


class Human:
    def __init__(self, cfg: dict, seed=None):
        h = cfg.get("human", {}) or {}
        self.enabled = bool(h.get("enabled", True))
        # 统一随机源：同 seed 可复现整条动作序列（A5 随机配置化）
        self._rng = random.Random(seed)
        # 对数正态分布参数：mu 高度比例与 sigma 随机区间（默认与旧硬编码等价）
        ln_cfg = h.get("lognormal", {}) or {}
        self.mu_ratio = float(ln_cfg.get("mu_ratio", 0.18))
        self.sigma_lo, self.sigma_hi = self._pair(
            ln_cfg.get("sigma_range", [0.45, 0.75]))
        # 人类手势轨迹生成器（贝塞尔 + 速度轮廓 + 末段微颤），
        # 替代 u2 原生 d.swipe 直线滑动，见 anti-detection upgrade。
        self.trajectory = HumanTrajectory(cfg.get("trajectory"))

        # 作息窗口：hh:mm
        ww = h.get("wake_window", {}) or {"start": "07:30", "end": "23:00"}
        self.wake_start = self._to_minutes(ww.get("start", "07:30"))
        self.wake_end = self._to_minutes(ww.get("end", "23:00"))

        # 各阶段延迟区间（秒）；支持两种写法：
        #   delay_between: [0.6, 2.2]                    # 区间
        #   delay_between: {range:[0.6,2.2], dist:uniform|lognormal}  # 区间+分布
        self.delay_between, self.delay_between_ln = self._parse_delay(
            h.get("delay_between_actions", [0.6, 2.2]))
        self.delay_after_open, self.delay_after_open_ln = self._parse_delay(
            h.get("delay_after_open", [3.0, 6.0]))
        self.think_delay, self.think_delay_ln = self._parse_delay(
            h.get("think_delay", [1.5, 4.0]))
        self.swipe_duration = self._pair(h.get("swipe_duration", [0.5, 0.9]))
        self.swipe_duration_ln = self._dist_flag(h.get("swipe_duration", [0.5, 0.9]),
                                                 self.delay_between_ln)

        # 启动时刻随机偏移（秒）
        self.start_jitter = h.get("run_jitter_seconds", [0, 600])

        # 抖动与概率
        self.tap_jitter_px = int(h.get("tap_jitter_px", 12))
        self.wander_prob = float(h.get("wander_probability", 0.06))
        self.scroll_prob = float(h.get("scroll_probability", 0.5))
        self.use_swipe_home = bool(h.get("use_swipe_home", False))

        # 随机分布升级：默认用时序延迟用"对数正态"（偏态、长尾），
        # 更接近真人操作间隔统计；设 use_lognormal: false 退回均匀分布。
        self.use_lognormal = bool(h.get("use_lognormal", True))
        # 每项分布自定义：如 delay_between: {range:[0.6,2.2], dist:uniform|lognormal}

        # ---------- F2 反检测增强（AUTOP-FEAT-2026-10-20） ----------
        # 配置段 anti_detection：缺省即下方默认值；所有随机消费走 self._rng
        # （seed 可复现，禁裸 random.* —— monkeypatch 不动的写法不许引入）。
        ad = cfg.get("anti_detection") or {}
        self._anti_enabled = bool(ad.get("enabled", True))
        self.mistake_prob = float(ad.get("mistake_prob", 0.05))
        # wander_probability：anti_detection 段优先，缺省回落 human 段值；
        # 两段都未配置时用 F2 默认 0.10（比旧人设 0.06 更高的乱逛频率）。
        if "wander_probability" in ad:
            self.wander_prob = float(ad.get("wander_probability"))
        elif "wander_probability" not in h:
            self.wander_prob = 0.10
        self.cooldown_every = max(0, int(ad.get("cooldown_every", 12)))
        self.cooldown_seconds = float(ad.get("cooldown_seconds", 20))
        self.cooldown_on_captcha = float(ad.get("cooldown_on_captcha", 300))
        # 点击计数（限流长停用）；验证码冷却期间不再计数猛点
        self._tap_count = 0


    # ---------- 工具 ----------
    @staticmethod
    def _to_minutes(hhmm: str) -> int:
        try:
            h, m = hhmm.strip().split(":")
            return int(h) * 60 + int(m)
        except Exception:
            return 450

    @staticmethod
    def _pair(v):
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            return (float(v[0]), float(v[1]))
        return (0.0, 1.0)

    @classmethod
    def _parse_delay(cls, v):
        """解析延迟配置，返回 (lo,hi, 是否对数正态)。

        支持 [lo,hi] 或 {range:[lo,hi], dist:uniform|lognormal}。
        默认分布取全局 use_lognormal 折算：未显式指定时按 True 计（对数正态）。
        """
        flag = True
        if isinstance(v, dict):
            dist = str(v.get("dist", "lognormal")).lower()
            flag = dist != "uniform"
            v = v.get("range", v.get("lo_hi", []))
        lo, hi = cls._pair(v)
        return (lo, hi), flag

    @classmethod
    def _dist_flag(cls, v, default_flag):
        """判断某项是否显式覆盖了分布（dict 形式才生效）。"""
        if isinstance(v, dict):
            return str(v.get("dist", "lognormal")).lower() != "uniform"
        return default_flag

    def _rand(self, a, b, lognormal=False):
        lo, hi = min(a, b), max(a, b)
        if hi <= lo:
            return lo
        if not lognormal:
            return self._rng.uniform(lo, hi)
        # 对数正态（偏态/长尾）：大部分值贴近区间低端，偶尔一段偏长的停顿，
        # 更接近真人操作间隔的统计形态（多数快、偶尔慢）。
        # mu 设在区间约 18% 高度处，sigma 控制长尾；结果 clamp 回 [lo, hi]。
        mean = max(lo, lo + (hi - lo) * self.mu_ratio)
        sigma = self.sigma_lo + (self.sigma_hi - self.sigma_lo) * self._rng.random()
        v = math.exp(self._rng.gauss(math.log(max(mean, 1e-6)), sigma))
        return min(hi, max(lo, v))

    def _sample(self, rng, use_ln):
        return self._rand(*rng, lognormal=use_ln)

    def reseed(self, seed=None):
        """重置随机源：同 seed 可复现整条动作序列。"""
        self._rng = random.Random(seed)
        self._tap_count = 0

    # ---------- 对外行为 ----------
    def in_wake_window(self, now=None) -> bool:
        """当前时刻是否在作息的活跃窗口内"""
        if not self.enabled:
            return True
        now = time.localtime(now if now else time.time())
        cur = now.tm_hour * 60 + now.tm_min
        if self.wake_start <= self.wake_end:
            return self.wake_start <= cur <= self.wake_end
        # 跨天窗口（如 22:00 -> 02:00）
        return cur >= self.wake_start or cur <= self.wake_end

    def start_wait(self) -> float:
        """返回启动前应等待的随机秒数（把动作时刻打散）"""
        if not self.enabled:
            return 0.0
        return self._rng.uniform(*self._pair(self.start_jitter))

    def delay(self):
        """两次不相关动作之间的间隔"""
        time.sleep(self._sample(self.delay_between, self.delay_between_ln))

    def think(self):
        """页面切换后的'思考'停留"""
        time.sleep(self._sample(self.think_delay, self.think_delay_ln))

    def after_open(self):
        """app 首屏加载后的随机停留"""
        time.sleep(self._sample(self.delay_after_open, self.delay_after_open_ln))

    def jitter_point(self, x: int, y: int):
        """对控件中心坐标做小幅随机偏移，避免每次都点正中心"""
        if not self.enabled or self.tap_jitter_px <= 0:
            return x, y
        return (x + self._rng.randint(-self.tap_jitter_px, self.tap_jitter_px),
                y + self._rng.randint(-self.tap_jitter_px, self.tap_jitter_px))

    # ---------- F2 反检测增强 ----------

    def tap(self, d, x: int, y: int):
        """统一点击入口（F2，替代 locator._click_obj 里的裸 d.click）：

        1. 限流：每 cooldown_every 次点击后强制一次长停（防机械节奏）；
        2. 误触-回退：以 mistake_prob 概率先点附近错位（小偏移，多数落在
           空白处/同排），愣神一下再点正确位置 —— 增加输入熵。
        误触点刻意保持小偏移：大幅乱点可能真的点进别的功能改变页面状态，
        "像真人"与"不破坏流程"之间取保守值（此取舍已写入
        docs/ANTI_DETECTION.md）。
        """
        self._tap_count += 1
        if self._anti_enabled and self.cooldown_every > 0:
            if self._tap_count % self.cooldown_every == 0:
                time.sleep(self._rand(self.cooldown_seconds * 0.7,
                                      self.cooldown_seconds * 1.3))
        if self._anti_enabled and self.mistake_prob > 0 \
                and self._rng.random() < self.mistake_prob:
            try:
                wh = _win_wh(d)
                w, h = wh if wh else (1080, 2340)
                mx = min(max(x + self._rng.randint(-160, 160), 8), w - 8)
                my = min(max(y + self._rng.randint(-160, 160), 8), h - 8)
                d.click(mx, my)
                time.sleep(self._rand(0.25, 0.7))
            except Exception:
                pass
        d.click(x, y)

    def captcha_cooldown(self) -> float:
        """验证码/风控命中后的会话级冷却（F2）：长停，期间不重试猛点。

        返回实际冷却秒数（0=未启用/零配置）。调用点：_step_captcha 求解失败
        抛 StepError 之前。
        """
        if not self._anti_enabled or self.cooldown_on_captcha <= 0:
            return 0.0
        sec = self._rand(self.cooldown_on_captcha * 0.8,
                         self.cooldown_on_captcha * 1.2)
        time.sleep(sec)
        return sec

    def natural_swipe(self, d):
        """自然滑动：贝塞尔曲线 + 慢-快-慢速度轮廓 + 末段微颤，模拟真实手指。

        若轨迹注入失败（底层异常）则退回 u2 原生 d.swipe 兜底。
        """
        if not self.enabled:
            d.swipe(*self._plain_swipe(d))
            return
        wh = _win_wh(d)
        w, h = wh if wh else (1080, 2340)
        # 起手点在 55%~75% 高度处
        sy = int(h * self._rng.uniform(0.55, 0.75))
        sx = int(w * self._rng.uniform(0.35, 0.65))
        # 终点在 20%~38% 高度处，横向也带随机
        ey = int(h * self._rng.uniform(0.15, 0.38))
        ex = sx + int(w * self._rng.uniform(-0.08, 0.08))
        points, intervals = self.trajectory.generate_gesture((sx, sy), (ex, ey))
        ok = self.trajectory.inject_touch(d, points, intervals)
        if not ok:
            # 兜底：曲线注入失败回到原生 swipe
            d.swipe(sx, sy, ex, ey, duration=self._rand(*self.swipe_duration))

    def _plain_swipe(self, d):
        wh = _win_wh(d)
        w, h = wh if wh else (1080, 2340)
        return (int(w * 0.5), int(h * 0.7), int(w * 0.5), int(h * 0.3), 0.5)

    def maybe_wander(self, d):
        """随机'分心'：小概率做一次轻轻滑动/浏览式连滑或短暂停，模拟真人偶尔手滑"""
        if not self.enabled or self._rng.random() > self.wander_prob:
            return
        coin = self._rng.random()
        try:
            if coin < 0.45:
                # 随手向下轻轻翻一点再翻回来
                wh = _win_wh(d)
                if not wh:
                    w, h = 1080, 2340
                else:
                    w, h = wh
                y0, y1 = int(h * 0.4), int(h * 0.6)
                d.swipe(int(w * 0.5), y0, int(w * 0.5), y1, duration=0.3)
                time.sleep(self._rand(0.3, 0.8))
                d.swipe(int(w * 0.5), y1, int(w * 0.5), y0, duration=0.3)
            elif coin < 0.70:
                # F2 乱逛扩展：浏览式连滑 2-3 次（间隔不等，末端停顿不等）
                wh = _win_wh(d)
                if not wh:
                    w, h = 1080, 2340
                else:
                    w, h = wh
                reps = self._rng.randint(2, 3)
                for _ in range(reps):
                    y0 = int(h * self._rng.uniform(0.55, 0.75))
                    y1 = int(h * self._rng.uniform(0.2, 0.35))
                    x0 = int(w * self._rng.uniform(0.35, 0.65))
                    d.swipe(x0, y0, x0, y1,
                            duration=self._rand(0.4, 0.8))
                    time.sleep(self._rand(0.5, 1.5))
            else:
                # 单纯发呆
                time.sleep(self._rand(1.0, 2.5))
        except Exception:
            pass

    def close_naturally(self, d):
        """自然退场：返回键或 Home 键随机选择退出 app"""
        if not self.enabled:
            d.press("back")
            return
        try:
            if self._rng.random() < 0.6:
                d.press("back")
            else:
                d.press("home")
            time.sleep(self._rand(0.8, 1.6))
        except Exception:
            pass
