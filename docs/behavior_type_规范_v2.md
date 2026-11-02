# behavior / type 分层重规划（v2 提案 · 2026-10-28）

> 起因：用户指出「behavior 是准确意图、type 是具体行为」且「分类的逻辑性太差」。
> 本文先给诊断（全部有实测数据），再给 v2 模型与迁移路径。**未改一行配置、未改一行运行期代码。**

---

## 0 结论先行

你问的方向是对的，但**现状不是"两层"，而是"一层 + 一个 98% 冗余的补丁"**：

| 层 | 现在实际是什么 | 问题 |
|---|---|---|
| behavior | 名字就是意图名（99 个 behavior 只用 8 个名字，全部 ⊂ 9 个意图名） | 两层其实是同一层 |
| intent_map | 62 条映射里 61 条是恒等（`sign: sign`），唯一非恒等只有抖音火山版 | 补丁，不是机制 |
| type | 19 个名字里只有 6 个是"动作"，其余是定位/控制流/业务宏 | 四个正交维度压进一个枚举 |

所以"分类逻辑性差"不是命名不好看，是**维度混了**：
`click_text` 和 `click_point` 不是两种动作，是同一个动作的两种"找法"；
`any_of` 不是动作，是控制流；`reward` 不是动作，是数据抽取。
把它们平铺成 19 个 type，就只能靠"别名"和"未知 type 只 WARN"来兜。

---

## 1 诊断（实测数据）

### 1.1 behavior 层：名存实亡

```
99 个 behavior 的去重名字：bonus collect gift open reserve sign watch withdraw   （8 个）
9 个 intent 的名字：        sign reserve watch withdraw collect bonus gift growth open
                            ↑ 完全包含，behavior 名没有一个是意图之外的词
```

```
intent_map 条目 62 条，其中恒等映射 61 条（98%）
非恒等只有 1 条：抖音火山版 sign -> reserve
```

**结论**：`intent_map` 在 98% 的 app 上是纯仪式。真正缺的是"行为"这一层——那些
**跨 app 复用、但没有名字的动作序列**：

- 进任务中心（我的 → 任务中心 → 等页面）
- 关弹窗（多候选 × 8 个文案）
- 回顶再下滑找目标行

这三类在 34 份配置里被抄了 34 遍，改一处要改 34 处。**这才是 behavior 层该装的东西，而不是再写一遍 `sign`。**

### 1.2 type 层：四个维度压进一个枚举

| 维度 | 现有 type | 实测 | 问题 |
|---|---|---|---|
| **动作** | `click` `swipe` `wait` `think` `back` `home` | 6 个 | 这部分是对的 |
| **定位** | `click_text` `click_id` `click_desc` `click_point` `click_first` `scroll_to` | 6 个 | 与动作混在一起 |
| **控制流** | `any_of` `random` `ensure` | 3 个 | 不是动作 |
| **业务宏** | `reward` `dismiss_popups` `captcha` | 3 个 | 不是原语，是复合流程 |

四条硬证据：

1. **同名字段两种含义**：`click_first.candidates` 里写 `type: text`（444 处）/ `type: desc`（8 处），
   这里的 `type` 表示**定位方式**；而顶层 `type` 表示**动作**。同名不同义，且顶层根本没有 `text` 这个 type。
2. **一个 type 里混了两种性质**：`click_point` 118 处 = 78 处带 `images`/`vlm_prompt`（视觉定位）+ 40 处纯坐标（盲点）。
3. **用开关补维度**：`vision: false` 出现 65 处——明明是"定位策略"的差异，却做成 step 上的布尔开关。
4. **粒度不一致**：`scroll_to` = 滑动 + 定位 + 点击 三合一；`click_first` = 多候选定位 + 点击；
   而 `click` 只做点击。三者是同一个动作的不同"搜索策略"，却被拆成三个 type。

另外两个附带问题：

- `optional` 出现 **237/541 = 44%**。一个布尔同时表达"找不到就跳过"（`on_miss: skip`）和
  "这步必须成功"（`on_miss: fail`），后者与 `ensure` 语义重复。
- 命名词性混乱：`click`(动) / `reward`(名) / `dismiss_popups`(动+名) / `ensure`(动)。behavior 名强制 ASCII，
  type 名却不校验，未知 type 只记 WARN 然后跳过——**拼错一个 type，等于静默跳过一步**。

---

## 2 v2 模型：三个正交维度 + 两种宏

一个 step 只可能是**动作步**或**分支步**，其余全部是属性。

```
step = action_step | flow_step

action_step:
  action: click | swipe | key | wait | input | extract      ← 只回答"对屏幕做什么"
  target: {...}      ← 仅 click 用：只回答"找哪个、怎么找、找不到怎么办"
  ...action 自己的参数（swipe 的 from/to、wait 的 seconds、extract 的 pattern）

flow_step:
  flow: any_of | random                                     ← 只回答"按什么顺序试"
  branches: [ [step...], [step...] ]
```

