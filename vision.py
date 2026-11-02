# -*- coding: utf-8 -*-
"""
vision.py - 视觉兜底定位模块 (VisionLocator)

背景：uiautomator2 依赖控件树（text / resource-id / content-desc），
当 App 改版、控件变成纯图片按钮、或 H5/WebView 内元素无法命中时，
元素定位会超时失败。本模块提供两级"视觉兜底"，在元素定位失败后接管：

  (a) OpenCV 模板匹配后端（默认，需 opencv-python）：
      给定按钮"局部截图/图片资源"路径，在当前设备全屏截图上做
      多尺度模板匹配，返回中心坐标与置信度。未安装 opencv-python 时
      自动降级跳过，不报错。

  (b) VLM 视觉定位后端（可选占位）：
      调用 OpenAI 兼容的"截图 + 文本 -> 坐标"视觉接口，让大模型
      直接识别目标按钮位置。仅当配置开启且 base_url/api_key/model
      齐全时启用；未配置静默跳过。

所有命中/失败都经由 recorder.log 落盘，便于复盘。
"""
import os
import base64
import json
import logging
import time

log = logging.getLogger("vision")

try:
    import cv2  # noqa: F401
    import numpy as np
    _HAS_CV2 = True
except Exception:  # pragma: no cover - 依赖缺失时优雅降级
    cv2 = None
    np = None
    _HAS_CV2 = False


class TemplateMatch:
    """单次模板匹配结果：中心坐标 + 置信度 + 命中的缩放尺度"""
    __slots__ = ("x", "y", "score", "scale")

    def __init__(self, x, y, score, scale):
        self.x = int(x)
        self.y = int(y)
        self.score = float(score)
        self.scale = float(scale)


