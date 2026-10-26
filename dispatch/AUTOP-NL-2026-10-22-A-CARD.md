# 派单卡 A：自然语言 → 动作链 YAML（第 1 层，模板填槽）

派单编号：`AUTOP-NL-2026-10-22-A`
工作目录：`C:\Users\VUL\WorkBuddy AI\Android自动化\AndroidAutopilot`
环境：**必须**用 `./.venv/Scripts/python.exe`（系统 Python 无 pytest / uiautomator2）

## 1. 任务

新建 `devtools/nl_to_steps.py` + `tests/test_nl_to_steps.py`：把一句中文自然语言 + App 名，
生成可直接插入 `config/apps/<app>.yaml` 的 `behaviors.<bid>` 动作链 YAML 片段。

**只产出片段，不写配置**（写回由 `devtools/yaml_writer.py` 负责，Host 已落地并通过 14 例测试）。

## 2. 可写 / 禁碰

| 类别 | 文件 |
|---|---|
| **可写** | `devtools/nl_to_steps.py`、`tests/test_nl_to_steps.py`、`dispatch/AUTOP-NL-2026-10-22-A/PROGRESS.md` |
| **只读** | `devtools/yaml_writer.py`、`candidates.py`、`config_loader.py`、`config/apps/*.yaml` |
| **绝对禁碰** | `candidates.py`、`behavior_runner.py`、`executor.py`、`config_loader.py`、`main.py`、`config.yaml`、`config/apps/**`、`devtools/yaml_writer.py`、任何既有测试 |

## 3. 已有依赖（不要重写）

`devtools/yaml_writer.py` 已提供（只读调用）：

```python
render_actions(actions: list[dict], indent: int = 2) -> list[str]   # 走 PyYAML，产出 `- - type:` 风格
render_behavior_block(bid, actions, indent, comments=None) -> list[str]
app_path(app_name, config_path=None, base_dir=None) -> str
snapshot(config_path=None) -> dict
```

`candidates.py`（词表唯一入口，**禁止复制词表**）：

```python
candidates_for(category, app_cfg=None) -> list[str]   # 全局表 → 跨App归纳 → App extra
category_for_intent(intent) -> str | None             # sign/reserve/bonus→sign; growth/collect→task_center; watch/open→nav_tab
```

## 4. 必须实现的 API

```python
# ---- 纯函数：解析（无 IO、无设备、无全局状态）----
_SPLIT_RE = r"[，,；;。]|然后|接着|之后|再|并(?=[点滑等返找翻])|\s*->\s*"
_VERBS = {  # 长词优先：点击/点开/点/戳/按/打开 → tap；上滑/向上滑/下滑/往下滑/滑 → swipe；翻页/滚动/翻 → scroll_to；等待/等/停留 → wait；返回/后退 → back；找/查找/出现 → find
}
_POS = {"右下角": (0.90, 0.914), "右上角": (0.93, 0.12), "底部最右": (0.90, 0.914),
        "底部右二": (0.70, 0.914), "底部左二": (0.30, 0.914), "底部最左": (0.10, 0.914),
        "屏幕中间": (0.50, 0.50), "中间": (0.50, 0.50)}

def parse_line(text: str) -> tuple[list[dict], list[str]]
    # steps: [{"verb","target","pos","seconds","raw"}]；无法识别 → verb="unknown" + warning，不抛异常
def parse_script(text: str) -> tuple[list[dict], list[str]]     # 多行/多句
def _cn_number(s: str) -> float | None                          # 三秒/五秒/十秒/半分钟
def _strip_quotes(s: str) -> str                                # 「」""''《》

# ---- 模板（结构化，非字符串拼接）----
TEMPLATES = {"personal_center": {"hops": ["tab", "hub", "sign"]},
             "feed_ball":       {"hops": ["tab", "ball", "sign"]},
             "home_direct":     {"hops": ["anchor", "sign"]}}
def template_names() -> list[str]
def guess_entry(text: str) -> str            # 含「我的/个人中心」→personal_center；含「浮球/金币/右上」→feed_ball；否则 home_direct
def render_hop(kind: str, params: dict, category: str, app_cfg: dict | None = None) -> list[dict]
def render_chain(entry: str, params: dict, category: str, app_cfg: dict | None = None) -> tuple[list[dict], list[str]]
def render_steps(steps: list[dict], params: dict, category: str, app_cfg: dict | None = None) -> tuple[list[dict], list[str]]
def build_behavior(text: str, app_name: str, bid: str, *, entry: str = "auto",
                   params: dict | None = None, app_cfg: dict | None = None) -> dict
    # -> {"behavior": bid, "entry": entry, "actions": [...], "warnings": [...], "candidates_used": {...}}
def to_yaml_fragment(actions: list[dict], indent: int = 2) -> str   # 转调 yaml_writer.render_actions
```

`params` 槽位：`tab_text/tab_xy/hub_text/hub_xy/ball_xy/anchor_text/anchor_xy/sign_xy/h5_offset/scroll_text/confirm_text`。

## 5. 结构约束（Host 已实测验证，违反即返工）