### 2.1 action（6 个，动词原形）

| action | 语义 | 对应 v1 |
|---|---|---|
| `click` | 点一个目标 | click / click_text / click_id / click_desc / click_point / click_first / scroll_to |
| `swipe` | 划 | swipe / swipe_natural |
| `key` | 系统键 | back / home |
| `wait` | 等 | wait / think |
| `input` | 输入文本 | （暂无，预留） |
| `extract` | 读屏抽数 | reward |

### 2.2 target（click 的目标描述符）

```yaml
target:
  by: text | id | desc | point | template | vlm   # 找法（名词）
  value: 立即签到                                  # by=point 时给 [0.5, 0.53]
  pool: [...]                                      # 多候选，按序试（v1 的 click_first）
  search: none | scroll                            # 找不到时要不要滚屏找（v1 的 scroll_to）
  expect: {text_any: [...], phash: ..., retry: 1}  # 落地校验（v1 的 expect）
  on_miss: skip | fail                             # v1 的 optional / ensure
```

关键收敛：

- `vision: false` **自动消失**——没给 `template`/`vlm` 就不走视觉，不需要开关。
- `optional: true` **自动消失**——`on_miss` 默认就是 `skip`；只有"必须命中"的步才写 `on_miss: fail`。
- `ensure` **不再是 type**——它是 `on_miss: fail` + 断言条件。
- `click_text/id/desc/point/first/scroll_to` **六个 type 变一个 action + 属性**。

### 2.3 flow（2 个，连词）

| flow | 语义 | 对应 v1 |
|---|---|---|
| `any_of` | 按序试分支，第一组命中即停 | any_of |
| `random` | 随机挑一组 | random |

> 实测 `any_of` 嵌套深度：1 层 47 处、2 层 1 处。控制流本来就浅，没必要做成任意嵌套的表达式树。

### 2.4 macro（2 个，明确标注为宏，不是原语）

| macro | 内部是什么 | 对应 v1 |
|---|---|---|
| `popup_sweep` | 文案 → 关闭 id → 右上角 → BACK，含资金黑名单熔断 | dismiss_popups |
| `solve_captcha` | 检测滑块 → 缺口识别 → 拟人拖拽 | captcha |

宏与动作的区别必须显式：宏**可以**包含等待与多次尝试，动作**只做一件事**。
现在这两者混在一个枚举里，是"分类逻辑性差"的直接来源。

---

## 3 映射表：19 → 6 + 2 + 2

| v1 type | 用量 | v2 | 说明 |
|---|---|---|---|
| `click` | 0（新） | `action: click` + `target.by` | — |
| `click_text` | 41 | `click` + `by: text` | 日志动词不变 |
| `click_id` | 2 | `click` + `by: id` | |
| `click_desc` | 2 | `click` + `by: desc` | |
| `click_point` | 118 | `click` + `by: point`（可带 template/vlm） | 78 带视觉、40 纯坐标 |
| `click_first` | 143 | `click` + `target.pool` | 候选的 `type: text` → `by: text` |
| `scroll_to` | 1 | `click` + `target.search: scroll` | |
| `swipe` | 24 | `action: swipe` | `natural` 保留为参数 |
| `swipe_natural` | 0 | `swipe` + `natural: true` | |
| `wait` | 31 | `action: wait` | |
| `think` | 103 | `wait` + `human: true` | 拟人停顿 |
| `back` / `home` | 1 / 0 | `key` + `name: back/home` | |
| `any_of` | 48 | `flow: any_of` | |
| `random` | 0 | `flow: random` | |
| `reward` | 25 | `action: extract` | 字段 pattern/unit/name 不变 |
| `ensure` | 1 | 任意步 + `on_miss: fail` | 不再是独立 type |
| `dismiss_popups` | 1 | `macro: popup_sweep` | |
| `captcha` | 0 | `macro: solve_captcha` | |

---

## 4 同一个步骤，v1 / v2 对照（三个真实例子）

**① 抖音火山版：预约主按钮（文本 + 坐标兜底）**

```yaml
# v1
- type: any_of
  optional: true
  choices:
  - - type: click_text
      text: 立即预约领取
      timeout: 10
  - - type: click_point
      x: 0.5
      y: 0.529
      optional: true
      vision: false

# v2
- flow: any_of
  branches:
  - - action: click
      target: {by: text, value: 立即预约领取, timeout: 10}
  - - action: click
      target: {by: point, value: [0.5, 0.529]}
```

**② 快手：坐标 + 落地校验（phash）**

```yaml
# v1
- type: click_point
  x: 0.638
  y: 0.161
  vision: false
  expect: {phash: images/快手/landing/ref_task.png, phash_max_dist: 8, settle: 3.0}

# v2
- action: click
  target:
    by: point
    value: [0.638, 0.161]
    expect: {phash: images/快手/landing/ref_task.png, phash_max_dist: 8, settle: 3.0}
```

