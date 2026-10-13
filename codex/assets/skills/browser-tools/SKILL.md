---
name: browser-tools
description: 依目前可用工具選擇瀏覽器或桌面操作方式；開手測入口、頁面探索、重播或效能診斷時使用。
---

# 瀏覽器與桌面工具

先盤點本回合實際可用的 purpose-built connector、native CUA/browser、CLI 與 MCP；讀相應工具文件後操作，不假定工具名稱或已安裝狀態。

| 需求 | 選擇 |
| --- | --- |
| 對服務做結構化讀寫 | 該服務 connector／API，遵守使用者授權 |
| 看現有頁面、互動探索、桌面原生 app | 可用的 native CUA/browser；依其初始化與觀測契約 |
| 已知流程、需可重播證據 | 已安裝 playwright-cli 具名 session 或專案 Playwright runner |
| 頁面結構需要探索且 native 不適用 | 可用 Playwright MCP，收斂後記錄可重走步驟 |
| performance trace／heap／效能診斷 | 可用 chrome-devtools；共用目標選擇器時串行操作 |

前端驗證先走 local-stack，核實 API／proxy 確實指向地端且對外連線已列明。頁面 200 不算環境證據。測試流程使用獨立測試帳號及隔離 storage state，不借用個人 persistent profile。storage state、HAR、trace、截圖可能含敏感資料，留本機 scratch，不進 Git。

每個並行任務用自己的具名 session；桌面焦點／共享 browser target 操作須串行。以 snapshot、DOM／AX、console／network 查到的事實選 selector；不要憑記憶猜元素。需要畫面證據才截圖，存檔並依目前工具的影像觀測能力與工作流 context 規則判讀，不能強制依賴不存在的截圖代理。

Mike 手測入口：App 工具有 `open_in_codex` 時可開宣告中的 URL；否則回報可點擊 URL 與步驟。只關閉自己建立的 session/tab，不 close-all，不更動既有視窗配置。
