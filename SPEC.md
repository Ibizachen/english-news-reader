# 英文閱讀練習網站 — 開發規格文件

> 本文件為完整的開發規格，包含專案目標、技術架構、實作階段、資料結構、AI prompt 範本、新聞來源清單與部署設定。Claude Code 請依照本文件實作。

---

## 1. TL;DR — 給 Claude Code 的快速摘要

我要建一個「**英文閱讀練習網站**」，每天自動產生 4-5 篇 AI 合成的英文新聞文章，提供中英對照閱讀模式和選擇題練習。

**核心特色**：
- 每篇文章由本地 LLM 從 3-5 篇真實新聞合成，不是單純翻譯或轉貼
- 所有 AI 任務跑在使用者本地的 Ollama（Qwen 3.6-35B-A3B），不依賴雲端 API
- 但保留切換到 Claude API 的設計彈性
- 八大分類：政治、經濟、科技、能源、社會、醫學、公衛、中醫
- 內容難度 CEFR B1-B2，用字簡單但主題具專業深度
- 支援純英文閱讀模式 + 段對段中英對照模式
- 每篇文章含 4 題深度選擇題（含答案和中文解析）
- 部署到 Cloudflare Pages，公開可訪問

**使用者背景**：使用者沒有程式背景。請寫詳細的 README 和 setup 指引，所有需要使用者操作的步驟都要可以複製貼上。

---

## 2. 完整需求清單

### 2.1 內容需求

| 項目 | 規格 |
|------|------|
| 文章長度 | 600-1000 字（英文） |
| 文章難度 | CEFR B1-B2，**用字簡單但內容有深度** |
| 文章風格 | 新聞深度報導，含前因後果、多方觀點、影響評估 |
| 每日新文章數 | 4-5 篇 |
| 分類 | 政治 (politics)、經濟 (economics)、科技 (technology)、能源 (energy)、社會 (society)、醫學 (health)、公衛 (public-health)、中醫 (tcm) |
| 來源引用 | 文末列出所有參考來源；行文中用「According to Reuters...」「BBC reports that...」風格 |
| AI 標註 | 每篇文章顯眼處標註「本文由 AI 綜合多家報導生成，事實請以原始來源為準」 |

### 2.2 閱讀模式

- **純英文模式**：只顯示英文，乾淨閱讀
- **中英對照模式**：段對段對照，桌面左右並排、手機上下交錯
- 兩個模式可在文章頁切換（toggle 按鈕）

### 2.3 練習功能

每篇文章末尾 4 題選擇題：
- 題型：1 題細節、1 題推論、1 題單字情境、1 題主旨
- 每題 4 個選項
- 提交答案後顯示對錯、正確答案、**中文詳細解析**（解釋為什麼這個答案對、其他為什麼錯）

### 2.4 網站結構

- **首頁**：列出最近文章（按日期、按分類篩選）
- **文章頁**：文章內容 + 模式切換 + 選擇題
- **分類頁**：依八個類別瀏覽（醫學側重個別治療／藥物／臨床；公衛側重族群層級議題如疫情、疫苗政策、健康促進；中醫側重針灸、草藥、傳統醫學整合與相關研究）
- **關於頁**：說明這個網站是什麼、AI 是怎麼合成文章的、誠實的免責聲明

---

## 3. 技術架構

### 3.1 兩層架構

```
┌───────────────────────────────────────────────────────────┐
│                 Layer 1: News Fetching                     │
│   (Python script, runs daily, accesses internet)           │
│                                                             │
│   - Fetches RSS feeds from 15+ news sources                │
│   - Extracts full article text from URLs                   │
│   - Outputs raw articles as JSON                           │
└────────────────────────┬──────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────┐
│              Layer 2: AI Processing                        │
│   (Local Ollama / Qwen 3.6-35B-A3B, fully offline)        │
│                                                             │
│   - Selects 4-5 topics from today's headlines              │
│   - Synthesizes long-form article from 3-5 sources         │
│   - Translates to Traditional Chinese                      │
│   - Generates 4 quiz questions with explanations           │
└────────────────────────┬──────────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────────────────────────┐
│              Layer 3: Static Site (Astro)                  │
│                                                             │
│   - Reads generated JSON files                             │
│   - Builds static HTML pages                               │
│   - Deploys to Cloudflare Pages                            │
└───────────────────────────────────────────────────────────┘
```

