#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""页面归属判定单测 —— 防跨 App 污染。

背景（踩过的坑）：
    目标 App 启动失败/崩溃时，前台会停留在**上一个 App**，于是两个 App 会得到
    完全相同的坐标（看似合理、实为垃圾数据）。uiautomator2 的
    `d.info.currentPackageName` 在这种时序下会失真（已报新包名但屏幕上还是旧 App），
    所以必须从 **dump XML 自身** 的 package 属性分布来判断「屏幕上实际是谁」。

本测试用工程内真实 dump 作为语料，确保：
  1. 正常页面被正确判为「属于目标 App」；
  2. 已知污染样本被正确判为「不属于目标 App」。
"""
import os
import sys
import glob
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "devtools"))

from calibrate import (  # noqa: E402
    package_profile, dominant_package, page_belongs_to, SYS_PKGS,
)

CALIB = os.path.join(ROOT, "devtools", "calib")

# 已知污染样本：天天快讯极速版 的离线 dump 实际抓到的是系统时钟/图库。
# （App 没起来，前台停在系统 App 上）
KNOWN_CONTAMINATED = {
    "天天快讯极速版": "skysky.cy.kuaixun",
}

# 期望判为「属于目标 App」的样本（离线 dump 已确认干净）
KNOWN_CLEAN = {
    "河马剧场": "com.dz.hmjc",
    "红果免费短剧": "com.phoenix.read",
    "抖音": "com.ss.android.ugc.aweme",
    "一淘": "com.taobao.etao",
    "蛋花免费小说": "com.eggflower.read",
}


def _load(app, fname="ui.xml"):
    p = os.path.join(CALIB, app, fname)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8", errors="ignore") as f:
        return f.read()


class TestPageOwner(unittest.TestCase):
    def test_system_packages_excluded(self):
        """系统 UI 包不应计入归属统计。"""
        xml = '<hierarchy><node package="com.android.systemui" class="x"/>' \
              '<node package="com.dz.hmjc" class="y"/></hierarchy>'
        prof = package_profile(xml)
        self.assertEqual(prof, {"com.dz.hmjc": 1})
        for p in SYS_PKGS:
            self.assertNotIn(p, prof)

    def test_dominant_package_picks_majority(self):
        xml = ('<hierarchy>'
               + '<node package="com.a"/>' * 3
               + '<node package="com.b"/>' * 7
               + '</hierarchy>')
        self.assertEqual(dominant_package(xml), "com.b")

    def test_belongs_true_for_own_page(self):
        xml = '<hierarchy>' + '<node package="com.dz.hmjc"/>' * 5 + '</hierarchy>'
        ok, dom, mine, dom_n = page_belongs_to(xml, "com.dz.hmjc")
        self.assertTrue(ok)
        self.assertEqual(dom, "com.dz.hmjc")
        self.assertEqual((mine, dom_n), (5, 5))

    def test_belongs_false_for_foreign_page(self):
        """目标 App 一个节点都没有 -> 判定为不属于。"""
        xml = '<hierarchy>' + '<node package="com.vivo.gallery"/>' * 9 + '</hierarchy>'
        ok, dom, mine, dom_n = page_belongs_to(xml, "skysky.cy.kuaixun")
        self.assertFalse(ok)
        self.assertEqual(dom, "com.vivo.gallery")
        self.assertEqual(mine, 0)

    def test_belongs_tolerates_webview_minority(self):
        """目标包是少数派但达到 ratio 阈值 -> 仍算属于（WebView 内嵌场景）。"""
        xml = ('<hierarchy>'
               + '<node package="com.dz.hmjc"/>' * 6
               + '<node package="com.other.sdk"/>' * 10
               + '</hierarchy>')
        ok, _, mine, dom_n = page_belongs_to(xml, "com.dz.hmjc", ratio=0.5)
        self.assertTrue(ok, f"mine={mine} dom_n={dom_n}")
        # ratio 提高后应判为不属于
        ok2, _, _, _ = page_belongs_to(xml, "com.dz.hmjc", ratio=0.9)
        self.assertFalse(ok2)

    def test_empty_dump_not_belongs(self):
        ok, dom, mine, dom_n = page_belongs_to("", "com.dz.hmjc")
        self.assertFalse(ok)
        self.assertEqual(dom, "")

    def test_known_clean_samples(self):
        """真实干净 dump 应判为属于目标 App。"""
        for app, pkg in KNOWN_CLEAN.items():
            xml = _load(app)
            if xml is None:
                continue
            ok, dom, mine, dom_n = page_belongs_to(xml, pkg)
            self.assertTrue(ok, f"{app}: 期望属于 {pkg}，实际主导 {dom}")

    def test_known_contaminated_samples(self):
        """真实污染 dump 必须被判为不属于目标 App（防假数据）。"""
        checked = 0
        for app, pkg in KNOWN_CONTAMINATED.items():
            for fname in ("ui.xml", "ui_after.xml"):
                xml = _load(app, fname)
                if xml is None:
                    continue
                ok, dom, mine, dom_n = page_belongs_to(xml, pkg)
                self.assertFalse(
                    ok, f"{app}/{fname}: 污染样本被误判为属于 {pkg}（主导 {dom}）")
                checked += 1
        self.assertGreater(checked, 0, "未找到污染样本语料，测试无效")


if __name__ == "__main__":
    unittest.main(verbosity=2)
