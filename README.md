---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: 58c070810b91e31b76e5016e97ae2974_6d5432e0ac5711f1af37525400826444
    ReservedCode1: kUMB3CpSXZR3iTViD6S+mvrJ6chYEh0FDSAcuhnmUob97cW/Hn7RkZ2xv8EaXXxVSxFTxmysa9vkF6EH7TEvoEDqrn3B4TIQBaS/HUAxgIk15MnVjm3DrGXaMsXBNEbG0zjM/F5i+6KHhd4aZ5zutbi5Ui9iSX1o/6YOEYyJBuPg90zzQeiJ+7RWHu4=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: 58c070810b91e31b76e5016e97ae2974_6d5432e0ac5711f1af37525400826444
    ReservedCode2: kUMB3CpSXZR3iTViD6S+mvrJ6chYEh0FDSAcuhnmUob97cW/Hn7RkZ2xv8EaXXxVSxFTxmysa9vkF6EH7TEvoEDqrn3B4TIQBaS/HUAxgIk15MnVjm3DrGXaMsXBNEbG0zjM/F5i+6KHhd4aZ5zutbi5Ui9iSX1o/6YOEYyJBuPg90zzQeiJ+7RWHu4=
---





# Android Autopilot

在 Windows 侧通过 **uiautomator2 + ADB** 控制 Android 设备/模拟器，按【app 配置 + 自然语言行为】自动完成
**签到 / 打卡 / 预约打卡 / 看视频 / 领金币 / 提现** 等日常操作，并**记录每次操作收益**（SQLite 记账）。

全程内置**真人模拟**：作息窗口、启动时刻随机偏移、点击坐标抖动、随机思考/滑屏/分心、自然退场，降低被风控识别的概率。

```
签名/打卡/看视频/提现……  ← 自然语言
        │  nlu.py 关键词意图解析
        ▼
   意图列表(sign/watch/withdraw...)
        │  绑定 config.yaml 中 app 行为模板
        ▼
   executor.py (uiautomator2)  →  模拟真人点击/滑动
        │
        ▼
   recorder.py 收益记账(SQLite + 日志) + 每日汇总
```

## 目录结构

```
android_autopilot/
├── main.py          # 入口：解析参数 -> 目标app -> 意图 -> 执行
├── config.yaml      # 设备 / 真人模拟 / 视觉兜底 / 知识库 / app 行为模板（核心配置）
├── nlu.py           # 自然语言 -> 意图 关键词解析
├── executor.py      # uiautomator2 执行引擎（全部动作原语 + 视觉兜底回退链 + 知识库联动）
├── vision.py        # 视觉兜底定位层（OpenCV 模板匹配 + VLM 占位）
├── knowledge.py     # 元素知识库（经验回写：读取/查询/成功刷新/失败计数/自动停用）
├── human.py         # 真人模拟模块（延迟/抖动/作息/滑屏等）
├── recorder.py      # 收益与操作记录（SQLite）
├── element_knowledge.yaml  # 元素知识库数据文件（示例，运行后自动回写维护）
├── requirements.txt
├── README.md
└── data/            # 运行时自动生成：records.db 与运行日志
```

## 一、环境准备（Windows + 安卓模拟器/真机）

```bash
# 1) 安装依赖
pip install -r requirements.txt

# 2) 启动你的安卓模拟器（雷电/夜神/MuMu 均可），并让它可被 adb 访问
#    模拟器常见 adb 地址：雷电 127.0.0.1:5555、夜神 127.0.0.1:62001、MuMu 127.0.0.1:16384

# 3) 连接并初始化（给设备装上 ATX 自动化服务，仅首次需要）
adb connect 127.0.0.1:5555
adb devices                        # 确认设备可见
python -m uiautomator2 init         # 首次初始化（装 ATX/minicap 等）
```

> 若 `adb` 不在 PATH：把 `platform-tools` 目录加入环境变量，或把 adb.exe 路径写进脚本调用。

## 二、快速上手

```bash
# 查看当前配置了哪些 app 与其可用行为
python main.py --list

# 完成一次任务：app 名 + 自然语言行为
python main.py --task "去示例阅读App签到"
python main.py --task "去示例阅读App签到，然后看视频"
python main.py --task "去示例任务屋签到并提现"

# 用 --app 单独指定目标（app 名/别名/序号）
python main.py --app 阅读App --task "签到并看视频，最后提现"

# dry-run：只打印执行计划，不碰设备（建议先跑一遍确认）
python main.py --task "去示例阅读App签到" --dry-run

# 查看今日收益汇总
python main.py --today
```

