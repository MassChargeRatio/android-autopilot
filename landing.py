# -*- coding: utf-8 -*-
"""landing.py - 点击后的「落地校验」（多信号投票，2026-10-23）

背景：坐标点击是盲点。拼多多签到入口是个 ~90px 的圆形浮标，配置写 (0.93,0.12)、
实际在 (0.856,0.167)，偏 80×110px 就静默走到错误页面 —— 整条链后面全错，日志却只有
「滚动 4 页未找到」，看不出是第一步就偏了。

所以坐标点完必须**验证落到了预期页面**。单个信号都不可靠（节点可能为空、模板会因
皮肤/分辨率失效、OCR 会认错字），因此这里做多信号投票：

  S1 text_nodes   页面节点里的 text/desc 是否含期望词（App 有节点时最可靠）
  S2 template     cv2.matchTemplate 在实时截图上找参考小图（纯图形）
  S3 phash        整屏 dHash 与参考截图的海明距离（纯图形，抗轻微缩放/压缩）
  S4 structure    节点数区间 / 前台包名 / activity 关键字
  S5 ocr          若环境装了 OCR 引擎则用（当前 venv 无，自动跳过并记 skipped）

契约：每个信号三态 —— True 通过 / False 失败 / None 不适用（跳过）。
判定：所有「跑起来的」信号都通过才算 ok；全部跳过则 ok=None（未知，不阻断，只记日志）。

配置写法（click_point 可选字段）：

    - type: click_point
      x: 0.856
      y: 0.167
      expect:
        text_any: [金币, 签到, 现金]      # S1
        template: images/拼多多/coin_circle.png   # S2
        phash: images/拼多多/ref_coin_center.png  # S3
        min_nodes: 15                     # S4
        pkg: com.xunmeng.pinduoduo        # S4
        min_pass: 1                       # 可选：允许 N 个信号通过即算过（默认全过）
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    import cv2
    import numpy as np
except Exception:  # pragma: no cover - 无 cv2 时降级为纯 PIL
    cv2 = None
    np = None


# ---------- 基础信号 ----------

def dhash(img, size: int = 8) -> int:
    """差值哈希（64bit 整数）。抗压缩、抗轻微缩放，对布局变化敏感。"""
    g = img.convert("L").resize((size + 1, size))
    px = list(g.getdata())
    bits = 0
    for row in range(size):
        base = row * (size + 1)
        for col in range(size):
            bits = (bits << 1) | (1 if px[base + col] > px[base + col + 1] else 0)
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _read_gray(path: str):
    """读灰度图。必须用 np.fromfile+imdecode：cv2.imread 在 Windows 上读不了
    含中文的路径（本项目所有模板都在 images/<中文App名>/ 下）。"""
    if cv2 is None or not os.path.isfile(path):
        return None
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except Exception:  # noqa: BLE001
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)


def template_score(screen, tpl_path: str) -> float | None:
    """参考小图在实时截图中的最佳匹配度（0~1）。缺 cv2 / 文件不存在 / 模板近乎均匀 → None。

    2026-10-23 修正：TM_CCOEFF_NORMED 对**方差≈0 的均匀模板会退化成恒等于 1**
    （实测 40x40 纯白模板在灰屏上得 1.0），这种模板提供不了任何判别信息，
    必须判为「不适用」而不是高分，否则会用假阳性把落地校验变成摆设。
    """
    tpl = _read_gray(tpl_path)
    if tpl is None:
        return None
    if float(tpl.std()) < 5.0:          # 近乎纯色：无判别力
        return None
    scr = cv2.cvtColor(np.array(screen.convert("RGB")), cv2.COLOR_RGB2GRAY)
    if tpl.shape[0] > scr.shape[0] or tpl.shape[1] > scr.shape[1]:
        return 0.0
    res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
    return float(res.max())


def _node_texts(xml: str | None) -> list[str]:
    if not xml:
        return []
    import re
    out = []
    for m in re.finditer(r'(?:text|content-desc)="([^"]{1,40})"', xml):
        v = m.group(1).strip()
        if v:
            out.append(v)
    return out


def _ocr_texts(img) -> list[str] | None:
    """OCR 信号：环境无引擎时返回 None（跳过，不假装通过）。"""
    for mod_name in ("pytesseract", "easyocr", "paddleocr"):
        try:
            __import__(mod_name)
        except Exception:  # noqa: BLE001
            continue
        if mod_name == "pytesseract":
            try:
                import pytesseract
                return [t for t in pytesseract.image_to_string(img, lang="chi_sim").split()
                        if t.strip()]
            except Exception:  # noqa: BLE001
                return None
        return None       # 其它引擎未接入，保持跳过语义
    return None


# ---------- 主入口 ----------

# 参考图与实时截图都先归一到这个尺寸再算 dHash，否则分辨率/缩放差异会
# 把「同一页面」算成「不同页面」（实测同页 JPEG 重压缩距离 0，跨页 12~33，
# 阈值取 8 有干净间隔；这是拼多多白底卡片页唯一可靠的判别信号）。
PHASH_SIZE = (240, 520)


def _norm(im):
    return im.convert("RGB").resize(PHASH_SIZE)


def _crop_norm(im, region):
    """按归一化 region [x1,y1,x2,y2] 裁剪后再归一到统一尺寸。

    整页 dHash 会被业务状态干扰（实测：签到前/签到后同页距离 23~31，超过阈值 8），
    而页头等稳定区域不受影响。所以参考图与实时截图必须裁同一区域再比。
    """
    im = im.convert("RGB")
    if region and len(region) == 4:
        w, h = im.size
        box = (int(region[0] * w), int(region[1] * h),
               int(region[2] * w), int(region[3] * h))
        box = (max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3]))
        if box[2] > box[0] and box[3] > box[1]:
            im = im.crop(box)
    return im.resize(PHASH_SIZE)

def check_landing(screen, expect: dict, xml: str | None = None,
                  pkg: str | None = None, activity: str | None = None,
                  base_dir: str | None = None) -> dict:
    """按 expect 逐信号校验，返回 {ok, signals, reason, score}。

    ok: True 通过 / False 失败 / None 全部跳过（无法判断，不阻断）
    """
    expect = expect or {}
    base = base_dir or _ROOT
    signals: dict[str, object] = {}

    # S1 文案（节点）
    want = [str(w) for w in (expect.get("text_any") or []) if str(w).strip()]
    if want:
        texts = _node_texts(xml)
        joined = " ".join(texts)
        hit = [w for w in want if w in joined]
        signals["text_nodes"] = bool(hit)
        signals["_text_hit"] = hit
    forbid = [str(w) for w in (expect.get("text_none") or []) if str(w).strip()]
    if forbid:
        joined = " ".join(_node_texts(xml))
        bad = [w for w in forbid if w in joined]
        signals["text_forbidden"] = (not bad)
        signals["_text_bad"] = bad

    # S2 图形模板
    tpl = expect.get("template")
    if tpl:
        path = tpl if os.path.isabs(tpl) else os.path.join(base, tpl)
        score = template_score(screen, path)
        if score is None:
            signals["template"] = None
        else:
            thr = float(expect.get("template_threshold", 0.75))
            signals["template"] = score >= thr
            signals["_template_score"] = round(score, 3)

    # S3 感知哈希（支持 phash_region 只 hash 稳定区域，避开业务状态变化）
    ref = expect.get("phash")
    if ref:
        path = ref if os.path.isabs(ref) else os.path.join(base, ref)
        if os.path.isfile(path):
            from PIL import Image
            region = expect.get("phash_region")
            screen_img = _crop_norm(screen, region)
            try:
                with Image.open(path) as im:
                    ref_img = _crop_norm(im.convert("RGB"), region)
            except Exception as e:  # noqa: BLE001 - 参考图损坏/解码失败时降级为跳过，勿假阴性/勿崩
                signals["phash"] = None
                signals["_phash_error"] = f"{type(e).__name__}: {e}"
            else:
                dist = hamming(dhash(screen_img), dhash(ref_img))
                max_d = int(expect.get("phash_max_dist", 8))
                signals["phash"] = dist <= max_d
                signals["_phash_dist"] = dist
        else:
            signals["phash"] = None

    # S4 结构
    if expect.get("min_nodes") is not None:
        n = (xml or "").count("<node")
        signals["min_nodes"] = n >= int(expect["min_nodes"])
        signals["_nodes"] = n
    if expect.get("max_nodes") is not None:
        n = (xml or "").count("<node")
        signals["max_nodes"] = n <= int(expect["max_nodes"])
    if expect.get("pkg") and pkg:
        signals["pkg"] = (pkg == expect["pkg"])
    if expect.get("activity_contains") and activity:
        signals["activity"] = (str(expect["activity_contains"]) in activity)

    # S5 OCR（可选）
    if expect.get("ocr_any"):
        got = _ocr_texts(screen)
        if got is None:
            signals["ocr"] = None
        else:
            joined = " ".join(got)
            signals["ocr"] = any(str(w) in joined for w in expect["ocr_any"])

    ran = {k: v for k, v in signals.items()
           if not k.startswith("_") and v is not None}
    if not ran:
        return {"ok": None, "signals": signals, "reason": "无可执行信号（全部跳过）",
                "score": 0.0}

    passed = [k for k, v in ran.items() if v]
    min_pass = expect.get("min_pass")
    if min_pass is None:
        ok = len(passed) == len(ran)
    else:
        ok = len(passed) >= int(min_pass)
    reason = ("通过 " + ",".join(passed)) if ok else \
             ("失败：" + ",".join(k for k in ran if not ran[k]))
    return {"ok": ok, "signals": signals, "reason": reason,
            "score": round(len(passed) / len(ran), 3)}


def describe(signals: dict) -> str:
    """把信号压成一行日志。"""
    parts = []
    for k, v in signals.items():
        if k.startswith("_"):
            continue
        if v is None:
            parts.append(f"{k}=skip")
        else:
            parts.append(f"{k}={'ok' if v else 'FAIL'}")
    for k in ("_text_hit", "_text_bad", "_template_score", "_phash_dist", "_nodes"):
        if k in signals:
            parts.append(f"{k[1:]}={signals[k]}")
    return " ".join(parts)
