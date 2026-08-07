---
name: review-chain
description: Review chain 積木：reviewer 觸發表、review 對照物、打回重跑與收工規則。/feature 與 /solo 在 /verify 通過後呼叫。
---

# /review-chain — 審查鏈

## 觸發表

| Reviewer | 觸發 | 模型 |
|----------|------|------|
| code-reviewer | 每次都跑 | `sonnet`（金流 / 架構大改用 `opus`） |
| ui-reviewer | 改動面含前端——拿 brief（或任務描述）的實測步驟用 Chrome DevTools MCP 重走一遍 | `sonnet` |
| security-reviewer | 金流 / 付款 / 認證授權 / secrets | `opus` |
| db-reviewer | DB schema / migration | `opus` |

## Review 對照物（Spec 軸拿什麼審）

- /feature、/bug 大修：該工人的 **brief**。
- /solo：大腦的**任務描述**（宣告文擴寫成 2-4 句：要做什麼、為什麼、預期行為邊界）。
- 沒給對照物，reviewer 會明講「Spec 軸跳過」——那是大腦漏給，不是 reviewer 的錯。

## 派工紀律

- reviewer 的 prompt 必帶回報條款（/brief 的 BRAIN-CHECKLIST）：SendMessage 主動送報告、沒發現問題也要回「審了哪些重點項」。
- reviewer 只讀不改；發現的既有問題照「既有問題不處理」判準，列一行即可。

## 打回與收工

- 任一 reviewer 打回 → 退回修復（重派或直改，依 lane）→ 修完**重跑整條觸發鏈**，不只重跑打回的那個。
- 全數通過 → 該工人 **TaskStop** 收掉（派工 lane）；記退件依全域迴饋迴路。
