---
name: quick
description: 低風險小改 lane：預估 ≤3 檔案、行為變更小、有測試網接住、範圍一眼見底。改欄位、調參數、改文案、已知修法的小 bug 屬之（硬排除清單見全域不變式）。
---

# /quick — 低風險小改

## 入選標準（全部成立才進）

- 預估改動 ≤3 個檔案
- 行為變更小（改欄位、改文案、調參數、小 bug 已知修法）
- 有既有測試 / typecheck 網接得住
- 範圍一眼見底，不需要探索

## 硬排除

依全域 CLAUDE.md 不變式的 /quick 硬排除清單，命中一律踢去 /feature。

## 流程

1. **宣告**：第一句「走 /quick，因為…」。
2. 大腦在 feature 分支上**直接改**（依 /sync-dev 拉最新 dev 後切 feature 分支；不開 worktree、不寫 brief、不派工）。
3. **親自跑證據**：相關測試 ＋ typecheck/build 至少各一項，附實際輸出。
4. Review chain **不跑**。
5. 改動涉及 API 且專案有 `bruno/` → 照跑 /bruno-sync。
6. Commit 後停下。

## 領域插件

- Go：`go test ./...`（相關套件）＋ `go build ./...` 輸出為證據。
- Vue：`vue-tsc --noEmit` ＋ Chrome DevTools MCP 開頁面實測受影響畫面（依 /vue-dev）。

## 跳線

- 改到第 4 個檔案、或出現未預期耦合 → **停手**、宣告「升級 /feature，因為…」、帶著已知情報走 /feature。
- 改的過程發現行為壞掉但根因不明 → 宣告轉 /bug。
- 升級跳線自主宣告即跳；本 lane 無降級問題。

## 回報格式（一段式）

一段話講完：改了什麼＋為什麼＋證據（測試/typecheck 實際輸出摘要）。不用五點回報。順路發現的範圍外問題列一行「要不要處理？」。
