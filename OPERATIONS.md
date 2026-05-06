# 操作手冊 — 給專案擁有者的維護指南

> 這份文件給未來的你（或下一個 AI 助手）看，**不是給訪客看**。
> 內容假設讀者完全沒看過這個專案，從零交接。

---

## 1. 這個專案在做什麼

**一個給中文使用者的英文新聞閱讀練習網站**。每天自動：
1. 從 24 個新聞來源抓 130+ 篇真實英文新聞
2. 用 AI 從中挑 4-5 個主題、合成成 B1-B2 級英文文章（含中英對照、易誤解詞、選擇題）
3. 自動部署到公開網址：[https://english-news-reader.pages.dev](https://english-news-reader.pages.dev)

**完全免費 + 完全自動 + 不需要任何電腦在線**。

---

## 2. 整體架構（5 個階段疊加）

```
[Phase 5] GitHub Actions (雲端排程，每天 22:00 UTC = 6:00 台北)
    │
    │  觸發
    ▼
[Phase 4] bin/run_daily.sh (一鍵串接腳本)
    │
    │  step 1
    ▼
[Phase 2] scripts/fetch_news.py (抓 24 個 RSS)
    │
    │  data/raw/<日期>/
    ▼
[Phase 3] scripts/ai_pipeline.py (5 階段 AI 流水線)
    │
    │  data/published/<日期>/articles/
    ▼
git push → GitHub repo
    │
    ▼
[Phase 5] Cloudflare Pages 偵測到 push，自動 build & deploy
    │
    ▼
[Phase 1] Astro 網站 (前端介面 + 文章渲染)
    │
    ▼
全球 CDN 上線給訪客瀏覽
```

| Phase | 做什麼 | 檔案 / 工具 |
|-------|-------|-----------|
| 1 | 網站前端外觀（首頁、文章頁、選擇題互動）| `src/` 下的 Astro + React + Tailwind |
| 2 | 抓 RSS 新聞當原料 | `scripts/fetch_news.py` + `scripts/sources.yaml` |
| 3 | AI 把原料變成最終文章 | `scripts/ai_pipeline.py` + `scripts/prompts.py` + `scripts/llm_client.py` |
| 4 | 一鍵串接 Phase 2+3 + 排程 | `bin/run_daily.sh` + launchd 排程（已停用，被 Phase 5 取代） |
| 5 | 部署 + 雲端排程（取代 Phase 4 的 launchd） | `.github/workflows/daily.yml` + Cloudflare Pages |

---

## 3. 檔案結構地圖

```
nm-claude-code-ver/
├─ README.md             ← 給訪客看的，有 setup 步驟
├─ SPEC.md               ← 最初的開發規格
├─ PHASE3_ADDENDUM.md    ← Phase 3 設計補充規格
├─ OPERATIONS.md         ← 你正在讀這個（給專案擁有者看）
│
├─ src/                  ← 前端網站（Phase 1）
│  ├─ pages/
│  │  ├─ index.astro              ← 首頁
│  │  ├─ articles/[slug].astro    ← 文章頁
│  │  ├─ category/[category].astro ← 分類頁
│  │  ├─ about.astro              ← 關於頁
│  │  ├─ admin/settings.astro     ← 本機 admin 設定 UI（部署時被排除）
│  │  └─ api/                     ← admin 用的 API 端點（部署時被排除）
│  ├─ components/        ← 可重用的 UI 元件
│  ├─ layouts/           ← 頁面共用骨架
│  ├─ lib/               ← 工具函式（讀文章、設定等）
│  └─ styles/            ← 全域樣式
│
├─ scripts/              ← 後端 Python 腳本
│  ├─ fetch_news.py      ← Phase 2：抓 RSS
│  ├─ sources.yaml       ← 24 個新聞來源清單
│  ├─ ai_pipeline.py     ← Phase 3：AI 流水線主邏輯
│  ├─ prompts.py         ← AI 用的 prompts (改 prompt 在這)
│  ├─ llm_client.py      ← AI provider 抽象層 (Ollama/Claude/Gemini/OpenRouter)
│  └─ ai_config.yaml     ← 預設 AI 設定（Ollama for everything，但實際被 ai_settings.json 覆寫）
│
├─ bin/                  ← Bash 腳本
│  ├─ run_daily.sh           ← Phase 4 核心：抓+生成+push
│  ├─ install_schedule.sh    ← 設 launchd 排程（已不用，被 GitHub Actions 取代）
│  ├─ uninstall_schedule.sh  ← 取消 launchd 排程
│  └─ build_for_deploy.sh    ← 部署用 build 腳本（排除 admin/api）
│
├─ .github/workflows/
│  └─ daily.yml          ← Phase 5：GitHub Actions 排程（每天 22:00 UTC 跑）
│
├─ data/
│  ├─ raw/               ← 抓回來的原始新聞（gitignore，每天重生）
│  ├─ published/         ← AI 生成的最終文章（會 commit 到 GitHub）
│  ├─ logs/              ← 本機 launchd / run_daily 的執行日誌（gitignore）
│  └─ config/
│     └─ ai_settings.json ← 本機 admin UI 寫入的 AI 設定（gitignore）
│
├─ astro.config.mjs       ← Astro 設定（output: static）
├─ package.json           ← 前端依賴
├─ pyproject.toml         ← Python 依賴
├─ uv.lock                ← Python lock 檔
└─ .env                   ← 本機 API key（gitignore，重要！）
```

---

## 4. 每天會發生什麼

```
台北時間 06:00（= UTC 22:00 前一天）
GitHub Actions 觸發 .github/workflows/daily.yml
  │
  ├─ Checkout repo (5 秒)
  ├─ 裝 Python + uv + 依賴 (40 秒)
  ├─ 寫一份雲端用 ai_settings.json (1 秒)
  ├─ Phase 2 抓 RSS (10-20 秒)
  ├─ Phase 3 AI 流水線跑 4-5 篇 (5-7 分鐘)
  ├─ git commit + push (5 秒)
  └─ 結束（Cloudflare Pages 自動偵測到 push 開始 build）

台北時間 06:08 左右
Cloudflare Pages build & deploy 完成
全球 CDN 上線新內容

→ 你打開 english-news-reader.pages.dev 就有當天新聞
```

**全程不需要你 Mac 醒著、不需要任何人動手**。

---

## 5. 平常維護 SOP

### 5.1 平常什麼都不用做 ✅

每天看網站就好。**不用碰任何東西**。

### 5.2 想知道今天有沒有跑成功

打開 [https://github.com/Ibizachen/english-news-reader/actions](https://github.com/Ibizachen/english-news-reader/actions)
- 綠色 ✅ = 成功
- 紅色 ❌ = 失敗（GitHub 也會寄 email 給你）

### 5.3 想立刻手動觸發更新（不等到明天 6 點）

兩個方法：

**A. 在 GitHub 介面點按鈕（推薦）**
1. 開 [Actions 頁面](https://github.com/Ibizachen/english-news-reader/actions/workflows/daily.yml)
2. 右上角點 「Run workflow」 → Run workflow
3. 等 5-10 分鐘看綠色

**B. 在你 Mac 本機跑（救急用）**
```bash
cd /Users/ibizachen/Projects/news-master/nm-claude-code-ver
git pull   # 先把雲端的更新拉下來
bin/run_daily.sh
```
跑完會自動 push、Cloudflare 會自動 deploy。

### 5.4 想改 AI 設定（換 model、改 temperature 等）

**重要**：本機 admin UI（`/admin/settings`）只影響本機跑。**真正每天運作的設定在 `.github/workflows/daily.yml` 裡**。

兩個方法：

**A. 在 GitHub 網頁直接改**
1. 開 [`.github/workflows/daily.yml`](https://github.com/Ibizachen/english-news-reader/blob/main/.github/workflows/daily.yml)
2. 點右上鉛筆 ✏️
3. 找到 「Configure pipeline for cloud」 那段，改裡面的 model 名稱 / temperature
4. 下面填 commit message → Commit changes
5. 下次 daily 跑就生效

**B. 本機改完 push**
```bash
# 改 .github/workflows/daily.yml
git add .github/workflows/daily.yml
git commit -m "Switch model to xxx"
git push
```

### 5.5 想加 / 減新聞來源

編輯 `scripts/sources.yaml`，加減項目，commit + push。下次 daily 跑就用新清單。

### 5.6 想改 AI 寫文章的風格 / 規則

編輯 `scripts/prompts.py`，改裡面的 prompt 文字。常見想改的地方：
- `ARTICLE_SYNTHESIS_PROMPT` → 文章寫作風格、避用詞清單
- `TRANSLATION_PROMPT` → 翻譯規則、台灣用語、譯名對照
- `KEY_TERMS_EXTRACTION_PROMPT` → 易誤解詞挑選邏輯
- `QUIZ_GENERATION_PROMPT` → 選擇題設計

commit + push，下次 daily 跑用新 prompt。

### 5.7 完全停止自動更新

開 [Actions 頁面](https://github.com/Ibizachen/english-news-reader/actions/workflows/daily.yml) → 右上 「⋯」 → Disable workflow

恢復：同位置點 Enable workflow。

### 5.8 想看歷史文章

```
https://github.com/Ibizachen/english-news-reader/tree/main/data/published
```

按日期分資料夾，每篇都是 JSON。網站上也都看得到（首頁拉到底有 「Earlier」 區塊）。

### 5.9 想清理本機磁碟空間

最大宗：Ollama 模型（32 GB），如果確定不切回本地優先模式就可以刪：
```bash
ollama rm qwen3.6:35b-a3b
ollama rm qwen2.5:14b
```

其他可清的小東西：
```bash
cd /Users/ibizachen/Projects/news-master/nm-claude-code-ver
rm -rf node_modules .venv data/raw data/logs dist
```
都隨時可以 `npm install` / `uv sync` 裝回來。

---

## 6. 緊急問題處理 SOP

### 6.1 連續 2-3 天網站沒更新

1. 檢查 [Actions 頁面](https://github.com/Ibizachen/english-news-reader/actions) 有沒有紅色失敗
2. 點進失敗的 run，看哪一步爆掉
3. 常見爆掉原因：
   - **Phase 3 AI pipeline 失敗**：通常是 Gemini API 暫時 503 或廢棄 model
   - **commit + push 失敗**：通常是權限問題（罕見）
   - **fetch_news 失敗**：通常是某些 RSS 來源暫時掛了（不影響整體）

### 6.2 Gemini 模型廢棄 / 改名

症狀：Phase 3 全部 4xx 錯誤、log 顯示 `404 NOT_FOUND` 或 `model not found`

處理：
1. 去 Google AI Studio Rate Limit 頁面看現在有哪些 model 可用
2. 用這個指令找 model 名稱：
   ```bash
   curl -s "https://generativelanguage.googleapis.com/v1beta/models?key=YOUR_KEY" | python3 -c "import json,sys;[print(m['name']) for m in json.load(sys.stdin)['models']]"
   ```
3. 改 `.github/workflows/daily.yml` 裡的 model 名稱
4. commit + push

或直接找 AI 助手說「Gemini 把 X model 廢棄了，幫我換成 Y」。

### 6.3 Gemini 配額爆了

症狀：log 顯示 `429 RESOURCE_EXHAUSTED`

處理：
- **如果是免費 tier 自然超量**：去 Google AI Studio 看 Rate Limit 頁，把 workflow 改用 RPD 較高的 model（例如從 2.5-flash 換 3.1-flash-lite-preview）
- **臨時超量**：等明天 UTC 午夜配額重置就好

### 6.4 Cloudflare 部署失敗

症狀：Actions 綠色但網站沒更新

處理：
1. 開 [Cloudflare Pages dashboard](https://dash.cloudflare.com)
2. 找 english-news-reader 專案 → Deployments
3. 看最新一筆 deploy 是不是紅色 failed
4. 點進去看 build log
5. 通常是：build script 找不到某個檔案、依賴變了等

### 6.5 想完整重建本機開發環境

```bash
# 在新電腦上 clone repo
git clone https://github.com/Ibizachen/english-news-reader.git
cd english-news-reader

# 裝前端依賴
npm install

# 裝後端依賴
uv sync

# 設 Gemini key
cp .env.example .env
# 編輯 .env 把 GEMINI_API_KEY 填進去

# 啟動 dev server
npm run dev
# 打開 http://localhost:4321
```

---

## 7. 重要連結

| 用途 | URL |
|------|-----|
| 正式網站（給訪客） | [english-news-reader.pages.dev](https://english-news-reader.pages.dev) |
| GitHub repo | [github.com/Ibizachen/english-news-reader](https://github.com/Ibizachen/english-news-reader) |
| GitHub Actions（看排程跑得如何） | [Actions 頁面](https://github.com/Ibizachen/english-news-reader/actions) |
| Workflow 檔（改 AI 設定 / 排程時間） | [daily.yml](https://github.com/Ibizachen/english-news-reader/blob/main/.github/workflows/daily.yml) |
| Cloudflare Pages dashboard | [dash.cloudflare.com](https://dash.cloudflare.com) |
| Google AI Studio（看 Gemini 配額） | [aistudio.google.com](https://aistudio.google.com) |
| Google AI Studio Rate Limit 頁 | [aistudio.google.com/rate-limits](https://aistudio.google.com/rate-limits) |

---

## 8. 重要的設計決定（為什麼這樣做）

### 8.1 為什麼選 Astro 而不是 Next.js / 其他

- 內容為主的網站（讀文章），不需要 React 的全套客戶端互動
- Astro 預設輸出純 HTML，速度快、Cloudflare Pages 友善
- 但仍可在需要互動的地方（選擇題、雙語切換）載入 React island

### 8.2 為什麼用 RSS 而不是直接爬網站

- RSS 是新聞網站「歡迎機器讀的版本」
- 直接爬網頁可能違反條款、容易壞掉
- 配合 trafilatura 萃取主文，乾淨且穩定

### 8.3 為什麼把 keyTerms 拆成獨立階段

早期 keyTerms 是合成階段一起做的，但 AI 經常把例句寫成「原始來源」的句子（不是簡化後文章的句子）。獨立成階段後 AI 只看簡化文章，例句保證對得上。

### 8.4 為什麼用 GitHub Actions 而不是繼續用 launchd

- launchd 要 Mac 醒著
- GitHub Actions 跑在雲端、永遠在線
- 公開 repo 完全免費、無時數上限
- 部署到 Cloudflare 後架構自然延伸

### 8.5 為什麼 admin UI 只能在本機

- admin 需要寫 JSON 設定檔 + 子程序執行 → 需要 Node.js runtime
- Cloudflare Pages 純靜態，不能跑 Node.js
- 所以部署時用 `bin/build_for_deploy.sh` 把 admin/api 排除
- 「日常設定」由 workflow 檔承擔；admin UI 只剩本機測試用

### 8.6 為什麼日期顯示用台北時區

預設 Intl.DateTimeFormat 會用「執行環境的時區」。在 Cloudflare 上 build 時是 UTC，會顯示錯日期。所以強制 `timeZone: "Asia/Taipei"`。

### 8.7 為什麼 publishedAt 還是存 UTC

ISO 8601 時間最好存絕對時間（UTC），顯示時再轉時區。**不要存「台北時間」當原始值**，否則跨時區計算會出錯。

---

## 9. AI 設定的選擇（按優先級）

當前設定（`.github/workflows/daily.yml` 裡）：

```
所有 5 階段 → gemini-3.1-flash-lite-preview（500 RPD 免費 tier）
全部 fallback → gemini-2.5-flash（20 RPD 免費 tier）
```

可選方案（如果要切換）：

| 模式 | 設定 | 何時用 |
|------|------|------|
| 全 Gemini Lite | 現在這個 | **預設、推薦**：免費、快 |
| 全 Gemini 2.5 Flash | 主 = 2.5-flash | 想要稍微更高品質、且每天 < 4 篇 |
| 全 Claude | 主 = claude-sonnet-4-x | 想要最高品質、有付費預算 |
| 混合 | 合成+出題用 Gemini，其他用 Ollama | **本機跑時推薦**（GitHub Actions 沒 Ollama 不行） |
| 全本地 Ollama | 主 = qwen3.6:35b-a3b | **本機跑時想完全離線** |

---

## 10. 給未來 AI 助手的話

如果有人（你或下一個 AI）拿這份手冊來新對話討論這個專案，重點：

1. **5-phase 架構是已經定型的**，不要無故重構
2. **GitHub Actions 是現在的執行引擎**（不是 launchd / 本地排程）
3. **admin UI 是本機限定**，部署時被 `bin/build_for_deploy.sh` 排除
4. **`data/published/` 永遠不應該被腳本刪除**（歷史文章是價值）
5. **`data/raw/`、`data/config/`、`data/logs/` 都是 gitignore**
6. **API key 在兩個地方**：本機 `.env`、GitHub repo Secret（同一支）
7. **Gemini preview model 有風險**，廢棄時要備援切換到穩定版
8. **改 prompt 要一次跑 1 篇驗證**（`bin/run_daily.sh` 太貴）

最常被詢問的問題：
- 「為什麼日期顯示錯」→ 多半是時區 bug，看 §8.6 §8.7
- 「為什麼 admin 改了沒用」→ admin 只影響本機，不影響 GitHub Actions，看 §5.4
- 「Gemini API 出錯」→ 看 §6.2、§6.3

---

## 11. 整個專案的「靈魂」

這不是一個普通的新聞 RSS 聚合站。**它是給特定使用者（中文母語、學英文到 B1-B2）量身打造的閱讀練習工具**。

每個設計細節都有原因：
- 8 個分類覆蓋學習興趣（不只政經科技、還有醫學公衛中醫）
- B1-B2 用字嚴格控制，避免讀者卡關
- 「易誤解詞彙」針對中文母語者常踩的坑
- 翻譯用台灣繁體規範（譯名、用詞）
- 4 種題型涵蓋不同閱讀技能
- AI 生成清楚標註（誠信）

**改任何東西都要記得這個受眾**。如果以後想改成「給日本人學英文」、「給程度 B2+ 的人」，那是不同產品，要重新想很多細節。

---

_這份手冊是 2026-05-06 寫的。如果改了重大東西，請更新這份文件。_
