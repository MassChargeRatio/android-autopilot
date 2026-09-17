# -*- coding: utf-8 -*-
"""
human_trajectory.py - 人类手势轨迹生成与触摸注入

背景：uiautomator2 的 d.swipe() 本质是直线插值（steps=duration*200），
速度恒定、轨迹笔直，与真人"慢-快-慢 + 弧线 + 末段微颤"的运动特征差异明显，
是行为检测的重要暴露点。

本模块将 Web 端成熟的人类轨迹算法（pyclick 的伯恩斯坦贝塞尔 + 高斯失真、
bezier-mouse-js 的三次贝塞尔、ghost-cursor 的 Fitts 步数 + 过冲修正）移植为
纯 Python 轨迹生成器，并通过 u2 底层触摸接口 d.touch.down/move/up 注入
任意密度的轨迹点，绕开 d.swipe 的直线限制。全程无需 root。

核心算法：
  1. 步数估算（Fitts 思想）：steps = clamp(距离/15, steps_min, steps_max)
  2. 三次贝塞尔曲线，控制点沿垂直于主方向的随机偏移，模拟人手弧线
  3. 速度轮廓（最关键）：smoothstep ease-in-out 把均匀步长映射成
     慢-快-慢的间隔分布，替代匀速
  4. 末段高斯微颤：模拟手指生理抖动（3-25Hz 人体抖动的一个简化）
  5. 过冲回拉（可选，非滑块场景）：远目标先越过再回拉，模拟真人惯性

所有生成函数为纯函数（不依赖设备），可独立单元测试；注入函数才需要设备对象。
"""
import math
import random

try:  # 有 numpy 则用高斯抖动，无则退化 uniform
    import numpy as _np
    _HAS_NUMPY = True
except Exception:  # pragma: no cover
    _HAS_NUMPY = False


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _gauss(mu=0.0, sigma=1.0):
    """单值高斯采样；无 numpy 时用 Box-Muller 近似。"""
    if _HAS_NUMPY:
        return float(_np.random.normal(mu, sigma))
    u1 = random.random()
    if u1 < 1e-12:
        u1 = 1e-12
    u2 = random.random()
    z = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return mu + sigma * z


def _smoothstep(t):
    """smoothstep：3t^2 - 2t^3，构成慢-快-慢的速度轮廓。"""
    t = _clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _ease_out_quad(t):
    """easeOutQuad：1-(1-t)^2，下降/回拉常采用。"""
    t = _clamp(t, 0.0, 1.0)
    u = 1.0 - t
    return 1.0 - u * u


