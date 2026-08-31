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

## 步驟

1. **環境**：/local-stack 起棧；API 指地端判準唯一依據 /vue-dev「瀏覽器實測」0-1 步。`BASE_URL` 一律顯式傳入，spec 內不得寫死任何位址（防指到正式線）。測試帳號取自該專案 `.claude/localstack.json`。開跑前在 cmux 內把 `BASE_URL` 開成內嵌瀏覽器 pane（`"$CMUX_BUNDLED_CLI_PATH" browser open <BASE_URL>`，規則見全域 CLAUDE.md「Browser 自動化工具鏈」末條）——headless 測試本身照跑，pane 是給 Mike 同步看被測站與事後手測用；/local-stack 已開過就不重開。
2. **產 spec**：依 brief 實測步驟（或 Mike 交代的流程）每條流程一個 `test()`：操作路徑 → 畫面斷言（`expect(locator)`）→ 關鍵 API 斷言（`page.waitForResponse` 比對 endpoint＋回應關鍵欄位）；console 錯誤用 `page.on('console')` 收集並斷言無新增 error。沒有 brief 時自行列流程清單附在回報開頭。
3. **跑＋收證據**：exit code＋失敗自動截圖＋trace（`--trace on`；`show-trace` 可逐步回看，即舊三件證據的超集）。失敗輸出原文附回報，不轉述。
4. **回放**：差異重測／回歸直接重跑同一 spec（review chain 手測站引用本步）。跑紅先分辨「真回歸 vs selector 漂移」——漂移修 spec 再跑，功能錯才是發現。

## 邊界

- spec 是驗證資產不是專案測試檔：不受「Vue 專案不寫測試檔」裁示約束，也不進 repo。
- 工具選擇（CLI vs MCP）唯一依據全域 CLAUDE.md「Browser 自動化工具鏈」。寫 spec 時 selector 未知，先用 `playwright-cli snapshot`／`generate-locator` 對著地端頁面取 locator 再寫，不用 MCP 逐步驅動探。
- 登入態：獨立測試帳號的 storage state（`playwright-cli state-save` 產出、spec 用 `storageState` 載入），不用 persistent profile 殘留的登入狀態。
