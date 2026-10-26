#!/usr/bin/env bash
# 17 个 App 串行带跑（Host 侧，2026-10-23）
# 关键点：python -u（否则被 timeout 杀掉时 stdout 块缓冲会丢全部日志）
set -u
cd "C:/Users/VUL/WorkBuddy AI/Android自动化/AndroidAutopilot" || exit 1
U2ADB=".venv/Lib/site-packages/adbutils/binaries/adb.exe"
OUT="dispatch/AUTOP-BATCH-2026-10-23/logs_host"
RES="dispatch/AUTOP-BATCH-2026-10-23/HOST_RESULT.tsv"
mkdir -p "$OUT"
: > "$RES"

APPS=(
  趣头条 拼多多 京东 美团 快手 百度地图 海马畅听 UC浏览器极速版 飞猪旅行
  米读小说 米读极速版 大众点评 天天快讯极速版 蛋花免费小说 喜番免费短剧 河马剧场 红果免费短剧
)

for APP in "${APPS[@]}"; do
  "$U2ADB" connect 192.168.1.54:5555 >/dev/null 2>&1
  LOG="$OUT/h_$APP.log"
  START=$(date +%s)
  timeout 300 ".venv/Scripts/python.exe" -u main.py --app "$APP" --task 签到 --force --fast > "$LOG" 2>&1
  RC=$?
  END=$(date +%s)
  DUR=$((END-START))
  HIT=$(grep -E "命中并点击|点击坐标" "$LOG" | tail -2 | sed 's/.*\[INFO\] \[[^]]*\] //' | tr '\n' ';' | tr -d '\r')
  DONE=$(grep -cE "执行完毕" "$LOG")
  if [ "$RC" -eq 124 ]; then
    STATE="TIMEOUT"
  elif [ "$DONE" -gt 0 ]; then
    STATE="DONE"
  else
    STATE="PARTIAL"
  fi
  printf '%s\t%s\t%ss\t%s\n' "$APP" "$STATE" "$DUR" "$HIT" >> "$RES"
  echo "$(date +%H:%M) $APP $STATE ${DUR}s" >> "$OUT/progress.log"
done
echo "ALL_DONE" >> "$OUT/progress.log"
