#!/usr/bin/env bash
# =============================================================================
# run_daily.sh — Phase 4 一鍵每日執行腳本
# =============================================================================
#
# 流程：
#   1. 抓今天的新聞（Phase 2: scripts/fetch_news.py）
#   2. AI 處理流水線（Phase 3: scripts/ai_pipeline.py）
#   3. 完成 — Astro dev server / 部署版會自動讀新文章
#
# 用法：
#   手動執行：       bin/run_daily.sh
#   被 launchd 呼叫：（會自動寫到 data/logs/）
#
# 結束代碼：
#   0  全部成功
#   1  抓新聞失敗（後面不跑）
#   2  AI 流水線失敗（但抓新聞成功）
# =============================================================================

set -uo pipefail

# 切換到專案根目錄（不論在哪裡呼叫這個 script）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# 確保 PATH 找得到 uv（launchd 環境通常很乾淨，找不到 brew 安裝的工具）
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin"

# 寫日誌（按日期）
mkdir -p data/logs
DATE_UTC="$(date -u +'%Y-%m-%d')"
LOG_FILE="data/logs/daily-${DATE_UTC}.log"

{
  echo "============================================================"
  echo " Daily run — $(date)"
  echo " 專案：$PROJECT_ROOT"
  echo "============================================================"
  echo ""

  echo "--- Step 1/2：抓新聞（Phase 2 fetch_news.py）---"
  if ! uv run python scripts/fetch_news.py; then
    echo ""
    echo "❌ 抓新聞失敗，中止後續步驟。"
    echo "   詳細日誌：$LOG_FILE"
    exit 1
  fi

  echo ""
  echo "--- Step 2/2：AI 流水線（Phase 3 ai_pipeline.py）---"
  if ! uv run python scripts/ai_pipeline.py; then
    echo ""
    echo "❌ AI 流水線失敗。raw 資料還在 data/raw/$DATE_UTC/，可手動重跑。"
    exit 2
  fi

  echo ""
  echo "--- Step 3/3：推送到 GitHub（觸發 Cloudflare 自動部署）---"
  if [ -d ".git" ]; then
    git add data/published/ 2>&1
    if git diff --cached --quiet; then
      echo "  · 沒有新增 / 變更的文章，跳過 commit"
    else
      git commit -m "🤖 Daily articles for $DATE_UTC" 2>&1
      if git push 2>&1; then
        echo "  ✓ 已推送到 GitHub — Cloudflare Pages 將在 1-3 分鐘後自動重新部署"
      else
        echo "  ⚠️  git push 失敗（網路問題？尚未設 remote？），文章已 commit 在本機"
        echo "     可手動執行：git push"
      fi
    fi
  else
    echo "  · 還沒 git init，跳過推送（Phase 5 才會用到）"
  fi

  echo ""
  echo "============================================================"
  echo " ✅ 完成 — $(date)"
  echo " 新文章：data/published/$DATE_UTC/articles/"
  echo "============================================================"

} 2>&1 | tee -a "$LOG_FILE"
