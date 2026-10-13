---
name: auto-e2e
description: 使用者要求自動實測或明確要求 runtime 重現／差異回放時，建立可重播的瀏覽器證據；不自動擴大一般驗收。
---

# On-demand 瀏覽器實測

先列出此次要求的流程、操作與預期結果。依 browser-tools 選本回合可用工具；需要真 API 的流程先用 local-stack，明確取得 BASE_URL、frontend env override 與地端 API 證據。

## Runner preflight

讀 lock 檔、package scripts、Playwright config 與本機宣告。優先使用專案已鎖定且存在的 runner；也可用使用者已宣告的獨立 runner，其路徑由本機設定提供。核實 Node、`@playwright/test`、browser executable 與命令入口。缺 runner/browser 就回報缺項，不以裸 npx、下載 browser 或新增 package dependency 解決。新裝／新建共享 runner 另需使用者授權。

spec 放既有約定的驗證資產目錄或本機 scratch；repo 不新增 test 檔的專案用 scratch，確保 runner 能解析其模組及 testDir。BASE_URL 一律顯式傳入，spec 不硬編目標或測試帳密；帳號/storage state 從已授權本機設定取得，不印出值。

每條流程包含：可觀測 DOM 斷言、關鍵 API endpoint/status/必要 response 欄位斷言、console 新增 error 的收集與判定。實際 API 斷言不可用 mock 回應替代卻宣稱聯測通過。未知 selector 先取 snapshot／locator 再寫。

使用既有 runner 的本機 binary 執行指定 spec，開 trace 並保存失敗截圖。回報完整 invocation（遮罩秘密）、exit code、失敗訊息、trace／artifact 絕對路徑及已走／未走流程。失敗先辨別環境、selector 或產品行為；修 selector 後再回放同一流程。不把 stale artifact 稱為本次成功。App 可開地端 URL 供 Mike 手測，CLI 回報 URL。
