---
name: bug
description: 診斷未知根因的故障或性能問題，以重現與呼叫鏈證據選實作 lane。
---

# bug

先收最小重現、錯誤輸出、改動時間與 producer/consumer 呼叫鏈，按實際可用工具定位；有 graft 圖先 /graft。只查詢時不派工，可獨立跨模組診斷才用 native explorer，spec與cwd/log證據明確。

不可在正式 API 送測試資料；環境按 /local-stack，瀏覽器按 /browser-tools，runtime重現與自動測仍須實際授權。根因明確後宣告轉 /quick、/solo 或 /feature，未知選型 /mega；既有雷放 ledger，不猜修/擴scope。修復附根因與原最小重現的適用驗證，缺依賴明示未驗。