## 三、配置你自己的 app（config.yaml）

在 `apps:` 段新增一条：

```yaml
- name: "我的App"                  # 展示名，用于自然语言匹配
  package: "com.example.app"      # 真实包名（adb shell pm list packages | grep xxx 可查）
  aliases: ["我的", "APP别名"]     # 自然语言里可能出现的叫法
  intent_map:                     # 可选：意图 -> 行为id 自定义绑定
    sign: sign
  behaviors:
    sign:                         # 行为 id
      - type: click_text
        text: "我的"
        timeout: 8
      - type: click_first         # 文案会变时用多候选
        candidates:
          - {type: text, value: "每日签到"}
          - {type: text, value: "签到"}
      - type: reward              # 识别页面收益数字入账
        pattern: "金币[:：]?\\s*(?P<amount>[0-9]+)\\s*(?P<unit>个|枚)?"
        unit: "金币"
        name: "签到奖励"
```

### 动作原语速查（executor.py 已实现）

| type | 参数 | 说明 |
|---|---|---|
| `wait` | seconds | 固定等待 |
| `think` | - | 随机"思考"停留 |
| `click_text` | text, timeout | 按文本(模糊)定位并点击 |
| `click_id` | res_id, timeout | 按 resource-id 点击 |
| `click_desc` | desc, timeout | 按 content-desc 点击 |
| `click_point` | x, y | 坐标点击，支持 0~1 比例 |
| `click_first` | candidates: [{type,value}] | 点第一个出现的候选 |
| `swipe` | from, to, duration, natural, straight | 滑动；默认走贝塞尔轨迹注入，`natural:true` 走真人随机滑动，`straight:true` 强制直线 |
| `swipe_natural` | from, to（可省略） | 显式自然滑动原语，只给起终点，轨迹交给 human_trajectory |
| `captcha` | mode: slider, optional | 检测并求解滑块验证码（见下方"滑块验证码"节） |
| `scroll_to` | text, max_pages | 向下翻页找目标并点击 |
| `back` / `home` | - | 返回 / 回桌面 |
| `reward` | pattern, unit, name | 从页面 XML 正则提取收益并记账 |
| `ensure` | text, exists, timeout | 关键页面校验 |

### 元素知识库（经验回写，knowledge.py）

#### 动机

config.yaml 里写死的元素定位（text / resource-id / content-desc）在 App 改版、
文案变动后会失效。参考 AppAgent"元素用法知识库 + 失败经验回写"思想，本项目用
`element_knowledge.yaml` 单独维护每个 app 的元素使用经验，并在每次真实执行中
**自动回写**：哪个 selector 最近成功过、连续失败多少次、哪些备选可用——脚本
越用越懂目标 App，改版后也能靠历史经验自行换 selector 兜底。

#### 工作机制

```
click_text / click_id / click_desc / click_first
        │  执行前先查知识库 (knowledge.py)
        ▼
(0) 知识库无该元素记录 ─────────────► 走原逻辑（用 config 静态 selector）
        │ 有记录且启用
        ▼
(1) 按知识库推荐 selector 顺序尝试：[主] + [alternatives 轮换]
        │  命中
        ▼
    mark_ok：刷新 last_ok、fail_times 清零、解除 disabled
        │  全部未命中
        ▼
(2) mark_fail：fail_times+1；达阈值(默认3) 自动 disabled 并写 WARN 日志
        │  元素已 disabled / alternatives 用尽
        ▼
(3) 转入视觉兜底（vision.py 模板匹配 / VLM）→ 仍未命中则记录失败
```

- **成功回写**：某个 selector 定位并点击成功后，自动刷新 `last_ok`（当天日期）、
  `fail_times` 归零；若此前被 disabled，会自动解除。
- **失败计数 + 替代轮换**：主 selector 定位失败后，本次执行内自动轮换尝试
  `alternatives`；无论如何都失败则 `fail_times+1`；连续失败 ≥ 阈值自动
  `disabled: true`，下次执行直接跳过该元素所有 selector 转视觉兜底。
- **全链路日志**：所有回写动作都经 `recorder.log` 输出（含 dry-run 的 `[dry-run]`
  计划日志），便于复盘某个元素为何被停用。
- **dry-run 兼容**：dry-run 模式下只打印回写计划（`[dry-run] 将回写...`），
  **不落盘、不改知识库文件**。

#### 数据文件结构

