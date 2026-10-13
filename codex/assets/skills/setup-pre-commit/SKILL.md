---
name: setup-pre-commit
description: 使用者要求 Husky／lint-staged 或 commit-time checks 時，整合既有格式化與檢查工具。
---

# Commit hooks 設定

只有明確要求setup hooks時才用；普通工程不自動安裝hook。讀AGENTS、packageManager欄位、lock、package scripts、現有Husky／其他hook與CI約定。多個lock／manager矛盾先說明，不default npm造成第二份lock。

沿用現有formatter配置與glob。需要Husky、lint-staged、Prettier但未安裝時列出缺依賴，按用戶setup請求及網絡權限安裝指定compatible devDependencies，不能用會靜默download的裸npx。初始化命令先查當前版本文檔／本機help；保留現有prepare與hook內容，不能整段覆蓋。

precommit先staged格式化，後專案已有typecheck／test script；依已要求檢查範圍選擇，缺script如實省略，不編空的pass。formatter只碰支持擴展與stage範圍。調用本機binary／專案script，不能package-manager混用或從hook遞歸git commit。

先審閱hook將執行的script，避免隱藏deletion／deploy／DB操作。格式化可能觸碰已staged文件，檢查index/worktree差異，保留用戶部分stage。Husky平台支持依版本，Windows未實測標未驗，不硬加Unix shebang命令假稱跨平台。

回報hook內容、相關配置、已安裝／未安裝依賴、實際執行證據與未驗專案。不為煙霧驗證自動commit／push，也不篡改live global hooks或Codex trust settings。
