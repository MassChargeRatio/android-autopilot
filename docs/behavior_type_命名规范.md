# behavior / type 命名规范（v3 · 2026-10-29 定稿）

> 本文只回答"叫什么"。**为什么这么分维度**见 `behavior_type_规范_v2.md`；
> **返回值契约**见 `behavior_runner.ACTION_CATEGORY`（已落地，9 类）。
> 命名到此冻结，再改需要给出"旧名造成的实际故障"，不接受纯偏好理由。

## 0 一句话

`behaviors → routines`、`intent_map → route`（只写例外）、`type` 取消并拆成
`action` / `flow` / `macro` 三个并列主键；`target` 只属于 `action: click`；
`expect` / `on_miss` / `label` 在 step 级；`by` 只装"找元素的条件"。

## 1 层级

```
intent（意图：用户要什么，6 个）
  → route（路由：只写例外，全项目 2 条）
    → routine（例程：替代 behaviors，app 特有链）
      → step（步骤：action | flow | macro 三选一）
```

| 层 | 现名 | 定稿 | 说明 |
|---|---|---|---|
| 链容器 | `behaviors` | **`routines`** | 有固定步骤的例行做法 |
| 意图→链 | `intent_map` | **`route`** | 只写非恒等；默认同名即通，61 条恒等映射清零 |

## 2 三个主键

| 主键 | 成员 | 说明 |
|---|---|---|
| **`action`** | `click` `tap` `swipe` `press` `wait` `extract`（`input` 预留） | 对设备的原子操作，动词原形 |
| **`flow`** | `first_ok` `pick_one` | 控制流；别名 `any_of` / `random` 永久有效 |
| **`macro`** | `dismiss_popups` `captcha` | 组合体，内部可有等待与重试，不是原语 |

`flow: first_ok` 的语义是"按序试，第一组**全部成功**即停"。顺序是功能性的：
只有最后一个分支走视觉兜底，前面的分支是"便宜探测"。旧名 `any_of` 丢掉了这层语义，
但它作为别名永久保留，老配置不需要改。

## 3 step 级属性

| 属性 | 取值 | 说明 |
|---|---|---|
| `on_miss` | `skip`（默认）/ `fail` | 这步没命中怎么办；`flow` 与 `action` 都用它 |
| `expect` | `text_any` / `phash` / `retry` / `settle` | 落地校验；retry 只在这里，不在 `on_miss` |
| `label` | 任意字符串 | 人类标签，进日志（原 `desc` 双义中的"标签"义） |

## 4 target（仅 `action: click`）

| 字段 | 取值 |
|---|---|
| `by` | `text` `id` `desc` `image` `vision`（**无 `coord`**） |
| `value` | 选择器值 / 图片路径 / VLM 提示词 |
| `pool` | 多候选，按序试（原 `click_first.candidates`） |
| `search` | `scroll`（原 `scroll_to`） |
| `fallback` | `[x, y]` 视觉锚点未命中时的坐标兜底 |
| `vision` | `false` 关闭视觉分支 |

**`coord` 不在 `by` 里的理由**：`by` 的语义是"按什么条件找元素"，坐标没有"找"的过程。
把坐标塞进 `by` 只是把 `click_point` 一肩挑"定位+点击"的耦合从字段层挪进值域层。
坐标走两条路：纯坐标 → `action: tap`；视觉锚点兜底 → `target.fallback`。

## 5 三种点击形态

```yaml
# ① 元素点击（188 处）
- action: click
  target: {by: text, pool: [立即打卡, 打卡]}

# ② 视觉锚点 + 坐标兜底（78 处）
- action: click
  target: {by: image, value: 领火苗.png, fallback: [0.9, 0.138]}

# ③ 纯坐标（40 处）
- action: tap
  value: [0.5, 0.641]
  expect: {phash: ref.png}
```

实测分布：118 个 `click_point` = 40 纯坐标 + 78 视觉锚点。**66% 的"坐标点击"其实有寻找过程**，
一刀切成 `tap` 会让那 78 处重新长出 `by`，耦合原样搬回。

## 6 日志动词（硬约束，不可协商）

| 形态 | 日志 | 进 `sign_evidence.CLICK_LINE` |
|---|---|---|
| `click` + `by: text` | `点击文本: X` | 是 |
| `click` + `by: id` | `点击控件: X` | 是 |
| `click` + `by: desc` | `点击描述: X` | 是 |
| `tap` | `点击坐标: (x,y)` | **否**（盲点不能当签到凭据） |
| `first_ok` 命中 | `多候选命中并点击: X` | 是 |

`sign_evidence` 靠这些措辞认"签到按钮确实被点过"。改名只改 YAML 层 key，
**日志动词一律不动**，且必须由测试锁住（见 `tests/test_action_contract.py`）。

## 7 intent

| 现名 | 定稿 | 说明 |
|---|---|---|
| `sign` `reserve` `watch` `withdraw` | 不改 | 语义准确 |
| `collect` | 不改 | "收能量/喂鸡/浇水"是采集，`harvest` 偏收割 |
| `bonus` | **`claim`** | 名词→动词 |
| `gift` | 并入 `claim` | 仅快手 1 处，与 claim 无本质区别 |
| `growth` | 已删 | 0 使用 |
| `open` | 已删 | 系统动作不是意图；百度极速版靠 `route: {sign: open}` 桥接 |

## 8 别名与迁移

| 阶段 | 内容 | 配置改动 |
|---|---|---|
| 1 | 别名层：`action`/`flow`/`macro`/`target`/`on_miss` 可解析，旧 `type` 继续可用 | 0 |
| 2 | `intent_map → route` 双 key 兼容，删 61 条恒等映射 | 增量 |
| 3 | 编译层 + **语义投影对拍**（不是逐字相等） | 0 |
| 4 | `behaviors → routines` 双 key 兼容，逐 app 迁移 | 结构性 |

**对拍口径**：编译前后各生成 `(维度, 值, by, selector, timeout, on_miss, vision, expect)`
元组序列再比对。`--dry-run` 现在打印的是原始 YAML dict，编译后 schema 必然不同，
"逐字相等"这个验收做不出来——它已在三份 review 里被误写三次，勿再提。

## 9 三个实测数据点（用于判断命名是否站得住）

1. `click_point` 118 = 40 纯坐标 + 78 视觉锚点；纯坐标**全部**带 `vision: false`。
   改成 `tap` 后这 40 个 `vision: false` 自动消失（`tap` 没有视觉分支）。
2. 另有 **25 个"带图像锚点却 `vision: false`"**——锚点是死配置。
   编译层遇到应报 WARN，v2 里 `by: image` + `vision: false` 语义自相矛盾，应拒绝。
3. 跨 app 复用的步模板只有 16 个，最多省 119 步（30.6%），且前几名是
   `think`(31 app) / `swipe`(17) / `wait`(17) 这类单步——recipe 层收益是排版，不是维护成本。
