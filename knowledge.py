# -*- coding: utf-8 -*-
"""
knowledge.py - 元素知识库经验回写模块 (KnowledgeBase)

背景：App 改版 / 文案变动 / 页面结构变化时，config.yaml 里写死的元素定位
（text / resource-id / content-desc）会逐渐失效。参考 AppAgent 的
"元素用法知识库 + 失败经验回写"思想，本项目用一份本地 YAML 积累每个 app 的
元素使用经验：

  - 每个元素带备选 selector（alternatives），失败后自动轮换尝试；
  - 连续失败超过阈值自动标记 disabled，下次执行直接跳过该元素；
  - 执行成功刷新 last_ok、重置 fail_times，经验回写，越用越准。

数据文件：element_knowledge.yaml（结构见示例文件头部注释）。

关键行为：
  - 读取 / 按 app+selector 查询；
  - 执行成功 -> mark_ok（刷新 last_ok、fail_times 归零、自动解除 disabled）；
  - 执行失败 -> mark_fail（fail_times+1，达阈值置 disabled 并写日志）；
  - dry-run 模式：所有写操作只打印计划，不改动文件。
"""
import os

try:
    import yaml
except ImportError:  # pragma: no cover - 无 PyYAML 时用内置零依赖解析器兜底
    try:
        import miniyaml as yaml
    except ImportError:
        yaml = None


DEFAULT_THRESHOLD = 3          # 连续失败多少次后停用该元素
DEFAULT_FILE = "element_knowledge.yaml"


