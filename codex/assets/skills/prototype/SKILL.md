---
name: prototype
description: 用可丟棄邏輯或 UI prototype 回答明確設計問題；不自動轉成正式功能。
---

# Prototype

先說明要回答的問題與成功判準：state／邏輯選 [references/logic.md](references/logic.md)，視覺／layout選 [references/ui.md](references/ui.md)。資訊足夠就採取合理假設，只有分支會影響產物且無法推斷才問。

prototype預設記憶體state與合成資料，明顯標注實驗。專案內修改依工程lane/worktree；chat artifact依指定輸出位置。不打真實付款／通知或正式API，想連後端先用local-stack。依賴優先專案已有工具，不為prototype引入新架構。

簡單可啓動／分享，暴露有關state，優先讓使用者操作edge cases。prototype本身不自動加tests或production hardening；驗證結論的方式按需求。App可開文件／地端URL時展示，否則給絕對路徑與命令。

回報答案、假設／限制與產物路徑。只有使用者要求落地時才轉正式實現；保存prototype／issue記錄按既有授權，不擅自commit、發佈或消息他人。
