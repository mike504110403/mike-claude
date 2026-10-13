---
name: playwright-cli
description: 用已安裝 Playwright CLI 的具名 session 探索頁面、操作與收集可重播證據。
---

# Playwright CLI

先依 browser-tools 確定 CLI 適用，查本機 binary、`--version` 與 `--help`；命令隨版本而異。全域 binary 可用即用，否則查專案已安裝的 binary／script。缺少工具就回報，不自行 npm install 或裸 npx。專案測試 runner 與 playwright-cli 是不同入口，不把 `playwright test` 當 CLI。

以下為支援這些命令之版本的最小範例，`<url>` 必須是已核實且獲授權的目標：

```sh
playwright-cli -s=<task> open <url>
playwright-cli -s=<task> snapshot
playwright-cli -s=<task> click <snapshot-ref>
playwright-cli -s=<task> fill <snapshot-ref> <value>
playwright-cli -s=<task> console
playwright-cli -s=<task> requests
playwright-cli -s=<task> close
```

從最新 snapshot 選元素；page 變動後重新取得 ref。可用 role/test-id locator 時選穩定語義定位。檔案、URL、參數使用符合目前 shell 的 quoting；Windows 優先參數陣列呼叫，避免 `&` 被 shell 解釋。

需要登入測試時用隔離帳號，版本支援則 `state-save <本機路徑>`／`state-load <本機路徑>`；此檔視為 credential，不進 Git、不印內容。需要重播則 `tracing-start`／`tracing-stop`，截圖存檔；支援程度以 `--help` 為準。trace/HAR 可能含秘密。

run-code/eval 只用於已獲授權的頁面觀測或流程，不拿它繞過網站／runtime 操作限制。mock route 要標為模擬，不能當真 API 證據。只清自己建立的 session；不要 kill-all、close-all 或刪使用者 profile。測試程式的產生與實跑依 auto-e2e 的 on-demand 邊界。
