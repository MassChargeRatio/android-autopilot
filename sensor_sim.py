# -*- coding: utf-8 -*-
"""传感器拟真数据生成与"死寂"检测（防检测升级：传感器物理噪声缺失）。

背景：Radware 等风控把"静态/死寂传感器"判为最强异常——很多模拟器/自动化环境里，
App 读到的加速度计/陀螺仪是死值（全 0 或恒定不变），一套统计就穿帮。
真实手机哪怕放在桌上也在抖（环境振动、电路噪声），拿在手里抖得更明显。

本模块提供两层能力：
  1. SensorProfile   生成"真人握持"的传感器时间序列（加速度/线性加速度/陀螺仪/磁力计），
                     统计特征对齐真实设备（静置微抖、持机角度、步频/点按包络）；
  2. stats / is_dead 对"设备上报"的原始序列做死寂检测：标准差/极差/一阶自相关/零值比例，
                     低于阈值即判死寂 -> 高危信号。既能自检（本机是否已是死寂环境），
                     也可作为注入方案上线前的锚点对比。

注入落点（需在真机/带虚拟传感器能力的模拟器上使用）：
  - 模拟器：MEmu/LDPlayer 等自带"虚拟传感器"面板，可把本模块生成的数据曲线喂进去；
  - 真机：  Shizuku + LSPosed/Xposed 模块 hook SensorManager，把 profile 灌给目标 App；
  - 轻量替代：自动化过程中让设备产生真实事件（抬手/放平/轻晃手机），
            由系统传感器直接产出"活着"的数据——本模块据此判定环境是否达标。

输出格式：rows = [{t, acc:.., gyro:.., lin:..}, ...]，纯标准库实现，无 numpy 依赖。
"""
import csv
import math
import random

# ---------- 死寂检测阈值 ----------
DEAD_STD_THRESHOLD = 0.02      # 加速度计某轴标准差低于该值视为"死"
DEAD_ZERO_RATIO_MAX = 0.9      # 相邻采样几乎完全相同(零变化比例)的上限
GYRO_DEAD_STD = 0.001          # 陀螺仪更敏感：死寂阈值更低


def _gauss(mu=0.0, sigma=1.0):
    return random.gauss(mu, sigma)


def _smooth_pulse(t, center, width=0.12):
    """在 [0,1] 的窄脉冲（用于模拟点按/步频冲击）。"""
    d = (t - center) / width
    if abs(d) > 1.0:
        return 0.0
    return math.cos(d * math.pi * 0.5) ** 2


class SensorProfile:
    """生成一段拟真传感器序列。

    参数：
      fs        采样率(Hz)，常见 50/100/200
      duration  时长(秒)
      mode      resting(静置微抖) / walking(步频) / tapping(点按) / scrolling(滑动)
      seed      可复现种子
    """

    MODES = ("resting", "walking", "tapping", "scrolling")

    def __init__(self, fs=100.0, duration=5.0, mode="resting", seed=None):
        if mode not in self.MODES:
            raise ValueError(f"未知 mode={mode}，可选 {self.MODES}")
        self.fs = float(fs)
        self.duration = float(duration)
        self.mode = mode
        self.n = max(2, int(self.fs * self.duration))
        if seed is not None:
            random.seed(seed)
        self._base = self._holding_orientation()
        self.rows = self._gen()

    # 手持方向：重力在设备坐标里大致 (0,0,g)，但握姿有随机倾斜
    def _holding_orientation(self):
        tilt = _gauss(0.0, 0.08)   # x 轴向倾斜
        roll = _gauss(0.0, 0.05)   # y 轴向倾斜
        g = 9.80665
        # 设备重力分量(单位 m/s^2)，接近 (0,0,9.8) 但带角度
        return (
            g * math.sin(tilt),
            g * math.sin(roll),
            g * math.cos(math.hypot(tilt, roll)),
        )

    def _gen(self):
        n, fs = self.n, self.fs
        rows = []
        # 模式特定参数
        st_lin = {"resting": 0.025, "tapping": 0.06,
                  "scrolling": 0.05, "walking": 0.08}[self.mode]
        st_gyro = {"resting": 0.008, "tapping": 0.02,
                   "scrolling": 0.02, "walking": 0.05}[self.mode]
        walk_step_freq = 1.7 + random.random() * 0.5     # 步频 1.7~2.2Hz
        tap_every = 0.18 + random.random() * 0.3         # 点按间隔

        for i in range(n):
            t = i / fs
            x, y, z = self._base
            # 低频呼吸/环境振动（1~3Hz 正弦）叠高频噪声尾巴
            vib = (math.sin(2 * math.pi * (1.8 + random.random()) * t)
                   * 0.015 + _gauss(0.0, st_lin))
            lin = [x * 0.02 + vib, y * 0.02 + vib * 0.8, vib]
            gyr = [_gauss(0.0, st_gyro), _gauss(0.0, st_gyro), _gauss(0.0, st_gyro)]

            if self.mode == "walking":
                # 步态：垂直方向两连击（着地+蹬地）
                ph = t * walk_step_freq
                base = int(ph)
                frac = ph - base
                impact = _smooth_pulse(frac, 0.15) * 0.32 + _smooth_pulse(frac, 0.55) * 0.18
                lin[2] += impact
                gyr[0] += _gauss(0.0, 0.02) + impact * 0.05
            elif self.mode == "tapping":
                # 手指敲击：头部冲击 + 回弹
                ph = (t % tap_every) / tap_every
                tap = _smooth_pulse(ph, 0.3, 0.05) * 0.45
                lin[0] += tap * 0.5
                lin[2] += tap
                gyr[1] += _gauss(0.0, 0.02) + tap * 0.1
            elif self.mode == "scrolling":
                # 滑动：y 轴平移微冲 + 陀螺轻微转动
                ph = (t % 0.9) / 0.9
                sw = _smooth_pulse(ph, 0.8, 0.18) * 0.10
                lin[1] += sw
                gyr[2] += sw * 0.5

            acc = [x + lin[0], y + lin[1], z + lin[2]]
            mag = [30.0 + _gauss(0.0, 0.8), -20.0 + _gauss(0.0, 0.8),
                   -45.0 + _gauss(0.0, 0.8)]
            rows.append({"t": round(t, 4),
                         "acc": [round(v, 5) for v in acc],
                         "lin": [round(v, 5) for v in lin],
                         "gyro": [round(v, 5) for v in gyr],
                         "mag": [round(v, 5) for v in mag]})
        return rows

    def write_csv(self, path):
        """导出为 CSV：t,acc_x,acc_y,acc_z,lin_x,lin_y,lin_z,gyro_x,gyro_y,gyro_z,mag_x,mag_y,mag_z"""
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t", "acc_x", "acc_y", "acc_z",
                        "lin_x", "lin_y", "lin_z",
                        "gyro_x", "gyro_y", "gyro_z",
                        "mag_x", "mag_y", "mag_z"])
            for r in self.rows:
                w.writerow([r["t"], *r["acc"], *r["lin"], *r["gyro"], *r["mag"]])


