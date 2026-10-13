---
name: brief
description: 在派 native subagents 前寫自足任務 brief、查核證據與明確 ownership。
---

# brief

派工前主代理讀 [BRAIN-CHECKLIST.md](BRAIN-CHECKLIST.md)；工人只需要自足 brief，不要求載入大腦全部規則。

八欄：需求來源、範圍/ownership（第一行改動面）、工作環境（絕對 worktree、branch/base、可用工具與 logs）、seam/產品決策、驗收標準、紀律、禁止事項/已知雷、回報格式。前端驗收附操作步驟與預期畫面；環境 facts 派工當下親驗。共享元件及全部消費者屬同一 ownership，含間接、同族與測試消費者。

具體指明可寫檔案、不是唯一工作者、不得 revert 他人 edits。附已驗 file:line、範圍與樣本來源；外部輸入明示不受信及型別/路徑/大小驗證。刪除或重置任務列清除後不變式及可能重新寫回的機制。前提與程式互斥時工人停下回報，不能自行選邊。

讀取型 explorer 只給一個可回答的問題；reviewer 附固定 diff/spec、限制與相關 ledger 裁示。每種角色完成時必交最終回覆，沒問題也說審了什麼，不能把 idle 當回報。使用本回合 native follow-up/message API，不機械套 Claude 通訊工具。
