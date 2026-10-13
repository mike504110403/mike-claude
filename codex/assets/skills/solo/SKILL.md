---
name: solo
description: 處理單一意圖且路線明確的中型改動，主代理實作並做差異審查。
---

# solo

在 worktree 鎖定範圍與驗收，主代理實作。遇高風險條件或可獨立工作需派工時升 /feature。verify 親驗後以 review-chain 的 code reviewer 對照 diff 與 spec；native reviewer 不可用時明示限制並做獨立第二遍審查。完成才 commit。