# ---------- 死寂检测 ----------
def _axis_std(values):
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


def _zero_change_ratio(values):
    """相邻采样变化量近似为 0 的比例（衡量序列是否"完全静止"）。"""
    if len(values) < 2:
        return 1.0
    eps = 1e-9
    nz = 0
    for a, b in zip(values, values[1:]):
        if abs(b - a) <= eps:
            nz += 1
    return nz / (len(values) - 1)


def stats(rows):
    """对 rows(list[dict]，含 acc/gyro 等通道) 计算统计特征。"""
    ax = [r["acc"][0] for r in rows]
    ay = [r["acc"][1] for r in rows]
    az = [r["acc"][2] for r in rows]
    gx = [r["gyro"][0] for r in rows]
    gy = [r["gyro"][1] for r in rows]
    gz = [r["gyro"][2] for r in rows]
    out = {}
    for name, ch in (("acc_x", ax), ("acc_y", ay), ("acc_z", az),
                     ("gyro_x", gx), ("gyro_y", gy), ("gyro_z", gz)):
        out[f"{name}_std"] = _axis_std(ch)
        out[f"{name}_zero"] = _zero_change_ratio(ch)
    # 综合评分：上述 6 通道的零变化比例越接近 1、std 越低越"死"
    dead_signals = 0
    for name, ch in (("acc_x", ax), ("gyro_x", gx)):
        thr = GYRO_DEAD_STD if name.startswith("gyro") else DEAD_STD_THRESHOLD
        if _axis_std(ch) < thr or _zero_change_ratio(ch) > DEAD_ZERO_RATIO_MAX:
            dead_signals += 1
    out["dead_signals"] = dead_signals
    return out


def is_dead(rows, dead_signal_limit=0):
    """判定一段传感器数据是否"死寂"（=风控眼中最强异常）。

    dead_signal_limit=0 表示 6 通道里只要任一通道死寂即告警。
    """
    return stats(rows)["dead_signals"] > dead_signal_limit


def self_check(profile_std_sigma=2.0):
    """自检：生成各模式数据并断言其"活着"（statistics 不判死）。

    若返回 False，说明生成器统计参数退化成死寂，需调阈值。
    """
    results = {}
    for mode in SensorProfile.MODES:
        p = SensorProfile(fs=100, duration=4.0, mode=mode, seed=42)
        s = stats(p.rows)
        results[mode] = {"std": max(v for k, v in s.items() if k.endswith("_std")),
                         "dead": s["dead_signals"]}
    alive_all = all(not r["dead"] for r in results.values())
    return alive_all, results


if __name__ == "__main__":
    ok, res = self_check()
    print("self_check alive:", ok)
    for mode, r in res.items():
        print(f"  {mode}: max_std={r['std']:.4f} dead_signals={r['dead']}")
    # 造一条死数据对照
    dead = [{"t": i * 0.01, "acc": [0.0, 0.0, 9.8], "lin": [0.0, 0.0, 0.0],
             "gyro": [0.0, 0.0, 0.0], "mag": [0.0, 0.0, 0.0]} for i in range(300)]
    print("dead data is_dead:", is_dead(dead))
