# Phase 3 補充規格 — AI 流水線的彈性與健壯性

> 本文件為原始 SPEC.md 第 3 階段（AI 處理流水線）的補充規格。請於 Phase 3 動工前完整閱讀並依此實作。

---

## 1. 為什麼這份補充規格存在

原始 SPEC 在 AI 流水線的設計只說了「支援切換 Ollama 和 Claude API」，這個彈性遠遠不夠。實務上 AI 處理階段是整個專案最容易出包的環節，原因有三：

1. **模型品質不可預測**——本地 Qwen3 在某些任務（如英文新聞風格寫作）可能達不到使用者要求，需要能局部換成更強的模型
2. **LLM 輸出本身不穩定**——格式錯亂、長度失控、幻覺、欄位漏寫等問題每天都會發生
3. **單點失敗會放大**——一個階段崩潰會拖累整個 pipeline，需要隔離機制

本補充規格新增的核心能力：
- 四個 AI 階段獨立配置 provider 和 model
- 支援四個 provider（Ollama / Claude / Gemini / OpenRouter）
- 四個必做的健壯性機制
- 數個選做的觀察與維護工具

---

## 2. 核心架構：分階段獨立配置

四個 AI 階段（選題、合成、翻譯、出題）必須能各自獨立指定 provider 和 model，使用者透過編輯設定檔就能改變行為，不需要動程式碼。

### 2.1 設定檔 `scripts/ai_config.yaml`

```yaml
# AI 流水線分階段配置
# provider: ollama | claude | gemini | openrouter
ai_pipeline:

  topic_selection:
    provider: ollama
    model: qwen3.6:35b-a3b
    temperature: 0.3
    max_tokens: 2000
    fallback:
      provider: gemini
      model: gemini-2.5-flash

  article_synthesis:
    provider: ollama
    model: qwen3.6:35b-a3b
    temperature: 0.4
    max_tokens: 4000
    fallback:
      provider: claude
      model: claude-sonnet-4-6

  translation:
    provider: ollama
    model: qwen3.6:35b-a3b
    temperature: 0.2
    max_tokens: 4000
    # 注意：Qwen 系列中文能力強，這個階段通常不用換
    fallback:
      provider: gemini
      model: gemini-2.5-flash

  quiz_generation:
    provider: ollama
    model: qwen3.6:35b-a3b
    temperature: 0.5
    max_tokens: 3000
    fallback:
      provider: claude
      model: claude-sonnet-4-6

# 全域設定
global:
  json_retry_max: 3              # JSON 解析失敗最多重試次數
  stage_failure_isolation: true  # 某階段失敗不影響同批其他文章
  cost_cap_usd_per_run: 5.0      # 單次執行成本上限（用於付費 provider）
```

### 2.2 環境變數 `.env`

```bash
# 哪些 API key 有設定，對應 provider 才可用
ANTHROPIC_API_KEY=sk-ant-...        # Claude API（可選）
GEMINI_API_KEY=AIza...              # Google Gemini（可選，免費 tier 足夠個人使用）
OPENROUTER_API_KEY=sk-or-...        # OpenRouter（可選）

# Ollama（預設、已安裝）
OLLAMA_HOST=http://localhost:11434
```

`.env.example` 要列出所有環境變數的格式範本。`.env` 要進 `.gitignore`，**絕對不能上 git**。

---

## 3. 支援的 Provider 與選擇建議

### 3.1 Ollama（預設、本地、免費）

- 模型：`qwen3.6:35b-a3b`（推薦，多語言能力強）
- 備選本地模型：`gemma3:27b`、`deepseek-v4-flash`（看使用者偏好）
- 優點：完全免費、零隱私顧慮、可離線
- 缺點：英文新聞寫作風格可能不如雲端模型

### 3.2 Claude（Anthropic API）