### 3.2 技術棧

| 層 | 技術選型 |
|----|---------|
| 前端框架 | **Astro** + TypeScript |
| 樣式 | **Tailwind CSS** |
| 後端腳本 | **Python 3.11+** |
| 套件管理 | npm (前端) + uv (Python) |
| LLM 執行 | **Ollama**（已安裝），預設模型 `qwen3.6:35b-a3b` |
| RSS 解析 | `feedparser` |
| 文章內容擷取 | `trafilatura` 或 `newspaper3k` |
| HTTP 請求 | `httpx` |
| LLM 客戶端（本地） | `ollama` Python SDK |
| LLM 客戶端（備用） | `anthropic` Python SDK（可切換） |
| 部署 | **Cloudflare Pages**（免費 tier） |
| 自動排程 | macOS `launchd` 本機跑（Phase 5 再考慮 GitHub Actions） |
| 版本控制 | Git + GitHub |

---

## 4. 分階段實作計畫

> **重要**：請依照下列五階段循序實作，每階段完成後讓使用者驗證再進下一階段。不要一次寫到底。

### Phase 1 — 前端骨架 + 假資料 (Day 1)

**目標**：能用 `npm run dev` 啟動網站，看到首頁 + 文章頁 + 中英對照切換 + 選擇題互動，全部用 mock data。

**交付物**：
- Astro 專案完整 setup（含 Tailwind 設定）
- 至少一篇 mock 文章涵蓋每個分類（共 8 個分類）
- 首頁、文章頁、分類頁、關於頁
- 中英對照模式切換功能可用
- 選擇題互動可用（提交、顯示答案和解析）
- 響應式設計（手機可讀）

**完成判斷**：使用者打開瀏覽器能完整體驗閱讀和練習流程。

### Phase 2 — 新聞抓取模組 (Day 2)

**目標**：寫好 Python 腳本，能從 15+ 新聞源抓今天的新聞並儲存原始資料。

**交付物**：
- `scripts/fetch_news.py`
- 設定檔 `scripts/sources.yaml` 列出所有 RSS feed 和對應分類
- 輸出格式：`data/raw/YYYY-MM-DD/headlines.json` 和 `data/raw/YYYY-MM-DD/articles/`
- 錯誤處理：某個來源掛了不影響其他來源
- 使用者可以手動跑：`python scripts/fetch_news.py`

**完成判斷**：執行一次後，`data/raw/<今日>/` 下有 50+ 篇新聞原始資料。

### Phase 3 — AI 處理流水線 (Day 3)

**目標**：寫好 AI 處理流水線，吃 raw articles 吐出最終文章 JSON。

**交付物**：
- `scripts/ai_pipeline.py` 主程式
- `scripts/prompts.py` 集中放所有 prompt 範本（見第 8 節）
- `scripts/llm_client.py` 抽象層，支援切換 Ollama / Claude API（透過環境變數 `LLM_PROVIDER=ollama|claude`）
- 輸出：`data/published/YYYY-MM-DD/articles/<slug>.json`
- 流程：選題 → 合成英文 → 翻譯中文 → 出題 → 寫檔
- 完整日誌：每步驟產生什麼、用了多少 token、花了多少時間

**完成判斷**：執行 `python scripts/ai_pipeline.py --date today` 後產生 4-5 篇完整文章 JSON。

### Phase 4 — 整合 + 自動化 (Day 4)

