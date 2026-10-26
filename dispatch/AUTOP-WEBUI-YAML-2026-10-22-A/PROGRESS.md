# PROGRESS - AUTOP-WEBUI-YAML-2026-10-22-A

派单：实现 `webui/routes_yaml.py`（6 路由契约）+ `tests/test_webui_yaml_api.py`（>=12 例）
环境：`./.venv/Scripts/python.exe`（必须）
验收：新测试全绿 + 全量 >= 360 + config/apps sha256 不变 + AST 词表门禁零命中

## 终态表（Host 复核）

| 阶段 | 状态 | 说明 |
|---|---|---|
| 读卡/依赖/基线 | DONE | 卡片已读；yaml_writer/nl_to_steps/server/config_loader 已读；基线 360 passed；sha256 基线 34 apps + config.yaml |
| PROGRESS 骨架 | DONE | 本文件 |
| routes_yaml.py | TODO | 6 路由：apps / app / fragment / app(POST) / generate / apply |
| test_webui_yaml_api.py | TODO | >=12 例 |
| pytest 新测试 | TODO | 待跑 |
| 全量回归 | TODO | 待跑（>=360） |
| sha256 校验 | TODO | 待跑 |

## 处理函数清单（每完成一个立即更新）

（待填充）