```yaml
apps:
  - app: "示例阅读App"              # 必须与 config.yaml 的 name 一致
    elements:
      - selector: "text=每日签到"    # 主定位：u2 表达式或文本
        kind: text                  # 定位方式：text / id / desc
        desc: "签到页-每日签到按钮"    # 用途注释
        usage: "点它完成当日签到领取金币"  # 用法说明
        alternatives:               # 备选 selector（可空），失败自动轮换
          - "text=签到"
          - "id=com.example.reader:id/btn_sign"
        last_ok: "2026-09-08"       # 最近成功日期（自动回写）
        fail_times: 0               # 连续/累计失败次数（自动回写）
        disabled: false             # 是否停用（自动置位）
```

#### 配置

`config.yaml` 的 `knowledge:` 节：

```yaml
knowledge:
  file: "element_knowledge.yaml"   # 知识库文件（相对项目根目录）
  fail_threshold: 3                # 连续失败多少次自动停用（disabled）该元素
```

#### 维护建议

- 元素主 selector 建议与 config.yaml 保持一致，这样"自动回写"能直接作用于
  当前正在使用的定位；改动 selector 时同步更新知识库（或删除旧记录让它重建）。
- 若某元素被自动 disabled 且确认是临时性问题，可直接把 `element_knowledge.yaml`
  里该条目的 `disabled` 改回 `false`、`fail_times` 清零；下次成功后也会自动恢复。
- 知识库由程序规范重写，为给新条目自动生成骨架，可自行参考示例文件的字段结构，
  无需手工维护全部字段。

#### 单元自测

```bash
python test_knowledge.py        # 覆盖：读取/查询、成功刷新、失败计数、
                                # alternative 轮换、超阈值禁用、无记录走原逻辑、dry-run 不改盘
```

### 视觉兜底定位（vision.py，可选增强）

#### 原理

uiautomator2 依赖控件树（text / resource-id / content-desc）定位。当 App 改版、
控件变成纯图片按钮、或 H5/WebView 内元素无法命中时，元素定位会超时失败。此时
`executor.py` 的各 click 原语会依次回退到视觉层：

```
click_text/click_first/click_id/click_point ...
        │  uiautomator2 元素定位失败（含超时）
        ▼
(1) 该行为 config 绑定的 images/template 图片资源
        │  OpenCV 多尺度模板匹配 -> 命中即点击（需 opencv-python）
        ▼ 未命中
(2) vision.vlm 开启且已配置 base_url/api_key/model
        │  VLM（OpenAI 兼容视觉接口）"截图+自然语言" -> 坐标 -> 点击
        ▼ 仍未命中
记录 WARN 日志，按原样返回失败（不影响后续意图）
```

- 所有命中/失败均写入日志（含置信度、坐标、来源：模板/VLM），便于复盘鲁棒性。
- 依赖 `opencv-python`（含 numpy），若未安装，模板后端自动跳过（try import 优雅降级），
  仅 VLM 后端仍可用。

#### 配置

在 `config.yaml` 的 `vision:` 节（默认已提供示例值）：

```yaml
vision:
  enabled: true                 # 兜底层总开关
  template_dir: "templates"     # 按钮局部截图目录（相对项目根目录）
  template_threshold: 0.80      # 模板匹配最低置信度 0~1
  template_scales: [0.6, 0.8, 1.0, 1.2, 1.4]   # 多尺度搜索
  vlm:
    enabled: false              # VLM 默认关闭
    base_url: "https://api.example.com/v1"     # OpenAI 兼容 endpoint（占位，需改）
    api_key: "sk-XXXXXXXXXXXXXXXX"              # 占位，勿提交真实密钥
    model: "qwen-vl-plus"       # 视觉模型名（占位）
    timeout: 30
```

在某个点击动作上绑定视觉兜底：

```yaml
- type: click_text
  text: "我的"
  timeout: 8
  images: ["reader_my_tab.png"]        # 按钮局部截图，相对 template_dir 或项目根目录
  vlm_prompt: "点击底部'我的'标签"      # 可选；启用 vlm 时生效
```

#### 依赖安装

```bash
pip install -r requirements.txt
# 或单独装模板后端：pip install opencv-python
```

#### 局限

- 模板匹配依赖截图与模板的分辨率/缩放接近：多尺度覆盖常用分辨率，但极端缩放仍可能
  失配；模板应截取"按钮 + 少量背景"的局部图，避免整块大图（整块截图适配性差）。
- 模板匹配是像素级匹配，对颜色/主题变化敏感（夜间模式、深浅色主题切换可能失配）。
- VLM 后端为占位实现：默认走 OpenAI 兼容 `/chat/completions` 并解析 `{"x","y"}`，
  需要自备服务与密钥；未配置或调用失败时静默跳过，不影响主流程。
