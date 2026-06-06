# HANDOFF.md

> 這份文件是給 Codex、Claude Code 等 AI 助手之間交接用的。
> 每次開始工作前先讀這份，每次完成階段或暫停前更新這份。
> **不可寫入任何 API key、secret、token、密碼、個人資料。**

---

## 目前目標

Stories 第二階段已完成並部署。
目前沒有進行中的工作，等待 Ibiza 決定下一步方向。
候選方向：增加更多 Stories 主題、改善文章字數/品質、或開始其他功能。

---

## 最近完成

### 2026-06-06（Claude Code）

#### 1. parse_json_response bug 修復
- **問題**：Gemini 偶爾在 JSON 後附加多餘的 `}}}` 字元，導致解析失敗。
- **修法**：改用 `json.JSONDecoder().raw_decode()`，遇到第一個完整 JSON 就停。
- **檔案**：`scripts/llm_client.py`（第 544–551 行）
- **已 commit**：✅ `1b6ed59`
- **已 push**：❌（本機）

#### 2. Stories 連載大綱產生器
- **新增**：`scripts/generate_series.py`
  - `uv run python scripts/generate_series.py --topic "主題" --overwrite`
  - 呼叫 Gemini 產生 5 篇連載大綱，輸出 JSON + 中英對照 Markdown 預覽
  - 大綱包含每篇的角度、學習目標、核心問題、來源規劃（含 `bylinePlan`、`attributionExample`）
- **新增**：`docs/SERIES.md`
  - 記錄連載風格規範（source-led、byline header、attribution in every paragraph）
  - 說明 `parse_json_response` 修復原因
- **已 commit**：✅ `1b6ed59`
- **已 push**：❌（本機）

#### 3. Stories 連載文章產生器
- **新增**：`scripts/generate_series_article.py`
  - `uv run python scripts/generate_series_article.py --series <id> --part 1`（測試單篇）
  - `uv run python scripts/generate_series_article.py --series <id> --all`（全部 5 篇）
  - 讀取 `data/series_drafts/<id>.json` 大綱，呼叫 Gemini 產生完整文章
  - 輸出格式與每日新聞完全相容（`Article` interface），多一個 `series` 欄位
  - 每篇含：英文正文（6–8 段）、中文對照、詞彙表、4 題測驗、來源規劃
- **已 commit**：✅ `922c551`
- **已 push**：❌（本機）

#### 4. 已產生的草稿文章
- **主題**：The Power Behind the Prompt: AI and the Energy Crisis
- **系列 ID**：`ai-data-centers-energy-series`
- **草稿位置**：`data/series_drafts/ai-data-centers-energy-series/`
  - `part-1.json` / `part-1.md`（363 字，已審閱，品質 OK）
  - `part-2.json` / `part-2.md`（305 字）
  - `part-3.json` / `part-3.md`（354 字）
  - `part-4.json` / `part-4.md`（364 字）
  - `part-5.json` / `part-5.md`（336 字）
- **注意**：`data/series_drafts/` 已加入 `.gitignore`，不會被 commit
- **待辦**：需要人工審閱所有 5 篇，確認 OK 後才能發佈

---

## 目前未完成

### ✅ 全部完成（2026-06-06）

1. ✅ 審閱 Part 1 草稿（Ibiza 確認 OK）
2. ✅ 修復字數太短問題（改為 7 段 × 90+ 字，實際 680–734 字）
3. ✅ 發佈 5 篇文章到 `data/published/2026-06-06/articles/`
4. ✅ 建立 `data/stories/ai-data-centers-energy-series.json`
5. ✅ Push（commit `cfbcd74`，已上線）

### 候選下一步

- 新增更多 Stories 主題（跑 `generate_series.py` 選新題目）
- 考慮寫 `publish_series.py` 腳本，把審閱 → 發布自動化
- 每日新聞可以考慮讓 AI 自動偵測「可做成 Stories」的主題並提示 Ibiza

---

## 重要檔案

| 檔案/資料夾 | 用途 |
|---|---|
| `scripts/generate_series.py` | 產生連載大綱草稿（呼叫 Gemini，輸出 JSON + MD） |
| `scripts/generate_series_article.py` | 根據大綱產生完整文章草稿（輸出到 series_drafts/）|
| `scripts/llm_client.py` | Gemini/Ollama/Anthropic 客戶端（含 parse_json_response 修復）|
| `docs/SERIES.md` | 連載風格規範（source-led、attribution、byline 等）|
| `data/series_drafts/<id>.json` | 連載大綱（本機審閱，gitignored）|
| `data/series_drafts/<id>/<id>/part-N.json` | 產生的文章草稿（本機審閱，gitignored）|
| `data/stories/<id>.json` | Stories 書籤清單（已 commit，正式網站讀取）|
| `data/published/<date>/articles/<slug>.json` | 正式發佈的文章（已 commit）|
| `src/pages/stories/index.astro` | `/stories/` 頁面（已完成，不需修改）|
| `src/pages/stories/[id].astro` | `/stories/<id>/` 頁面（已完成，不需修改）|
| `src/lib/stories.ts` | 讀取 data/stories/ 並 resolve 文章 slug（已完成）|
| `src/lib/articles.ts` | Article 型別定義與載入邏輯 |
| `.env` | 本機環境變數（含 GEMINI_API_KEY，不可 commit）|

