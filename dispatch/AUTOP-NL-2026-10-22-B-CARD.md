# 派单卡 B：引导式录制 → YAML（第 2 层，录制 + 一句话命名）

派单编号：`AUTOP-NL-2026-10-22-B`
工作目录：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
环境：**必须**用 `./.venv/Scripts/python.exe`

## 1. 任务

新建 `devtools/record_flow.py` + `tests/test_record_flow.py`：交互式录制。
用户逐步输入一句自然语言指令（`点签到` / `点右下角` / `上滑` / `等2秒` / `返回`），
脚本执行并记录每步（命中方式、归一化坐标、执行前后 activity、页面差分），
结束时给一句命名 + 指定 app/behavior，渲染成 YAML 片段交给 `yaml_writer` 写回（缺省预览）。

## 2. 可写 / 禁碰

| 类别 | 文件 |
|---|---|
| **可写** | `devtools/record_flow.py`、`tests/test_record_flow.py`、`dispatch/AUTOP-NL-2026-10-22-B/PROGRESS.md` |
| **只读** | `devtools/nl_to_steps.py`（A 卡产物，可能稍后出现）、`devtools/yaml_writer.py`、`devtools/calibrate.py`、`candidates.py`、`config_loader.py`、`pick_locate.py`、`human_trajectory.py` |
| **绝对禁碰** | `candidates.py`、`behavior_runner.py`、`executor.py`、`config_loader.py`、`main.py`、`config.yaml`、`config/apps/**`、`devtools/yaml_writer.py`、`devtools/nl_to_steps.py`、任何既有测试 |

## 3. 为什么不用 `getevent` 抓物理触摸（写进模块 docstring）

1. **无语义**：raw ABS_MT 只给 slot/tracking_id/pressure，拿不到「点的是哪个元素」；
2. **坐标空间不同**：event 是触摸屏原始量程，需 `getevent -p` 读 `0035/0036` 的 max 自行换算，多指 slot 还要解析 `SYN_REPORT` 分帧；
3. **无法归因**：录制期脚本注入的点击与用户物理点击混在同一事件流；
4. **阻塞流收尾差**：`adb shell getevent -lt` 是长驻流，Windows 下易留僵尸 adb；
5. **H5 场景坐标本身不可信**（星图金融打卡按钮被透明层遮挡就是证据）。

结论：录制输入是「一句 NL 指令」，坐标由 `d.dump_hierarchy()` 的 bounds 反算。

## 4. 必须实现的 API

```python
@dataclass
class Step:
    seq: int; cmd: str; verb: str; target: str | None; pos: str | None
    hit_kind: str | None      # text|desc|id|point|None
    hit_value: str | None
    bounds: tuple | None      # (l,t,r,b) 像素
    point_norm: tuple | None  # (x,y) round(4)
    act_before: str; act_after: str; delta: float
    confirmed: bool; note: str = ""

# ---- 纯函数（可单测，无设备）----
def ui_digest(xml: str) -> frozenset                 # 可点节点的 (text,desc,id,bounds) 集合
def page_delta(a: frozenset, b: frozenset) -> float  # 1 - Jaccard
def step_to_action(step: Step) -> dict | None
def steps_to_actions(steps: list[Step]) -> tuple[list[dict], list[str]]
def guess_entry(steps: list[Step]) -> str
def is_money_step(step: Step, money_words: set[str]) -> bool

# ---- 设备层 ----
class FlowRecorder:
    def __init__(self, app, package, serial=None, out_dir=None, max_steps=20, allow_money=False)
    def start(self) -> None
    def record_step(self, cmd: str) -> Step | None
    def undo(self) -> Step | None
    def show_trace(self) -> None
    def finish(self, name: str, behavior: str, entry: str = "auto",
               apply: bool = False, force: bool = False) -> object   # yaml_writer.WriteResult
    def close(self) -> None
```

`step_to_action` 映射：`text/desc/id` 命中 → `{"type":"click_first","candidates":[{"type":kind,"value":v}],"timeout":8,"optional":True}`；`point` 命中 → `{"type":"click_point","x":..,"y":..,"vision":False,"desc":..}`；`swipe` → `{"type":"swipe_natural"}`；`wait` → `{"type":"wait","seconds":..}`；`back` → `{"type":"back"}`。

