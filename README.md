# 英文閱讀練習網站

每天自動產生 AI 合成的英文新聞文章，支援中英對照閱讀和選擇題練習。涵蓋政治、經濟、科技、能源、社會、醫學、公衛、中醫八大分類。完整規格請見 [SPEC.md](./SPEC.md)。

> **正式網址**：[https://english-news-reader.pages.dev](https://english-news-reader.pages.dev)
>
> **目前進度**：✅ 全部 5 階段完成。每天早上 6:00（台北時間）自動更新。

## 技術棧

- **前端**：Astro 6 + React 19 + Tailwind CSS 4 + TypeScript
- **後端腳本**：Python 3.11+，套件管理用 `uv`
- **本地 LLM**：Ollama（預設模型 `qwen3.6:35b-a3b`），可切到 Claude API
- **部署**：Cloudflare Pages（Phase 5）

## 快速開始

### 1. 環境需求

| 工具 | 最低版本 | 安裝方式（macOS） |
|------|---------|----------|
| Node.js | 20+ | `brew install node` |
| Python | 3.11+ | macOS 已內建，或 `brew install python@3.11` |
| Ollama | 最新 | https://ollama.com/download |
| uv | 最新 | `brew install uv` |
| Git | 任意 | macOS 已內建 |

下載 LLM 模型（約 23 GB，下載一次就好）：

```bash
ollama pull qwen3.6:35b-a3b
```

### 2. 安裝專案依賴

下面這兩段指令分別安裝前端（Astro / React / Tailwind）和後端（Python 腳本）需要的套件。

```bash
# 安裝前端套件
npm install

# 安裝後端 Python 套件
uv sync
```

### 3. 啟動開發伺服器

```bash
npm run dev
```

啟動後打開瀏覽器到 `http://localhost:4321/` 就能看到網站。

## 抓取今日新聞（Phase 2）

執行下面這個指令會從 24 個 RSS 來源（BBC、The Guardian、NPR、AP、Al Jazeera、DW、WHO、STAT 等）抓今天的新聞，自動擷取每篇文章的全文，存到 `data/raw/<今日日期>/`：

```bash
uv run python scripts/fetch_news.py
```

預估時間：3–5 分鐘。完成後會看到一份摘要表，列出每個來源抓到幾篇、各分類的數量分布等。

**進階選項**：

```bash
# 只測試 RSS 是否能連通，不下載文章內文（30 秒內結束）
uv run python scripts/fetch_news.py --dry-run

# 把時間範圍從 24 小時拉長到 48 小時（新聞較少時很有用）
uv run python scripts/fetch_news.py --window 48

# 限制每個來源只抓 5 篇（debug 用）
uv run python scripts/fetch_news.py --limit 5
```

抓回來的資料是 Phase 3 AI 流水線的輸入，**不會直接顯示在網站上**。網站顯示的是 `data/published/` 裡的最終文章。

## 產出今日文章（Phase 3）

把 Phase 2 抓回來的原始新聞餵給 AI，跑四個階段（選題 → 合成英文 → 翻譯中文 → 出題），最後寫入 `data/published/<日期>/articles/`：

```bash
uv run python scripts/ai_pipeline.py
```

預估時間（看你 [`scripts/ai_config.yaml`](scripts/ai_config.yaml) 裡選的 provider）：
- 全 Ollama 本地：每篇 8-15 分鐘 × 4-5 篇 ≈ **30-60 分鐘**
- Ollama + Gemini Flash 混用：每篇 2-4 分鐘 × 4-5 篇 ≈ **10-20 分鐘**

**第一次測試建議**：先跑 1 篇看品質再決定要不要全跑：

```bash
uv run python scripts/ai_pipeline.py --max-articles 1
```

**進階選項**：

```bash
# 只跑選題階段，不真的合成文章（debug 用，~30 秒）
uv run python scripts/ai_pipeline.py --topic-only

# 從特定日期的 raw 資料產出
uv run python scripts/ai_pipeline.py --date 2026-05-05

# 測試 Gemini API 連線是否正常（消耗幾乎為 0 的 token）
uv run python scripts/llm_client.py --check gemini
```

### 切換 AI Provider

預設四個階段都先試 **Ollama** 跑本地，失敗才 fallback 到 **Gemini Flash**（免費 tier）。

**兩種切換方式**：

#### 方法 A：用網頁設定（推薦，視覺化）

```bash
npm run dev
```

打開 [`http://localhost:4321/admin/settings`](http://localhost:4321/admin/settings) — 這個頁面**只在你本機可見**，部署到 Cloudflare 後不會公開。可以：

- 用下拉選單切換每個階段的 provider 與 model
- 自動列出本機已下載的 Ollama 模型
- 沒設 API key 時即時警告
- 「💾 儲存設定」寫入 [`data/config/ai_settings.json`](data/config/)（覆蓋 `scripts/ai_config.yaml` 預設）
- 「🔄 重設為預設」刪掉 JSON 檔，恢復 YAML 預設值

#### 方法 B：直接編輯 YAML（手動）

編輯 [`scripts/ai_config.yaml`](scripts/ai_config.yaml)，把要改的階段 `provider:` 從 `ollama` 改成 `gemini` 即可（檔案末尾有完整範例）。如果同時也存了 JSON 設定（方法 A），JSON 會優先生效。

API key 設定在 [`.env`](.env)（複製 [.env.example](.env.example) 而來）。詳見「[環境變數](#環境變數)」段。

## 一鍵每日執行（Phase 4）

把抓新聞 + AI 處理串成一個指令：

```bash
bin/run_daily.sh
```

預估 1-3 分鐘（依 AI 模型而定）。執行紀錄寫到 `data/logs/daily-<日期>.log`。

### 設定每天自動跑（macOS launchd）

```bash
# 預設每天早上 7:00
bin/install_schedule.sh

# 或自訂時間（早上 9:30）
bin/install_schedule.sh 9 30
```

驗證有跑進去：

```bash
launchctl list | grep com.englishnews.daily
```

看排程跑出來的日誌：

```bash
ls -t data/logs/ | head -3
tail -50 data/logs/launchd.out
```

解除排程：

```bash
bin/uninstall_schedule.sh
```

> ⚠️ **重要**：launchd 排程在 **Mac 睡眠或關機** 時不會跑。如果你晚上會把 Mac 闔上、早上才打開，那麼設「早上 9:30」這種你 Mac 已經醒著的時段，比設「凌晨 4:00」可靠很多。

> 補充：第一次跑 `install_schedule.sh` 時，macOS 可能會跳出「允許執行 shell script」的權限視窗，照著允許即可。

## 目錄結構

```
.
├── SPEC.md               # 完整開發規格
├── src/                  # Astro 前端（頁面、元件、styles）
├── scripts/              # Python 後端腳本（fetch_news, ai_pipeline）
├── data/
│   ├── raw/              # 抓回來的原始新聞（不上 git）
│   └── published/        # 處理後的最終文章 JSON（上 git）
├── bin/run_daily.sh      # 一鍵每日執行腳本（Phase 4）
└── .env.example          # 環境變數範例（複製成 .env 後使用）
```

## 環境變數

複製 `.env.example` 為 `.env`：

```bash
cp .env.example .env
```

預設用本地 Ollama，不需要任何 API key。如需切到 Claude API，編輯 `.env`：

```
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
```

## 各階段狀態

- [x] Phase 1 — 前端骨架 + 假資料
- [x] Phase 2 — 新聞抓取模組
- [x] Phase 3 — AI 處理流水線（含 /admin/settings 視覺化設定 UI）
- [x] Phase 4 — 一鍵腳本 + macOS launchd 排程
- [ ] Phase 5 — 部署到 Cloudflare Pages（需處理 admin 頁面的部署排除 + 重新啟用 prerender）

## 內容免責聲明

每篇文章皆由 AI 從多個原始新聞來源綜合生成，**不是逐字翻譯也不是新聞原文轉貼**。事實請以原始來源為準，文章末尾會列出所有引用來源連結。
