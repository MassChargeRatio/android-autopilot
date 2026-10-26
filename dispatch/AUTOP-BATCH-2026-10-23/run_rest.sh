#!/usr/bin/env bash
# 剩余 10 个未验证 App 全跑一遍（2026-10-23）
set -u
cd "C:/Users/VUL/WorkBuddy AI/Android自动化/AndroidAutopilot" || exit 1
U2ADB=".venv/Lib/site-packages/adbutils/binaries/adb.exe"
OUT="dispatch/AUTOP-BATCH-2026-10-23/logs_host"
RES="dispatch/AUTOP-BATCH-2026-10-23/HOST_RESULT2.tsv"
mkdir -p "$OUT"
: > "$RES"

# "App|Task" —— 无 sign 的 App 按其实际 behaviors 选任务
LIST=(
  "悟空浏览器|sign"
  "抖音极速版|sign"
  "抖音火山版|sign"
  "今日头条极速版|sign"
  "京东理财|sign"
  "点淘|collect"
  "全民K歌|collect"
  "支付宝|collect"
  "抖音|watch"
  "百度极速版|open"
)

for ITEM in "${LIST[@]}"; do
  APP="${ITEM%%|*}"; TASK="${ITEM##*|}"
  "$U2ADB" connect 192.168.1.54:5555 >/dev/null 2>&1
  LOG="$OUT/h2_$APP.log"
  START=$(date +%s)
  timeout 300 ".venv/Scripts/python.exe" -u main.py --app "$APP" --task "$TASK" --force --fast > "$LOG" 2>&1
  RC=$?
  DUR=$(( $(date +%s) - START ))
  HIT=$(grep -E "命中并点击|点击坐标" "$LOG" | tail -2 | sed 's/.*\[INFO\] \[[^]]*\] //' | tr '\n' ';' | tr -d '\r')
  DONE=$(grep -c "执行完毕" "$LOG")
  if [ "$RC" -eq 124 ]; then STATE="TIMEOUT"
  elif [ "$DONE" -gt 0 ];  then STATE="DONE"
  else                       STATE="PARTIAL"; fi
  printf '%s\t%s\t%s\t%ss\t%s\n' "$APP" "$TASK" "$STATE" "$DUR" "$HIT" >> "$RES"
  echo "$(date +%H:%M) $APP($TASK) $STATE ${DUR}s" >> "$OUT/progress2.log"
done
echo "ALL_DONE" >> "$OUT/progress2.log"