- H5/WebView 内动态 id 属于运行时生成，模板匹配可兜底，但页面频繁变化仍建议定期
  更新模板。

### 获取元素定位信息（重要，建议先做）

```bash
python -m uiautomator2 connect 127.0.0.1:5555   # 或直接跑：
python -c "import uiautomator2 as u2; d=u2.connect('127.0.0.1:5555'); d.watch()"
```

`d.watch()` 会实时展示当前界面元素树，可直接看到按钮的 text / resource-id / bounds，照抄进 config 即可。更快的方式：
`python -c "import uiautomator2 as u2; d=u2.connect('127.0.0.1:5555'); print(d.dump_hierarchy())"`

## 四、真人模拟都在做什么（human.py）

| 维度 | 实现 |
|---|---|
| 作息习惯 | `wake_window` 活跃窗口，只在该时段执行，避免半夜"上班" |
| 启动时刻 | `run_jitter_seconds` 随机偏移，避免每天同一秒 |
| 点击习惯 | `tap_jitter_px` 坐标抖动，不点按钮正中心；两次动作 `delay_between_actions` 随机间隔 |
| 查看习惯 | 打开 app 随机停留、翻页后 `think_delay` 思考、完成后概率性随手轻滑 `scroll_probability` |
| 分心/手滑 | `wander_probability` 概率做一次"误触-回正"小动作 |
| 页面切换 | 退出使用返回键/Home 随机结合 `close_naturally` |

### 人类手势轨迹（human_trajectory.py，防检测升级）

所有滑动都不再是直线：改为 **贝塞尔曲线 + Fitts 步数 + 慢-快-慢速度轮廓 + 末段高斯微颤 + 概率过冲回拉**，通过 u2 底层 `d.touch.down/move/up` 逐点注入（绕开 `d.swipe` 的直线限制）。

- 关键参数在 `config.yaml` 的 `trajectory` 节：曲线弯曲度 `perpendicular_ratio`、微颤幅度 `jitter_sigma`、过冲概率 `overshoot_prob` 等。
- 滑块拖拽场景（`for_slider=True`）走独立分支：几乎纯水平、头尾贴轨道、终点精确到像素，避免弧线残余导致对齐失败。
- 轨迹注入异常时自动回退 `d.swipe_points` 折线 → `d.swipe` 直线，保证任务不中断。
- 参考实现：pyclick / bezier-mouse-js（曲线算法）、ghost-cursor（Fitts 步数 + 过冲）。

### 滑块验证码处理（captcha_slider.py，防检测升级）

检测到"按住滑块 / 向右滑动"等文案后，自动求解：

1. 缺口定位（`captcha.slider.gap.mode`）：
   - `edge`（默认）：OpenCV 单图边缘检测找凹槽，零外部依赖；
   - `diff`：双图 RGB 差分（需配置 `background_template` 原始背景图，cuiqingcai 法）；
   - `vlm`：复用 `vision.vlm` 的视觉模型输出缺口 x 坐标。
2. 拟人拖拽：复用 human_trajectory 的滑块分支轨迹，全程慢-快-慢 + 末段微抖，终点精确命中缺口中心。
3. 校验 + 重试：拖完检测"验证成功"类文案，失败按 `retry_times` 微扰轨迹参数重试（每段时长抖动、起点微扰）。

启用步骤：`config.yaml` 中 `captcha.enabled` 置为 `true`，按需选缺口模式；在行为模板里需处理验证码的动作后加 `- type: captcha`（加 `optional: true` 可在未出现滑块时静默跳过）。依赖 `opencv-python`（安装见上文）。

### 行为序列多样化（diversify，防检测升级）

真人重复做同一件事时动作细节每次都有差异；固定模板序列会让风控的"行为序列 replay 图网络"一判一个准。`executor` 现在支持三类表现：

- **候选模板**：`config.yaml` 的 `diversify.variant_prob`（默认 0.8）决定每个意图按概率从多套候选模板中随机挑选一套，并记录上次用过的模板避免连续重复；
- **random 分支原语**：模板里可写 `- type: random`，从 `choices`（可混排 dict 动作与动作列表）中随机挑一支执行，制造行动顺序上的不确定性；
- **内部差异**：同一动作的执行细节本身已由随机分布层打散（见下节）。

无需改代码，多套候选直接写进 YAML。

### 随机分布升级（对数正态，防检测升级）

人类的操作间隔不是均匀分布，而是**偏态长尾**：大量间隔短、偶发长停顿。此前 `delay_between_actions` / `think_delay` / `after_open_delay` 用均匀分布，间隔谱一眼机器味。

