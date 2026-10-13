---
name: quick
description: 處理小而範圍可界定的低風險工程改動，主代理直接實作。
---

# quick

先鎖目標、改動面與適用驗收；金流/認證/secrets/migration/全域配置/不可逆操作不適用。按 /feature-flow 核實主幹與 worktree，不能在主 checkout 改碼。主代理實作後 /verify 對 diff 與證據自驗；必要風險審查升 /feature，scope 變大即宣告升級。

驗收通過才逐檔 commit，push 另 /ship。保留短段式回報：結論、實際改動與驗證/限制、後續；commit/本地合併/push/套用設定依全域真實狀態規則，不假稱同步。