**目標**：前後端完全整合；網站動態讀今天的最新文章；本機自動每日執行。

**交付物**：
- Astro 改成讀 `data/published/` 下的真實 JSON
- 文章列表按日期排序
- 一鍵腳本 `bin/run_daily.sh`：執行抓新聞 → AI 處理 → 重新建置網站
- macOS launchd 設定檔（每天早上某時間自動跑），含設定教學

**完成判斷**：使用者隔天起床，網站上有 4-5 篇新文章。

### Phase 5 — 公開部署 (Day 5)

**目標**：部署到 Cloudflare Pages 公開可訪問。

**交付物**：
- GitHub repo 設定
- Cloudflare Pages 自動部署設定
- 網域綁定教學（可選）
- 完整 README.md

**完成判斷**：可以從外部任何裝置打開網址看到網站。

---

## 5. 專案目錄結構

```
english-news-reader/
├── README.md                       # 完整說明文件（給使用者讀的）
├── package.json
├── astro.config.mjs
├── tailwind.config.mjs
├── tsconfig.json
├── pyproject.toml                  # uv 管理 Python 依賴
│
├── src/                            # Astro 前端
│   ├── pages/
│   │   ├── index.astro             # 首頁
│   │   ├── about.astro             # 關於
│   │   ├── articles/
│   │   │   └── [slug].astro        # 文章頁（動態路由）
│   │   └── category/
│   │       └── [category].astro    # 分類頁
│   ├── components/
│   │   ├── ArticleCard.astro       # 文章卡片
│   │   ├── ReadingModeToggle.tsx   # 中英對照切換（互動，需要 React island）
│   │   ├── BilingualReader.tsx     # 雙語閱讀元件
│   │   ├── Quiz.tsx                # 選擇題元件
│   │   └── Header.astro
│   ├── layouts/
│   │   └── BaseLayout.astro
│   ├── lib/
│   │   └── articles.ts             # 讀取 data/published 的 helper
│   └── styles/
│       └── global.css
│
├── scripts/                        # Python 後端
│   ├── fetch_news.py               # Phase 2
│   ├── ai_pipeline.py              # Phase 3
│   ├── llm_client.py               # AI 抽象層
│   ├── prompts.py                  # 所有 prompt 範本
│   ├── sources.yaml                # 新聞源設定
│   └── utils.py
│
├── data/
│   ├── raw/                        # 抓回來的原始新聞（不上 git）
│   │   └── 2026-05-06/
│   │       ├── headlines.json
│   │       └── articles/
│   │           └── <hash>.json
│   └── published/                  # 處理完的最終文章（上 git，給網站用）
│       └── 2026-05-06/
│           └── articles/
│               └── <slug>.json
│
├── bin/
│   └── run_daily.sh                # 一鍵執行腳本
│
├── .github/
│   └── workflows/                  # Phase 5 才用
│
└── .env.example                    # 環境變數範例
```

---

## 6. 資料模型

### 6.1 已發布文章 JSON Schema

`data/published/YYYY-MM-DD/articles/<slug>.json`

