# Changelog

本檔案記錄這個英文新聞閱讀網站每個版本的變動。
版本號採用 [SemVer](https://semver.org/lang/zh-TW/) 風格：MAJOR.MINOR.PATCH。

## [2.4.0] — 2026-05-07（Unreleased，準備 push）

### 新增
- **兩階段已讀標記**（取代原本只有綠勾的單階段）：
  - 🩶 **灰色 ✓「看過」**：點進文章頁就標記（即使秒退）
  - 🟢 **綠色 ✓「真的讀完」**：滾過 BilingualReader 70% **且** 做完 Quiz
  - 從首頁卡片右上角直接看出哪些是「點過但沒讀完」、哪些是「真的讀進去」
- **新增 `enr.visited` localStorage 鍵**追蹤點擊紀錄

### 變更
- **文章頁區段順序**：Quiz **移到** 易誤解詞彙之前
  - 原因：Quiz 常考易誤解詞彙裡的字。先看詞彙再做 Quiz 等於洩題
  - 新流程：讀文章 → 做 Quiz 看自己懂多少 → 看詞彙釐清不會的字
  - 「易誤解詞彙」上方跳轉按鈕仍然有效（只是落點變到下方）
- **原本 v2.1+ 的綠勾語意改變**：以前「讀過」= 滾過 70% 即可。現在「真的讀完」需要**滾完 + Quiz**。舊使用者已存在 `enr.read` 紀錄會降級為灰勾，等做完 Quiz 後升級為綠勾

### 技術細節
- `getEngagementStatus(slug)` 統一邏輯：`engaged` 需要 `read[slug] && scores[slug]`
- BaseLayout 的 late script 改用 `data-status="visited"|"engaged"`，CSS 對應顯示不同顏色
- 連續閱讀天數仍然以 `enr.read` 為準（不算「只有點過」），保持嚴謹

## [2.3.0] — 2026-05-07

### 新增
- **每天文章數從 4-5 → 6** — 更平均覆蓋各分類
- **10 個新 RSS 來源**（醫學 / 公衛 / The Conversation 政治）：
  - BMJ News（英國醫學期刊新聞）
  - MedPage Today（臨床醫療新聞）
  - KFF Health News（美國公衛深度報導）
  - CDC MMWR（疾管署週報）
  - Lancet Public Health（頂級期刊新聞）
  - EurekAlert Medicine & Health（學界新聞稿聚合）
  - The Conversation Health / Medicine / Public Health / Politics（學者寫的科普）
- **首頁限縮為「最近 7 天」** — 過往超過 7 天的文章移到 `/archive`，避免首頁無限長
- **新增 `/archive` 完整文章庫**：每頁 20 篇，分頁排序
- **分類頁支援分頁**：每分類超過 20 篇自動分頁（`/category/{cat}/page/2/`）

### 變更
- **AI topic 選擇 prompt 強化**：明確要求嘗試包含至少 1 篇醫學 + 1 篇公衛
- **首頁區段順序**：今日 → 過往 7 天 → 瀏覽分類

### 移除
- **中醫分類完全砍掉** — 英文世界沒有足夠的中醫新聞來源，這個分類三個月內絕對是空的；砍掉乾淨
  - 移除 `tcm` from `CATEGORIES` 與 `CATEGORY_LABELS`
  - 移除 `China Daily Lifestyle` 與 `SCMP Lifestyle` RSS 來源（這兩個來源從沒實際產出有用內容）
  - 移除 prompts.py 與 ai_pipeline.py 裡所有 `tcm` references

### 預期影響
- 每天 cron 跑稍久（~9 分鐘 vs 原 ~7 分鐘）— 因為多 1 篇文章
- API 用量 ~21 RPD → ~25 RPD（仍在 500 RPD 免費額度內，無感）
- 首頁載入速度**保持輕快**，無論未來累積多少文章都不會變慢

## [2.2.0] — 2026-05-07

### 新增
- **全文搜尋**：header 加入放大鏡 icon → 連到新的 `/search` 頁
- 使用 [Pagefind](https://pagefind.app/) 在 build 階段預先索引所有文章內容（標題、本文、易誤解詞彙、Quiz）
- 完全 client-side 搜尋——靜態索引下載到瀏覽器、本地過濾，**沒有後端、沒有 API 呼叫**
- 支援中英混合查詢（雖然繁中沒有 stemming，但精確匹配運作正常）

### 技術細節
- `bin/build_for_deploy.sh` 在 `npm run build` 之後加跑 `npx pagefind --site dist`
- Pagefind 把索引輸出到 `dist/pagefind/`，內含 `.pf_meta`、`fragment/`、`index/` 等
- `/search` 頁面只載入 `pagefind-ui.css` 和 `pagefind-ui.js`（不影響其他頁面）
- 搜尋介面文字客製成繁中 placeholder / 提示

## [2.1.0] — 2026-05-07

### 新增
- **已讀標記**：卡片右上角綠色小勾。讀者滾過整個文章本文後自動標記，回首頁就能看到哪些已讀過
- **Quiz 分數紀錄**：每篇文章記錄最後一次成績；下次再做題時會顯示「上次：X / N」
- **連續閱讀天數**：以台北時區為準，每天讀至少一篇就 +1，中斷一天歸零
- **設定頁學習統計區塊**：顯示「已讀文章數、目前連續天數 🔥、最長連續天數、Quiz 平均分數」四個指標
- 「重置所有資料」按鈕現在也會清掉閱讀紀錄與 Quiz 分數

### 技術細節
- 已讀偵測使用 `IntersectionObserver` 追蹤一個放在 BilingualReader 後面的 sentinel；可見即標記
- 連續天數計算在 client side 即時從 `enr.read` 的時間戳推導（不存獨立的 streak 變數），避免狀態不一致
- 首頁 / 分類頁的 ✓ 標記由 `<body>` 結尾的內聯腳本套上 `data-read=""`，CSS 控制顯示

## [2.0.0] — 2026-05-07

### 新增
- **英文練習模式**：預設開啟，隱藏首頁卡片與文章頁的中文摘要，避免劇透干擾閱讀練習
- **設定頁面**（`/settings`）：齒輪 icon 在 header 右上角
  - 練習模式開關
  - 內文字體大小三段切換（小 / 中 / 大）
  - **段落對照預設改為直式**（英文上、中文下），可在設定切回橫式（電腦上左右並排）
  - 重置所有資料按鈕
- **CHANGELOG.md** 開始紀錄版本變動

### 變更
- 段落對照閱讀器（BilingualReader）的版面預設從「桌面橫式 / 手機直式」改為**永遠直式**，更適合中→英閱讀流程；偏好橫式的使用者可在設定切換回去
- 首頁卡片在練習模式只顯示「標題 + 英文小標」，不再顯示英文摘要，卡片更清爽（小標已經是一句話電梯簡報，摘要在卡片層級是冗餘的）。練習模式關閉時則顯示中文摘要

### 技術細節
- 使用者偏好存在瀏覽器 localStorage（鍵名 `enr.*`）
- 透過 `<head>` 內聯腳本在首次繪製前就套用設定，避免畫面閃爍
- 不需要任何雲端帳號或後端

## [1.0.0] — 2026-05-06

### 初版
- 5 階段資料管線：fetch_news → ai_pipeline（topic_selection / synthesis / translation / key_terms / quiz）
- 每天台北時間 6:00 自動產生 4–5 篇英文新聞文章（CEFR B1–B2）
- 8 個分類：政治、經濟、科技、能源、社會、醫學、公衛、中醫
- 中英對照閱讀模式、易誤解詞彙、四題深度選擇題
- Cloudflare Pages 自動部署、GitHub Actions 雲端排程
- 使用 Gemini 3.1 Flash Lite Preview（主）+ Gemini 2.5 Flash（備援）
