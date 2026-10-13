---
name: feature
description: 執行需獨立切片派工或專門審查的工程變更。
---

# feature

固定範圍、基底與驗收；feature-flow 建 worktree。主代理先判斷是否存在獨立切片，有才按 brief 派 native subagents；無則自己做。派工前確認有效角色/sandbox 與 runtime 額度，不指定假模型或固定並行數。不覆蓋其他人 edits。先親跑 verify，再 review-chain；報 BLOCKER 才中止依賴工作。修正後只重跑受影響證據。commit 後停在 ship 前。

收尾遵守全域 AGENTS.md「工程收尾」節的五點格式與四項實際狀態；該節是格式唯一 source，依實際執行與證據填寫。
