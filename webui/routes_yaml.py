# -*- coding: utf-8 -*-
"""routes_yaml.py - WebUI 的 YAML 配置读写 + 自然语言生成接口（AUTOP-WEBUI-YAML-2026-10-22）

原计划派 marvis A 卡实现，但其会话 failed（零产物），由 Host 接手完成。
契约见派单卡 `dispatch/AUTOP-WEBUI-YAML-2026-10-22-A-CARD.md`。

设计要点：
  * 只暴露 `YamlRoutes`，`handle_get/handle_post` 返回 `None` 表示「不是我的路由」。
  * 写盘一律走 `devtools/yaml_writer`（eol 保真 / 备份 / 原子写），不自己 open(path,"w")。
  * 自然语言生成一律走 `devtools/nl_to_steps.build_behavior`，不复制词表。
  * `_snapshot/_verify` 按**当前 APPS_DIR** 做快照与比对（模块级常量可 monkeypatch），
    测试用临时目录即可，不必依赖真实 config.yaml。
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

try:
    import yaml  # noqa: E402
except ImportError as _exc:  # pragma: no cover - 解释器选错时的友好提示
    raise ImportError(
        "routes_yaml 需要 PyYAML，但当前解释器没装它。\n"
        "本项目依赖装在仓库根目录的 .venv 里，请用项目解释器：\n"
        "    C:\\Users\\VUL\\WorkBuddy AI\\Android自动化\\AndroidAutopilot\\.venv\\Scripts\\python.exe\n"
        "正确启动方式（注意是 gui.py，不是本文件）：\n"
        "    ./.venv/Scripts/python.exe gui.py --port 8765\n"
        "本文件是被 webui/server.py import 的库模块，直接运行它没有入口。"
    ) from _exc

from devtools import yaml_writer  # noqa: E402
from devtools import nl_to_steps  # noqa: E402

APPS_DIR = os.path.join(_ROOT, "config", "apps")
CONFIG_YAML = os.path.join(_ROOT, "config.yaml")


class YamlRoutes:
    """挂到 server.py 的 Handler 上：self.h 提供 _json/_err。"""

    def __init__(self, handler):
        self.h = handler

    # ---------- 入口 ----------

    def handle_get(self, path, q):
        if path == "/api/yaml/apps":
            return self._apps()
        if path == "/api/yaml/app":
            return self._app_text((q.get("name") or [""])[0])
        if path == "/api/yaml/fragment":
            return self._fragment((q.get("name") or [""])[0],
                                  (q.get("behavior") or ["sign"])[0])
        return None

    def handle_post(self, path, payload):
        if path == "/api/yaml/app":
            return self._save(payload or {})
        if path == "/api/yaml/generate":
            return self._generate(payload or {})
        if path == "/api/yaml/apply":
            return self._apply(payload or {})
        return None

    # ---------- 共用 ----------

    @staticmethod
    def _app_file(name: str) -> str:
        if not name or "/" in name or "\\" in name or ".." in name or "\x00" in name:
            raise ValueError(f"非法 app 名: {name!r}")
        for fn in sorted(os.listdir(APPS_DIR)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            stem = fn[:-5]
            if stem == name or stem.split("_", 1)[-1] == name:
                return os.path.join(APPS_DIR, fn)
        raise ValueError(f"未找到 App 配置: {name}")

    @staticmethod
    def _app_name_of(path: str) -> str:
        try:
            return (yaml_writer.load_app(path).get("name") or "").strip()
        except Exception:  # noqa: BLE001
            return os.path.splitext(os.path.basename(path))[0]

    def _snapshot(self) -> dict:
        """{app_name: app_dict}，范围=当前 APPS_DIR（可 monkeypatch）。"""
        out = {}
        for fn in sorted(os.listdir(APPS_DIR)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            p = os.path.join(APPS_DIR, fn)
            out[self._app_name_of(p)] = yaml_writer.load_app(p)
        return out

    def _verify(self, path: str, before: dict) -> tuple[bool, list[str]]:
        """目标文件可解析 + 除目标外其余 App 逐字不变。"""
        problems: list[str] = []
        try:
            target_name = (yaml_writer.load_app(path).get("name") or "").strip()
        except Exception as exc:  # noqa: BLE001
            return False, [f"目标文件无法解析: {exc}"]
        after = self._snapshot()
        if len(after) != len(before):
            problems.append(f"app 数量变化: {len(before)} -> {len(after)}")
        for name, app in before.items():
            if name == target_name:
                continue
            if after.get(name) != app:
                problems.append(f"误伤其他 App: {name}")
        return (not problems), problems

    @staticmethod
    def _money_behaviors() -> set:
        try:
            import config_loader
            return set(config_loader.money_behaviors(
                config_loader.load_config(CONFIG_YAML)))
        except Exception:  # noqa: BLE001
            return {"withdraw"}

    # ---------- GET ----------

    def _apps(self):
        apps = []
        for fn in sorted(os.listdir(APPS_DIR)):
            if not fn.endswith((".yaml", ".yml")):
                continue
            p = os.path.join(APPS_DIR, fn)
            try:
                data = yaml_writer.load_app(p)
            except Exception:  # noqa: BLE001
                continue
            apps.append({
                "name": (data.get("name") or "").strip(),
                "file": fn,
                "size": os.path.getsize(p),
                "mtime": int(os.path.getmtime(p)),
                "behaviors": sorted((data.get("behaviors") or {}).keys()),
            })
        return 200, {"ok": True, "apps": apps}

    def _app_text(self, name):
        try:
            path = self._app_file(name)
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}
        try:
            _lines, eol, _ends = yaml_writer.read_text(path)
            with open(path, "r", encoding="utf-8", newline="") as f:
                text = f.read()
        except OSError as e:
            return 500, {"ok": False, "error": str(e)}
        return 200, {"ok": True, "name": name, "file": os.path.basename(path),
                     "eol": eol, "text": text}

    def _fragment(self, name, behavior):
        try:
            path = self._app_file(name)
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}
        data = yaml_writer.load_app(path)
        acts = (data.get("behaviors") or {}).get(behavior)
        if acts is None:
            return 404, {"ok": False, "error": f"{name} 没有行为 {behavior}"}
        lines, _eol, _ends = yaml_writer.read_text(path)
        indent = yaml_writer.behavior_indent(lines, 0, len(lines)) or 2
        block = yaml_writer.render_behavior_block(behavior, acts, indent)
        return 200, {"ok": True, "fragment": "\n".join(block)}

    # ---------- POST ----------

    def _save(self, payload):
        name = str(payload.get("name") or "").strip()
        text = payload.get("text")
        if not name or not isinstance(text, str):
            return 400, {"ok": False, "error": "缺少 name 或 text"}
        try:
            path = self._app_file(name)
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}

        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as e:
            return 400, {"ok": False, "error": f"YAML 解析失败: {e}"}
        if not isinstance(parsed, dict) or not parsed.get("name"):
            return 400, {"ok": False, "error": "YAML 顶层必须是含 name 的映射"}

        before = self._snapshot()
        lines, eol, ends_nl = yaml_writer.read_text(path)
        new_lines = text.replace("\r\n", "\n").rstrip("\n").split("\n")
        if new_lines == lines:
            return 200, {"ok": True, "action": "unchanged", "diff": ""}

        bak = yaml_writer.backup(path, tag="WEBUI")
        yaml_writer.atomic_write(path, new_lines, eol, ends_nl)
        ok, problems = self._verify(path, before)
        if not ok:
            import shutil
            shutil.copy2(bak, path)
            return 200, {"ok": False, "action": "rolled_back", "backup": bak,
                         "diff": "", "warnings": problems}
        diff = yaml_writer._unified_diff(lines, new_lines, path)
        return 200, {"ok": True, "action": "saved", "backup": bak, "diff": diff}

    def _generate(self, payload):
        name = str(payload.get("name") or "").strip()
        behavior = str(payload.get("behavior") or "sign").strip()
        text = str(payload.get("text") or "").strip()
        if not name or not text:
            return 400, {"ok": False, "error": "缺少 name 或 text"}
        if behavior in self._money_behaviors() and not payload.get("allow_money"):
            return 400, {"ok": False,
                         "error": f"拒绝为资金类行为生成配置: {behavior}（需 allow_money）"}
        try:
            app_cfg = yaml_writer.load_app(self._app_file(name))
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}

        params = {}
        for key in ("tab_text", "tab_xy", "hub_text", "hub_xy",
                    "anchor_text", "anchor_xy", "ball_xy"):
            if payload.get(key):
                params[key] = payload[key]
        if payload.get("xy"):
            params["sign_xy"] = payload["xy"]      # 前端的 xy 就是签到跳坐标
        if payload.get("h5"):
            params["h5"] = True
            params["h5_offset"] = float(payload.get("h5_offset") or 60)
        entry = str(payload.get("entry") or "auto")

        result = nl_to_steps.build_behavior(text, name, behavior,
                                            entry=entry, params=params,
                                            app_cfg=app_cfg)
        return 200, {"ok": True, "entry": result["entry"],
                     "actions": result["actions"],
                     "fragment": nl_to_steps.to_yaml_fragment(result["actions"]),
                     "warnings": result["warnings"],
                     "candidates_used": result["candidates_used"]}

    def _apply(self, payload):
        name = str(payload.get("name") or "").strip()
        behavior = str(payload.get("behavior") or "sign").strip()
        actions = payload.get("actions")
        force = bool(payload.get("force"))
        if not name:
            return 400, {"ok": False, "error": "缺少 name"}
        if behavior in self._money_behaviors() and not payload.get("allow_money"):
            return 400, {"ok": False,
                         "error": f"拒绝写入资金类行为: {behavior}（需 allow_money）"}
        try:
            path = self._app_file(name)
        except ValueError as e:
            return 404, {"ok": False, "error": str(e)}

        if not actions and payload.get("text"):
            gen_code, gen = self._generate({
                "name": name, "behavior": behavior, "text": payload["text"],
                "entry": payload.get("entry") or "auto",
                **{k: payload[k] for k in ("tab_text", "tab_xy", "hub_text", "hub_xy",
                                           "anchor_text", "anchor_xy", "ball_xy", "xy",
                                           "h5", "h5_offset") if payload.get(k)},
            })
            if gen_code != 200:
                return gen_code, gen
            actions = gen["actions"]
        if not isinstance(actions, list) or not actions:
            return 400, {"ok": False, "error": "缺少 actions（或提供 text 由后端生成）"}

        # yaml_writer 的路径白名单按 base_dir 判定；base_dir 取 APPS_DIR 的上两级，
        # 这样测试把 APPS_DIR 指到临时目录时同样合法。
        base_dir = os.path.dirname(os.path.dirname(APPS_DIR))
        before = self._snapshot()
        if force:
            wr = yaml_writer.replace_behavior(path, behavior, actions,
                                              apply=True, force=True, tag="WEBUI",
                                              base_dir=base_dir)
        else:
            wr = yaml_writer.insert_behavior(path, behavior, actions,
                                             apply=True, tag="WEBUI",
                                             base_dir=base_dir)
        if not wr.changed:
            return 200, {"ok": True, "action": wr.action, "diff": wr.diff,
                         "warnings": wr.warnings}
        ok, problems = self._verify(path, before)
        if not ok:
            import shutil
            if wr.backup and os.path.exists(wr.backup):
                shutil.copy2(wr.backup, path)
            return 200, {"ok": False, "action": "rolled_back", "backup": wr.backup,
                         "diff": wr.diff, "warnings": problems}
        return 200, {"ok": True, "action": wr.action, "backup": wr.backup,
                     "diff": wr.diff, "warnings": wr.warnings}


if __name__ == "__main__":  # pragma: no cover - 只给人看，不该被直接运行
    print(__doc__ or "")
    print("本文件是被 webui/server.py import 的库模块，没有可执行入口。")
    print("启动 Web 控制台请用项目 venv：")
    print("    ./.venv/Scripts/python.exe gui.py --port 8765")
    print("启动后浏览器打开 http://127.0.0.1:8765/ ，左侧导航「✎ YAML 编辑」。")
    sys.exit(2)
