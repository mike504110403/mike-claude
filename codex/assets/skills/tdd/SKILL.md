---
name: tdd
description: 使用者要求 test-first／red-green-refactor 或整合測試時，按已確認 seam 做逐片行為驗證。
---

# TDD

測試從用戶可觀察的行為與獨立expected值出發。先讀CONTEXT、ADR、已有runner與tests，確定public interface／seam與範圍。會影響架構或測試成本的未決seam才問用戶；已有明確spec／授權seam不重復索取確認。

一片一個行為：寫會因該行為缺失而紅的test，記錄red，再寫最小implementation使其green，再在green狀態下按需求refactor。不要先bulk寫所有imagined tests，避免為未來用例堆功能。fail若來自環境／fixture就先解決，不把任意失敗當有效red。

不要測試private methods、用DB side channel代替interface、mock內部結構，或在assert重算同一算法得到預期。expected來自spec、worked example或已知literal；測試應能因行為錯誤失敗，並在內部重構後保持有效。mock只在external／不可控依賴seam，時間、random和IO盡量確定化。

使用專案本機runner、lock和腳本，缺工具明示不下載替代。遇到repo禁止新增test文件等裁示，依更具體用戶授權處理；不能把本技能自動觸發為新增tests授權。回報seam、red/green實際輸出、測到行為與未驗限制。
