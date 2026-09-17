# -*- coding: utf-8 -*-
"""webui - Android Autopilot 本地 Web 控制台

为什么不是 tkinter：本项目运行环境（`.workbuddy-ai` 托管的 Python venv）
**没有编译 tkinter**，`import tkinter` 直接 ModuleNotFoundError，
所以任何 tkinter GUI 在这台机器上根本起不来。

改用 stdlib `http.server` + 浏览器前端：
  * 零第三方运行时依赖（与本工程一贯约束一致）；
  * 只监听 127.0.0.1，不对外暴露；
  * 后端直接复用工程自身的模块（config / records.db / devtools），
    不重复实现设备访问与记账逻辑。
"""

__all__ = ["data", "jobs", "server"]
__version__ = "1.0.0"