---

## 測試結果

| 指令 | 結果 |
|---|---|
| `uv run python scripts/generate_series.py --topic "AI data centers and energy" --overwrite` | ✅ 成功，產生大綱 JSON + MD |
| `uv run python scripts/generate_series_article.py --series ai-data-centers-energy-series --part 1` | ✅ 成功，363 字，3670 tokens，18.4s |
| `uv run python scripts/generate_series_article.py --series ai-data-centers-energy-series --all` | ✅ 成功，5 篇全部產生 |
| `npm run dev`（前端） | 未跑（前端無改動，不需要）|
| `bash bin/build_for_deploy.sh` | 未跑（等 push 後 Cloudflare 自動執行）|

---

## 錯誤與注意事項

### 1. Gemini `parse_json_response` 解析失敗（已修復）
- **錯誤訊息**：`json.JSONDecodeError: Extra data: line 110 column 1`
- **原因**：Gemini 3.1 Flash Lite 有時在合法 JSON 後面多附加 `}\n}\n}\n  \n  ]\n}` 等字元
- **修法**：改用 `raw_decode()` 取代 `json.loads()`，只解析第一個完整 JSON，後面全忽略
- **位置**：`scripts/llm_client.py` 第 544–551 行

### 2. Python `.format()` 與 JSON 模板衝突（已修復）
- **錯誤訊息**：`KeyError: '\n  "title"'`
- **原因**：`ARTICLE_PROMPT` 裡含有 JSON schema 範例（有 `{}`），被 Python 的 `.format()` 誤認為佔位符
- **修法**：改用 `prompt.replace("{key}", value)` 手動替換，不用 `.format()`
- **位置**：`scripts/generate_series_article.py` 的 `build_article_prompt()` 函式

### 3. Gemini API Key 注意事項
- 本機 `.env` 的 key 格式為 `AQ.xxxx`（非標準 `AIzaSy...` 格式，但有效）
- 目前配額：已使用約 55–60 / 500 RPD，非常安全
- 模型：`gemini-3.1-flash-lite`（500 RPD 免費，已確認可用）
- fallback 模型 `gemini-2.0-flash-lite` 在本機的 quota 為 0，不可用，**不要切換**

### 4. 產生文章字數偏短
- 目前 Part 1–5 產生的文章約 300–360 字，目標是 600–900 字
- 原因：`max_tokens=5000` 足夠，但 prompt 沒有明確要求最低字數
- 目前未修復，可在之後的 prompt 調整中處理

---

## 下一步建議

按優先順序：

1. **審閱 Part 2–5 草稿**（打開 `data/series_drafts/ai-data-centers-energy-series/*.md`）
2. **（選）調整字數**：若覺得太短，修改 `ARTICLE_PROMPT` 要求更多段落再重跑 `--all --overwrite`
3. **發佈文章**：把審閱 OK 的 part-N.json 複製到 `data/published/2026-06-06/articles/`
4. **建立書籤**：新增 `data/stories/ai-data-centers-energy-series.json`
5. **Push**：`git push origin main`（會觸發 Cloudflare 自動重建部署）

---

## 給下一位 AI 助手的接手提示

你好，這是 English News Reader 專案的 Stories（追蹤專題）功能。

**先讀**：`AGENTS.md`（專案架構說明）→ 這份 `HANDOFF.md`（目前進度）

**現在最重要的事**：
- 5 篇連載文章草稿已產生完畢，放在 `data/series_drafts/ai-data-centers-energy-series/`
- 但還沒有發佈到網站——需要審閱後，手動複製到 `data/published/`，再建 `data/stories/` 書籤
- 前端頁面（`/stories/`）已完整，**不需要修改任何前端程式碼**
- 所有 Stories 邏輯靠 `data/stories/<id>.json` 書籤清單驅動，參考 `global-ebola-response.json` 格式

**不要做**：
- 不要修改 `src/pages/stories/` 的前端（已完成）
- 不要把 `data/series_drafts/` 加進 git commit（已 gitignore）
- 不要 push 前讓 Ibiza 確認

**所有 commit 已 push**（最新：`cfbcd74`，2026-06-06）