class HumanTrajectory:
    """人类手势轨迹生成器。

    用法（一般由 human.py / captcha_slider.py 调用）：
        ht = HumanTrajectory(config.get("trajectory"))
        points, intervals = ht.generate_gesture((100, 800), (900, 800))
        ht.inject_touch(d, points, intervals)
    """

    def __init__(self, cfg=None):
        c = cfg or {}
        self.enabled = bool(c.get("enabled", True))

        # 步数（Fitts 思想：距离越远步数越多）
        self.steps_min = int(c.get("steps_min", 20))
        self.steps_max = int(c.get("steps_max", 60))
        self.px_per_step = float(c.get("px_per_step", 15))

        # 总时长估算（秒）
        self.duration_per_px = float(c.get("duration_per_px", 0.0007))
        self.duration_min = float(c.get("duration_min", 0.3))
        self.duration_max = float(c.get("duration_max", 1.5))

        # 曲线形态
        self.perpendicular_ratio = float(c.get("perpendicular_ratio", 0.12))
        self.use_ease_in_out = bool(c.get("use_ease_in_out", True))

        # 末段微颤
        self.jitter_sigma = float(c.get("jitter_sigma", 1.2))
        self.jitter_tail_fraction = float(c.get("jitter_tail_fraction", 0.25))

        # 过冲（非滑块场景）
        self.overshoot_prob = float(c.get("overshoot_prob", 0.25))
        self.overshoot_ratio = float(c.get("overshoot_ratio", 0.06))

        # 滑块拖拽专用（captcha 复用）
        self.slider_track = int(c.get("slider_track", int(c.get("slider_track_points", 40))))
        self.slider_duration = (float(c.get("slider_duration", (0.8, 1.4))[0] if isinstance(
            c.get("slider_duration"), (list, tuple)) else c.get("slider_duration", 1.0)))

    # ------------------------------------------------------------------
    # 纯函数：轨迹点生成
    # ------------------------------------------------------------------
    @staticmethod
    def _bezier3(p0, p1, p2, p3, t):
        """三次贝塞尔曲线采样。"""
        u = 1.0 - t
        x = (u ** 3) * p0[0] + 3 * (u ** 2) * t * p1[0] + 3 * u * (t ** 2) * p2[0] + (t ** 3) * p3[0]
        y = (u ** 3) * p0[1] + 3 * (u ** 2) * t * p1[1] + 3 * u * (t ** 2) * p2[1] + (t ** 3) * p3[1]
        return (x, y)

    def _control_points(self, start, end, dist):
        """生成三次贝塞尔控制点：沿垂直于主方向的单侧随机偏移，避免怪异弯曲。

        返回 (p1, p2)。偏移幅度约为行程的 perpendicular_ratio 倍。
        """
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        if dist < 1e-6:
            return start, end
        # 单位法向
        nx, ny = -dy / dist, dx / dist
        # 单侧：法向方向随机取正或负（保持整条弧线向一侧偏）
        side = 1.0 if random.random() < 0.5 else -1.0
        amp = dist * self.perpendicular_ratio * random.uniform(0.5, 1.4)
        mx, my = (start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0
        # 控制点向弧侧外扩展，模拟人手"绕弯"
        p1 = (mx + nx * side * amp, my + ny * side * amp)
        p2 = (mx + nx * side * amp * random.uniform(0.5, 1.2),
              my + ny * side * amp * random.uniform(0.5, 1.2))
        return p1, p2

    def generate_gesture(self, start, end, for_slider=False, exact_end=True):
        """生成一条人类手势轨迹。

        参数：
          start/end : (x, y) 起点/终点（设备物理坐标）
          for_slider: 滑块拖拽模式：强制终点精确、末段不显著过冲、轨迹更"贴着水平线"
          exact_end : 是否强制最后一点恰好等于 end（滑块/点选时 True）
        返回：
          (points, intervals)
            points    : [(x,y), ...] 长度 n>=2
            intervals : [0.0, dt1, dt2, ...] 每两点的睡眠秒数（总长 n-1）
        """
        if not self.enabled:
            n = 8
            pts = [(start[0] + (end[0] - start[0]) * i / (n - 1),
                    start[1] + (end[1] - start[1]) * i / (n - 1)) for i in range(n)]
            return pts, [0.0] + [0.02] * (n - 1)

        p0 = (float(start[0]), float(start[1]))
        p3 = (float(end[0]), float(end[1]))
        dx = p3[0] - p0[0]
        dy = p3[1] - p0[1]
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            return [p0, p3], [0.02]

        # 1) 步数与总时长
        steps = int(_clamp(dist / self.px_per_step, self.steps_min, self.steps_max))
        duration = _clamp(dist * self.duration_per_px, self.duration_min, self.duration_max)

        if for_slider:
            # ---- 滑块模式：近乎纯水平拖动，无贝塞尔弧线，y 仅轻微生理抖动 ----
            n = steps
            ts = [_smoothstep(i / (n - 1)) for i in range(n)]
            pts = []
            for i in range(n):
                x = p0[0] + dx * ts[i]
                # y 在中间段有 ±0.5px 微抖；头尾（贴轨道）保持精确水平
                if 2 <= i <= n - 3:
                    y = p0[1] + _gauss(0, 0.5)
                else:
                    y = p0[1]
                pts.append((x, y))
            intervals = [0.0]
            for i in range(1, n):
                dt = duration * (ts[i] - ts[i - 1]) * random.uniform(0.7, 1.3)
                intervals.append(dt)
            # exact_end 永远成立（渐进映射到 p3）
            pts[-1] = p3
            pts = [(int(round(x)), int(round(y))) for x, y in pts]
            return pts, intervals[1:]

        # 2) 过冲（仅普通滑动）：先越过终点再回拉一小段
        overshoot = 0.0
        if (not for_slider) and random.random() < self.overshoot_prob:
            overshoot = dist * self.overshoot_ratio * random.uniform(0.6, 1.2)
        # 过冲后的真实终点
        if overshoot > 0:
            s = overshoot / dist
            p3o = (p0[0] + dx * (1 + s), p0[1] + dy * (1 + s))
        else:
            p3o = p3

        # 3) 贝塞尔控制点 + 采样
        p1, p2 = self._control_points(p0, p3o, dist + overshoot)
        pts = [self._bezier3(p0, p1, p2, p3o, t)
               for t in (i / (steps - 1) for i in range(steps))]

        # 4) 过冲回拉：末尾追加返回终点的点
        if overshoot > 0:
            back_n = max(3, steps // 6)
            for i in range(1, back_n + 1):
                f = 1.0 - i / back_n
                pts.append((p3[0] + (p3o[0] - p3[0]) * f,
                            p3[1] + (p3o[1] - p3[1]) * f))

        # 5) 速度轮廓：对均匀序号应用缓动，生成非均匀间隔
        n = len(pts)
        if self.use_ease_in_out:
            # 起点慢-中段快-终点慢
            ts = [_smoothstep(i / (n - 1)) for i in range(n)]
        else:
            # 快-慢（常用于"划走"类动作）
            ts = [_ease_out_quad(i / (n - 1)) for i in range(n)]
        intervals = [0.0]
        for i in range(1, n):
            dt = duration * (ts[i] - ts[i - 1])
            # 随机微扰间隔，破坏"每两个点间几乎同一时长"的规整性
            dt *= random.uniform(0.6, 1.4)
            intervals.append(dt)

        # 6) 末段微颤：人体手指抖动（保留起点/终点稳定）
        if self.jitter_sigma > 0:
            tail_from = int(n * (1.0 - self.jitter_tail_fraction))
            for i in range(tail_from, n - 1):
                f = (i - tail_from) / max(1, (n - 1 - tail_from))
                sigma = self.jitter_sigma * (0.3 + 0.7 * f)
                pts[i] = (pts[i][0] + _gauss(0, sigma), pts[i][1] + _gauss(0, sigma))

        # 7) exact_end：强制终点恰为 end（滑块关键：累积误差不许留在终点）
        if exact_end:
            pts[-1] = p3
            # 把最后一个 sleep 稍拉长，模拟"落定"
            intervals[-1] = intervals[-1] + random.uniform(0.05, 0.2)

        # 整数化坐标（设备用像素）
        pts = [(int(round(x)), int(round(y))) for x, y in pts]
        # intervals 首位为 0.0 表示"起点位移 0"，对外统一返回长度 n-1
        return pts, intervals[1:]

    # ------------------------------------------------------------------
    # 注入：u2 底层触摸接口
    # ------------------------------------------------------------------
    def inject_touch(self, d, points, intervals, use_swipe_points_fallback=True):
        """把轨迹点序列通过 u2 touch 底层注入设备。

        优先 d.touch.down/move/up；若底层异常则退回 d.swipe_points（多段折线）。
        points   : [(x,y), ...]
        intervals: 每两点间的睡眠秒数，长度 == len(points)-1
        """
        if d is None or len(points) < 2:
            return False
        coords = [(int(p[0]), int(p[1])) for p in points]
        try:
            touch = d.touch
            touch.down(coords[0][0], coords[0][1])
            # 首点停一小段再开动（真人的"着手"延迟）
            import time as _t
            _t.sleep(min(0.12, intervals[0] * 0.5 if intervals else 0.08))
            for i in range(1, len(coords)):
                touch.move(coords[i][0], coords[i][1])
                dt = intervals[i - 1] if i - 1 < len(intervals) else 0.02
                if dt > 0:
                    _t.sleep(dt)
            touch.up(coords[-1][0], coords[-1][1])
            return True
        except Exception:
            if use_swipe_points_fallback:
                try:
                    # 折线兜底：分段滑动（每段 0.005s）
                    d.swipe_points([(int(p[0]), int(p[1])) for p in points], duration=0.005)
                    return True
                except Exception:
                    return False
            return False

    # ------------------------------------------------------------------
    # 便捷：一段自然滑动（给 human.natural_swipe 用）
    # ------------------------------------------------------------------
    def natural_swipe_points(self, d, start=None, end=None, duration_fixed=None):
        """按屏幕比例生成一段自然滑动并注入。

        start/end 缺省时按模拟器/真机常规比例随机取（参考 human.py natural_swipe）：
        起手 55%~75% 高度，终点 15%~38% 高度。
        返回 (points, intervals) 供日志/测试。
        """
        if d is None:
            return None, None
        info = d.window_size()
        w, h = info.width, info.height
        if start is None:
            sx = int(w * random.uniform(0.35, 0.65))
            sy = int(h * random.uniform(0.55, 0.75))
        else:
            sx, sy = start
        if end is None:
            ex = sx + int(w * random.uniform(-0.08, 0.08))
            ey = int(h * random.uniform(0.15, 0.38))
        else:
            ex, ey = end
        points, intervals = self.generate_gesture((sx, sy), (ex, ey))
        self.inject_touch(d, points, intervals)
        return points, intervals
