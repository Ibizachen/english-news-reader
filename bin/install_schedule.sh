#!/usr/bin/env bash
# =============================================================================
# install_schedule.sh — 設定 macOS launchd 每天自動跑 run_daily.sh
# =============================================================================
#
# 用法：
#   bin/install_schedule.sh           # 預設每天早上 7:00 跑
#   bin/install_schedule.sh 9 30      # 早上 9:30 跑
#   bin/install_schedule.sh 22 0      # 晚上 10:00 跑
#
# 解除排程：執行 bin/uninstall_schedule.sh
# =============================================================================

set -euo pipefail

HOUR="${1:-7}"
MINUTE="${2:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUN_SCRIPT="$PROJECT_ROOT/bin/run_daily.sh"

if [[ ! -x "$RUN_SCRIPT" ]]; then
  echo "❌ 找不到可執行的 $RUN_SCRIPT" >&2
  echo "   請先執行：chmod +x $RUN_SCRIPT" >&2
  exit 1
fi

LABEL="com.englishnews.daily"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/${LABEL}.plist"

mkdir -p "$PLIST_DIR"
mkdir -p "$PROJECT_ROOT/data/logs"

# 如果已經裝過，先卸載再裝（idempotent）
if launchctl list | grep -q "$LABEL" 2>/dev/null; then
  echo "🔁 偵測到已存在的排程，先卸載..."
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${RUN_SCRIPT}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${PROJECT_ROOT}</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>${HOUR}</integer>
        <key>Minute</key>
        <integer>${MINUTE}</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>${PROJECT_ROOT}/data/logs/launchd.out</string>

    <key>StandardErrorPath</key>
    <string>${PROJECT_ROOT}/data/logs/launchd.err</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:${HOME}/.local/bin:/usr/bin:/bin</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
PLIST

launchctl load "$PLIST_PATH"

# 印出總結
TIME_STR=$(printf "%02d:%02d" "$HOUR" "$MINUTE")
echo ""
echo "✅ 已設定排程"
echo "   時間：每天 ${TIME_STR}（你 Mac 的本地時間）"
echo "   plist：${PLIST_PATH}"
echo "   執行：${RUN_SCRIPT}"
echo "   日誌：${PROJECT_ROOT}/data/logs/"
echo ""
echo "📋 確認指令："
echo "   launchctl list | grep ${LABEL}"
echo ""
echo "🧪 立即測試（不等到排程時間）："
echo "   ${RUN_SCRIPT}"
echo ""
echo "🛑 想停止排程："
echo "   bin/uninstall_schedule.sh"
echo ""
echo "⚠️  注意：launchd 排程在「Mac 在睡眠 / 關機」時不會跑。"
echo "   設定時間建議選你 Mac 平常開著的時段（例如早上 9 點而不是凌晨）。"
