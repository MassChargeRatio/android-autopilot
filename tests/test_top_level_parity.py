# -*- coding: utf-8 -*-
"""test_top_level_parity.py - A4 _at_top_level 与 ui_page 判据对拍（无需真机）

背景：执行器与验证器必须用同一套「页面长什么样」的判据（度量与执行同口径）。
本文件把**同一份 XML**分别喂给：
  1. 真实 Executor._at_top_level（走 dump -> nodes_from_xml -> at_top_level_nodes）；
  2. ui_page.at_top_level_nodes(nodes_from_xml(xml), screen_h)；
断言两者输出一致，杜绝执行器与判据库悄悄分叉。

运行：
    python -m pytest tests/test_top_level_parity.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from executor import Executor  # noqa: E402
from ui_page import nodes_from_xml, at_top_level_nodes  # noqa: E402


# 顶层页：底部带 首页/推荐/我的 三个 tab；页面中部还有一个「我的」假命中
XML_TOP = (
    '<hierarchy rotation="0" width="1080" height="2340">'
    '<node index="0" text="" content-desc="" class="android.widget.FrameLayout" '
    'bounds="[0,0][1080,2340]">'
    '<node index="0" text="我的" content-desc="" class="android.widget.TextView" '
    'bounds="[0,627][200,700]"/>'
    '<node index="1" text="首页" content-desc="" class="android.widget.TextView" '
    'bounds="[0,2000][270,2200]"/>'
    '<node index="2" text="推荐" content-desc="" class="android.widget.TextView" '
    'bounds="[270,2000][540,2200]"/>'
    '<node index="3" text="我的" content-desc="" class="android.widget.TextView" '
    'bounds="[810,2000][1080,2200]"/>'
    '</node></hierarchy>'
)

# 二级页：底部只有一个「签到」，中部「我的」是假命中 -> 非顶层页
XML_SECONDARY = (
    '<hierarchy rotation="0" width="1080" height="2340">'
    '<node index="0" text="我的" content-desc="" class="android.widget.TextView" '
    'bounds="[0,627][200,700]"/>'
    '<node index="1" text="签到" content-desc="" class="android.widget.TextView" '
    'bounds="[0,2000][270,2200]"/>'
    '</hierarchy>'
)


class _Rec:
    def log(self, event, app="", level="INFO"):
        pass


def _executor_from(xml, size=(1080, 2340)):
    class _D:
        def window_size(self):
            return size

    ex = Executor.__new__(Executor)
    ex.d = _D()
    ex.recorder = _Rec()
    ex._dump_safe = lambda: xml
    return ex


def _ui_page_verdict(xml, size=(1080, 2340)):
    return at_top_level_nodes(nodes_from_xml(xml), size[1])


def test_parity_top_level_xml():
    """同一顶层页 XML：两个实现都必须判 True。"""
    ex_verdict = _executor_from(XML_TOP)._at_top_level()
    ui_verdict = _ui_page_verdict(XML_TOP)
    assert ex_verdict is True and ui_verdict is True, (ex_verdict, ui_verdict)
    print("OK  顶层页 XML 对拍一致（均 True）")


def test_parity_secondary_xml():
    """同一二级页 XML：两个实现都必须判 False（中部假命中不计）。"""
    ex_verdict = _executor_from(XML_SECONDARY)._at_top_level()
    ui_verdict = _ui_page_verdict(XML_SECONDARY)
    assert ex_verdict is False and ui_verdict is False, (ex_verdict, ui_verdict)
    print("OK  二级页 XML 对拍一致（均 False）")


def test_empty_xml_matches_empty_nodes():
    """空 XML：两个实现输出一致（均为 False）。"""
    ex_verdict = _executor_from("")._at_top_level()
    ui_verdict = _ui_page_verdict("")
    assert ex_verdict is False and ui_verdict is False, (ex_verdict, ui_verdict)
    print("OK  空 XML 对拍一致（均 False）")