```json
{
  "id": "2026-05-06-iran-us-tensions",
  "slug": "iran-us-tensions-may-2026",
  "publishedAt": "2026-05-06T08:00:00Z",
  "category": "politics",
  "title": "Iran-US Tensions Reach New Peak Amid Strait of Hormuz Standoff",
  "subtitle": "Why diplomacy stalled, and what could come next",
  "summary": {
    "en": "Five sentences in English summarizing the article.",
    "zh": "五句中文摘要。"
  },
  "paragraphs": [
    {
      "id": "p1",
      "en": "First paragraph of the English article...",
      "zh": "第一段的中文翻譯..."
    },
    {
      "id": "p2",
      "en": "Second paragraph...",
      "zh": "第二段..."
    }
  ],
  "wordCount": 847,
  "readingLevel": "B1-B2",
  "keyTerms": [
    {
      "term": "frame",
      "partOfSpeech": "verb",
      "definitionEn": "To describe something in a chosen way to influence how people see it.",
      "definitionZh": "把某件事描述成某種樣子，藉此影響別人怎麼看它。",
      "noteZh": "常見作名詞（畫框），這裡作動詞用，意思是「把……說成是……」。文中：state media framed the move as a response."
    }
  ],
  "sources": [
    {
      "name": "Reuters",
      "url": "https://www.reuters.com/...",
      "title": "Original article title",
      "publishedAt": "2026-05-05T14:30:00Z"
    },
    {
      "name": "BBC News",
      "url": "https://www.bbc.com/...",
      "title": "...",
      "publishedAt": "2026-05-06T03:15:00Z"
    }
  ],
  "quiz": [
    {
      "id": "q1",
      "type": "detail",
      "question": "According to the article, what triggered the latest escalation?",
      "options": {
        "A": "...",
        "B": "...",
        "C": "...",
        "D": "..."
      },
      "correct": "B",
      "explanationZh": "詳細解析：正確答案是 B，因為文章第三段明確指出...。A 不對是因為...。C 不對是因為...。D 不對是因為..."
    }
  ],
  "aiGenerated": true,
  "aiModel": "qwen3.6:35b-a3b",
  "aiDisclaimer": "本文由 AI 綜合多家報導生成，事實請以原始來源為準。"
}
```

### 6.2 新聞源設定 sources.yaml

```yaml
sources:
  - name: BBC News
    rss: https://feeds.bbci.co.uk/news/world/rss.xml
    categories: [politics, society]
  - name: BBC Business
    rss: https://feeds.bbci.co.uk/news/business/rss.xml
    categories: [economics]
  - name: BBC Technology
    rss: https://feeds.bbci.co.uk/news/technology/rss.xml
    categories: [technology]
  - name: BBC Science & Environment
    rss: https://feeds.bbci.co.uk/news/science_and_environment/rss.xml
    categories: [energy, society]
  - name: The Guardian World
    rss: https://www.theguardian.com/world/rss
    categories: [politics, society]
  - name: The Guardian Business
    rss: https://www.theguardian.com/business/rss
    categories: [economics]
  - name: The Guardian Technology
    rss: https://www.theguardian.com/technology/rss
    categories: [technology]
  - name: The Guardian Environment
    rss: https://www.theguardian.com/environment/rss
    categories: [energy, society]
  - name: NPR News
    rss: https://feeds.npr.org/1001/rss.xml
    categories: [politics, society]
  - name: NPR Business
    rss: https://feeds.npr.org/1006/rss.xml
    categories: [economics]
  - name: AP News Top
    rss: https://rsshub.app/apnews/topics/apf-topnews   # AP 沒有官方 RSS，用 RSSHub
    categories: [politics, society, economics]
  - name: Al Jazeera English
    rss: https://www.aljazeera.com/xml/rss/all.xml
    categories: [politics, society]
  - name: Deutsche Welle (DW) Top
    rss: https://rss.dw.com/rdf/rss-en-top
    categories: [politics, economics, society]
  - name: Reuters World (via Google News)
    rss: https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com&hl=en-US&gl=US&ceid=US:en
    categories: [politics, economics, society]
    note: "Reuters removed direct RSS in 2020; we use Google News as a workaround"
  - name: Ars Technica
    rss: https://feeds.arstechnica.com/arstechnica/index
    categories: [technology]
  - name: The Verge
    rss: https://www.theverge.com/rss/index.xml
    categories: [technology]
  - name: POLITICO
    rss: https://www.politico.com/rss/politicopicks.xml
    categories: [politics]
  - name: BBC Health
    rss: https://feeds.bbci.co.uk/news/health/rss.xml
    categories: [health, public-health]
  - name: The Guardian Health
    rss: https://www.theguardian.com/society/health/rss
    categories: [health, public-health]
  - name: NPR Health
    rss: https://feeds.npr.org/1128/rss.xml
    categories: [health, public-health]
  - name: STAT News
    rss: https://www.statnews.com/feed/
    categories: [health]
    note: "Specialised in medicine, biotech, and clinical research"
  - name: WHO News
    rss: https://www.who.int/rss-feeds/news-english.xml
    categories: [public-health]
    note: "Authoritative source for global public health updates"
  # --- TCM (Traditional Chinese Medicine) sources ---
  # English-language RSS coverage of TCM is limited; we draw from broader
  # health/society outlets and these region-specific sources.
  - name: China Daily Lifestyle
    rss: https://www.chinadaily.com.cn/rss/lifestyle_rss.xml
    categories: [tcm, society]
    note: "English coverage of Chinese culture, medicine, lifestyle. Verify URL in Phase 2."
  - name: SCMP Lifestyle
    rss: https://www.scmp.com/rss/318208/feed
    categories: [tcm, health, society]
    note: "Hong Kong-based English coverage including TCM, wellness. Verify URL in Phase 2."
```

