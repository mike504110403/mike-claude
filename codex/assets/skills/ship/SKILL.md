---
name: ship
description: 在 Mike 明確授權後推送已驗收本地成果，核實遠端 hash 與跨裝置狀態。
---

# ship

先盤點 repo 主幹/remote/branch、本地待推 commits、驗收/review、ledger與wip待裁示、未保存工作及原dirty檔。主幹按repo記錄，不硬設dev/main；裁示攢批一次處理，附建議與各選項後果。

未經Mike明確說推不可push；主幹推送前明確問。「推了嗎」只查狀態，已有同一範圍推送授權則不重問。技術sandbox核准不等於人類同意。授權後普通push精確remote/branch，禁止force，再git ls-remote比本地commit hash；一致才宣稱已推。失敗保留logs，不換remote/branch沿用授權。

以全域五點/四狀態（各lane回報例外保留）說明commit、本地合併、push、套用設定。Git pull只更新來源；其他裝置依README安裝器預覽/匯入後才有相同Codex資產，hooks仍需trust。沒有實際部署證據不說已套用。