class VisionLocator:
    """视觉兜底定位器。

    用法（一般由 executor.py 在元素定位失败时调用）：
        vl = VisionLocator(vision_cfg, base_dir, recorder)
        hit = vl.locate_on_screen(
            templates=["templates/sign_btn.png"],
            prompt="定位'每日签到'按钮",
            device_image=PIL.Image,           # 当前全屏截图
        )
        if hit:
            d.click(hit.x, hit.y)
    """

    def __init__(self, cfg=None, base_dir=None, recorder=None):
        """
        cfg       : config.yaml 的 vision 节（dict），缺省为空 dict
        base_dir  : 项目根目录，用于把 template_dir 相对路径解析成绝对路径
        recorder  : 可选，提供 .log(msg, app, level) 用于落盘；None 时走 logging
        """
        self.cfg = cfg or {}
        self.base_dir = base_dir or os.getcwd()
        self.recorder = recorder

        self.enabled = bool(self.cfg.get("enabled", True))

        # ---- OpenCV 模板后端 ----
        self.template_dir = self.cfg.get("template_dir", "templates")
        self.threshold = float(self.cfg.get("template_threshold", 0.80))
        self.scales = self.cfg.get("template_scales", [0.6, 0.8, 1.0, 1.2, 1.4])
        if isinstance(self.scales, (int, float)):
            self.scales = [float(self.scales)]
        else:
            self.scales = [float(s) for s in (self.scales or [1.0])]
        # 低置信度时是否继续尝试更高（供多候选用）
        self.min_score = max(0.0, min(float(self.cfg.get("min_score", 0.5)), 1.0))

        # ---- VLM 后端 ----
        vlm = self.cfg.get("vlm") or {}
        self.vlm_enabled = bool(vlm.get("enabled", False)) and self.enabled
        self.vlm_base_url = (vlm.get("base_url") or "").rstrip("/")
        self.vlm_api_key = vlm.get("api_key") or ""
        self.vlm_model = vlm.get("model") or ""
        self.vlm_timeout = float(vlm.get("timeout", 30))
        self._vlm_session = None

        self._template_sizes = {}  # 模板绝对路径 -> (w,h)，缓存防重复加载

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _log(self, msg, app="", level="INFO"):
        if self.recorder is not None:
            self.recorder.log(msg, app, level)
        else:
            getattr(log, level.lower() if level.lower() in ("info", "warn", "error") else "info")(msg)

    # ------------------------------------------------------------------
    # 后端可用性
    # ------------------------------------------------------------------
    @property
    def template_available(self) -> bool:
        return _HAS_CV2 and self.enabled

    @property
    def vlm_available(self) -> bool:
        return bool(self.vlm_enabled and self.vlm_base_url and self.vlm_api_key and self.vlm_model)

    # ------------------------------------------------------------------
    # (a) OpenCV 模板匹配后端
    # ------------------------------------------------------------------
    def _abs_template_path(self, path: str) -> str:
        """把模板路径解析为绝对路径。支持相对 base_dir、相对 template_dir。"""
        p = str(path)
        if os.path.isabs(p):
            return p
        for root in (self.base_dir, os.path.join(self.base_dir, self.template_dir or "")):
            cand = os.path.join(root, p)
            if os.path.exists(cand):
                return cand
        return os.path.join(self.base_dir, self.template_dir or "", p)

    @staticmethod
    def _imread_unicode(path: str):
        """cv2.imread 在 Windows 下无法解析中文路径，改用 np.fromfile+imdecode。"""
        try:
            data = np.fromfile(path, dtype=np.uint8)
            if data.size == 0:
                return None
            gray = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
            return gray
        except Exception:
            return None

    def _load_template_gray(self, path: str):
        """加载模板灰度图（带缓存），返回 (gray, w, h) 或 None"""
        apath = self._abs_template_path(path)
        if not os.path.exists(apath):
            self._log(f"模板图片不存在: {apath}", "", "WARN")
            return None
        if apath in self._template_sizes:
            w, h = self._template_sizes[apath]
            gray = self._gray_cache.get(apath)
            if gray is not None:
                return gray, w, h
        gray = self._imread_unicode(apath)
        if gray is None:
            self._log(f"模板图片无法解析(cv2): {apath}", "", "WARN")
            return None
        if gray.size == 0:
            return None
        # 缩小模板，避免模板比截图还大
        h, w = gray.shape[:2]
        self._template_sizes[apath] = (w, h)
        self._gray_cache = getattr(self, "_gray_cache", {})
        self._gray_cache[apath] = gray
        return gray, w, h

    def match_template(self, screen_gray, template_path: str, threshold=None) -> TemplateMatch:
        """在屏幕灰度图上做多尺度模板匹配，返回最佳命中（None 表示未达到阈值）。

        screen_gray : 全屏截图灰度图（numpy uint8 2D）
        template_path: 模板图片路径（按钮局部截图）
        threshold   : 可选，本次调用覆盖全局 template_threshold（按步骤精调判别用）
        """
        if not self.template_available:
            return None
        loaded = self._load_template_gray(template_path)
        if loaded is None:
            return None
        tpl_gray, tw, th = loaded
        if tw < 4 or th < 4:
            return None
        sh, sw = screen_gray.shape[:2]
        if tw > sw or th > sh:
            # 模板大于屏幕：按屏幕尺寸整体缩放模板
            scale = min(sw / tw, sh / th) * 0.95
            tw2, th2 = max(4, int(tw * scale)), max(4, int(th * scale))
            tpl_gray = cv2.resize(tpl_gray, (tw2, th2), interpolation=cv2.INTER_AREA)
            tw, th = tw2, th2

        best = None
        for s in self.scales:
            tws, ths = max(4, int(tw * s)), max(4, int(th * s))
            if tws > sw or ths > sh:
                continue  # 该尺度超出屏幕，跳过
            tpl_s = cv2.resize(tpl_gray, (tws, ths), interpolation=cv2.INTER_AREA)
            try:
                res = cv2.matchTemplate(screen_gray, tpl_s, cv2.TM_CCOEFF_NORMED)
            except cv2.error:
                continue
            _, maxv, _, maxloc = cv2.minMaxLoc(res)
            if best is None or maxv > best.score:
                best = TemplateMatch(
                    maxloc[0] + tws / 2.0,
                    maxloc[1] + ths / 2.0,
                    maxv, s)
        if best is None or best.score < (self.threshold if threshold is None else threshold):
            return None
        return best

    # ------------------------------------------------------------------
    # (b) VLM 后端（OpenAI 兼容，可选占位）
    # ------------------------------------------------------------------
    def _vlm_chat(self, screen_bytes_b64: str, prompt: str) -> dict:
        """调用 OpenAI 兼容视觉接口，期望返回 JSON：{"x":..,"y":..} 或 {"center":[...]}

        支持主/备用后端：主后端（cfg.vlm）请求或解析失败时，自动切换到
        cfg.vlm.fallback（如 ModelScope 主 / BigModel 备）。
        """
        if not self.vlm_available:
            return None
        try:
            import requests  # 延迟导入，避免硬依赖
        except ImportError:
            self._log("VLM 后端需要 requests（未安装），已跳过", "", "WARN")
            return None

        vlm = self.cfg.get("vlm") or {}
        fbk = vlm.get("fallback") or {}

        def _parse(r):
            content = r["choices"][0]["message"]["content"]
            # content 可能是字符串，或 [{"type":"text","text":...}]
            if isinstance(content, list):
                content = "".join(
                    c.get("text", "") for c in content if isinstance(c, dict))
            content = content or ""
            # 从返回文本中提取第一个 JSON 对象；取不到就抛错，交由上层重试。
            # 实测网关偶发返回内容安全串（如 "User Safety: safe"）而非 JSON，
            # 因此这里必须显式失败，不能静默当成"未命中"。
            if "{" not in content or "}" not in content:
                raise ValueError(
                    f"返回内容中无 JSON 对象: {content.strip()[:80]!r}")
            frag = content[content.find("{"): content.rfind("}") + 1]
            return json.loads(frag), content

        # 尝试一组后端：(主/base_url/api_key/model/timeout)
        backends = [
            (self.vlm_base_url, self.vlm_api_key, self.vlm_model, self.vlm_timeout),
        ]
        if fbk.get("base_url") and fbk.get("api_key") and fbk.get("model"):
            backends.append((fbk["base_url"].rstrip("/"), fbk["api_key"], fbk["model"],
                             float(fbk.get("timeout", 30))))

        last_err = None
        attempts = max(1, int(vlm.get("attempts", 3)))
        for idx, (base_url, api_key, model, timeout) in enumerate(backends):
            url = base_url + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt + (
                                "\n严格按以下要求作答：\n"
                                "1) 坐标必须是 **0-1000 的归一化整数**："
                                "x=0 表示图像最左、x=1000 表示最右，"
                                "y=0 表示图像最上、y=1000 表示最下；"
                                "不要输出像素值；\n"
                                "2) 只有在图中确实能看到该目标时才给坐标；"
                                "若图中不存在该目标，必须返回 "
                                '{"x": null, "y": null}，严禁猜测或退而求其次；\n'
                                "3) 只返回一个 JSON 对象 "
                                '{"x": 整数, "y": 整数}，不要任何其他文字。'
                                if "{target}" not in prompt else ""),
                        },
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screen_bytes_b64}"}},
                    ],
                }],
                "temperature": 0,
            }
            for attempt in range(attempts):
                try:
                    r = self._vlm_post(url, headers, payload, timeout=timeout)
                except Exception as e:  # 网络/超时/4xx 等：换后端
                    last_err = e
                    if len(backends) > 1:
                        self._log(f"VLM 后端#{idx + 1} 调用失败: {e}，切换备用",
                                  "", "WARN")
                    break
                try:
                    data, content = _parse(r)
                    if data:
                        if attempt:
                            self._log(f"VLM 第 {attempt + 1} 次尝试成功",
                                      "", "DEBUG")
                        return data
                    last_err = RuntimeError("JSON 解析为空")
                except Exception as e:
                    last_err = e
                    self._log(f"VLM 后端#{idx + 1} 返回解析失败"
                              f"（第 {attempt + 1}/{attempts} 次）: {e}",
                              "", "DEBUG")
                time.sleep(0.5)
            if len(backends) > 1:
                self._log(f"VLM 后端#{idx + 1} 用尽重试，切换备用", "", "WARN")
        self._log(f"VLM 调用失败(全部后端): {last_err}", "", "WARN")
        return None

    def _vlm_post(self, url, headers, payload, timeout=None):
        """单次 POST（不复用连接会话）。

        坑位记录：本工程所用视觉网关会下发 cookie；若复用 requests.Session，
        从第二次请求起会陷入重定向环并抛
        `TooManyRedirects: Exceeded 30 redirects`（实测第 1 次成功、第 2/3 次必失败）。
        因此这里改为每次独立请求，且不自动跟随重定向：3xx 直接判失败，
        交由上层重试（重试时无旧 cookie，可立即恢复正常）。
        """
        import requests
        resp = requests.post(
            url, headers=headers, json=payload,
            timeout=timeout if timeout else self.vlm_timeout,
            allow_redirects=False)
        if resp.status_code >= 300:
            loc = resp.headers.get("Location")
            raise RuntimeError(f"HTTP {resp.status_code}"
                               + (f" Location={loc}" if loc else ""))
        resp.raise_for_status()
        return resp.json()

    def locate_by_vlm(self, screen_img, prompt: str) -> TemplateMatch:
        """VLM 视觉定位：输入全屏截图(PIL) + 自然语言目标，返回中心坐标与置信度。

        未启用/未配置时返回 None（静默跳过）。置信度为占位值 0.9（模型已确认坐标）。
        该接口为占位实现：支持本地替换成任意可返回 JSON 坐标的服务。
        """
        if not self.vlm_available or screen_img is None:
            return None
        vlm = self.cfg.get("vlm") or {}
        try:
            import io
            from PIL import Image
            buf = io.BytesIO()
            img = screen_img if isinstance(screen_img, Image.Image) else Image.open(screen_img)
            img = img.convert("RGB")
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception as e:
            self._log(f"截图编码失败: {e}", "", "WARN")
            return None
        data = self._vlm_chat(b64, prompt)
        if not data:
            return None
        # 模型显式声明未命中
        if data.get("found") is False:
            self._log("VLM 明确回报未命中（found=false）", "", "DEBUG")
            return None
        center = data.get("center") or []
        x = data.get("x")
        y = data.get("y")
        if x is None and len(center) >= 1:
            x = center[0]
        if y is None and len(center) >= 2:
            y = center[1]
        # 注意：不能用 `or` 兜底，x/y 合法值可能是 0
        if x is None or y is None:
            self._log(f"VLM 未命中/缺少坐标: {data}", "", "DEBUG")
            return None
        try:
            x, y = float(x), float(y)
        except (TypeError, ValueError):
            self._log(f"VLM 坐标非数值: {data}", "", "WARN")
            return None

        # ---- 坐标空间换算（关键修复）----
        # 实测：该网关背后的视觉模型默认返回 **0~1000 归一化坐标**（Qwen-VL 系列惯例），
        # 而旧代码直接当成像素用，导致同一目标误差高达 ~960px（例如真值 y=1685，
        # 模型回 y=720 → 720/1000*2340 = 1685，完全吻合）。
        # 明确要求归一化后再换算，实测误差降到 8~14px。
        space = str(vlm.get("coord_space", "norm1000")).strip().lower()
        w, h = img.size
        if space == "norm1000" and (x > 1000 or y > 1000):
            # 越界说明模型这次给的是像素坐标，自动切换解释方式，避免误缩放
            self._log(f"VLM 坐标超出归一化范围（{x:g},{y:g}），改按像素解释",
                      "", "DEBUG")
            space = "pixel"
        if space == "norm1000":
            px, py = x / 1000.0 * w, y / 1000.0 * h
            self._log(f"VLM 归一化坐标 ({x:g},{y:g}) -> 像素 ({px:.0f},{py:.0f})",
                      "", "DEBUG")
        else:
            px, py = x, y

        # 边界校验：换算后的像素坐标必须落在截图范围内，否则视为幻觉
        try:
            if not (0 <= px < w and 0 <= py < h):
                self._log(f"VLM 坐标越界（{px:.0f},{py:.0f} 不在 {w}x{h} 内），"
                          "按未命中处理", "", "WARN")
                return None
        except Exception:
            pass
        return TemplateMatch(px, py, 0.9, 1.0)

    # ------------------------------------------------------------------
    # 统一入口（供 executor 调用）
    # ------------------------------------------------------------------
    def locate_on_screen(self, templates=(), prompt="", screen_img=None,
                         app="", tag="", threshold=None):
        """对当前全屏截图依次执行：OpenCV 模板匹配 -> VLM 定位。

        返回第一个有效的 TemplateMatch；全部失败返回 None。
        templates : 模板路径列表（先匹配）
        prompt    : VLM 自然语言目标（在模板全部失败后尝试）
        screen_img: PIL.Image（当前设备截图）
        tag       : 日志标识，如 "click_text[每日签到]"
        threshold : 可选，覆盖全局 template_threshold（按步骤精调判别用）
        """
        if not self.enabled:
            return None
        if screen_img is None:
            return None
        try:
            from PIL import Image
            if isinstance(screen_img, Image.Image):
                arr = np.array(screen_img.convert("RGB"))
                gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            else:
                # 允许直接传 numpy BGR 或灰度
                arr = np.asarray(screen_img)
                gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY) if arr.ndim == 3 else arr
        except Exception as e:
            self._log(f"截图转灰度失败: {e}", app, "WARN")
            return None

        # 1) OpenCV 模板匹配
        if self.template_available:
            for tpl in (templates or []):
                hit = self.match_template(gray, tpl, threshold)
                if hit is not None:
                    self._log(
                        f"视觉兜底[模板] 命中 {os.path.basename(str(tpl))} "
                        f"score={hit.score:.3f} scale={hit.scale} -> ({hit.x},{hit.y}) {tag}",
                        app, "INFO")
                    return hit
                self._log(f"视觉兜底[模板] 未命中 {os.path.basename(str(tpl))} {tag}", app, "DEBUG")

        # 2) VLM 定位
        if self.vlm_available and prompt:
            hit = self.locate_by_vlm(screen_img, prompt)
            if hit is not None:
                self._log(f"视觉兜底[VLM] 命中 -> ({hit.x},{hit.y}) {tag}", app, "INFO")
                return hit

        self._log(f"视觉兜底 全部未命中（templates={len(templates or [])}, vlm={'on' if self.vlm_available else 'off'}）{tag}", app, "DEBUG")
        return None

    # ------------------------------------------------------------------
    # 便捷：从当前设备截图并定位（executor dry-run/demo 用）
    # ------------------------------------------------------------------
    def screenshot_from_device(self, d):
        """从 uiautomator2 设备对象取全屏截图，返回 PIL.Image，失败返回 None"""
        if d is None:
            return None
        try:
            return d.screenshot()
        except Exception as e:
            self._log(f"设备截图失败: {e}", "", "WARN")
            return None