> **注意**：RSS feed URL 偶爾會變動，Phase 2 實作時先逐一驗證每個 URL 還能正常解析。如果某個失效，先註解掉，最後在 README 留一份「需要定期檢查」的清單給使用者。

---

## 7. 新聞抓取邏輯（Phase 2 細節）

### 7.1 流程

```
1. 讀 sources.yaml
2. 對每個來源並行（asyncio）抓 RSS
3. 從 RSS 取得最新 30 筆條目
4. 過濾：發布時間在過去 24 小時內、有完整 URL
5. 對每個 URL 用 trafilatura 抓全文
6. 失敗的 URL 跳過、記錄錯誤
7. 全部彙整成 headlines.json
   - 每個條目含: title, url, source, category_hints, published_at, full_text
8. 同時把每篇文章存成 data/raw/YYYY-MM-DD/articles/<sha1>.json
```

### 7.2 錯誤處理原則

- 任何單一來源失敗不影響其他
- 完整文字抓不到就跳過該文章（不要送殘缺資料給 AI）
- 完成後打印摘要：成功 X 篇 / 失敗 Y 篇 / 各分類數量

---

## 8. AI Prompt 範本

> 以下 prompt 統一用英文撰寫（給 LLM 看），instruction 部分明確、結構化、要求 JSON 輸出。

### 8.1 主題選擇 Prompt

```
You are a news editor selecting today's topics for an English reading practice site.

Review the headlines below, organized by category. Select 4-5 topics that meet ALL of these criteria:
1. Cover at least 3 different categories (politics, economics, technology, energy, society, health, public-health, tcm)
2. Are SUBSTANTIVE — avoid celebrity gossip, sports scores, weather, minor accidents
3. Have multiple independent sources covering them (cluster headlines about the same story)
4. Have clear cause-and-effect or multi-perspective angles
5. Would be interesting to an intermediate English learner

For each selected topic, identify which 3-5 source articles to use as raw material.

Headlines (format: [SOURCE] title — url):
{headlines_block}

Output as valid JSON, nothing else:
{
  "selected_topics": [
    {
      "topic_title": "Short topic name",
      "category": "politics|economics|technology|energy|society|health|public-health|tcm",
      "rationale": "One sentence on why this topic and angle",
      "source_urls": ["url1", "url2", "url3"]
    }
  ]
}
```

### 8.2 文章合成 Prompt

