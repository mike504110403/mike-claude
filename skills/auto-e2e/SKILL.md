---
name: auto-e2e
description: on-demand 瀏覽器自動化實測：產 Playwright 腳本 headless 實跑。Mike 說「自動測」「幫我測」、/bug 需要 runtime 重現證據、或 review chain 差異重測回放時使用。
---

# auto-e2e — Playwright 腳本實測

證據產生器：大腦把流程寫成 Playwright spec、headless 一發跑完（2026-08-20 起取代 Chrome MCP 逐步驅動——腳本比 MCP 快一個數量級、可回放、可平行）。

## Runner（共用，零專案污染）

- Runner＝`~/.claude/e2e/`（package.json＋`@playwright/test`＋playwright.config.ts，已建好），**專案 repo 不裝依賴、不動 package.json**。
- spec 存 `~/.claude/e2e/specs/<repo>-<需求slug>/`（testDir 的子目錄，模組解析靠 runner 的 node_modules），**不進 git**；需求三清（/feature-flow 階段四）時一併刪目錄。
- 跑法（positional 參數是相對 testDir 的過濾字串，不是路徑；禁裸 npx，hook 也會擋）：

  ```
  cd ~/.claude/e2e && BASE_URL=<地端前端位址> ./node_modules/.bin/playwright test <repo>-<需求slug>
  ```

  trace 已在 config 全域開啟（`trace: 'on'`）；證據在 `test-results/`。

## PC 模式（2026-09-17 起，spec pc-offload D11）

棧在 PC 時（/local-stack 回報「棧：PC」）e2e 也在 PC 跑，Mac 不開瀏覽器也不需 Docker Desktop：

```
~/.claude/bin/pc-e2e <spec-filter> --base-url http://<PC IP>:<前端 port> [-- playwright 參數]
```

它把 runner（package.json、config、`specs/`）rsync 到 PC `~/ai-gateway/e2e/`，在 `mcr.microsoft.com/playwright:v<runner 同版>-noble` 容器（`--network host`、PC 使用者 uid）跑 `playwright test`；node_modules 在 PC 端用同一 image 的 node `npm ci`（lockfile 沒變就跳過）。輸出第一行「e2e：PC（host）」或「e2e：Mac（原因）」，**exit 4＝PC 不可達**（棧也在 PC 所以一起不可達：/local-stack 改 Mac 模式重起棧、BASE_URL 改地端後用下方 Mac 跑法），exit 3＝同步／安裝失敗，exit 255＝ssh 中途斷線，其餘含 1＝playwright exit code（1 是有紅或找不到 spec，不是 PC 問題）。**證據（trace、失敗截圖）落 PC `~/ai-gateway/e2e/test-results/`**，要判讀派 subagent 經 `ssh ai-pc-wsl` 看或 scp 回 scratchpad，不進大腦 context。`BASE_URL` 一律給 PC 的 Tailscale IP（與 /local-stack 回報同值）；spec 寫法、回放規則與下方步驟相同。

## 步驟

1. **環境**：/local-stack 起棧（棧在 PC → 跑法改用上節 `pc-e2e`，其餘步驟不變）；API 指地端判準唯一依據 /vue-dev「瀏覽器實測」0-1 步。`BASE_URL` 一律顯式傳入，spec 內不得寫死任何位址（防指到正式線）。測試帳號取自該專案 `.claude/localstack.json`。開跑前在 cmux 內把 `BASE_URL` 開成內嵌瀏覽器 tab（開法唯一依據 /browser-tools末條：加 tab、不開新 pane）——headless 測試本身照跑，tab 是給 Mike 同步看被測站與事後手測用；/local-stack 已開過就不重開。
2. **產 spec**：依 brief 實測步驟（或 Mike 交代的流程）每條流程一個 `test()`：操作路徑 → 畫面斷言（`expect(locator)`）→ 關鍵 API 斷言（`page.waitForResponse` 比對 endpoint＋回應關鍵欄位）；console 錯誤用 `page.on('console')` 收集並斷言無新增 error。沒有 brief 時自行列流程清單附在回報開頭。
3. **跑＋收證據**：exit code＋失敗自動截圖＋trace（`--trace on`；`show-trace` 可逐步回看，即舊三件證據的超集）。失敗輸出原文附回報，不轉述。**截圖與 trace 留在 `test-results/` 不 Read 進大腦 context**——要判讀畫面派 subagent 看（唯一依據全域「Context 預算紀律」截圖列）。
4. **回放**：差異重測／回歸直接重跑同一 spec（review chain 手測站引用本步）。跑紅先分辨「真回歸 vs selector 漂移」——漂移修 spec 再跑，功能錯才是發現。

## 邊界

- spec 是驗證資產不是專案測試檔：不受「Vue 專案不寫測試檔」裁示約束，也不進 repo。
- 工具選擇（CLI vs MCP）唯一依據 /browser-tools。寫 spec 時 selector 未知，先用 `playwright-cli snapshot`／`generate-locator` 對著地端頁面取 locator 再寫，不用 MCP 逐步驅動探。
- 登入態：獨立測試帳號的 storage state（`playwright-cli state-save` 產出、spec 用 `storageState` 載入），不用 persistent profile 殘留的登入狀態。
