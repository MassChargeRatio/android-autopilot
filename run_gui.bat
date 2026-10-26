@echo off
chcp 65001 >nul
REM 一键启动 Web 控制台（强制使用项目 venv，绕开 VS Code / uv 的解释器选择）
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERROR] 找不到项目 venv: %PY%
  echo 请先在项目根目录执行: py -3 -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  pause
  exit /b 1
)

echo 使用解释器: %PY%
"%PY%" -c "import yaml,sys;print('PyYAML',yaml.__version__,'| Python',sys.version.split()[0])" || (
  echo [ERROR] 该 venv 缺 PyYAML，请执行 .venv\Scripts\pip install pyyaml
  pause
  exit /b 1
)

cd /d "%ROOT%"
REM 8765 常被 MySessions 占用（实测 PID 14236），默认改用 8770
echo 启动中… 浏览器将打开 http://127.0.0.1:8770/
"%PY%" gui.py --port 8770
pause