```
You are an expert journalist writing for English language learners at CEFR B1-B2 level.

Synthesize a SINGLE long-form news article from the source materials below.

REQUIREMENTS:
- Length: 600-1000 words (count carefully)
- Vocabulary: Use SIMPLE, COMMON words. Avoid literary, flowery, or rare vocabulary. Specialized terms (economic, political, technical) are OK when necessary, but explain them in simple terms on first mention.
- Sentence structure: Mostly simple-to-medium. Occasional complex sentences are fine but don't overdo it.
- Depth: Despite simple wording, cover the topic SUBSTANTIVELY. Include:
  * Background / why this matters
  * Current situation
  * Multiple perspectives or stakeholder views
  * Implications or what might come next
- Citation style: Throughout the article, attribute claims to specific sources using natural news-writing phrases:
  * "According to Reuters, ..."
  * "BBC reports that ..."
  * "The Guardian noted ..."
  * "AP cited a senior official saying ..."
- Tone: Neutral, factual, balanced. Do not editorialize.
- Structure: Compelling lead → background → current development → multiple angles → outlook
- Output the article in clearly separated paragraphs (use \n\n between paragraphs).
- Vocabulary callouts (key_terms): Pick 3-5 "TRICKY" words/phrases FROM the article body that intermediate (B1-B2) Taiwanese learners are likely to misread. PRIORITISE these kinds of words:
  * Used in a non-literal / metaphorical sense (e.g. "stalled" for talks, "cooled" for spending — not engines or temperature)
  * Used in an UNCOMMON part of speech (e.g. "frame" as a verb meaning "to describe in a particular way", "split" as a noun meaning "disagreement", "block" as a verb meaning "to prevent")
  * Phrasal verbs / idioms whose meaning is not obvious from the parts (e.g. "drop out", "line up", "outweigh")
  * Words that look easy but mean something specific in this context
  AVOID picking words that are merely "specialized terms" already explained in the article body (those help readers but aren't tricky).
  For each, include: the part of speech (`partOfSpeech`), an English definition in this article's sense (`definitionEn`), a Chinese definition (`definitionZh`), and a Chinese note (`noteZh`) explaining WHY it is easy to misread (e.g. "常見為名詞，這裡作動詞") plus a brief quote from the article showing where it appears.

Topic: {topic_title}
Category: {category}

Source materials (each article preceded by [SOURCE_N - source_name]):

{source_articles_block}

Output as valid JSON, nothing else:
{
  "title": "Engaging article title",
  "subtitle": "Optional one-line subtitle that adds nuance",
  "summary_en": "Five sentences summarizing the article.",
  "body": "Full article body, paragraphs separated by \\n\\n",
  "word_count": 847,
  "key_terms": [
    {
      "term": "frame",
      "partOfSpeech": "verb",
      "definitionEn": "To describe something in a chosen way to influence how people see it.",
      "definitionZh": "把某件事描述成某種樣子，藉此影響別人怎麼看它。",
      "noteZh": "常見作名詞（畫框），這裡作動詞用。文中：state media framed the move as a response."
    }
  ],
  "sources_used": ["Reuters", "BBC News", "The Guardian"]
}
```

### 8.3 中文翻譯 Prompt

```
You are a professional translator. Translate the following English news article into Traditional Chinese (繁體中文) for Taiwanese readers learning English.

REQUIREMENTS:
- Translate paragraph by paragraph. The number of output paragraphs MUST equal the number of input paragraphs.
- Use natural, fluent Chinese. Avoid translation-ese (避免翻譯腔).
- Use Taiwan-standard terminology (e.g., "雪茄" not "雪茄菸"; "資訊" not "信息"; "總統" terms as used in Taiwan media).
- For specialized terms, use the standard Taiwanese rendering. On first mention of an unfamiliar term, you may include the English in parentheses: 「制裁 (sanctions)」.
- Preserve attribution phrases naturally: "According to Reuters" → 「根據路透社報導」.
- Translate the summary as well.

English article (paragraphs separated by [PARA] markers):

{english_paragraphs_marked}

English summary:
{english_summary}

Output as valid JSON, nothing else:
{
  "translated_paragraphs": ["第一段翻譯", "第二段翻譯", ...],
  "translated_summary": "中文摘要"
}
```