class KnowledgeBase:
    def __init__(self, path=None, recorder=None, threshold=DEFAULT_THRESHOLD,
                 dry_run: bool = False, base_dir: str = None):
        """
        path     : 知识库 yaml 文件绝对路径；缺省用 base_dir/element_knowledge.yaml
        recorder : 可选，提供 .log(msg, app, level) 用于落盘；None 时静默
        threshold: 连续失败停用阈值（>= 该值置 disabled）
        dry_run  : 不写盘，仅打印计划
        base_dir : 项目根目录，用于解析缺省路径
        """
        self.base_dir = base_dir or os.getcwd()
        self.recorder = recorder
        self.threshold = max(1, int(threshold or DEFAULT_THRESHOLD))
        self.dry_run = dry_run
        self.path = os.path.abspath(path or os.path.join(self.base_dir, DEFAULT_FILE))
        # 索引：app_name -> {selector: element_dict}
        self._apps = {}
        self._loaded = False
        self._dirty = False

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _log(self, msg, app="", level="INFO"):
        if self.recorder is not None:
            self.recorder.log(msg, app, level)

    # ------------------------------------------------------------------
    # 加载与索引
    # ------------------------------------------------------------------
    def load(self):
        """读取 yaml 并建立 app->selector 索引。文件不存在/空则初始化为空库。"""
        if self._loaded:
            return self
        self._apps = {}
        if yaml is None:
            self._log("缺少依赖 PyYAML，元素知识库不可用（视为空库）", "sys", "WARN")
        elif os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                for app in data.get("apps", []) or []:
                    app_name = str(app.get("app") or app.get("name") or "").strip()
                    if not app_name:
                        continue
                    idx = {}
                    for e in app.get("elements", []) or []:
                        sel = str(e.get("selector") or "").strip()
                        if not sel:
                            continue
                        idx[sel] = e
                    if idx:
                        self._apps[app_name] = idx
            except Exception as e:
                self._log(f"元素知识库解析失败: {e}，按空库处理", "sys", "WARN")
        self._loaded = True
        self._dirty = False
        return self

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def has_element(self, app: str, selector: str) -> bool:
        """按 app+selector 判断知识库中是否存在该元素记录。"""
        self.load()
        return bool(self._apps.get(app or "") and (selector or "") in self._apps[app])

    def get(self, app: str, selector: str):
        """返回元素记录 dict；不存在返回 None。"""
        self.load()
        return (self._apps.get(app or "") or {}).get(selector or "")

    def candidate_selectors(self, app: str, selector: str) -> list:
        """返回当前应尝试的 selector 有序列表（不含 disabled 的）。

        - 主 selector 若未 disabled，优先排第一；
        - 随后依次是仍然启用的 alternatives（去重、去 disabled）；
        - 元素整体 disabled（含主与所有 alternatives 均 disabled 或主 disabled
          且无可用替代）时返回空列表 -> 调用方转入视觉兜底。
        """
        self.load()
        elem = self.get(app, selector)
        if elem is None:
            return [selector]
        if self._is_disabled(elem):
            self._log(f"元素[{selector}] 已停用(disabled)，跳过其 selector 尝试", app, "DEBUG")
            return []
        cands = []
        if not self._is_disabled(elem, use_alt=False):
            cands.append(selector)
        for alt in (elem.get("alternatives") or []):
            s = str(alt).strip()
            if not s or s in cands:
                continue
            if self._is_disabled(elem, alt=s):
                continue
            cands.append(s)
        if not cands:
            self._log(f"元素[{selector}] 无可启用 selector，转入视觉兜底", app, "DEBUG")
        return cands

    # ------------------------------------------------------------------
    # 经验回写（写操作）
    # ------------------------------------------------------------------
    @staticmethod
    def _is_disabled(elem: dict, use_alt: bool = True, alt: str = None) -> bool:
        """disabled 判定：
        - 元素级 disabled=True 视为整体停用（连同其 alternatives）；
        - alternatives 里若有 disabled 标记（dict 形态），单独跳过该替代。
        """
        if bool(elem.get("disabled")):
            return True
        if not use_alt or alt is None:
            return False
        for a in (elem.get("alternatives") or []):
            if isinstance(a, dict) and str(a.get("selector") or a.get("value") or "") == alt:
                return bool(a.get("disabled"))
        return False

    def mark_ok(self, app: str, selector: str) -> bool:
        """执行成功回写：刷新 last_ok、fail_times 归零、解除 disabled。
        返回是否有记录被更新（False 表示无此元素记录，未做任何事）。"""
        self.load()
        elem = self.get(app, selector)
        if elem is None:
            return False
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        changes = {}
        if str(elem.get("last_ok")) != today:
            changes["last_ok"] = today
        if int(elem.get("fail_times") or 0) != 0:
            changes["fail_times"] = 0
        if elem.get("disabled"):
            changes["disabled"] = False
        if changes:
            if self.dry_run:
                self._log(f"[dry-run] 知识库回写 mark_ok: {selector} {changes}", app, "DEBUG")
            else:
                elem.update(changes)
                self._dirty = True
                self.save()
                self._log(f"元素经验回写成功: {selector} last_ok={today} fail_times=0", app)
        return True

    def mark_fail(self, app: str, selector: str) -> bool:
        """执行失败回写：fail_times+1，达到阈值自动 disabled 并写日志。
        返回是否达到阈值直至停用（True 表示 disabled_now）。"""
        self.load()
        elem = self.get(app, selector)
        if elem is None:
            return False
        cur = int(elem.get("fail_times") or 0) + 1
        disabled_now = cur >= self.threshold
        if self.dry_run:
            action = "达阈值将停用" if disabled_now else ""
            self._log(f"[dry-run] 知识库回写 mark_fail: {selector} fail_times={cur} {action}", app, "DEBUG")
            return disabled_now
        elem["fail_times"] = cur
        if disabled_now:
            elem["disabled"] = True
            self._dirty = True
            self.save()
            self._log(f"元素[{selector}] 连续失败 {cur} 次（阈值{self.threshold}），已标记停用 disabled", app, "WARN")
        else:
            self._dirty = True
            self.save()
            self._log(f"元素[{selector}] 失败计数 fail_times={cur}/{self.threshold}", app, "DEBUG")
        return disabled_now

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def save(self):
        """把内存索引写回 yaml（非 dry-run）。写文件前先写临时文件再替换，避免半写。"""
        if self.dry_run or not self._dirty:
            return
        data = {"apps": []}
        for app_name in sorted(self._apps):
            data["apps"].append({
                "app": app_name,
                "elements": list(self._apps[app_name].values()),
            })
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(self._header_comment())
                yaml.safe_dump(
                    data, f, allow_unicode=True, default_flow_style=False,
                    sort_keys=False)
            os.replace(tmp, self.path)
            self._dirty = False
        except Exception as e:
            self._log(f"元素知识库保存失败: {e}", "sys", "ERROR")

    @staticmethod
    def _header_comment() -> str:
        return (
            "# =====================================================================\n"
            "# element_knowledge.yaml - 元素知识库（由 knowledge.py 自动维护）\n"
            "# 参考 AppAgent 元素用法知识库 + 失败经验回写思想本地化落地。\n"
            "#\n"
            "# 结构：apps[*].app（app 名，对应 config.yaml 的 name）-> elements[]\n"
            "#   元素字段：\n"
            "#     selector    主定位：u2 表达式 'kind=value'，kind 为 text/id/desc\n"
            "#     desc        用途注释\n"
            "#     usage       用法说明（何时点击、要点在哪）\n"
            "#     alternatives 备选 selector 列表（可空），失败后自动轮换尝试\n"
            "#     last_ok     最近一次成功日期 YYYY-MM-DD\n"
            "#     fail_times  连续/累计失败次数，达到阈值自动 disabled\n"
            "#     disabled    是否停用（true 后跳过该元素，转入视觉兜底）\n"
            "#\n"
            "# 运行机制：成功 mark_ok（刷新 last_ok/清零 fail_times/解除 disabled）；\n"
            "# 失败 mark_fail（fail_times+1，达阈值置 disabled）。\n"
            "# 本文件由程序重写，格式请以本模板为基准（注释不会保留在重写结果中）。\n"
            "# =====================================================================\n"
        )
