# behavior / type 规范（2026-10-25 重新规划整理）

> 本文是行为层（behavior）与步骤层（type）的**唯一规范来源**。改这两层之前先读本文；
> 规范与代码不一致时，以本文为准并同步改代码（或改本文并说明原因）。

---

## 1. 为什么要整理

整理前的实地问题（全部有实机/日志证据）：

| # | 问题 | 证据 |
|---|---|---|
| P1 | `click_text`/`click_id`/`click_desc` 是同一段 20 行代码的三份拷贝 | 三个方法体只差 selector 前缀和日志措辞；B6「未命中不抛 StepError」当年只改进了 `click_text` |
| P2 | `swipe` 写 `natural: true` **忽略 from/to** 且永远向下滑 | 抖音火山版校准实测：写 natural 想上滑回顶，结果连滑到底，预约行被推得更远 |
| P3 | behavior 名出现中文（快手「白拿礼物」） | 中文名无法被任何标准意图命中，只能靠 intent_map 手写映射，形同虚设 |
| P4 | `reserve`/`growth` 两个意图定义了但没有任何 app 用 | NLU 词典里有、配置里没有，意图层和行为层脱节 |
| P5 | NLU 关键词「签到领」挂在 growth 下，会劫持「签到」 | 长词优先匹配，「签到领金币」被解析成 growth 而不是 sign |
| P6 | `nlu.resolve_behavior` 与 `Executor._resolve` 逐行相同且全仓库无人调用 | 两份相同逻辑必然漂移，死代码 |
| P7 | `behavior_runner.py` 模块 docstring 抄了一份 executor.py 旧行号索引 | 代码三分拆后行号全部失效，反而误导定位 |
| P8 | 体检脚本 `targets()` 用 `"sign" in behaviors` 选目标 | intent_map 把 sign 映射到别名的 app（抖音火山版）会被静默漏掉 |

---

## 2. behavior 层规范

### 2.1 标准意图表（9 个）

behavior 名**必须**从下表选小写 ASCII 名。配置里写别的名字 = 不规范。

| 意图 | 关键词（NLU） | 语义 | 当前使用 |
|---|---|---|---|
| `sign` | 签到、每日签到、打卡、签到打卡 | 每日签到 | 29 app |
| `reserve` | 预约打卡、预约签到、预约 | 预约（没有签到按钮的 app 的唯一每日动作） | 1（抖音火山版） |
| `watch` | 看视频、刷视频、看广告… | 看视频/广告任务 | 18 |
| `withdraw` | 提现、提钱、兑换红包 | 提现 | 22 |
| `collect` | 收集、收取能量、喂鸡、浇水 | 收集类 | 18 |
| `bonus` | 领红包、领金币、领取奖励 | 领奖励 | 9 |
| `gift` | 白拿礼物、白拿、免费领、领礼物 | 免费领礼物 | 1（快手，原「白拿礼物」） |
| `growth` | 浇花、施肥、升级、做任务 | 养成类 | 0（保留，待有 app 用） |
| `open` | 打开、启动、开启应用 | 仅打开 app（百度极速版/海马畅听） | 2 |

> 「签到领」已从 growth 删除（P5）。新增意图必须先加关键词再改配置，
> 并补一条 `tests/test_unified_steps.py` 的解析用例。

### 2.2 intent_map 契约

```yaml
intent_map:
  sign: reserve     # 意图 → behavior 名；behavior 名可以与意图不同
```

解析顺序（唯一实现在 `behavior_runner.Executor._resolve`）：
1. `intent_map[intent]` 存在且 behaviors 里有 → 用它；
2. 否则 behaviors 里恰好有同名 `intent` → 用它；
3. 否则该意图在本 app 上**不存在**（跳过，不报错）。

**「没有签到只有预约」的 app 标准写法**（抖音火山版）：
`intent_map: {sign: reserve}` + `behaviors: {reserve: ...}`。
这样用户说「签到」能跑通，behavior 名又不会撒谎。按用户判定规则
（见 MEMORY.md），这类 app **永远不算「已成功签到」**——没有签到按钮可点。

### 2.3 命名硬规则（有测试钉住）

- 全部小写 ASCII，`^[a-z][a-z0-9_]*$`；
- 禁止中文 behavior 名；
- 回归：`tests/test_unified_steps.py::t_config_behavior_names_are_ascii`。

---

## 3. type 层规范

### 3.1 规范表（15 种）

