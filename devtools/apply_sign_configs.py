# -*- coding: utf-8 -*-
"""apply_sign_configs.py - 把用户 2026-10-20 人工勘察的 12 App 签到路径写入 sign 配置

替换既有 sign 段（京东/美团为新增插入 behaviors 顶部）。全部用现有 step 原语：
any_of / click_first / click_point / scroll_to / back / think。
坐标一律 0-1 归一化并注释「待真机校准」。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = os.path.join(ROOT, "config", "apps")

# ---------------- 12 份 sign 配置块 ----------------

S_QUKANTOUTIAO = """  sign:
  # 【用户人工描述 2026-10-20】需关好几个弹窗才进正式界面；底部5按钮右下=我的、右二=任务；任务界面中部最左=今日签到
  # 多轮弹窗清扫（F1 dismiss_popups 上线后由全局清扫接管，此处为过渡手写版）
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 暂不
        - type: text
          value: 关闭
        - type: text
          value: 以后再说
        - type: text
          value: 稍后再说
        - type: text
          value: 我知道了
        - type: text
          value: 知道了
        - type: text
          value: 不再提醒
        - type: text
          value: 取消
        timeout: 3
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 暂不
        - type: text
          value: 关闭
        - type: text
          value: 以后再说
        - type: text
          value: 我知道了
        - type: text
          value: 知道了
        timeout: 3
  # 底部右二 tab「任务」
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 任务
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.7
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部右二tab「任务」坐标兜底（待真机校准）
  - type: think
  # 任务界面中部最左「今日签到」
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 今日签到
        - type: text
          value: 立即签到
        - type: text
          value: 签到
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.16
        y: 0.45
        timeout: 8
        optional: false
        vision: false
        desc: 任务界面中部最左「今日签到」坐标兜底（待真机校准）
"""

S_PINDUODUO = """  sign:
  # 【用户人工描述 2026-10-20】左下数第2 tab=多多视频；其上部最右边缘圆形=签到/提现共用入口；入口任务列表没有签到就滑动；入口上部右侧=提现（暂略）
  # 注意：签到入口禁止截图 → 只用文案+归一化坐标，不用图像模板
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 多多视频
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.3
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部左二tab「多多视频」坐标兜底（待真机校准）
  - type: think
  # 上部最右侧边沿圆形共用入口（禁截图→坐标）
  - type: click_point
    x: 0.93
    y: 0.12
    timeout: 6
    optional: true
    vision: false
    desc: 多多视频页右上缘圆形共用入口（待真机校准）
  # 入口任务列表：没有签到就滑动
  - type: scroll_to
    text: 签到
    max_pages: 4
  - type: click_first
    candidates:
    - type: text
      value: 今日签到
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_JINGDONG = """  sign:
  # 【用户人工描述 2026-10-20】左下数第2 tab=逛；右上缘圆形=签到/提现共用入口；入口中部=连续签到/去提现
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 逛
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.3
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部左二tab「逛」坐标兜底（待真机校准）
  - type: think
  - type: click_point
    x: 0.93
    y: 0.12
    timeout: 6
    optional: true
    vision: false
    desc: 逛页面右上缘圆形共用入口（待真机校准）
  - type: click_first
    candidates:
    - type: text
      value: 连续签到
    - type: text
      value: 今日签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_MEITUAN = """  sign:
  # 【用户人工描述 2026-10-20】左下数第2 tab=视频；右上缘圆形=共用入口；入口上部=今日签到/提现（提现限8-20点，提现组暂略）
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 视频
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.3
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部左二tab「视频」坐标兜底（待真机校准）
  - type: think
  - type: click_point
    x: 0.93
    y: 0.12
    timeout: 6
    optional: true
    vision: false
    desc: 视频页右上缘圆形共用入口（待真机校准）
  - type: click_first
    candidates:
    - type: text
      value: 今日签到
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_KUAISHOU = """  sign:
  # 【用户人工描述 2026-10-20】首页左上角☰侧边栏→上部任务中心→签到，没有就滑动
  - type: click_point
    x: 0.07
    y: 0.06
    timeout: 6
    optional: true
    vision: false
    desc: 首页左上角☰侧边栏（待真机校准）
  - type: think
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 任务中心
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.5
        y: 0.18
        timeout: 8
        optional: false
        vision: false
        desc: 侧边栏上部「任务中心」坐标兜底（待真机校准）
  - type: think
  # 任务中没有签到就滑动
  - type: scroll_to
    text: 签到
    max_pages: 4
  - type: click_first
    candidates:
    - type: text
      value: 今日签到
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_BAIDUMAP = """  sign:
  # 【用户人工描述 2026-10-20】底部5按钮左下=首页右下=我的；首页中部偏下（或上部）「现金签到」
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 暂不
        - type: text
          value: 关闭
        - type: text
          value: 以后再说
        - type: text
          value: 我知道了
        timeout: 3
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 现金签到
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.5
        y: 0.45
        timeout: 8
        optional: false
        vision: false
        desc: 首页中部「现金签到」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 直接领取
    - type: text
      value: 立即签到
    - type: text
      value: 领取
    timeout: 6
    optional: true
"""

S_HAIMA = """  sign:
  # 【用户人工描述 2026-10-20】底部4文本右下=我的、右二=领现金；签到在领现金任务里，没有就滑动
  # 启动弹窗里可能出现签到按钮（旧版 open 弹窗），顺手先试
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 立即签到
        - type: text
          value: 签到领金币
        - type: text
          value: 关闭
        - type: text
          value: 暂不
        timeout: 4
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 领现金
        - type: text
          value: 我的
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.7
        y: 0.97
        timeout: 8
        optional: false
        vision: false
        desc: 底部右二tab「领现金」坐标兜底（待真机校准）
  - type: think
  # 领现金任务里没有签到就滑动
  - type: scroll_to
    text: 签到
    max_pages: 4
  - type: click_first
    candidates:
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    - type: text
      value: 签到领金币
    timeout: 8
    optional: true
