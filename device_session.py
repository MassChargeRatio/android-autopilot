# -*- coding: utf-8 -*-
"""device_session.py - 设备会话层（D 批从 executor.py 三分拆）

搬迁来源：executor.py 的 Executor 类 —— 连接（L115-129）、_at_top_level
（L133-152）、_reset_to_landing（L155-190）、_dump_safe（L860-866）、
_wait_page_ready（L948-990）、_open_app（L982-997）、_close_app（L999-1011）。

坑位注释原文照搬，禁止润色（见各方法 docstring）。

方法体内通过 `self._xxx` 同名可覆盖入口互相调用：本类被 executor.py 门面
多继承后，self 是 Executor 实例，tests 对 Executor 实例打桩仍然生效。
"""
import time


def win_wh(d):
    """取窗口尺寸，返回 (w, h) 或 None。

    为什么需要：uiautomator2 的 `d.window_size()` 返回的是 **plain tuple**
    (1080, 2340)，而历史代码多处按 `.width/.height` 属性访问 —— 一跑就
    AttributeError（2026-10-20 回归实测：click_point 归一化坐标、swipe、
    natural_swipe、maybe_wander 四类路径全部 latent crash，只因此前验证流程
    文案候选总是先命中、从未真正走到坐标/滑动分支）。
    这里统一兼容两种返回形态，替换全部 `info.width` 访问点。
    """
    if d is None:
        return None
    try:
        info = d.window_size()
    except Exception:
        return None
    if info is None:
        return None
    try:
        return int(info.width), int(info.height)
    except AttributeError:
        return int(info[0]), int(info[1])

try:
    from ui_page import nodes_from_xml, at_top_level_nodes
except ImportError:  # pragma: no cover - 未拷贝 ui_page.py 时关闭复位功能
    nodes_from_xml, at_top_level_nodes = None, None


class DeviceSession:
    """设备会话层：连接、启停 App、页面稳定等待、顶层复位、安全 dump。"""

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

    # ---------- 顶层判定 ----------
    def _at_top_level(self):
        """当前是否在 App 顶层页（底部有 tab 栏）。判据见 ui_page.py。

        与 devtools/verify_live.py 共用同一份实现 —— 两边口径不一致时，
        离线统计的命中率就无法代表真机执行结果。
        """
        # 函数体内读取 executor 模块全局 TOP_LEVEL_LABELS：
        # tests/test_executor_reset.py 打桩 executor.TOP_LEVEL_LABELS 必须生效。
        from executor import TOP_LEVEL_LABELS  # noqa: E402
        if TOP_LEVEL_LABELS is None or not TOP_LEVEL_LABELS:
            return True          # ui_page 缺失：关闭复位，保持旧行为
        try:
            _w, h = self.d.window_size()
        except Exception:
            return True
        xml = self._dump_safe()
        if not xml:
            return False
        nodes = nodes_from_xml(xml)
        return at_top_level_nodes(nodes, h)

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

    def _dump_safe(self):
        try:
            return str(self.d.dump_hierarchy())
        except Exception:
            return ""

    # ---------- 启停 ----------
    def _wait_page_ready(self, pkg, app_name, max_wait=30.0, min_nodes=25,
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
            # 2026-10-23 真机实测修正：地图/信息流/视频类页面的节点数永远在小幅波动
            # （瓦片加载、轮播、动画），永远凑不齐 2 次「连续稳定」，于是每 App 白等满
            # max_wait（实测百度地图 57s）。这里加一条兜底：已过一半预算且节点数
            # 已经足够丰富（>=80），说明真实 UI 已渲染，直接放行并记 WARN 供复盘。
            if (time.time() - t0 > max_wait * 0.5) and n >= 80:
                self.recorder.log(
                    f"页面就绪提前放行: 节点={n}（波动型页面，已过半数等待预算）",
                    app_name, "DEBUG")
                return n, time.time() - t0, True
            prev = n
            time.sleep(poll)
        return last_n, time.time() - t0, False

    def _open_app(self, pkg, app_name, reset=False):
        """启动 App。reset=True 时冷启动（stop=True）。

        2026-10-24 真机教训：默认 app_start 会**恢复上次停留的子页面**
        （实测 UC 停在文章详情页 → 点底部「任务」tab 落到内容区，整条链错）。
        凡入口靠底部 tab / 首页固定位置的 App，应在配置里写 `launch_reset: true`。
        """
        if self.dry_run:
            self.recorder.log(f"[dry-run] 将启动 {app_name} ({pkg})", app_name)
            return
        if reset:
            self.d.app_start(pkg, stop=True)
            self.recorder.log("冷启动（launch_reset）", app_name, "DEBUG")
        else:
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