### 8.4 選擇題 Prompt

```
You are an English reading comprehension quiz designer for intermediate (B1-B2) learners.

Create EXACTLY 4 multiple choice questions based on the article below. The 4 questions MUST cover these 4 distinct types in this order:

1. DETAIL: Test recall of a specific fact stated in the article. Should require careful reading, not just keyword spotting.
2. INFERENCE: Require connecting information across paragraphs to reach a conclusion not directly stated.
3. VOCABULARY IN CONTEXT: Pick a moderately challenging word from the article and ask its meaning AS USED in context.
4. MAIN IDEA: Test overall understanding of the article's central argument or message.

For each question:
- Provide 4 options (A, B, C, D)
- Exactly one is clearly correct
- The 3 distractors should be plausible — testing common misreadings, not absurd
- Provide a DETAILED explanation in Traditional Chinese explaining:
  * Why the correct answer is right (with reference to specific paragraph)
  * Why each of the 3 wrong answers is wrong

Article:
{article_body}

Output as valid JSON, nothing else:
{
  "questions": [
    {
      "id": "q1",
      "type": "detail",
      "question": "Question text in English",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct": "B",
      "explanation_zh": "詳細中文解析：正確答案 B，因為文章第三段明確提到...。選項 A 不對，因為...。選項 C 是常見誤讀，因為...。選項 D 雖然提到了，但不是問題問的重點..."
    },
    {"id": "q2", "type": "inference", ...},
    {"id": "q3", "type": "vocabulary", ...},
    {"id": "q4", "type": "main_idea", ...}
  ]
}
```

---

## 9. LLM 抽象層設計

`scripts/llm_client.py`：

```python
class LLMClient:
    """Abstraction over Ollama and Claude API. Switch via env var."""
    def __init__(self, provider: str = None):
        self.provider = provider or os.getenv("LLM_PROVIDER", "ollama")
        # ...

    def complete(self, prompt: str, system: str = None,
                 max_tokens: int = 4096,
                 response_format: str = "json") -> dict:
        """Returns parsed JSON if response_format='json', else raw text."""
        if self.provider == "ollama":
            return self._ollama_complete(...)
        elif self.provider == "claude":
            return self._claude_complete(...)
```

環境變數：
- `LLM_PROVIDER=ollama` (預設) 或 `claude`
- `OLLAMA_MODEL=qwen3.6:35b-a3b` (預設)
- `OLLAMA_HOST=http://localhost:11434`
- `ANTHROPIC_API_KEY=...` (僅切到 claude 時需要)
- `CLAUDE_MODEL=claude-sonnet-4-6` (備用)

---

## 10. 前端關鍵設計

### 10.1 中英對照模式排版

- **桌面（≥ 1024px）**：左右並排，左英右中，每段對齊
- **手機（< 1024px）**：上下交錯，每段英文後緊接該段中文，視覺上用淺色塊背景區分
- 切換按鈕在文章標題下方，狀態存 localStorage（下次造訪記得偏好）

### 10.2 選擇題互動

- 預設四題全部顯示題目和選項
- 使用者選擇後 → 點「Submit」→ 顯示結果
- 結果區塊：對勾或叉、正確答案標記、中文解析展開
- 顯示總分（X / 4）

### 10.3 首頁

- 頂部：今日 4-5 篇新文章卡片
- 中段：分類入口（八個方塊，桌面寬度 4×2 對稱排列、手機兩欄 4 列）
- 下方：歷史文章列表（按日期分組，可載入更多）

### 10.4 視覺風格

- 排版優先、文字優先（Reader-friendly）
- 字體：英文用 `Inter` 或系統 sans-serif，中文用 `Noto Sans TC`
- 行高 1.7-1.8、文章寬度限制在 65-75 字元
- 暗色模式支援（用 Tailwind 的 dark mode）

---

## 11. 部署設定（Phase 5）

