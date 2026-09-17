# -*- coding: utf-8 -*-
"""IP 信誉与出口代理助手（防检测升级）。

IP 信誉属于"环境层"风控：同一设备/同一出口 IP 高频出现、或机房/数据中心 IP，
都会被风控降权甚至直接拦截（配合设备指纹）。uiautomator2 脚本本身控制不了出口 IP，
需在接入层解决，本助手提供：

  1. 给设备设置/清除 http 代理（adb 层，立即可用）；
  2. 检查设备当前代理状态与 PC 出口 IP；
  3. 给出家用/住宅代理与轮换的使用建议（见 --advice）。

常用住宅/移动代理方案：
  - 4G/5G 手机热点 + 本机共享给模拟器（出口=运营商家宽/移动，信誉最好）；
  - 住宅代理（Bright Data / 巨量 / 品赞等），配置为设备 http 代理；
  - 动态拨号 VPS + 代理软件（机房出口，仅适合不在乎 IP 信用等级的场景）。

用法：
  python helper_proxy.py --set 127.0.0.1:7890     # 给默认设备设置代理
  python helper_proxy.py --clear                   # 清除设备代理
  python helper_proxy.py --status                  # 查看设备代理 + PC 出口
  python helper_proxy.py --advice                  # 打印 IP 策略建议
"""
import argparse
import subprocess
import sys

DEFAULT_SERIAL = None  # None = 使用 adb 默认设备（仅一台时）


def _adb(args, serial=DEFAULT_SERIAL):
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", "adb 未安装或不在 PATH，请先安装 Android platform-tools"


def set_proxy(proxy, serial=DEFAULT_SERIAL):
    """proxy 形如 host:port"""
    if ":" not in proxy:
        return False, f"代理格式应为 host:port，收到: {proxy}"
    rc, out, err = _adb(["shell", "settings", "put", "global", "http_proxy", proxy])
    ok = rc == 0
    return ok, (out or err or f"已设置 http_proxy={proxy}")


def clear_proxy(serial=DEFAULT_SERIAL):
    rc, out, err = _adb(["shell", "settings", "delete", "global", "http_proxy"])
    ok = rc == 0
    return ok, (out or err or "已清除 http_proxy（回到直连）")


def get_proxy(serial=DEFAULT_SERIAL):
    rc, out, err = _adb(["shell", "settings", "get", "global", "http_proxy"])
    if rc != 0:
        return None
    return out if out and out != "null" else None


def pc_exit_ip():
    """查 PC 出口公网 IP（尽力而为，不一定都通）。"""
    import urllib.request
    for url in ("https://ifconfig.me/ip", "https://api.ipify.org"):
        try:
            with urllib.request.urlopen(url, timeout=8) as f:
                return f.read().decode().strip()
        except Exception:
            continue
    return None


def status(serial=DEFAULT_SERIAL):
    lines = []
    p = get_proxy(serial)
    lines.append(f"设备 http_proxy: {p if p else '(无，直连)'}")
    ip = pc_exit_ip()
    lines.append(f"PC 出口 IP: {ip if ip else '(查询失败，可能断网或 CDN 拒绝)'}")
    if p:
        host = p.rsplit(":", 1)[0]
        lines.append(f"提示: 设备走代理 {p}，出口以代理为准；若代理为机房 IP，"
                     f"风控信任度低于家宽/移动。")
    return "\n".join(lines)


ADVICE = """IP 策略建议（按信任度从高到低）：
1. 真机 + 手机卡流量（移动/4G5G）：出口=运营商IP，设备指纹与 IP 归属一致，信任度最高；
2. 模拟器接"手机热点共享"（把热点代理给模拟器）：家宽移动出口，次优；
3. 住宅代理（Bright Data/品赞/巨量等）做设备 http 代理：可用，但需保证代理归属地与
   设备时区/语言/界面一致，且单 IP 低频使用；
4. 机房代理/机场：仅适合不在乎 IP 信用度或量级很小的场景，不建议用于签到/提现类。

轮换纪律：
- 同一设备长时间绑定同一 IP 是常态（真人也这样）；换 IP 反而异常，别刻意高频轮换；
- 若需新建任务批量跑，把一批账号按"IP 归属地->时区->设备语言"分成组，一组用一个 IP；
- 出口 IP 的 WHOIS 归属（家宽 vs 机房/云厂商）比 IP 是否变化更关键。

落地动作（立即可做）：
- 用 --status 确认当前出口类型（家宽/机房），记录到运维清单；
- 模拟器/真机场景去前台确认 App 显示的"IP 归属地"与设备本地一致。
"""


def main():
    ap = argparse.ArgumentParser(description="IP 代理与出口检查助手")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--set", metavar="host:port", help="给设备设置 http 代理")
    g.add_argument("--clear", action="store_true", help="清除设备 http 代理")
    g.add_argument("--status", action="store_true", help="查看代理/出口状态")
    g.add_argument("--advice", action="store_true", help="打印 IP 策略建议")
    ap.add_argument("--serial", default=DEFAULT_SERIAL, help="adb 序列号（多设备时必填）")
    args = ap.parse_args()

    if args.set:
        ok, msg = set_proxy(args.set, args.serial)
    elif args.clear:
        ok, msg = clear_proxy(args.serial)
    elif args.status:
        print(status(args.serial))
        return
    else:
        print(ADVICE)
        return
    print(("OK: " if ok else "FAILED: ") + msg)
    if ok and args.set:
        print(status(args.serial))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
