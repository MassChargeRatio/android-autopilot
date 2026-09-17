# -*- coding: utf-8 -*-
"""
captcha_slider.py - 滑块验证码识别与拟人拖拽求解

背景（来自反检测评估报告）：国内安卓原生 App 的滑块验证码，其风控核心已从
"视觉谜题"转移到"轨迹行为 + 环境指纹"。纯视觉缺口识别（OpenCV / VLM）只能拿到
"往哪拖"，真正决定能否通过的是"怎么拖"——匀速/直线轨迹必被判定为机器。

本模块把两者分工：
  1. 视觉识别层（缺口坐标）：
     - edge  单图边缘检测找凹槽（默认，零依赖外部服务）
     - diff  双图 RGB 差分（背景 vs 当前，参考 cuiqingcai 阈值法，需提供背景图）
     - vlm   可选，复用 vision.VisionLocator 的 OpenAI 兼容视觉接口输出缺口 x
  2. 轨迹层（拟人拖拽）：复用 human_trajectory.HumanTrajectory，
     生成"先加速后减速 + 中途随机停顿 + 末段微抖"三段式轨迹，
     位移终点强制精确（累积误差清零），经 u2 d.touch 底层注入。
  3. 校验与重试：拖完检测"验证成功"文案；失败则微扰参数重试（默认 3 次）。

坐标说明：d.screenshot() 返回截图尺寸与设备物理分辨率一致（u2 已处理缩放），
故截图像素坐标可直接用于 touch；若真机 dpi 异常可通过 scale 配置校正。
"""
import os
import logging

log = logging.getLogger("captcha")

try:
    import cv2
    import numpy as np
    _HAS_CV2 = True
except Exception:  # pragma: no cover - 依赖缺失时优雅降级
    cv2 = None
    np = None
    _HAS_CV2 = False