"""

S_UC = """  sign:
  # 【用户人工描述 2026-10-20】底部5按钮右下=任务；签到领元宝在任务界面里，没有就滑动
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 任务
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.9
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部右下tab「任务」坐标兜底（待真机校准）
  - type: think
  # 任务界面里没有签到就滑动
  - type: scroll_to
    text: 签到
    max_pages: 4
  - type: click_first
    candidates:
    - type: text
      value: 签到领元宝
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_FEIZHU = """  sign:
  # 【用户人工描述 2026-10-20】能量红包和里程签到都要自动化，都在首页中部
  # 第一目标：能量红包
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 能量红包
        - type: desc
          value: 能量红包
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.5
        y: 0.42
        timeout: 8
        optional: false
        vision: false
        desc: 首页中部「能量红包」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 立即领取
    - type: text
      value: 领取
    - type: text
      value: 签到
    timeout: 6
    optional: true
  - type: back
  - type: think
  # 第二目标：里程签到
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 里程签到
        - type: desc
          value: 里程签到
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.5
        y: 0.55
        timeout: 8
        optional: false
        vision: false
        desc: 首页中部「里程签到」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 今日签到
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 6
    optional: true
"""

S_MIDUXIAOSHUO = """  sign:
  # 【用户人工描述 2026-10-20】底部5按钮右下=任务；我的中部=福利中心；福利中心上部=立即签到
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 福利中心
        timeout: 8
        optional: false
    - - type: click_first
        candidates:
        - type: text
          value: 我的
        timeout: 8
        optional: false
      - type: think
      - type: click_first
        candidates:
        - type: text
          value: 福利中心
        timeout: 8
        optional: false
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_MIDUJISU = """  sign:
  # 【用户人工描述 2026-10-20】底部5按钮右下=我的、右二=福利；福利上部=立即签到
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 福利
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.7
        y: 0.955
        timeout: 8
        optional: false
        vision: false
        desc: 底部右二tab「福利」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

S_DIANPING = """  sign:
  # 【用户人工描述 2026-10-20】首页最右上=签到或得金币；进入后上部=立即签到
  - type: any_of
    optional: true
    choices:
    - - type: click_first
        candidates:
        - type: text
          value: 签到
        - type: text
          value: 得金币
        - type: desc
          value: 签到
        timeout: 8
        optional: false
    - - type: click_point
        x: 0.88
        y: 0.08
        timeout: 8
        optional: false
        vision: false
        desc: 首页右上「签到」坐标兜底（待真机校准）
  - type: think
  - type: click_first
    candidates:
    - type: text
      value: 立即签到
    - type: text
      value: 签到
    timeout: 8
    optional: true
"""

# 文件 -> (sign 块, 是否替换既有 sign 段；False=插入 behaviors 顶部)
JOBS = {
    "01_趣头条.yaml": (S_QUKANTOUTIAO, True),
    "02_拼多多.yaml": (S_PINDUODUO, True),
    "03_京东.yaml": (S_JINGDONG, False),
    "04_美团.yaml": (S_MEITUAN, False),
    "05_快手.yaml": (S_KUAISHOU, True),
    "06_百度地图.yaml": (S_BAIDUMAP, True),
    "07_海马畅听.yaml": (S_HAIMA, True),
    "08_UC浏览器极速版.yaml": (S_UC, True),
    "09_飞猪旅行.yaml": (S_FEIZHU, True),
    "10_米读小说.yaml": (S_MIDUXIAOSHUO, True),
    "11_米读极速版.yaml": (S_MIDUJISU, True),
    "13_大众点评.yaml": (S_DIANPING, True),
}

BOUNDARY = re.compile(r"^  ([A-Za-z]\S*?:)")


def splice_replace(txt, block):
    """替换已有 sign 段（从 '  sign:' 到下一个 behaviors 键或 EOF）。"""
    m = re.search(r"^  sign:\s*$", txt, re.M)
    if not m:
        return None
    lines = txt[m.start():].splitlines(keepends=True)
    end_rel = len(lines)
    for i in range(1, len(lines)):
        if BOUNDARY.match(lines[i]):
            end_rel = i
            break
    return txt[:m.start()] + block + txt[m.start():].split("\n", 0)[0] and \
        txt[:m.start()] + block + "".join(lines[end_rel:])


def splice_insert(txt, block):
    """behaviors: 之后插入新 sign 段。"""
    m = re.search(r"^behaviors:\s*$", txt, re.M)
    if not m:
        return None
    return txt[:m.start()] + "behaviors:\n" + block + txt[m.end():]


def main():
    import yaml
    for fname, (block, replace) in JOBS.items():
        path = os.path.join(APPS, fname)
        txt = open(path, encoding="utf-8").read()
        if replace:
            new = splice_replace(txt, block)
        else:
            new = splice_insert(txt, block)
        if new is None:
            print(f"!! {fname} 未找到锚点，跳过")
            sys.exit(1)
        # 校验 YAML 合法 + sign 在
        cfg = yaml.safe_load(new)
        assert cfg and "sign" in cfg.get("behaviors", {}), f"{fname} sign 缺失"
        assert isinstance(cfg["behaviors"]["sign"], list) and cfg["behaviors"]["sign"]
        open(path, "w", encoding="utf-8").write(new)
        print(f"OK {fname}: sign {len(cfg['behaviors']['sign'])} 步")
    print("ALL DONE")


if __name__ == "__main__":
    main()
