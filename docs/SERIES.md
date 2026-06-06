# Stories / 追蹤專題

追蹤專題是一組 4-5 篇文章的閱讀路徑，用來理解長期發展的新聞故事。

## 目前流程

第一版採用審閱模式，不會直接發佈：

```bash
uv run python scripts/generate_series.py --topic "AI data centers and energy"
```

成功後會產生：

```text
data/series_drafts/<story-id>.json
data/series_drafts/<story-id>.md
```

如果本機沒有 `GEMINI_API_KEY`，腳本會產生模板草稿，方便先看資料格式。  
如果有 `GEMINI_API_KEY`，腳本會用 Gemini 產生一份 5 篇連載大綱。

`.md` 檔是給人看的中英對照預覽；`.json` 檔是之後給程式轉成正式
Stories 或文章用的資料。

## 風格方向

連載文章的目標是**嚴肅英文閱讀材料**，接近台灣碩士班英文考試使用的
reading comprehension packet，而不是短新聞摘要。

### 五個具體要求

1. **Byline header**：每篇文章開頭要有完整標題列，例如：
   > “How AI Is Draining America's Power Grid,” by Jane Smith,
   > The Atlantic, March 2024

2. **Attribution in every paragraph（每段有出處）**：不能有憑空斷言。
   每段必須用以下模式之一引入事實：
   - `According to [outlet]...`
   - `[Expert name], a [title] at [institution], said...`
   - `[Outlet] reports that...`
   - `In a [date] report, [agency] found that...`

3. **Named quotes（引用真實人名）**：每個來源規劃至少一個具名引述，
   例如「Energy Secretary / IEA chief economist / company spokesperson」——
   不是模糊的「an expert said」。不能捏造引言。

4. **Multi-source per article（每篇 2-3 個不同類型的來源）**：
   - 新聞報導（建立事實與近況）
   - 分析文章或 explainer（補充脈絡與解讀）
   - 專家 Q&A 或官方報告（提供權威深度）

5. **Factual anchoring（數字與事實一定有出處）**：每篇至少 2-3 個
   可溯源的具體數字、日期、法規名稱或機構名稱。

### generate_series.py 產生的大綱欄位說明

| 欄位 | 用途 |
|------|------|
| `bylinePlan` | 建議的 byline 格式（記者類型、刊物類型、大概日期） |
| `sourcePlan[].attributionExample` | 實際行文時如何引用這個來源，例如 `”According to a 2024 IEA report...”` |
| `sourcePlan[].searchHint` | 搜尋這個來源用的關鍵字 |

### parse_json_response 修正（2026-06-06）

Gemini 偶爾會在 JSON 後面附帶多餘的 `}}}` 垃圾字元。
`llm_client.py` 的 `parse_json_response` 已改用 `json.JSONDecoder().raw_decode()`，
遇到第一個完整的 JSON 物件就停，自動忽略後面的多餘字元。

如果 GitHub Actions 已經換成新的 key，但本機還是出現 `403 PERMISSION_DENIED`
或 `dunning deny`，代表 `.env` 裡仍是舊的 Gemini key。把 `.env` 的
`GEMINI_API_KEY=` 換成 Google AI Studio 新 project 的免費 key 後再跑一次。

草稿檔 `data/series_drafts/` 只給本機審閱，已加入 `.gitignore`。確認要上線的
專題才整理進 `data/stories/`。

## 發佈原則

- 先審閱大綱，再產文章。
- 不直接自動推上正式網站。
- 每個故事以 4-5 篇為主，避免變成無限延伸。
- 題材要有長期脈絡，而不是單日新聞。
- 預設英文先行，繁中只作為學習支援。

## 資料位置

正式 Stories 入口資料放在：

```text
data/stories/
```

每個 JSON 對應網站上一個 `/stories/<id>/` 頁面。
