---
name: resolving-merge-conflicts
description: 處理進行中的 Git merge/rebase conflict；保留雙方意圖並記錄無法自動裁定之處。
---

# 衝突處理

先查 status、merge/rebase 狀態、歷史、base/ours/theirs 與未合併檔案。讀 commit、已提供 issue/spec 和 AGENTS，理解兩方動機；不只依表面 conflict marker 選整側。

逐 hunk 保留相容意圖。無法同時滿足者列出證據與建議，阻塞關鍵路徑才問使用者；不能 invent 新行為。保留他人未提交修改，不自動 stash、abort、reset 或 checkout 整側。二進位、刪改衝突另辨明需求。

依使用者授權及專案規則做適當檢查，確認無殘留 marker、未合併 entries 或引用破壞；不得把靜讀當 runtime 通過。未驗項如實記錄。逐檔 stage，merge commit／rebase continue 只在此任務涵蓋完成 Git 操作時執行；既有 session 授權不足就保留可審查結果，不擅自 publish/push。

回報每個衝突決定、兩方意圖如何保留、檢查證據、目前 Git 狀態和剩餘步驟。