## 5. 单步流程（防误触是核心）

```
1. parse_line(cmd)                        # 复用 nl_to_steps；A 卡未就绪时兜底（见 §6）
2. dump_before / act_before
3. 执行：text → contains → desc → id 顺序定位；pos 走 _POS 映射；swipe/wait/back 直执行
4. sleep 1.2s → dump_after / act_after / delta
5. 先机器校验，再人工确认：
   a. 包名跳走（≠ 目标 package）        → 标「跳转/误触」→ 默认拒绝
   b. delta < 0.02 且 activity 未变      → 标「疑似无效点击」→ 默认拒绝
   c. is_money_step 且 not allow_money   → 直接拒绝，不入 trace
   d. 其余                              → 自动 confirmed=True
6. 交互：打印 hit/bounds/point/activity/delta，输入 y=收下 / n=丢弃 / e=改文案后重记 / r=重试 / u=撤销上一步
7. 每步快照：devtools/calib/record/<pkg>/<yyyymmdd_HHMMSS>/NN_before.xml|png、NN_after.xml|png
```

**为什么先机器校验**：人会顺手按 `y`，而「跳包 / 零差分」是客观可判的。两条件取并集，
才能把「点错到相机页」这类误触（GUIDED 记录里拼多多 `(985,168)` 误入相机）拦在配置之外。

## 6. 与 A 卡的依赖（软依赖，禁止复制逻辑）

```python
try:
    from nl_to_steps import parse_line, render_hop, render_steps, guess_entry, to_yaml_fragment
except ImportError:
    # 兜底：仅 {"verb": "tap", "target": cmd}，全句当文案；PROGRESS 记 BLOCKED-DEP
```
**禁止**在 `record_flow.py` 里复制 `parse_line` 的动词表/切分逻辑。A 卡就绪后必须改回真 import（Host 验收会查）。

`finish()` 组装：`render_hop(entry, params)` + `steps_to_actions(trace)` 合并 → `yaml_writer.insert_behavior`（已有行为 → `replace_behavior(force=True)`）。

## 7. CLI

```
python devtools/record_flow.py --app 七猫免费小说 [--serial 192.168.1.54:5555] \
       [--behavior sign] [--entry auto] [--max-steps 20] [--allow-money] [--apply]
> 点右下角我的
> 点福利中心
> 点签到
> trace / undo / done
```
`done` 后问「一句话命名」，然后预览 YAML + diff；`--apply` 才写盘。

## 8. 测试（`tests/test_record_flow.py`，≥10 例，mock 设备，无真机）

`ui_digest` 对节点顺序不敏感；`page_delta` 同页=0、全换=1
`step_to_action` 四种命中 → 四种动作 dict 结构
`steps_to_actions` 丢弃 `confirmed=False` 并汇总 warnings
误触规则：包名变化 → `confirmed` 默认 False；`delta<0.02` → 需确认
资金红线：`is_money_step("立即提现")` 在 `allow_money=False` 时被拒
`finish` 合并顺序：entry hops 在前、录制步在后

## 9. 硬性节奏

1. **前 5 个工具调用内**创建 `dispatch/AUTOP-NL-2026-10-22-B/PROGRESS.md` 骨架。
2. 每完成一个函数立即覆盖写 PROGRESS（签名 + 测试命令 + 真实输出）。
3. 预算约 250 次工具调用；超预算落盘 OPEN/BLOCKED。
4. 不停在 `requires_action`；疑义写 PROGRESS 继续干。

## 10. 验收

1. `pytest tests/test_record_flow.py -q` 全绿；2. 全量 ≥ 291；3. `config/apps/*.yaml` sha256 不变；
4. `grep "今日签到\|立即签到\|任务中心" devtools/record_flow.py` 零命中；5. PROGRESS 有终态表。

## 11. 投递记录

| 项 | 值 |
|---|---|
| tag | `AUTOP-NL-B-2026-10-22` |
| cid | `conv_e22156a6780f4229bb736fa91aa6b4d2` |
| 投递时间 | 2026-10-22 10:10 |
| 投递前 marvis 状态 | 同 A 卡 |
| 首响 | 「我先读取任务卡片并同步创建 PROGRESS.md 骨架」 |
