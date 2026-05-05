#!/usr/bin/env bash
# 解除 macOS launchd 每日排程

set -euo pipefail

LABEL="com.englishnews.daily"
PLIST_PATH="$HOME/Library/LaunchAgents/${LABEL}.plist"

if [[ ! -f "$PLIST_PATH" ]]; then
  echo "· 沒有找到排程設定（$PLIST_PATH 不存在），可能本來就沒裝。"
  exit 0
fi

launchctl unload "$PLIST_PATH" 2>/dev/null || true
rm -f "$PLIST_PATH"

echo "✅ 已解除排程"
echo "   刪掉了：$PLIST_PATH"
echo ""
echo "如果你想之後再開啟：bin/install_schedule.sh"
