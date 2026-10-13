---
name: solo
description: 處理單一意圖且路線明確的中型改動，主代理實作並審實際差異。
---

# solo

按 /feature-flow 在 worktree 固定範圍與驗收，主代理實作；命中高風險硬排除或需要獨立切片升 /feature。先 /verify 親驗，再 /review-chain 的 code-reviewer 對 Standards/Spec；無 native API 明示 fallback及限制。

驗收/review 通過才 commit，push 另 /ship；保留短段式回報，包含結論、變更、實際證據/限制及下一步。四項實際狀態依全域規則，不拿本地合併當推送。
