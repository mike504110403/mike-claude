---
name: diagnosing-bugs
description: 對根因未知的故障／變慢建立重現訊號、逐一驗證假設並捕捉修復證據。
---

# 診斷迴圈

與 bug lane 配合：先讀需求、相關CONTEXT／ADR。找到能判斷「使用者這個症狀」的回饋迴圈，而非只有程序未崩潰。優先用既有fixture/test／CLI／HTTP重播；browser依browser-tools與local-stack，新增測試或實跑依使用者授權，不把debug自動變成全套TDD。

先記錄實際命令／步驟、輸入、觀測與預期。不能建立可運行訊號時列出缺環境／artifact／權限與已嘗試項，把根因標未知；可靜讀形成假說，但不能稱證實或修好了。人工-only重現用明確的操作清單與結果欄，不假設有Claude HITL腳本。

最小化輸入與步驟，每次只減一項，保留仍觸發同症狀的條件。非確定錯誤記錄seed／次數／出錯率，不把一次沒失敗當修復。效能問題先量baseline／profile／query plan，再改code。

列幾個可證偽假設，寫「若X是因，改Y會使Z變化」。按證據排序並向使用者簡述；不把排序當裁決或等待已授權研究的額外許可。每次probe對一個預測、改一個變量，優先debugger／REPL，必要log帶唯一prefix並避免秘密。

證明根因後轉合適修復lane。既有或已要求的回歸test須跨實際觸發seam，不能用單caller測試冒充多caller問題。無合適seam記錄限制，不為當前bug擴大架構修復。對修復重走原流程／同一量測，清理臨時debug輸出與自己建立的暫存資產（依刪除授權）。

回報症狀、重現證據、驗證過／排除假設、根因、修復結果與未驗限制；順路發現登ledger另開任務。
