# Cloudflare Worker — 排程觸發器

GitHub Actions 內建的 `schedule:` 觸發在我們的 repo 上**不可靠**（連續測試 4 次都沒自動跑）。這個 Cloudflare Worker 是**主要的排程觸發機制**——每天 06:13 台北時間觸發 `daily.yml` workflow。

> ⚠️ 程式碼放在這裡只是**文件用途**。實際部署是透過 Cloudflare 網頁介面，**不會** auto-deploy。

## 一次性設定（約 15 分鐘）

### 第 1 步：建立 GitHub Personal Access Token

1. 開 https://github.com/settings/tokens
2. 右上角 `Generate new token` → `Generate new token (classic)`
3. 設定：
   - **Note**: `Cloudflare Worker cron trigger`
   - **Expiration**: `No expiration`（或 `1 year`，到期時記得更新）
   - **Scopes**: 只勾 ✅ **`workflow`**（這個 scope 包含觸發 Action 所需權限，**不能修改程式碼**）
4. `Generate token`
5. **馬上把 token 字串複製起來**（離開頁面後就再也看不到了）

### 第 2 步：在 Cloudflare 建立 Worker

1. 開 https://dash.cloudflare.com/ → 左邊 `Workers & Pages`
2. `Create application` → `Create Worker`
3. 取個名字，例如 `news-reader-cron`
4. 預設範本不用管，按 `Deploy`
5. 進入 Worker 頁面，按右上角 `Edit code`
6. 把 [`cron-trigger.js`](./cron-trigger.js) 的**全部內容**貼進左邊編輯器（覆蓋預設）
7. 右上角 `Deploy`

### 第 3 步：把 GitHub Token 存成 Worker 的 Secret

1. 回到 Worker 頁面 → `Settings` 分頁 → 找 `Variables and Secrets`
2. `Add` → `Type: Secret`
3. **Variable name**: `GITHUB_TOKEN`（必須一字不差，code 在找這個名字）
4. **Value**: 貼第 1 步複製的 token
5. `Save`

### 第 4 步：加 Cron Trigger

1. 還在 Worker 頁面 → `Settings` → 找 `Triggers` → `Cron Triggers`
2. `Add Cron Trigger`
3. **Cron expression**: `13 22 * * *`（= UTC 22:13 = 台北 06:13 隔日）
4. `Save`

### 第 5 步：測試

1. 還在 `Triggers` 區塊 → 找 `Cron Triggers` 旁邊的 `Trigger Cron` 按鈕
2. 點下去
3. 開另一個 tab 看 https://github.com/Ibizachen/english-news-reader/actions
4. **應該立刻看到一筆新的 `Daily article generation` run 出現**，Event 欄是 `workflow_dispatch`
5. ✅ 看到 = 設定成功
6. ❌ 沒看到 = 看 Worker 的 `Logs` 分頁查錯誤訊息

## 日常運作

設定完成後，每天 06:13 台北時間：

```
Cloudflare Worker 鬧鐘響
      ↓
Worker 用 Token call GitHub Actions API
      ↓
GitHub 開始跑 daily.yml workflow（fetch + AI pipeline）
      ↓
Workflow 跑完 commit 文章到 main branch（~9 分鐘）
      ↓
Cloudflare Pages 偵測到 commit，自動重 build
      ↓
~06:25 線上看到今天的新文章
```

## 注意事項

- **Token 過期**：如果建 token 時設了 expiration，到期那天 Worker 會開始失敗（Cloudflare logs 看得到 401）。需要重新建 token 並更新 secret。
- **GitHub Actions 內建 cron 留著**：daily.yml 裡的 `schedule:` 我們**沒有移除**。萬一哪天 GitHub 自己醒過來，可能會在同一天觸發兩次（最壞結果是有重複文章）。要避免可以把 daily.yml 的 schedule 註解掉，但目前不急。
- **費用**：Cloudflare Workers Cron Triggers 完全免費（額度 100K 次/天，我們一天 1 次）。
