# -*- coding: utf-8 -*-
"""test_landing.py - 落地校验多信号投票（2026-10-23）

不依赖设备：用 PIL 合成图像验证 dHash / 模板匹配 / 信号投票逻辑。

运行：
    ./.venv/Scripts/python.exe -m pytest tests/test_landing.py -q
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image, ImageDraw  # noqa: E402

import landing  # noqa: E402


def _img(color=(240, 240, 240), size=(240, 480), box=None):
    im = Image.new("RGB", size, color)
    if box:
        d = ImageDraw.Draw(im)
        d.rectangle(box, fill=(200, 30, 30))
    return im


def test_dhash_identical_and_different():
    a = _img()
    b = _img()
    assert landing.hamming(landing.dhash(a), landing.dhash(b)) == 0
    c = _img(box=(20, 20, 120, 120))
    assert landing.hamming(landing.dhash(a), landing.dhash(c)) > 5
    print("OK  dHash：同图距离 0，异图距离显著")


def test_template_score_hits_crop():
    def _striped(size=(240, 480)):
        im = Image.new("RGB", size, (240, 240, 240))
        d = ImageDraw.Draw(im)
        for i in range(150, 220, 5):        # 带纹理，方差非零
            d.line((i, 60, i, 130), fill=(200, 30, 30))
        return im

    with tempfile.TemporaryDirectory() as tmp:
        screen = _striped()
        tpl_path = os.path.join(tmp, "tpl.png")
        screen.crop((150, 60, 220, 130)).save(tpl_path)
        score = landing.template_score(screen, tpl_path)
        assert score is not None and score > 0.95, score
        # 均匀模板无判别力：TM_CCOEFF_NORMED 会退化成 1.0，必须判「不适用」
        blank = os.path.join(tmp, "blank.png")
        _img(color=(255, 255, 255), size=(40, 40)).save(blank)
        assert landing.template_score(screen, blank) is None, \
            "近均匀模板应判不适用，否则假阳性会把校验变成摆设"
        # 有纹理但不匹配的模板：得分必须低
        noise = os.path.join(tmp, "noise.png")
        n = _img(color=(10, 10, 10), size=(70, 70))
        d = ImageDraw.Draw(n)
        for i in range(0, 70, 7):
            d.line((i, 0, i, 70), fill=(250, 250, 250))
        n.save(noise)
        assert landing.template_score(screen, noise) < 0.9
    print("OK  模板匹配：带纹理裁切命中 >0.95；均匀模板判不适用；异纹理不误命中")


def test_check_text_any():
    xml = '<h><node text="我的金币"/><node text="签到"/></h>'
    r = landing.check_landing(_img(), {"text_any": ["金币", "签到"]}, xml=xml)
    assert r["ok"] is True, r
    r = landing.check_landing(_img(), {"text_any": ["提现"]}, xml=xml)
    assert r["ok"] is False and "text_nodes" in r["reason"], r
    print("OK  文案信号：命中通过 / 未命中失败")


def test_check_text_forbidden():
    xml = '<h><node text="确认提现"/></h>'
    r = landing.check_landing(_img(), {"text_none": ["确认提现"]}, xml=xml)
    assert r["ok"] is False, r
    print("OK  禁用词信号：出现即失败（防误入提现页）")


def test_check_structure_nodes_and_pkg():
    xml = "<h>" + "<node/>" * 30 + "</h>"
    r = landing.check_landing(_img(), {"min_nodes": 20}, xml=xml)
    assert r["ok"] is True, r
    r = landing.check_landing(_img(), {"min_nodes": 50}, xml=xml)
    assert r["ok"] is False, r
    r = landing.check_landing(_img(), {"pkg": "com.x"}, pkg="com.x")
    assert r["ok"] is True
    r = landing.check_landing(_img(), {"pkg": "com.x"}, pkg="com.y")
    assert r["ok"] is False
    print("OK  结构信号：节点数区间 / 包名")


def test_check_no_signals_returns_unknown():
    r = landing.check_landing(_img(), {})
    assert r["ok"] is None, "无信号时应返回 None（不阻断）"
    print("OK  无可用信号 → ok=None（不阻断，只记日志）")


def test_check_phash_ref():
    with tempfile.TemporaryDirectory() as tmp:
        ref = os.path.join(tmp, "ref.png")
        _img(box=(30, 300, 200, 420)).save(ref)
        same = _img(box=(30, 300, 200, 420))
        other = _img(box=(0, 0, 100, 100))
        assert landing.check_landing(same, {"phash": ref})["ok"] is True
        assert landing.check_landing(other, {"phash": ref})["ok"] is False
    print("OK  phash：与参考截图一致通过，不一致失败")


def test_check_phash_corrupt_ref_degrades():
    """参考图损坏（解码抛 OSError）时应降级为跳过（ok=None + _phash_error），不假阴性也不崩。
    回归钉：2026-11-03 蛋花 ref_dialog.png 实测损坏（libpng bad adaptive filter），
    旧代码 Image.open().convert("RGB") 抛 OSError 未捕获 → 落地校验恒假阴性。"""
    with tempfile.TemporaryDirectory() as tmp:
        ref = os.path.join(tmp, "corrupt.png")
        with open(ref, "wb") as f:
            # 合法 PNG 头 + 非法 IDAT（bad adaptive filter），可触发解码失败
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 400)
        r = landing.check_landing(_img(), {"phash": ref})
        assert r["ok"] is None, f"损坏参考图应降级为 ok=None，实际 {r['ok']}"
        assert "_phash_error" in r["signals"], "应记录 _phash_error"
        assert r["signals"].get("phash") is None
    print("OK  phash：损坏参考图降级为跳过（ok=None），不崩不假阴性")


def test_min_pass_allows_partial():
    xml = '<h><node text="别的页面"/></h>'
    expect = {"text_any": ["金币"], "min_nodes": 1, "min_pass": 1}
    r = landing.check_landing(_img(), expect, xml=xml)
    assert r["ok"] is True, r        # text 失败但结构通过，min_pass=1 放行
    r2 = landing.check_landing(_img(), {"text_any": ["金币"], "min_nodes": 1}, xml=xml)
    assert r2["ok"] is False, "默认要求全部信号通过"
    print("OK  min_pass：允许部分信号通过（默认全过）")


def test_describe_is_one_line():
    r = landing.check_landing(_img(), {"text_any": ["金币"], "min_nodes": 1},
                              xml='<h><node text="金币"/></h>')
    s = landing.describe(r["signals"])
    assert "text_nodes=ok" in s and "min_nodes=ok" in s and "\n" not in s
    print("OK  describe 输出单行日志")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} 通过")
    sys.exit(1 if failed else 0)