| 分派名 | 作用 | 状态 | 配置用量 |
|---|---|---|---|
| `click` | **统一点击原语**：`by: text(默认)/id/desc` | ✅ 规范首选 | 新写用这个 |
| `click_text` / `click_id` / `click_desc` | 点击的旧写法 | 🔁 别名（永久保留，行为与 `click` 完全等价） | 45 步 |
| `click_first` | 多候选依次尝试 + 全局词表自搜寻 | ✅ 规范 | 143 步 |
| `click_point` | 比例坐标盲点，可绑 images 走视觉兜底 | ✅ 规范 | 118 步 |
| `swipe` | 滑动；`natural: true` 走人类轨迹且**尊重 from/to** | ✅ 规范（bug 已修） | 24 步 |
| `swipe_natural` | 滑动的旧写法 | 🔁 别名（= `swipe` + `natural: true`） | 0（recorder 录制流会产出） |
| `wait` / `think` | 固定等待 / 拟人停顿 | ✅ 规范 | 31 / 103 步 |
| `any_of` / `random` | 条件分支 / 随机分支 | ✅ 规范 | 48 / 0 步 |
| `scroll_to` | 滚动直到找到文本并点击 | ✅ 规范 | 1 步 |
| `back` / `home` | 系统返回 / 回桌面 | ✅ 规范 | 1 / 0 步 |
| `dismiss_popups` | 弹窗清扫（F1） | ✅ 规范 | 1 步 |
| `reward` | 收益数字识别 | ✅ 规范 | 25 步 |
| `ensure` | 硬断言（失败抛 StepError） | ✅ 规范 | 1 步 |
| `captcha` | 滑块验证码 | 🅢 预留（captcha.enabled 时才有意义） | 0 步 |

图例：✅ 规范 / 🔁 别名（老配置不改也能跑，新配置不要写）/ 🅢 预留。

**从 18 种收敛到 15 种**：`click_text/id/desc` 三合一为 `click`（−2），
`swipe_natural` 并入 `swipe`（−1）。老 type 名全部保留为别名，
**34 个 app 的 300+ 步配置一行没改**，行为零变化。

### 3.2 `click` 写法

```yaml
- type: click
  by: text          # text(默认) / id / desc
  text: 赚钱         # by=text 时读 text；by=id 读 res_id；by=desc 读 desc
  timeout: 12
  optional: true
  expect: landing_ref.png    # 可选：落地校验
```

三种 `by` 的日志动词保持旧样（测试钉住）：
`点击文本: X` / `点击控件: X` / `点击描述: X`。
未知 `by` → 返回 False 并记 `未知 click by: xxx`，**不静默点错东西**。

### 3.3 `swipe` 写法

```yaml
- type: swipe
  from: [0.5, 0.25]
  to:   [0.5, 0.78]
  duration: 0.45
  natural: true     # 可选：人类轨迹（默认也走轨迹，见下）
  straight: true    # 可选：强制直线（跳过轨迹注入）
```

- `natural: true` + 有 from/to → **按坐标**走人类轨迹（P2 已修）；
- `natural: true` + 无 from/to → 随机自然滑动（向下，recorder 录制流语义）；
- 不写 `natural` → 也走人类轨迹（`straight` 未设置时），两者差别只在起终点来源。

---

## 4. 本次改动明细

| 文件 | 改动 |
|---|---|
| `behavior_runner.py` | 新增 `_step_click` 统一点击原语 + `_CLICK_KINDS` 表；`_step_click_text/id/desc` 改为一行别名；`_step_swipe` 修 P2（natural 尊重 from/to）；`_step_swipe_natural` 改为别名；分派表加 `click`；`_VISION_GATED_STEPS` 加 `click`；模块 docstring 旧行号索引改为按职责列目录（P7） |
| `nlu.py` | growth 删「签到领」（P5）；新增 `gift` 意图；删除死代码 `resolve_behavior`（P6） |
| `config/apps/05_快手.yaml` | behavior「白拿礼物」→ `gift`（P3） |
| `config/apps/30_抖音火山版.yaml` | behavior `sign` → `reserve`；`intent_map: {sign: reserve}`（P4）；更新 swipe 注释（bug 已修，配置步骤保持实测原样未动） |
| `temp/health_check.py` | `targets()` 改为按 intent_map 解析「签到」意图（P8），抖音火山版不再被漏 |
| `tests/test_unified_steps.py` | 新增 14 条回归（点击等价性/未知 by/swipe 坐标/NLU 不劫持/behavior 名规范/意图路由） |
| `_backup_pre_fix/config.yaml.split_baseline` | 有意变更配置后按 C9 流程刷新（改前已备份 `.bak_20261025`） |

**回归门**：`pytest tests` 422 passed；`verify_coverage()` 99/99。

---

## 5. 明确不做的事（避免过度设计）

1. **不批量改写 34 个 app 的 300+ 步配置**。老 type 名是永久别名，改写只有仪式性收益，
   却要拿 34 份实机验证过的链路去赌。新写的配置用 `click`，老的等自然触达时再改。
2. **不删 `captcha`/`random`/`home`**。配置里暂无使用，但各自绑定真实能力
   （captcha_slider 412 行、random 分支、home 导航），删了要连带删模块。
3. **不为 `growth` 硬凑使用场景**。没有 app 需要就让它空着，意图层留位置比删了再加便宜。
4. **不改 recorder 的产出格式**。`step_to_action` 录制成 `swipe_natural` 依旧合法（别名）。
