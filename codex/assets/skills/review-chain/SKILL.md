---
name: review-chain
description: 驗收後依 diff 與規格做程式、金流安全或資料庫審查。
---

# review-chain

固定基底與 diff；提供原始 spec/brief、改動範圍及已跑證據。code-reviewer 每次必跑；涉及金流、認證或 secrets 另 security-reviewer，涉及 schema/migration 另 db-reviewer；獨立審查可並行，額度以 runtime 為準。確認派出角色有效 sandbox 為 read-only；角色配置預設可能被父回合 override，不把 TOML 視為絕對隔離。找具體缺陷與 file:line，無證據不擴範圍。修復後重驗相關 checks 並重審相同對照物；無 native agents 時明示改用主代理獨立審查及限制。
