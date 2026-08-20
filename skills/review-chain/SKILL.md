---
name: review-chain
description: Review chain 積木：reviewer 觸發表、review 對照物、打回重跑與收工規則。/feature 與 /solo 在 /verify 通過後呼叫。
---

# /review-chain — 審查鏈

## 觸發表

本表是 reviewer 觸發的**唯一 source**；模型選配唯一依據全域「角色 × 模型矩陣」，不在此重抄。

| Reviewer          | 觸發                             |
| ----------------- | -------------------------------- |
| code-reviewer     | 每次都跑                         |
| security-reviewer | 金流 / 付款 / 認證授權 / secrets |
| db-reviewer       | DB schema / migration            |

（ui-reviewer 已移出觸發表（2026-08-20 起），僅 Mike 點名時 on-demand 派；UI 行為驗證由下方「Mike 手測並行站」取代。）

## Mike 手測並行站（改動面含前端）

- 派 reviewer 的**同一時刻**起 /local-stack，並先驗前端 API 位址指向地端——指向判準與 env 分層查法**唯一依據 /vue-dev「瀏覽器實測」0-1 步**，不在此重抄。
- 驗完通知 Mike：測試入口＋本次改動的重點路徑清單（brief 實測步驟彙整）。
- **等 Mike 手測的空檔**：大腦照同一份清單把 /auto-e2e 回放腳本寫好存進 feature worktree——**差異重測先回放，回放紅或新增流程才找 Mike**；Mike 的手只花在第一輪清單外探測。
- Mike 手測結果與 reviewer 結果**會合**，兩者皆過才收工；Mike 不在 → 手測站等人，不阻塞其他需求開工。

## Review 對照物（Spec 軸拿什麼審）

- /feature、/bug 大修：該工人的 **brief**。
- /solo：大腦的**任務描述**（宣告文擴寫成 2-4 句：要做什麼、為什麼、預期行為邊界）。
- 沒給對照物，reviewer 會明講「Spec 軸跳過」——那是大腦漏給，不是 reviewer 的錯。

## 派工紀律

- 觸發表命中的 reviewer **一律同一則訊息一波派完**（多個 Agent 呼叫放同一 block），不逐個等回報；打回修復後重跑全鏈同樣一波派。唯一例外：動用 Chrome MCP 的 agent（僅剩 /bug 診斷與點名 ui-reviewer）同時僅 1；/auto-e2e 已是 Playwright 腳本，不受此限。
- reviewer 的 prompt 必帶回報條款（/brief 的 BRAIN-CHECKLIST）：SendMessage 主動送報告、沒發現問題也要回「審了哪些重點項」。
- reviewer 只讀不改；發現的既有問題照「既有問題不處理」判準，列一行即可。
- **runtime 行為斷言只能標 PLAUSIBLE**：reviewer 說「這個錯不會影響流程」這類 runtime 行為判斷，推得再細都不得作為放行理由——要 runtime 證據（實跑重現）才算定案（2026-08-06 GA spinner 案教訓）。

## 打回與收工

- 任一 reviewer 打回 → 退回修復（重派或直改，依 lane）。修復輪指令紀律：帶測試的 major 一律要求附雙向變異輸出（移除修復→紅）；reviewer 的 MINOR 備註若指向輸入空間缺口或 30 秒可查證的邊界值，當場升級成明確要求，不放行帶病合併。
- **重跑範圍按嚴重度分層（2026-08-20 起）**：修的含 **MAJOR/BLOCKER** → 修完重跑**整條觸發鏈**（修復輪是新錯高發區，退件 log 實證：重構蒸發防護、修復再收 5 MAJOR）；修的**只有 MINOR** → 只重跑打回的那隻確認修復。
- **Mike 手測的差異重測**：修復含 MAJOR/BLOCKER 且碰前端檔 → 給 Mike「只需重測這幾條路徑」的差異清單＋該 fix 的 `git diff --stat`（檔名讓 Mike 可自行覆核大腦的判斷）；只修 MINOR 或純後端修復 → 不回頭找 Mike，沿用原手測結果。
- 全數通過（含手測站）→ 該工人 **TaskStop** 收掉（派工 lane）；記退件依全域迴饋迴路。
