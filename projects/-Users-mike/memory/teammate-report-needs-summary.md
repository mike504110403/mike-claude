---
name: teammate-report-needs-summary
description: "工人用 SendMessage 回報時必須帶 summary，否則報 \"summary is required when message is a string\" 卡死不通知大腦"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 6c2d3071-2903-40e8-b6a8-056da82a0b7c
  modified: 2026-07-22T07:27:51.104Z
---

2026-07-10 實測：兩個 haiku 工人完成任務後回報大腦時踩到 `Error: summary is required when message is a string`，卡在原地 2h44m，大腦完全收不到 idle/完成通知。

**Why:** SendMessage 傳字串訊息時 `summary` 為必填；小模型工人不會自行重試補上。

**How to apply:** 派工 brief 統一加一句：「回報時用 SendMessage（to: "main"）並務必附上 summary 參數（5-10 字摘要）」。另外大腦不要乾等通知——工人產出落地後（檔案/commit 已可驗）就可主動驗收，用 TaskStop 收工人。

2026-07-22 追驗：brief 末尾明寫「最終回報用 SendMessage（to: "main"，字串訊息，務必帶 summary）」後，同 session 6 個 sonnet 工人/reviewer 全數穩定送達完整報告，零卡死。注意工人送完報告後仍會多發一則 idle_notification（殘留通知，可忽略）；未寫明這句的工人（如初期 haiku 研究工人）只發 idle 通知不送內容，需 SendMessage 去催。此寫法已定版進所有 brief 範式。