### 11.1 GitHub repo 結構

- 主分支 `main` → 自動部署到 Cloudflare Pages
- `data/raw/` 列入 `.gitignore`（原始資料不公開）
- `data/published/` 進 git（網站需要）

### 11.2 Cloudflare Pages 設定

- Build command: `npm run build`
- Build output: `dist/`
- 環境變數：不需要（純靜態）

### 11.3 每日內容更新流程

```
1. 本機 launchd 每天早上 7:00 觸發 bin/run_daily.sh
2. fetch_news.py 抓新聞
3. ai_pipeline.py 處理（用本地 Qwen3）
4. git add data/published && git commit && git push
5. Cloudflare Pages 偵測到 push 自動 build & deploy
```

---

## 12. 給 Claude Code 的開工指令

請依照以下順序執行：

### Step 0 — 確認環境

執行以下命令確認以下軟體都在：
- Node.js 20+ (`node --version`)
- Python 3.11+ (`python3 --version`)
- Ollama 並且 `qwen3.6:35b-a3b` 模型已下載 (`ollama list`)
- Git

如果任何缺漏，先告訴使用者怎麼裝再繼續。

### Step 1 — 初始化專案

1. 用 `npm create astro@latest english-news-reader -- --template minimal --typescript strict --tailwind --no-install --no-git` 建立 Astro 專案
2. 安裝依賴（npm install）
3. 設定 Tailwind 含 typography plugin
4. 加入 React integration（@astrojs/react）給互動元件用
5. 用 `uv init` 建立 Python 環境
6. 安裝 Python 依賴：feedparser, trafilatura, httpx, ollama, anthropic, pyyaml, python-dotenv
7. 建立第 5 節列出的目錄結構
8. 建立 `.env.example`、`.gitignore`、初始 `README.md`

### Step 2 — Phase 1 實作

依照第 4 節的 Phase 1 交付物，先做出可運作的前端骨架。完成後**停下來告訴使用者「Phase 1 完成，請開瀏覽器確認」**，不要繼續往 Phase 2。

每個 Phase 完成都這樣做：實作完 → 寫個簡短的 Phase 完成報告（做了什麼、怎麼測試）→ 停下來等使用者確認 → 再進下一個 Phase。

### Step 3 — 後續

按 Phase 2 → 3 → 4 → 5 順序執行，每階段完成都暫停等使用者確認。

---

## 13. 重要原則與注意事項

1. **使用者沒有程式背景**：所有需要使用者執行的指令都要可以複製貼上，並用中文解釋這個指令在做什麼。
2. **錯誤訊息要友善**：如果某個步驟失敗，給清楚的錯誤訊息和怎麼解決的建議，不要只丟英文 stack trace。
3. **進度可見**：長時間執行的腳本（特別是 AI pipeline）要有進度提示。
4. **AI 品質可能不到 Claude 等級**：這是已知的取捨。第一篇文章產出後讓使用者讀過再繼續。
5. **保留切換到 Claude API 的彈性**：這個彈性是規格的硬性需求，不要為了簡化而砍掉。
6. **誠實標註 AI 生成**：每篇文章顯眼處要有免責聲明，這是道德要求。
7. **不要過度工程化**：這是個人專案，不需要單元測試覆蓋率、CI/CD pipeline、複雜的設定管理。簡單能跑優先。
8. **遇到不確定就問使用者**：遇到設計取捨不確定，停下來問，不要自己假設。

---

## 14. 預期時程

- Phase 1: 半天 ~ 一天
- Phase 2: 半天
- Phase 3: 一天（AI prompt 調整可能花時間）
- Phase 4: 半天
- Phase 5: 半天

總計約 3-5 天可以做出完整版（取決於 AI prompt 的迭代次數）。

---

**請從 Step 0 開始，逐步執行。每個 Phase 完成後暫停，回報狀況等使用者確認後再繼續下一階段。**
