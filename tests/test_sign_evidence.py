# -*- coding: utf-8 -*-
"""test_sign_evidence.py - 「签到按钮确实被点过了吗」判定规则（2026-10-25）

用户定的口径：**只有复核过签到按钮确实被点过了，才认为已经成功签到。**

本测试锁死三件事：
  1. 认可的三类点击凭据能判出来（多候选 / 点击文本 / 视觉兜底命中）
  2. 一堆看着像成功、其实没有点击凭据的信号，一律判「未确认」
  3. 盲点（点击坐标）和导航类入口（任务/赚钱/任务中心）不算签到凭据

运行：
    ./.venv/Scripts/python.exe -m pytest tests/test_sign_evidence.py -q
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sign_evidence import signed_evidence, SIGN_WORDS, SIGN_EVIDENCE_RULE  # noqa: E402


# ---------- 1. 认可的点击凭据 ----------

def test_multicandidate_hit_on_qiandao():
    log = ("[13:57:51] [INFO] [趣头条] 已启动 趣头条\n"
           "[13:57:51] [INFO] [趣头条] 多候选命中并点击: (text)今日签到\n")
    ok, line, kind = signed_evidence(log)
    assert ok is True
    assert "今日签到" in line
    assert kind == "多候选命中"


def test_click_text_hit():
    log = "[14:13:12] [INFO] [梧桐免费小说] 点击文本: 签到\n"
    ok, line, kind = signed_evidence(log)
    assert ok is True and kind == "文本命中" and "签到" in line


def test_vision_hit_with_desc():
    # click_point 带 desc 时，视觉兜底日志里带得出人类语义
    log = ("[12:00:00] [INFO] [悟空浏览器] 视觉兜底点击成功: "
           "click_point[签到弹窗『立即领取』] -> (812,1463)\n")
    ok, line, kind = signed_evidence(log)
    assert ok is True and kind == "视觉兜底命中"
    assert "立即领取" in line


def test_all_sign_words_are_recognised():
    for w in SIGN_WORDS:
        ok, _, _ = signed_evidence(f"[t] 点击文本: {w}\n")
        assert ok is True, f"词表里的「{w}」应算签到凭据"


# ---------- 2. 没有点击凭据的信号一律未确认 ----------

def test_clean_run_without_click_is_not_success():
    """跑得干干净净、零失败信号，但没有点过签到按钮 → 仍是未确认。"""
    log = ("[t] [INFO] [XX] 已启动 XX\n"
           "[t] [INFO] [XX] 弹窗清扫: 屏幕干净，无需处理\n"
           "[t] [INFO] [XX] 行为[sign] 执行完成\n")
    ok, line, kind = signed_evidence(log)
    assert ok is False and line is None and kind is None


def test_gold_counter_is_not_evidence():
    log = "[t] [INFO] [XX] 金币收益: 3000（当前余额 12800）\n"
    assert signed_evidence(log)[0] is False


def test_no_failure_text_is_not_evidence():
    """没有「步骤失败」字样 ≠ 点过签到按钮。"""
    log = "[t] [INFO] [XX] 行为[sign] 执行完成（无失败步骤）\n"
    assert signed_evidence(log)[0] is False


def test_step_fail_and_miss_are_not_evidence():
    log = ("[t] [WARN] [XX] 步骤失败: 所有候选均未出现: "
           "[{'type': 'text', 'value': '签到'}]\n"
           "[t] [WARN] [XX] 视觉兜底全部未命中，放弃该步: click_point[visual]\n")
    assert signed_evidence(log)[0] is False


def test_empty_log():
    assert signed_evidence("") == (False, None, None)
    assert signed_evidence(None) == (False, None, None)


# ---------- 3. 盲点与导航入口不算凭据 ----------

def test_blind_coordinate_click_is_not_evidence():
    """click_point 的盲点兜底只留「点击坐标: (x,y)」——不能当签到凭据。"""
    log = "[t] [INFO] [XX] 点击坐标: (540,2141)\n"
    assert signed_evidence(log)[0] is False


def test_nav_entry_is_not_sign_button():
    """任务 / 任务中心 / 赚钱 / 多多视频 只是进门，不是签到按钮。"""
    for nav in ("任务", "任务中心", "赚钱", "多多视频", "我的", "首页"):
        log = f"[t] [INFO] [XX] 多候选命中并点击: (text){nav}\n"
        ok, _, _ = signed_evidence(log)
        assert ok is False, f"导航入口「{nav}」不应算签到凭据"


def test_rule_text_mentions_click_verification():
    assert "点过" in SIGN_EVIDENCE_RULE
