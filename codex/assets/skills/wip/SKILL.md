---
name: wip
description: 收斂未完工程或核實 repo .codex/wip.md 後續作，先避免與其他執行者撞車。
---

# wip

## 收斂

使用當回合 native API 收回本需求正在編輯的 agents，核對實際 cwd/branch或detached HEAD/commit/status/diff及logs。私人 .codex/wip.md、ledger/rejection-log 先按全域 ignore方法保護；記目標/邊界、worker ownership、開工base、實際落地、已驗命令/輸出、未驗與驗證債、ADR、待裁示（建議+後果）、下一步與回復位置。收斂不 merge/push/delete。

## 續作

先核實現有agent/可見chat與worktree進度，工具不保證能列出其他session時明示盲區並查磁碟時間線；實況超前交接或疑似仍有人寫時，只讀盤點，確認ownership後再接手。「幫我看」優先視為查狀態。對帳 wip 各branch/HEAD/base與磁碟，現況為準；引用已有授權共識，不重問同題。按下一步接流程，不能把續作自動擴成 merge/push/delete。

完成清理前將未結裁示/accepted risks 保存ADR，僅處理本需求自己建立且已保存的產物；未竟工作保留分支/worktree。無未竟事項不堆新交接檔，只提示新chat。不廣泛刪memory/共享索引/別人的檔。