- 模型：`claude-sonnet-4-6`（CP 值高）、`claude-opus-4-7`（最強但貴）
- 取得 API key：在 [console.anthropic.com](https://console.anthropic.com) 註冊、加信用卡、建立 API key
- 注意：**Claude Max 訂閱不包含 API 額度，需另外付費**
- 成本：Sonnet 約每篇文章 0.05-0.10 美元、Opus 約 0.30-0.60 美元
- 適用：article_synthesis 和 quiz_generation 這兩個最吃英文寫作品質的階段

### 3.3 Gemini（Google，有免費 tier）

- 模型：`gemini-2.5-pro`（強）、`gemini-2.5-flash`（快、便宜）
- 取得 API key：在 [aistudio.google.com](https://aistudio.google.com) 用 Google 帳號登入、Get API key，**不需要信用卡**
- 免費 tier 配額：對個人專案非常充裕（每分鐘數十次請求、每天上千次）
- 優點：免費、品質接近 Claude Sonnet、不用綁信用卡
- 缺點：偶爾有安全過濾誤判（特別是政治新聞）

### 3.4 OpenRouter（聚合服務）

- 一個 API key 可用幾百種模型（包含 Claude、Gemini、Llama 等）
- 取得 API key：在 [openrouter.ai](https://openrouter.ai) 註冊、儲值（最低 5 美元）
- 適用：想試不同模型但不想各自開帳號的人

### 3.5 推薦的常見配置組合

**配置 A — 全本地、零成本**（預設）
全部四個階段用 Ollama + Qwen3.6。新手起步用這個。

**配置 B — 關鍵階段升級**（建議第二步嘗試）
synthesis 和 quiz 用 Gemini Flash（免費），其他用 Ollama。零成本但品質提升。

**配置 C — 高品質**（願意付費時）
synthesis 和 quiz 用 Claude Sonnet，其他用 Ollama。每月約 30-50 美元。

**配置 D — 最高品質**（不在乎成本）
全部用 Claude Opus。每月約 150-300 美元。

---

## 4. LLM 抽象層的程式設計

`scripts/llm_client.py`：

```python
class BaseLLMClient(ABC):
    @abstractmethod
    def complete(self, prompt: str, system: str = None,
                 temperature: float = 0.5,
                 max_tokens: int = 2000,
                 response_format: str = "json") -> dict:
        pass

class OllamaClient(BaseLLMClient): ...
class ClaudeClient(BaseLLMClient): ...
class GeminiClient(BaseLLMClient): ...
class OpenRouterClient(BaseLLMClient): ...

def get_client_for_stage(stage_name: str) -> BaseLLMClient:
    """讀取 ai_config.yaml，回傳該階段對應的 client。"""

def get_fallback_client_for_stage(stage_name: str) -> BaseLLMClient | None:
    """讀取 ai_config.yaml 的 fallback 設定，回傳備用 client（沒設則 None）。"""
```

每個 client 實作要：
- 處理該 provider 的 SDK 呼叫
- 把回傳統一成 `{"content": str, "tokens_used": int, "duration_sec": float}`
- 處理該 provider 特有的錯誤（rate limit、auth 失敗等）

---

## 5. 必做的健壯性機制（第一級，Phase 3 第一輪一定要做）

這四項是讓流水線「能跑、不會崩」的最低門檻。

### 5.1 JSON 解析失敗的重試

LLM 經常吐出格式錯誤的 JSON：少括號、多 trailing comma、用了 smart quotes、外面包了 markdown 程式碼圍欄、開頭加了「Here is the JSON:」之類的廢話。

實作要求：
- 收到 LLM 回應後，先做 JSON 預清理：剝掉 ```json ... ```、剝掉開頭和結尾的非 JSON 文字
- 嘗試 `json.loads()`，失敗後重試最多 N 次（依 `ai_config.yaml` 的 `json_retry_max`）
- 重試 prompt 加註明：「Your previous response could not be parsed as JSON. Output ONLY valid JSON with no other text, no markdown fences, no preamble. Here was the error: {error_msg}」
- 三次都失敗：呼叫該階段的 fallback provider 重試一次
- 仍失敗：標記該文章為 `status: failed`，跳過、繼續下一篇

### 5.2 段落數對齊驗證（翻譯階段必做）

這是會弄壞前端的硬傷。英文 8 段、中文翻譯 7 段，網站對照模式直接崩。

實作要求：
- 翻譯階段產出後，比對英文段落數和中文段落數
- 不一致時：顯示明確錯誤訊息，自動重試（重試 prompt 強調「Output exactly N paragraphs, one Chinese paragraph per English paragraph, in the same order」）
- 重試仍失敗：呼叫 fallback provider
- 仍失敗：標記該文章 failed、跳過

### 5.3 單階段失敗隔離

不能因為某一篇文章某一階段失敗，就導致整批文章全部報廢。

實作要求：
- 五篇文章用迴圈處理，每篇獨立的 try/except
- 任何一篇任何一階段拋例外：記錄詳細錯誤、把該篇標 failed、繼續下一篇
- 跑完後 print 摘要：成功 X 篇、失敗 Y 篇、各篇失敗原因
- failed 文章不寫進 `data/published/`，避免半成品上線

### 5.4 基本欄位與長度驗證

LLM 偶爾會省欄位、寫太短、寫太長、欄位拼錯名。

實作要求：

文章合成階段，產出後檢查：
- 必要欄位都有：`title`, `summary_en`, `body`, `key_terms`, `sources_used`
- 字數在合理範圍：500-1200 字之間（外面就用 fallback 重做）
- 段落數 ≥ 4（不能只有兩三段）

選擇題階段，產出後檢查：
- 恰好 4 題
- 4 題的 `type` 涵蓋 `detail`、`inference`、`vocabulary`、`main_idea`
- 每題有 4 個選項、有 `correct`、`explanation_zh` 至少 50 字
- `correct` 是 A/B/C/D 之一

驗證不通過：fallback provider 重試一次，仍失敗則 mark failed。

---

## 6. 加分項（第二級，等第一輪跑通再考慮）

### 6.1 進度顯示
跑 4-5 篇文章可能要 60-90 分鐘，必須有清楚的進度提示：

```
[1/5] iran-us-tensions
  ✓ topic_selection (ollama, 12s)
  ✓ article_synthesis (claude, 28s, 6432 tokens)
  ⟳ translation (ollama, 35s elapsed...)
```

### 6.2 單階段重做命令

不滿意某一階段的產出時，能只重做那一階段：

```bash
python scripts/ai_pipeline.py regenerate --slug iran-us-tensions
python scripts/ai_pipeline.py regenerate --slug iran-us-tensions --stage translation
python scripts/ai_pipeline.py regenerate --slug iran-us-tensions --stage quiz --provider claude
```

`--provider` 參數可以臨時覆寫該階段的 provider，不用改設定檔。

### 6.3 主題去重

相鄰幾天可能 RSS 一直推同一條新聞，避免發布重複主題：

- 維護 `data/published/recent_topics.json`，記錄過去 7 天發過的主題標題
- 選題階段在 prompt 裡告訴 AI 「以下主題最近七天已發過，請避開：[...]」
- 同一天五篇之間也要去重（簡易 fuzzy match）

### 6.4 成本上限保護

用付費 provider 時防止失控：

- 每次 LLM 呼叫累計 token 用量、估算成本
- 累計成本接近 `cost_cap_usd_per_run` 時，警告並停止後續呼叫
- 完整成本紀錄寫進該日的 `run_summary.json`

### 6.5 generation_log

每篇文章 JSON 多一個欄位記錄怎麼產生的，方便追溯品質問題：

```json
{
  "generation_log": {
    "topic_selection": {
      "provider": "ollama",
      "model": "qwen3.6:35b-a3b",
      "duration_sec": 12,
      "tokens_used": 3450,
      "fallback_triggered": false,
      "json_retries": 0
    },
    "article_synthesis": {
      "provider": "claude",
      "model": "claude-sonnet-4-6",
      "duration_sec": 28,
      "tokens_used": 6432,
      "fallback_triggered": true,
      "fallback_reason": "ollama returned 380 words, below 500 minimum",
      "json_retries": 1
    }
  }
}
```

---

## 7. 第三級項目（非必要，可完全略過）

下面這些當作「未來可能想做」的清單，**不要在 Phase 3 第一輪做**，避免過度工程化：

- 對比模式（同一篇用兩個 provider 各跑一次比較）
- Web admin 頁面（透過網頁切換模型，而非編輯 yaml）
- 預覽再發布機制（產出後使用者點過才上線）
- 黑名單機制（永久排除某些主題或來源）
- 自動 prompt tuning（記錄哪些 prompt 較常成功）

---

## 8. 給 Claude Code 的實作順序

請依下列順序實作 Phase 3，每完成一段就告訴使用者，不要一次到底：

**Step 1**：建立 `ai_config.yaml`、`.env.example`、`scripts/llm_client.py` 的抽象基礎類別、四個 provider 的子類別。先各自寫一個能呼叫的最小版本（給定 prompt、回傳文字）。

**Step 2**：實作 `scripts/prompts.py`（依原始 SPEC 第 8 節的四個 prompt 範本）。

**Step 3**：實作 `scripts/ai_pipeline.py` 主流程，串起四個階段。**只實作第一級健壯性機制（5.1～5.4）**，其他先不要碰。

**Step 4**：實作 CLI 入口和基本日誌輸出（讓使用者能跑、能看到進度）。

**Step 5**：用 Phase 2 抓回來的真實素材跑一次完整流程，產出 1-2 篇文章 JSON 給使用者看。

**Step 6**：使用者驗收完第一篇文章後，如果他需要，再加第二級項目（進度顯示、單階段重做、主題去重、成本上限、generation_log）。

**第三級的東西不要主動實作。**

---

## 9. 重要原則

1. **不要過度工程化**。這是個人專案，不需要 100% 測試覆蓋率、複雜的 dependency injection、抽象到天邊的設計模式。簡單能跑優先。

2. **使用者沒有程式背景**。所有設定檔變更、CLI 命令、錯誤訊息都要寫得人類看得懂，附中文註解。

3. **預設值要安全**。預設配置（Ollama 全程）必須能在沒有任何 API key 的情況下完整跑通。使用者連 .env 都沒設定時不該崩潰。

4. **錯誤訊息要可診斷**。「ValueError」這種沒用，要寫成「翻譯階段失敗：英文 8 段、中文翻出 6 段，已嘗試重試 3 次。建議：檢查該文章 source 是否有特殊字元，或切換到 fallback provider」。

5. **使用者驗收後再前進**。Step 5 跑出第一篇文章後，**停下來給使用者讀**。不要等做完六個 step 才發現品質不行。
