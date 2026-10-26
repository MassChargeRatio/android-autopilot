# SELF_SEARCH_PLAYBOOK.md — 领现金路径引擎自搜寻手册

> 派单：AUTOP-SELFSEARCH-2026-10-20
> 用户原话：「应该总结这些app的领现金过程中，按钮名称、按钮位置、常用步骤的共性，使程序自己有一套思路，不用依赖外部描述而能自己搜寻。」

本文档回答三件事：共性是什么（词表/位置/步骤）、引擎怎么用（自搜寻机制）、新 App 怎么接（配置写法）。

---

## 1. 共性提炼：领现金路径的三要素

12 个 App（趣头条/拼多多/京东/美团/快手/百度地图/海马畅听/UC/飞猪/米读小说/米读极速/大众点评）
用户勘察出的领现金路径高度收敛，抽象为 **入口导航 → 任务容器 → 签到动作** 三段式：

| 要素 | 共性规律 | 典型文案 | 位置先验 |
|------|----------|----------|----------|
| 入口导航（tab） | 底部 tab 带；右二/右下/左二等位置 | 任务 / 我的 / 福利 / 逛 / 视频 / 多多视频 / 领现金 / 首页 | `tab_zone`（底部带） |
| 任务容器（entry） | 任务中心/福利中心等容器页；或首页中部直达入口 | 任务中心 / 福利中心 / 能量红包 / 里程签到 / 现金签到 | 中部（无强先验） |
| 签到动作 | 容器页上部/中部的签到按钮，命名以「签到」为核心族 | 今日签到 / 立即签到 / 签到 / 签到领元宝 / 签到领金币 / 连续签到 / 直接领取 / 领取 | 无（文案族兜底） |

词表落点：`candidates.py` 全局四表（SIGN / TASK_CENTER / NAV_TAB / WITHDRAW），
覆盖度由 `tests/test_selfsearch_candidates.py` 对 APP_PATHS.md 12 条描述全量钉死（未覆盖即红）。

---

## 2. 引擎自搜寻机制（本派单新增能力）

### 2.1 candidates_from：全局词表兜底注入

`click_first` 动作新增可选字段 `candidates_from: sign|task_center|nav_tab|withdraw`：

```
候选池 = 显式 candidates（精确定向，顺序优先） + 全局词表按序追加（自搜寻兜底）
```

规则：
- 显式 candidates 可以省略——只有 `candidates_from` 时即为纯自搜寻；
- 词表注入同样过知识库（disabled 候选跳过）；与显式候选重复自动去重；
- App 级微调：`config/apps/<app>.yaml` 顶部 `extra_candidates:` 段可追加专属文案
  （经 `config_loader.extra_candidates` 读取，追加语义、去重保序）；
- 未知分类：WARN 日志并忽略，不中断执行。

### 2.2 scroll_retry：找不到就滑

`click_first` 可选字段 `scroll_retry: N`：仅当一轮候选全 miss 时，自然向下滑动
1 次并整轮重试，最多 N 次；首轮命中绝不滑动。默认 0（旧行为）。

### 2.3 zone：位置先验加权

`click_first` 可选字段 `zone: tab_zone|top_right|right_edge`，多候选同文案时
`_pick_best` 按区加权：
- `tab_zone`：底部带（top ≥ 92% 屏高）+150，中部 -150；
- `top_right`：顶部右上 +150，其余 -150；
- `right_edge`：右缘（x 中心 ≥ 70% 屏宽）+100，左侧 -100；
- 未知屏尺寸 / 缺坐标 / 未知 zone：中性化，不猜、不惩罚。

### 2.4 三段式行为骨架（推荐配置形态）

```yaml
sign:
- type: any_of
  optional: true
  choices:
  - - type: click_first
      candidates:
      - type: text
        value: 任务        # 入口导航：精确定向词优先
      candidates_from: nav_tab   # 自搜寻兜底
      zone: tab_zone             # 位置先验
      timeout: 8
      optional: false
    - type: click_point         # 坐标兜底必须保留（待真机校准）
      x: 0.7
      y: 0.955
      timeout: 8
      optional: false
      vision: false
      desc: 底部tab坐标兜底
- type: think
- type: click_first
  candidates_from: sign        # 签到动作：纯词表自搜寻
  timeout: 8
  optional: true
```

---

## 3. 新 App 接入清单（自检）

1. 词表覆盖：新增按钮文案若不在 `candidates.py` 四表 → 先补全局表（并在
   `test_selfsearch_candidates.py` 的 fixture 挂上勘察文案）；
2. 配置收敛：sign 链路的 click_first 写 `candidates_from`（能进全局表的候选词
   不再硬编码；顺序敏感词保留显式在前）；
3. 位置先验：底部 tab 加 `zone: tab_zone`，右上浮球类加 `top_right`；
4. 坐标兜底：每个导航/签到入口保留归一化 `click_point` 兜底；
5. 回归：`pytest tests/ -q` 全绿 + `main.py --app <名> --task sign --dry-run`
   EXIT=0（命令行确认路径见 PROGRESS.md 验收段）。

---

## 4. 12 份配置收敛口径（本派单执行记录）

- 所有 12 份 sign 链路均接入 `candidates_from`（nav_tab/task_center/sign）；
- 签到动作步骤：顺序与全局 SIGN 前缀一致者删除硬编码（纯词表自搜寻），
  顺序敏感（如京东「连续签到」优先）者保留显式在前 + 词表去重追加；
- 混合步骤（如海马弹窗清扫+签到、飞猪能量红包 text+desc）：保留显式，词表追加兜底；
- 全部坐标兜底原样保留（米读小说为真机校准值，其余待真机校准）；
- 收敛后命中面不降：显式词仍在（或词表等价注入），坐标兜底俱在。

## 5. 验证结论（2026-10-21）

| 项 | 结果 |
|----|------|
| 全量回归 | 280 passed（基线 274 + 新增 6） |
| py_compile | 0 |
| dry-run | 趣头条 / 美团 EXIT=0 |
| parity 基线 | 已按 12 份收敛后配置刷新 split_baseline |