**③ 趣头条：多候选关弹窗（8 个文案挑一个）**

```yaml
# v1
- type: click_first
  candidates:
  - {type: text, value: 暂不}
  - {type: text, value: 关闭}
  ...

# v2
- action: click
  target:
    pool:
    - {by: text, value: 暂不}
    - {by: text, value: 关闭}
    ...
```

---

## 5 behavior 层：intent → recipe → step

v2 把"行为"拆成三个有明确职责的概念：

| 概念 | 数量 | 谁产生 | 职责 |
|---|---|---|---|
| **intent** | 9（固定） | NLU 从用户话里解析 | 用户想做什么（签到/看视频/提现…） |
| **recipe** | 按需 | 人写 | **可复用的动作序列**，有名字、可被多个 app 引用 |
| **route** | 每 app 每个 intent 一条 | 人写 | 把 recipe 串起来，声明"这个 app 上 sign 怎么走" |

```yaml
# config/apps/05_快手.yaml
routes:
  sign:
  - use: common/enter_task_center      # 共享 recipe
  - use: sign_click                     # 共享 recipe
  - use: common/popup_sweep             # 共享 recipe
  - use: kuaishou/sign_fallback         # app 私有 recipe

# config/recipes/common/enter_task_center.yaml
name: enter_task_center
steps:
- action: click
  target: {by: desc, value: 任务中心, pool: [{by: text, value: 任务中心}]}
  on_miss: fail
```

**这一步带来什么**：

- `intent_map` 消失——route 直接给序列，不需要"重命名"这层间接。
- 34 份重复收敛：进任务中心/关弹窗/回顶这类片段各写一次。
- `behavior` 这个词回归本义：**可命名的动作序列**，而不是"意图的另一个名字"。

**代价（必须说清）**：recipe 是共享的，改一个 recipe 会影响所有引用它的 app。
需要"改动影响面"检查（`grep use:` 反查）与实机回归；这也是为什么它必须放在最后一阶段做。

---

## 6 迁移路径（541 步一行不改）

| 阶段 | 做什么 | 验收门 | 风险 |
|---|---|---|---|
| **S0 冻结术语** | 本文定稿；`docs/behavior_type_规范.md` 标注 superseded；补一张 19→10 对照表进 README | 文档评审通过 | 无 |
| **S1 编译层** | 加载时把 v1 step 编译成 v2 模型（`_compile_step`），运行时只跑 v2；老配置原样可用 | ① 422 测试全绿；② **对拍**：同一配置下 v1/v2 的 dry-run 执行计划逐字相等；③ 抽 3 个 app 实机跑 sign 链 | 编译器是新的 bug 面 |
| **S2 新配置写 v2** | 新写的配置只允许 v2；`validate_config` 对 v1 写法告警 | 新增配置全部 v2 | 两套写法并存期 |
| **S3 recipe 化** | 抽 `common/` recipe，逐 app 改 route；`intent_map` 与 `behaviors` 退场 | 每个 app 迁移后实机体检不掉级 | **共享 recipe 一改全炸**，需逐 app 迁移 + 回归 |

**S1 的关键设计**：编译而不是重写。v1 的 541 步是实机资产，任何"批量改写"都是在拿已验证的链路赌。
编译层让内部模型先变干净，配置再慢慢跟。

---

## 7 明确不做

1. **不做表达式树/变量/循环**。控制流实测只有 2 层、48 处，加表达式语言是过度设计。
2. **不批量改写 541 步**。S1 之后老配置照跑，S3 只在自然触达时迁移。
3. **不引入新依赖**（schema 校验用自研 `miniyaml` 之上的轻量校验，不引 pydantic）。
4. **不改日志动词**（`点击文本:` / `多候选命中并点击:`）——`sign_evidence` 靠它判定，改了等于判定全灭。

---

## 8 需要你拍板的三个问题

1. **recipe 层要不要做？**
   做：34 份重复收敛、`intent_map` 消失，但要承担"共享片段一改全炸"的风险，且 S3 工作量最大。
   不做：只做 S0–S2（type 层正交化），behavior 层保持"意图名 = behavior 名"，收益小一半但风险低。

2. **`on_miss` 取代 `optional` + `ensure` 是否可接受？**
   收益：44% 的 `optional` 字段消失，语义唯一。风险：`optional: false` 在 48 个 `any_of` 里是
   "这组必须命中"，语义是**分支级**而非步骤级，需要区分 `branches[].on_miss` 与 `target.on_miss`。

3. **先做哪一步？**
   我建议 **S0 + S1**（只写文档 + 加编译层 + 对拍测试），因为它是唯一"改内部模型但不碰配置"的一步，
   做完就能拿到全部结构收益，且随时可回滚。S3 等 review 结论再定。
