# 累積需求清單 v2（取代散落在對話中的個別決定）

> 本文件彙整了 SPEC.md + PHASE3_ADDENDUM.md 之外，後續討論累積的新需求與修正。
> 按優先級排序：先做的在前面、未來的在後面。

---

## 0. 目前進度速覽

✅ 已完成：
- Phase 1（前端骨架 + mock data）
- Phase 2（新聞抓取腳本）
- Phase 3 部分完成：AI pipeline 主流程、第一級健壯性、Gemini provider 已接好
- 已產出兩篇文章驗證：Qwen3 寫的 US-Iran、Gemini Flash 寫的 UK Economy

🔧 進行中：
- Phase 3 收尾（修 bug + 設定 UI）

⏳ 未開始：
- Phase 4（一鍵腳本 + macOS launchd 排程）
- Phase 5（部署 Cloudflare Pages）

---

## 1. Phase 3 必修 Bug（最優先，影響每篇文章）

實際跑了兩篇文章後發現的問題。這些不修的話，每篇新文章都會繼承這些缺陷。

### 1.1 中文翻譯：禁止中英混雜
Qwen3 那篇出現「他將與伊朗 counterpart 商討」這種沒翻譯的英文字。
**修正**：在中文翻譯 prompt 加註：
> "CRITICAL: Output 100% Traditional Chinese in the body. Do NOT leave any English word untranslated. If a word resists direct translation, paraphrase it in Chinese. The ONLY exception: on first mention of a proper noun, you may include the English in parentheses for reader reference, like 馬克宏 (Emmanuel Macron)."

### 1.2 中文翻譯：使用台灣標準譯法
Qwen3 那篇用了「荷爾木茲」「馬克龍」這些大陸譯法。
**修正**：在中文翻譯 prompt 加註：
> "Use Taiwan-standard transliterations for proper nouns. Examples: Strait of Hormuz = 荷莫茲海峽 (NOT 荷爾木茲), Macron = 馬克宏 (NOT 馬克龍), Trump = 川普 (NOT 特朗普), Putin = 普丁 (NOT 普京), Zelensky = 澤倫斯基. When uncertain, prefer how Taiwan media (中央社, 自由時報, 聯合報) renders names."

### 1.3 英文用字難度控制
兩篇都有 brinkmanship、barrage、headwinds 這類 C1 字偏多。
**修正**：在英文合成 prompt 加註：
> "Vocabulary level: Target CEFR B1-B2. Use common, frequently-used words. AVOID rare, literary, or academic vocabulary unless absolutely necessary. If a specialized term must be used, briefly explain it inline on first mention. Examples to avoid: 'brinkmanship' (use 'risky standoff'), 'barrage' (use 'wave of'), 'unilateral' (use 'one-sided'), 'headwinds' (use 'challenges')."

### 1.4 易誤解詞彙區塊：只能列文章裡實際存在的字
Gemini Flash 那篇的詞彙區塊列了 jitters、swallowing up、upended 等字，**這些字根本不在簡化過的文章裡**，是從原始來源材料抄的。讀者點開找不到。

**修正方式**：把詞彙生成從合成階段獨立出來，變成第五個 AI 階段。
- 新階段名稱：`key_terms_extraction`
- 輸入：「已合成的英文文章」（不是原始來源）
- prompt 要求：
  > "Pick 4-6 words/phrases that ACTUALLY APPEAR in the synthesized article body below. For each, provide a context quote that is the exact sentence from the article body where the word appears. Verify each context quote by string match against the article body before outputting."
- 後置驗證：每個詞彙的 context 必須能在文章 body 裡 string match 到，找不到就重做

### 1.5 來源引用一致性
Gemini Flash 那篇文中提到「as reported by Reuters」，但來源列表沒有 Reuters。AI 幻覺了一個未實際使用的來源。

**修正**：英文合成 prompt 加註：
> "You may ONLY cite sources that are explicitly provided in the source materials. Do NOT invent attributions to outlets like Reuters, AP, NYT, BBC unless they appear in the input. Every outlet you reference in-text must match an entry in the final sources list."

**後置驗證**：合成完成後掃描全文，找出所有「according to X」「X reports」「as reported by X」的引用，確認 X 都在 sources 列表裡。不一致就 fallback 重做。

### 1.6 地理事實謹慎用語
Gemini Flash 那篇說「Areas around London, like North Norfolk」，但 North Norfolk 距倫敦約 200 公里，不在「around London」。

**修正**：英文合成 prompt 加註：
> "When describing geographic relationships ('near X', 'around X', 'close to X'), prefer general phrasing ('expensive areas including X and Y') over specific spatial claims unless you are certain. If unsure about a location's geographic relationship, omit the spatial qualifier."

### 1.7 Rate Limit 處理（外出模式必加）
全雲端模式短時間內多次重試可能撞 Gemini RPM 上限。

**修正**：在 LLM 抽象層加上：
- 偵測 `429 Too Many Requests` 錯誤時，等待 60 秒（exponential backoff）後重試，而非立即 fallback
- Pro model 呼叫之間至少間隔 2 秒
- 多篇文章一律 sequential（順序）處理，**禁止 parallel**

---

## 2. Phase 3 收尾：設定 UI + 快速切換

### 2.1 設定 UI 頁面 `/admin/settings`
- 四個 AI 階段（選題、合成、翻譯、出題）各兩個下拉選單：主要模型 + 備援模型
- 下拉選單列出 Ollama / Claude / Gemini / OpenRouter 各 provider 可用的 model
- 「💾 儲存設定」：寫入 `data/config/ai_settings.json`
- 「🧪 測試一篇文章」：用當前設定即時產一篇文章供預覽
- Python pipeline 讀同一個 `ai_settings.json` 檔案
- 設定頁不要在主選單顯示，只能直接輸入網址訪問