1. **每个 hop 独立成一个 `any_of`**：`choices[0]` = 文案支（`click_first` + **显式** `candidates_from` + `zone: tab_zone`（仅 tab 跳）），`choices[1]` = 坐标支（`click_point` + `vision: false`）。
2. **文案支/坐标支必须分属两个 choice**。原因：`any_of` 分支内任一步失败即整支 `break`（`behavior_runner._step_any_of` 文档已述），写在同一支里坐标永远执行不到。
3. **后续步骤不得复制进两个分支**（反例：`config/apps/10_米读小说.yaml` 的嵌套复制会让配置指数膨胀）。
4. **tab 跳必须显式 `candidates_from: nav_tab`**，hub 跳 `task_center`，sign 跳 `sign`。原因：`candidates_from` 缺省时会按**当前行为**自动推断（sign 行为里点 tab 会被推断成 sign 词表），不能依赖它。
5. **坐标兜底默认单点**；`--h5` 时才在坐标支内追加 `wait 1.5` + 下移 `--h5-offset`（默认 60px，实测 32/43/60 均有效）。原因：`_step_click_point` 除视觉分支外**没有 return**，`_run_kind` 把 `None` 当成功 —— 多点若拆成两个 choice，第二个永远不可达。
6. **任何 `*_xy` 缺省 → 该跳只出文案支** + warning「缺坐标兜底，建议真机校准后补」，**绝不猜坐标**。
7. 文案来源**只走 `candidates_for(category, app_cfg)`**。测试里必须有一条硬门禁：
   `assert "今日签到" not in inspect.getsource(nl_to_steps)`（防止出现第 6 份词表副本）。

## 6. CLI

```
python devtools/nl_to_steps.py --app 趣头条 --behavior sign \
       --text "点右下角我的，点福利中心，点签到" [--entry personal_center] \
       [--h5] [--h5-offset 60] [--xy 0.5,0.641] [--print-yaml] [--apply] [--force]
python devtools/nl_to_steps.py --templates     # 列出 3 模板与槽位
```

缺省行为：打印 warnings → 打印 YAML 片段 → 退出码 0，**不写盘**。
`--apply` 才调 `yaml_writer.insert_behavior(..., apply=True)`；已有行为时提示用 `--force` 走 `replace_behavior`。

**明确不做**：视觉/VLM；猜坐标；写 `config.yaml`；为资金类行为（`config_loader.money_behaviors`，默认 `{"withdraw"}`）生成配置（除非 `--allow-money`）。

## 7. 测试（`tests/test_nl_to_steps.py`，≥14 例，纯函数，不碰文件不碰设备）

`parse_line`：`点右下角我的` / `点击「立即签到」` / `等3秒` / `等三秒` / `上滑两次` / `点我的，然后点福利中心，最后点签到` / 无法识别动词（unknown + warning，不抛）
`guess_entry`：三分支
`render_chain` 结构断言：每 hop 是 `any_of`；`choices[0].type == "click_first"` 且 `optional is False`；`choices[1].type == "click_point"` 且 `vision is False`；tab 跳 `candidates_from == "nav_tab"` 且 `zone == "tab_zone"`
`--h5`：默认坐标支 1 个 `click_point`；`h5=True` 时 2 个且第二点 y 偏移 = `offset/2340`
缺 `*_xy`：无坐标支 + warning
词表门禁：monkeypatch `candidates.candidates_for` 记录调用 + `inspect.getsource` 无中文词表字面量
幂等：同输入两次 `build_behavior` 深相等
round-trip：`yaml.safe_load(to_yaml_fragment(actions))` 与 `actions` 深相等（含全角冒号、`+`、`%`）

## 8. 硬性节奏（上一轮教训：只探索不落盘 = 零产出）

1. **前 5 个工具调用内**创建 `dispatch/AUTOP-NL-2026-10-22-A/PROGRESS.md` 骨架（待办清单即可）。
2. 每完成一个函数**立即覆盖写** PROGRESS（签名 + 测试命令 + 真实输出），禁止攒到最后。
3. 预算约 250 次工具调用；到预算仍无结论 → 落盘「部分结论 + OPEN/BLOCKED」并结束。
4. 不要停在 `requires_action`；疑义写 PROGRESS「质疑记录」段，继续干。

## 9. 验收（Host 会逐条复核，不看截图看实跑）

1. `./.venv/Scripts/python.exe -m pytest tests/test_nl_to_steps.py -q` 全绿
2. 全量 `pytest tests/ -q` ≥ 291（派单前基线）
3. `grep -n "今日签到\|立即签到\|任务中心" devtools/nl_to_steps.py` **零命中**
4. `config/apps/*.yaml` 与 `config.yaml` 的 sha256 与派单前一致（开发期零写入）
5. PROGRESS 有「终态表」：函数签名 / 测试命令 / 真实输出 / 偏差 / 回滚点

## 10. 投递记录

| 项 | 值 |
|---|---|
| tag | `AUTOP-NL-A-2026-10-22` |
| cid | `conv_7f3de672ebd8473baf8ce0debc55cf25` |
| 投递时间 | 2026-10-22 10:10 |
| 投递前 marvis 状态 | 15 会话，1 个 in_progress（`A2A mesh probe` 历史探针） |
| 首响 | 「用户发来一个派单任务…第一步是读取任务卡片文件，并创建 PROGRESS.md 骨架」 |