现在 `human.py` 默认用**对数正态分布**采样（低端聚集 + 长尾），并钳制在配置区间内；显式想回退均匀分布，写成：

```yaml
delay_between_actions:
  range: [0.6, 2.2]      # 兼容旧写法（纯列表）与 dict 写法
  dist: uniform          # uniform | lognormal（默认 lognormal）
```

### 传感器模拟与"死寂"检测（sensor_sim.py，防检测升级）

Radware 等风控把"静态/死寂传感器"判为最强异常：模拟器/自动化环境里 App 读到的加速度计/陀螺仪常是死值（全 0 或恒定），统计即穿帮。`sensor_sim.py` 提供：

- `SensorProfile`：生成真人握持的传感器序列（加速度/线性加速度/陀螺仪/磁力计），四种模式 `resting / walking / tapping / scrolling`，统计特征对齐真机（静置微抖、低频呼吸振动、步频/点按包络）；可导出 CSV 喂给模拟器"虚拟传感器"面板；
- 死寂检测：对设备上报序列算标准差/零变化比例，判定是否"死寂"，既可用于移民后自检，也可在上线前对比接入效果；
- 自检命令：`python sensor_sim.py`——打印各模式是否"活着"，并造一条死数据验证检测能识别。

注入落点（接入层，本仓库不内置 hook）：
- 模拟器：MEmu/LDPlayer 等的"虚拟传感器"面板灌入生成的 CSV 曲线；
- 真机：Shizuku + LSPosed/Xposed 模块 hook `SensorManager`，把 profile 数据灌给目标 App；
- 轻量替代：过程中让设备产生真实事件（抬手/放平/轻晃），系统传感器自然产出"活数据"。

### IP 信誉与出口代理（helper_proxy.py，防检测升级）

出口 IP 属于环境层风控：机房/数据中心 IP 会直接降权，配合设备指纹锁定风险。脚本层控制不了出口，需在接入层处理，`helper_proxy.py` 提供落地工具：

```
python helper_proxy.py --set 127.0.0.1:7890   # 给默认设备设置 http 代理
python helper_proxy.py --clear                 # 清除设备代理
python helper_proxy.py --status                # 查看设备代理 + PC 出口 IP
python helper_proxy.py --advice                # 打印 IP 策略建议
```

要点：真机+运营商流量信任度最高（出口=家宽/移动 IP 且与设备指纹归属一致）；住宅代理可用但需代理归属地与设备时区/语言一致；**不要刻意高频换 IP**——真人长期绑定同一 IP 才是常态，成批跑时按"IP 归属→时区→语言"分组、一组一个 IP。

## 五、定时执行（Windows 任务计划程序）

```bat
:: 新建 bat 文件 auto_run.bat，内容如下；再在"任务计划程序"里设为每天某时段触发
@echo off
cd /d D:\...\android_autopilot
python main.py --task "去阅读App签到并看视频"
```

任务计划程序 -> 创建基本任务 -> 触发器选"每天"，时间任意（脚本内部还有随机偏移+作息窗口双重把关）。

## 六、让脚本跑在安卓端（可选，替代 Win 控制）

本项目默认 **Win 控制安卓**。若想让脚本**在安卓设备本机运行**（如旧手机/Termux）：

1. 设备安装 **Termux**；
2. `pkg install python android-tools` 安装 Python 与 adb；
3. `pip install uiautomator2`；
4. 复制本目录到 Termux，把 `config.yaml` 的 `serial` 留空，运行 `python main.py ...`；
   （本机跑时 uiautomator2 可通过 `adb` 连回本机 `127.0.0.1:5555` 的 adbd）
5. 用 `termux-job-scheduler` 或 cron 定时。

> 不同 app 兼容性：本项目以文本/控件定位优先，适配性高于纯坐标；但 app 改版后可能出现元素变化，属正常现象，更新 config 即可。

## 七、合规与风险提示

- 本工具仅用于**个人名下、可合法自动化**的设备和任务（个人签到/打卡等），请遵守所操作 App 的用户协议与相关法律法规。
- 自动化操作存在被 App 风控识别的可能；本项目通过"真人模拟"降低概率，但**无法保证 100% 不被识别**，滥用可能造成账号限制，后果自负。
- 项目思路参考了 GitHub 上的开源方案（coin11-tb、Sleepway2work、Android-Anti-Detection-Automation 等），在实现上做了通用化与"配置驱动 + 自然语言"的落地。
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
*（内容由AI生成，仅供参考）*
