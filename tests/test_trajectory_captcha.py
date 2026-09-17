# -*- coding: utf-8 -*-
"""
tests/test_trajectory_captcha.py - 轨迹曲线与滑块验证码模块单元测试

运行：python -m tests.test_trajectory_captcha
（从项目根目录运行，保证能 import human_trajectory / captcha_slider）
"""
import os
import sys
import math
import tempfile

# 让脚本能从项目根目录 import
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJ = os.path.dirname(_HERE)
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

import numpy as np

from human_trajectory import HumanTrajectory


def _avg_intervals(intervals):
    """去掉首段后统计剩余间隔的离散度（验证非匀速）。"""
    if len(intervals) <= 3:
        return 0.0
    mid = intervals[2:-2]
    if not mid:
        return 0.0
    mean = sum(mid) / len(mid)
    if mean <= 0:
        return 0.0
    var = sum((v - mean) ** 2 for v in mid) / len(mid)
    return math.sqrt(var) / mean  # 变异系数


def test_gesture_basics():
    ht = HumanTrajectory({})
    points, intervals = ht.generate_gesture((100, 1000), (800, 1000))
    assert len(points) >= 2, "至少要两个点"
    assert points[-1] == (800, 1000), "exact_end 应精确落在终点"
    assert len(intervals) == len(points) - 1, "间隔数应等于点数-1"
    assert points[0] == (100, 1000), "起点应保持"
    print(f"[basics] ok, points={len(points)}, distance~700px")


def test_gesture_fitts_steps():
    """距离越远步数越多（Fitts 思想），且被上下限钳制。"""
    ht = HumanTrajectory({})
    p_short, _ = ht.generate_gesture((0, 500), (100, 500))
    p_long, _ = ht.generate_gesture((0, 500), (2000, 500))
    assert len(p_short) < len(p_long), "远距离应有更多采样点"
    # 超长距离被 steps_max 钳制
    p_huge, _ = ht.generate_gesture((0, 0), (20000, 0))
    assert len(p_huge) <= ht.steps_max + ht.steps_max // 6  # 过冲可能加回拉点
    print(f"[fitts] ok, short={len(p_short)} long={len(p_long)} huge={len(p_huge)}")


def test_gesture_speed_profile():
    """速度轮廓应非匀速（ease-in-out 慢-快-慢），间隔存在明显离散。"""
    ht = HumanTrajectory({})
    _, intervals = ht.generate_gesture((100, 500), (1600, 500))
    cv = _avg_intervals(intervals)
    assert cv > 0.15, f"间隔变化过小(疑似匀速): cv={cv:.3f}"
    print(f"[speed] ok, 间隔变异系数={cv:.3f}")


def test_gesture_curve_nonstraight():
    """普通滑动应产生弧线（控制点法向偏移），轨迹不完全落在直线上。"""
    ht = HumanTrajectory({"perpendicular_ratio": 0.2})
    # 固定随机种子增强可复现性
    import random
    random.seed(7)
    points, _ = ht.generate_gesture((100, 1000), (1800, 1000))
    max_dev = max(abs(y - 1000) for x, y in points[1:-1])
    assert max_dev > 2, "贝塞尔曲线应偏离直线"
    print(f"[curve] ok, 最大垂向偏离={max_dev:.1f}px")


def test_gesture_slider_exact():
    """滑块模式：终点精确、末段微颤小、轨迹单调向右。"""
    ht = HumanTrajectory({})
    import random
    random.seed(11)
    pts, intervals = ht.generate_gesture((80, 1500), (1200, 1500), for_slider=True)
    assert pts[-1] == (1200, 1500), "滑块终点必须精确"
    xs = [p[0] for p in pts]
    assert all(xs[i] <= xs[i + 1] + 1 for i in range(len(xs) - 1)), "滑块应单调向右"
    # 末段抖动幅度应很小（缺口对齐精度）
    tail = pts[-5:]
    max_tail_dev = max(abs(y - 1500) for x, y in tail)
    assert max_tail_dev <= 4, f"滑块末段抖动过大: {max_tail_dev}"
    print(f"[slider] ok, pts={len(pts)}, 末段垂向误差={max_tail_dev:.2f}px")


def test_closed_form():
    """已禁用轨迹时退化为直线。"""
    ht = HumanTrajectory({})
    ht.enabled = False
    pts, intervals = ht.generate_gesture((10, 10), (50, 50))
    assert len(pts) == 8
    assert pts[-1] == (50, 50)