from human_trajectory import HumanTrajectory


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# 缺口坐标识别（纯函数，可单测）
# ---------------------------------------------------------------------------
def locate_gap_edge(screen_gray, band_y, band_h, min_area_ratio=0.02):
    """单图边缘检测法找滑块缺口。

    思路：滑块验证码的空缺凹槽通常呈"较暗的垂直条带"，两侧边界有明显梯度。
    在滑块所在的水平带内做 Canny，再对列做边缘投影，缺口竖边会造成局部高密度峰。

    参数：
      screen_gray: 全屏灰度图 (H,W) uint8
      band_y     : 滑块带的中心 y（绝对像素）
      band_h     : 滑块带的高度（绝对像素）
      min_area_ratio: 有效边缘投影值下限（相对于带宽），用于过滤噪声
    返回：
      缺口中心 x（绝对像素）；无法识别返回 None
    """
    if not _HAS_CV2 or screen_gray is None:
        return None
    H, W = screen_gray.shape[:2]
    y0 = int(_clamp(band_y - band_h // 2, 0, H - 1))
    y1 = int(_clamp(band_y + band_h // 2, 0, H))
    if y1 - y0 < 8:
        return None
    band = screen_gray[y0:y1, :]

    band = cv2.GaussianBlur(band, (5, 5), 0)
    edges = cv2.Canny(band, 50, 150)
    col_proj = edges.sum(axis=0).astype(np.float32)  # 每列边缘像素数

    # 滑动高斯窗口平滑投影（缺口竖边是连续的，噪点会稀疏）
    win = max(5, W // 120)
    kernel = np.ones(win, dtype=np.float32) / win
    smoothed = np.convolve(col_proj, kernel, mode="same")

    # 有效峰阈值：明显高于全带平均水平
    base = float(np.percentile(smoothed, 20))
    peak = float(np.max(smoothed))
    if peak - base < (y1 - y0) * min_area_ratio * 3:
        return None

    # 缺口通常偏右侧（滑块从左边拖过来）；找投影峰的质心
    thr = base + (peak - base) * 0.5
    idx = np.where(smoothed >= thr)[0]
    if idx.size == 0:
        return None
    # 取最高的那个峰（连续区域质心）
    runs = np.split(idx, np.where(np.diff(idx) > win * 2)[0] + 1)
    best_run = max(runs, key=lambda r: float(smoothed[r].sum()))
    run_votes = smoothed[best_run]
    total = float(run_votes.sum())
    if total <= 0:
        return None
    x_center = int(float((best_run * run_votes).sum()) / total)
    return x_center


def locate_gap_diff(bg_gray, cur_gray, diff_threshold=60, x_lo=0.0, x_hi=1.0):
    """双图 RGB 差分法找缺口（cuiqingcai 阈值法）。

    背景图 bg_gray（无滑块把手/拼图块的原始背景）与当前截图 cur_gray 相减，
    缺口凹槽处（背景图有图、当前图被拼图块填补）会产生高差分区域。
    返回差分区域质心 x（比例坐标 → 乘以宽度换算）；无明显差分返回 None。
    """
    if not _HAS_CV2 or bg_gray is None or cur_gray is None:
        return None
    if bg_gray.shape != cur_gray.shape:
        H = min(bg_gray.shape[0], cur_gray.shape[0])
        W = min(bg_gray.shape[1], cur_gray.shape[1])
        bg_gray = bg_gray[:H, :W]
        cur_gray = cur_gray[:H, :W]
    diff = cv2.absdiff(bg_gray, cur_gray)
    _, thresh = cv2.threshold(diff, diff_threshold, 255, cv2.THRESH_BINARY)
    # 去除零散噪点
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN,
                              np.ones((3, 3), np.uint8))
    cols = np.where(thresh.sum(axis=0) > 0)[0]
    if cols.size == 0:
        return None
    W = cur_gray.shape[1]
    lo = int(x_lo * W)
    hi = int(x_hi * W)
    cols = cols[(cols >= lo) & (cols <= hi)]
    if cols.size == 0:
        return None
    # 取连通列中最大连续块
    runs = np.split(cols, np.where(np.diff(cols) > 5)[0] + 1)
    best = max(runs, key=lambda r: int(thresh[:, r].sum()))
    return int(best.mean())


# ---------------------------------------------------------------------------
# 滑块验证码求解器
# ---------------------------------------------------------------------------
class SliderCaptchaSolver:
    """滑块验证码求解器。

    用法（由 executor._step_captcha 懒加载调用）：
        solver = SliderCaptchaSolver(captcha_cfg, base_dir, recorder, vision=vl)
        if solver.detect_slider(d, screen_img, dump):
            ok = solver.solve(d, app="xxx")
    """

    def __init__(self, cfg=None, base_dir=None, recorder=None, vision=None,
                 trajectory=None):
        c = cfg or {}
        slider = c.get("slider") or {}
        self.recorder = recorder
        self.base_dir = base_dir or os.getcwd()
        self.vision = vision  # VisionLocator 实例（可选）
        self.trajectory = trajectory or HumanTrajectory(cfg.get("trajectory"))

        self.detect_texts = slider.get("detect_texts") or [
            "按住滑块", "拖动滑块", "向右滑动", "拖动到最右边", "拖动到最右端"]
        self.success_texts = slider.get("success_texts") or [
            "验证成功", "验证通过", "验证完成", "拼图完成", "通过验证"]
        self.retry_times = int(slider.get("retry_times", 3))

        # ---- 滑块位置 ----
        self.handle_templates = list(slider.get("handle_templates") or [])
        self.handle_y_ratio = float(slider.get("handle_y_ratio", 0.85))
        self.handle_x_ratio = float(slider.get("handle_x_ratio", 0.08))
        self.band_h_ratio = float(slider.get("band_h_ratio", 0.06))
        self.scale = float(slider.get("scale", 1.0))  # 截图像素->物理坐标系数

        # ---- 缺口识别 ----
        gap = slider.get("gap") or {}
        self.gap_mode = str(gap.get("mode", "edge")).lower()
        self.diff_threshold = int(gap.get("diff_threshold", 60))
        self.bg_template = gap.get("background_template") or gap.get("bg") or ""
        self.vlm_prompt = gap.get("vlm_prompt") or (
            "图片中存在一个滑块拖拽验证码，请给出缺口（灰暗凹槽）中心的 x 坐标，"
            "只返回数字。")

        # ---- 拖拽 ----
        self.drag_cfg = slider.get("drag") or {}

        # ---- 状态 ----
        self._bg_cache = None  # 背景灰度缓存（diff 模式复用）

    # ------------------------------------------------------------------
    def _log(self, msg, app="", level="INFO"):
        if self.recorder is not None:
            self.recorder.log(msg, app, level)
        else:
            getattr(log,
                    level.lower() if level.lower() in ("info", "warn", "error") else "info")(msg)

    # ------------------------------------------------------------------
    # 检测
    # ------------------------------------------------------------------
    def detect_slider(self, d, screen_img=None, dump=""):
        """判断当前界面是否出现滑块验证码。

        优先用控件树文本匹配（dump text/content-desc），
        其次用 OCR/视觉语义（本实现不做 OCR，留待视觉兜底）。
        """
        if not _HAS_CV2:
            return False
        dump = dump or ""
        dlow = dump.lower()
        # 关键词也转小写对比
        for kw in self.detect_texts:
            if kw.lower() in dlow:
                self._log(f"[captcha] 检测到滑块关键字: {kw}", level="INFO")
                return True
        return False

    # ------------------------------------------------------------------
    # 缺口识别
    # ------------------------------------------------------------------
    def _gray_from(self, screen_img):
        """把 PIL 图 / numpy 图 / 灰度图统一转成灰度 numpy。"""
        if screen_img is None:
            return None
        if isinstance(screen_img, np.ndarray):
            arr = screen_img
        else:
            arr = np.asarray(screen_img)
        if arr.ndim == 3:
            return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
        return arr

    def _handle_position(self, screen_img):
        """取滑块把手起点与所在水平带。

        优先 OpenCV 模板匹配把手（handle_templates 配置）；
        否则用比例定位（handle_y_ratio / handle_x_ratio）。
        返回 ((sx, sy), band_h) 或 None。
        """
        H, W = screen_img.height, screen_img.width
        sy = int(H * self.handle_y_ratio)
        band_h = max(20, int(H * self.band_h_ratio))
        if self.handle_templates and self.vision and self.vision.template_available:
            # 用 VisionLocator 模板匹配找把手中心
            hit = self.vision.locate_on_screen(
                templates=self.handle_templates,
                screen_img=screen_img, tag="captcha_handle")
            if hit is not None:
                sx = int(hit.x * self.scale)
                return (sx, int(hit.y * self.scale)), band_h
        sx = int(W * self.handle_x_ratio * self.scale)
        return (sx, int(sy * self.scale)), band_h

    def locate_gap(self, screen_img, band_y, band_h):
        """识别缺口中心 x（物理坐标）。返回 int 或 None。"""
        gray = self._gray_from(screen_img)
        if gray is None:
            return None
        W = gray.shape[1]
        if self.gap_mode == "diff":
            bg = self._load_bg_gray()
            if bg is not None:
                x = locate_gap_diff(bg, gray, self.diff_threshold)
                if x is not None:
                    return int(x * self.scale)
                self._log(f"[captcha] diff 差分未检出缺口，面积/阈值不匹配", level="WARN")
            else:
                self._log(f"[captcha] 未配置 background_template，无法用 diff 模式", level="WARN")
        elif self.gap_mode == "vlm" and self.vision and self.vision.vlm_available:
            hit = self.vision.locate_by_vlm(screen_img, self.vlm_prompt)
            if hit is not None:
                return int(hit.x * self.scale)
        # 默认/兜底：edge 边缘检测
        x = locate_gap_edge(gray, int(band_y / self.scale), int(band_h / self.scale))
        if x is not None:
            return int(x * self.scale)
        return None

    def _load_bg_gray(self):
        """加载背景图灰度（diff 模式）。路径相对 base_dir 解析。"""
        if not self.bg_template:
            return None
        if self._bg_cache is not None:
            return self._bg_cache
        p = self.bg_template
        if not os.path.isabs(p):
            p = os.path.join(self._base_dir or "", p)
        if not os.path.exists(p):
            self._log(f"[captcha] 背景图不存在: {p}", level="WARN")
            return None
        try:
            data = np.fromfile(p, dtype=np.uint8)
            img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE) if data.size else None
        except Exception:
            img = None
        self._bg_cache = img
        return img

    @property
    def _base_dir(self):
        return self.base_dir

    # ------------------------------------------------------------------
    # 拖拽
    # ------------------------------------------------------------------
    def _drag(self, d, start, gap_x, band_y, attempt):
        """用拟人轨迹把滑块从 start 拖到 (gap_x, band_y)。

        attempt 用于失败重试时微扰参数（改变时长/步数/停顿）。
        返回 True（已注入）或 False。
        """
        duration = self.drag_cfg.get("duration", [0.9, 1.5])
        if isinstance(duration, (list, tuple)):
            dur = duration[0] + (duration[1] - duration[0]) * (0.5 + 0.5 * ((attempt * 37) % 10) / 10)
        else:
            dur = float(duration)
        # 微扰：失败重试时步数/抖动/偏移略变
        jitter = (1.2 + 0.6 * (attempt % 3))
        dist = abs(gap_x - start[0])
        if dist <= 0:
            return False
        # 滑块拖拽轨迹：先加速后减速，终点精确
        from human_trajectory import HumanTrajectory as _HT
        ht = self.trajectory
        # 用 trait 覆盖抖动（重试时增大微颤）
        old_j = ht.jitter_sigma
        ht.jitter_sigma = jitter
        points, intervals = ht.generate_gesture(
            (start[0], band_y), (gap_x, band_y),
            for_slider=True, exact_end=True)
        ht.jitter_sigma = old_j
        ok = ht.inject_touch(d, points, intervals)
        self._log(
            f"[captcha] 拖拽 attempt#{attempt + 1} "
            f"start=({start[0]},{band_y}) gap_x={gap_x} dist={dist}px "
            f"dur={dur:.2f}s points={len(points)} ok={ok}",
            level="INFO")
        return ok

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------
    def _verify_success(self, d, dump=""):
        """拖完后判断是否通过（检测成功文案 / 滑块提示消失）。"""
        dump = dump or ""
        dlow = dump.lower()
        for kw in self.success_texts:
            if kw.lower() in dlow:
                return True
        # 若滑块关键字与成功文案都不在，视为已通过（界面切走了）
        return not self.detect_slider(d, dump=dump)

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def solve(self, d, app="", screen_img=None, dump=""):
        """完整解一次滑块：定位 -> 识别缺口 -> 拟人拖拽 -> 校验 -> 重试。

        返回 bool 是否最终通过。
        """
        if d is None:
            return False
        if screen_img is None:
            screen_img = self._screenshot(d)
        if screen_img is None:
            self._log("[captcha] 截图失败，无法求解", app, "ERROR")
            return False

        handle, band_h = self._handle_position(screen_img)
        if handle is None:
            return False
        sx, sy = handle

        for attempt in range(max(1, self.retry_times)):
            gap_x = self.locate_gap(screen_img, sy, band_h)
            if gap_x is None:
                self._log("[captcha] 缺口识别失败，无法拖拽", app, "WARN")
                return False
            # 缺口 x 与起点同向且向右；容错：坐标异常视为识别失败
            if gap_x <= sx:
                if self.gap_mode == "edge":
                    self._log(f"[captcha] 缺口 x({gap_x}) 不在起点右侧，疑似误检", app, "WARN")
                    return False
            if not self._drag(d, (sx, sy), gap_x, sy, attempt):
                return False
            # 拖完停一小段等判定
            import time
            time.sleep(1.2)
            new_dump = self._dump(d)
            if self._verify_success(d, dump=new_dump):
                self._log("[captcha] 验证成功", app, "INFO")
                return True
            self._log(f"[captcha] 验证未通过，attempt#{attempt + 1} 重试", app, "WARN")
            if attempt + 1 < max(1, self.retry_times):
                # 重试前拖回起点，避免起点漂移
                self._drag_back(d, sx, sy)
                import time as _t
                _t.sleep(0.6)
        return False

    def _drag_back(self, d, sx, sy):
        """简单拖回起点（直线），准备下一轮。"""
        try:
            d.swipe(sx + 40, sy, sx, sy, duration=0.4)
        except Exception:
            pass

    def _screenshot(self, d):
        try:
            return d.screenshot()
        except Exception as e:
            self._log(f"[captcha] 截图失败: {e}", level="WARN")
            return None

    def _dump(self, d):
        try:
            return str(d.dump_hierarchy())
        except Exception:
            return ""