### 2.2 快速切換按鈕（兩個預設模式）
設定頁上方加「快速切換」區塊，兩個一鍵按鈕：

**🏠 在家模式（本地優先）**
```yaml
topic_selection:    主 ollama/qwen3.6:35b-a3b,  備援 gemini-2.5-flash
article_synthesis:  主 ollama/qwen3.6:35b-a3b,  備援 gemini-2.5-flash
translation:        主 ollama/qwen3.6:35b-a3b,  備援 gemini-2.5-flash
quiz_generation:    主 ollama/qwen3.6:35b-a3b,  備援 gemini-2.5-flash
```

**✈️ 外出模式（純雲端 Gemini）**
```yaml
topic_selection:    主 gemini-2.5-flash,  備援 gemini-2.5-flash-lite
article_synthesis:  主 gemini-2.5-pro,    備援 gemini-2.5-flash
translation:        主 gemini-2.5-flash,  備援 gemini-2.5-flash-lite
quiz_generation:    主 gemini-2.5-pro,    備援 gemini-2.5-flash
```

點按鈕一鍵切換，不用每次手動下拉選單。

---

## 3. 文案調整

### 3.1 拿掉首頁「4-5 篇」這類具體數量描述
網站不該對讀者承諾每天的文章數量（萬一某天失敗或新聞淡，做不到）。

**改為**：「每日更新最新國際新聞」或「綜合多家媒體的英文閱讀練習」之類的彈性描述。

整個網站任何提到「4-5 篇」「每天 N 篇」的字樣全部拿掉。

---

## 4. 未來進階功能（Phase 4 之後再考慮，**現在不做**）

這些是 Phase 3 + Phase 4 + Phase 5 都跑通、運作穩定後再加的東西。**不要現在就做**，會打亂目前進度。

### 4.1 跨日故事追蹤（Story Tracking）
維持每天 5 篇，但讓 1-2 個主題形成「跨日連載」：
- 系統記錄過去 7-14 天的「持續性主題」
- AI 選題時有意識地對其中 1-2 個追蹤主題寫「跟進文章」
- 跟進文章開頭顯示：「This is part 3 of our coverage of US-Iran tensions. Previous: [Day 1], [Day 2]」
- 文章頁有「相關報導時間線」側邊欄

### 4.2 深度版切換（Depth Variant）
每篇文章有兩種長度版本，讓讀者選：
- **Standard**（700 字，B1-B2）：目前的版本
- **Deep Dive**（1200-1500 字，B2-C1）：同主題加深版本

文章頁加切換按鈕：「📖 標準版 / 🔍 深度版」

實作方式：合成階段一次產出兩個版本（一個 prompt 產 standard、另一個產 deep dive），都存進 JSON。

### 4.3 周末總結（Weekly Recap）
每週日多產一篇特別文章「This Week in Review」：
- 五個分類各最重要的故事串起來
- 該週故事的後續發展
- 約 1500-2000 字深度版

---

## 5. 已否決的設計（不做）

❌ **每天每主題 2 篇 / 一天 10 篇**：太多讀不完、AI 容易硬擠、不符合真實新聞節奏。改用「跨日連載 + 周末總結」（見 4.1, 4.3）達成相同的「深度感」目標。

---

## 6. 給 Claude Code 的開工指示（合併版）

下次貼給 Claude Code 時用這個結構：

```
我整理了 Phase 3 收尾要做的事，分兩批：

【第一批：修現有 bug（先做）】

請依以下七項修正 AI prompt 和 pipeline 邏輯。修完後重新跑一篇文章驗證所有 bug 都解決：

1. 中文翻譯禁止中英混雜（見 [貼 1.1 內容]）
2. 中文翻譯用台灣標準譯法（見 [貼 1.2 內容]）
3. 英文用字壓到 B1-B2（見 [貼 1.3 內容]）
4. 易誤解詞彙區塊獨立成第五階段（見 [貼 1.4 內容]）
5. 來源引用一致性驗證（見 [貼 1.5 內容]）
6. 地理事實謹慎用語（見 [貼 1.6 內容]）
7. Rate limit 處理 with exponential backoff（見 [貼 1.7 內容]）

【第二批：設定 UI 和快速切換（第一批修完再做）】

8. /admin/settings 設定頁（見 [貼 2.1 內容]）
9. 在家/外出模式快速切換按鈕（見 [貼 2.2 內容]）
10. 拿掉首頁「4-5 篇」描述（見 [貼 3.1 內容]）

第二批完成後 Phase 3 結束，請通知我驗收。
```

把上面的 [貼 X.X 內容] 換成本文件對應章節的詳細內容貼進去。

---

## 7. 驗收清單（Phase 3 完成的標準）

Claude Code 說 Phase 3 結束時，你檢查這些事都做到：

- [ ] 重新產一篇新文章，中文沒有英文混雜
- [ ] 該篇出現的人名地名是台灣標準譯法
- [ ] 英文用字明顯比之前簡單
- [ ] 易誤解詞彙區塊的每個詞，都能在文章 body 裡找到對應句子
- [ ] 來源列表完整（沒有文中引用了但列表沒列的情況）
- [ ] `/admin/settings` 頁面打得開、下拉選單能選、儲存按鈕能用
- [ ] 「測試一篇文章」按鈕真的能用當前設定產文章
- [ ] 「🏠 在家模式」按鈕一鍵切回 Ollama
- [ ] 「✈️ 外出模式」按鈕一鍵切到全 Gemini
- [ ] 首頁找不到任何「4-5 篇」「每天 N 篇」字樣
- [ ] Rate limit 處理：故意限制 Gemini 流量試試會不會優雅 retry

全部打勾，Phase 3 完成。