# ------------------- 缺口识别（需 cv2） -------------------
def _make_synthetic_slider_gap():
    """合成一张 1080x240 的滑块底部图：灰色背景 + 中央一段暗色缺口条。"""
    H, W = 240, 1080
    img = np.full((H, W), 200, dtype=np.uint8)
    # 随机纹理噪声，模拟图片
    rng = np.random.default_rng(0)
    noise = rng.integers(-10, 10, size=img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    # 在 x=720 附近画一个缺口（暗条）
    x0, x1, w = 700, 760, 14
    img[:, x0:x1] = 60  # 暗色凹槽
    return img, x0 + w // 2  # 缺口中心


def test_locate_gap_edge():
    from captcha_slider import locate_gap_edge
    img, expect_cx = _make_synthetic_slider_gap()
    cx = locate_gap_edge(img, band_y=120, band_h=120)
    assert cx is not None, "应识别出缺口"
    assert abs(cx - expect_cx) <= 12, f"缺口中心偏移过大: got={cx}, expect={expect_cx}"
    print(f"[gap_edge] ok, 识别中心={cx}, 期望≈{expect_cx}")


def test_locate_gap_diff():
    from captcha_slider import locate_gap_diff
    base = np.full((240, 1080), 200, dtype=np.uint8)
    cur = base.copy()
    # 拼图块填补缺口处：当前图在缺口位置颜色不同 -> 差分出现
    cur[:, 700:760] = 130
    x = locate_gap_diff(base, cur, diff_threshold=40)
    assert x is not None
    assert abs(x - 730) <= 40, f"diff 差分中心偏移: {x}"
    # 无差异时应返回 None
    assert locate_gap_diff(base, base.copy(), diff_threshold=40) is None
    print(f"[gap_diff] ok, 差分中心={x}")


# ------------------- 滑块求解器组装测试（不连设备） -------------------
def test_solver_detect():
    from captcha_slider import SliderCaptchaSolver
    cfg = {
        "enabled": True,
        "slider": {
            "detect_texts": ["按住滑块", "向右滑动"],
            "success_texts": ["验证成功"],
        },
    }
    s = SliderCaptchaSolver(cfg)
    assert s.detect_slider(None, dump="<text>按住滑块向右拖动</text>") is True
    assert not s.detect_slider(None, dump="<text>首页</text>")
    assert s.retry_times == 3, "默认重试 3 次"


def test_solver_handle_position_fallback():
    """无模板时用比例兜底定位滑块起点。"""
    from captcha_slider import SliderCaptchaSolver
    s = SliderCaptchaSolver({"enabled": True, "slider": {}})
    class FakeImg:
        width = 1080
        height = 1920
    handle, band_h = s._handle_position(FakeImg())
    sx, sy = handle
    assert 0 < sx < 300, f"起点 x 应在左侧: {sx}"
    assert sy > 1000, f"滑块应在下半屏: {sy}"
    assert band_h >= 100
    print(f"[handle] ok, start=({sx},{sy}) band_h={band_h}")


def test_config_sections():
    """config.yaml 应包含 trajectory 与 captcha 节且结构合法。"""
    import yaml
    cfg_path = os.path.join(_PROJ, "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    assert "trajectory" in cfg, "缺少 trajectory 节"
    assert cfg["trajectory"]["enabled"] is True
    assert "captcha" in cfg, "缺少 captcha 节"
    assert cfg["captcha"]["slider"]["gap"]["mode"] in ("edge", "diff", "vlm")
    print(f"[config] ok, trajectory={list(cfg['trajectory'].keys())[:5]} "
          f"captcha.gap.mode={cfg['captcha']['slider']['gap']['mode']}")


# ------------------- main -------------------
def main():
    fns = [
        ("gesture_basics", test_gesture_basics),
        ("gesture_fitts_steps", test_gesture_fitts_steps),
        ("gesture_speed_profile", test_gesture_speed_profile),
        ("gesture_curve_nonstraight", test_gesture_curve_nonstraight),
        ("gesture_slider_exact", test_gesture_slider_exact),
        ("closed_form", test_closed_form),
        ("locate_gap_edge", test_locate_gap_edge),
        ("locate_gap_diff", test_locate_gap_diff),
        ("solver_detect", test_solver_detect),
        ("solver_handle_position_fallback", test_solver_handle_position_fallback),
        ("config_sections", test_config_sections),
    ]
    failed = 0
    for name, fn in fns:
        try:
            fn()
        except Exception as e:
            failed += 1
            print(f"[FAIL] {name}: {type(e).__name__}: {e}")
        else:
            print(f"[PASS] {name}")
    print(f"\n== 结果: {len(fns) - failed}/{len(fns)} 通过 ==")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
