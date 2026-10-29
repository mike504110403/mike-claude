---
name: review-chain
description: 驗收後對固定 diff/spec 做 Standards、Spec 與風險專門審查，管理修正及複審。
---

# review-chain

/mvp 專案不適用本技能：畢業總審以 /mvp 為準。

code-reviewer 每次必跑；金流/付款/認證授權/secrets 加 security-reviewer；DB schema/migration 加 db-reviewer。獨立 reviewer 可同波 native 派工，額度依 runtime；核對有效 read-only sandbox，父回合 override 可能蓋掉角色預設。工具不可用時明示主代理獨立第二遍審查與限制，不假稱 native reviewer 已跑。

每份 prompt 附：固定 base/head（未提交時明確 diff 狀態）、diff --stat、對照 spec（feature 用 brief、solo 用任務描述）、已跑證據、改動檔與直接呼叫端邊界。以 **Standards**（repo 規範）及 **Spec**（需求）兩軸回報；沒有 spec 不可悄悄跳過。沒 findings 也列審查範圍。

內聯 repo .codex/ledger.md 中相關已裁示不修/非雷條目與裁示前提；前提被本次 diff 改變時重新裁示。既有問題只列一行、不擴範圍。Reviewer 不跑 router/DB 共享整合測試、不下 SQL、不動共享測試庫；需 runtime 證據向主代理要，不自行搶跑。只有實跑重現及 logs 才能確認 runtime 斷言，否則標 PLAUSIBLE，不能作為放行依據。

前端依 /verify 與 Mike 手測並行；兩者皆過才整合。任何 reviewer 打回先彙整**全體修正清單**（項目、軸、owner、誰確認），每位複審都收到全表。含 MAJOR/BLOCKER 修復後重跑整條觸發鏈；只有 MINOR 只找原打回 reviewer。前端 MAJOR/BLOCKER 修正給 Mike 受影響路徑及 diffstat 重測；純後端/MINOR 不重跑無關手測。

使用本回合 native follow-up 續聊原 reviewer，原 agent 不可續用才新建。按實際修正重驗受影響 checks，不用 idle 通知代替最終報告。退件記 repo .codex/rejection-log.md（忽略方法見全域 AGENTS），記任務/原因/家族/修正；同族反覆才調整規則源頭，不廣泛刪歷史或 memory。
