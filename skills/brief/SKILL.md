---
name: brief
description: 大腦拆任務派工前，用這個模板寫每份自足 brief。工人只憑 brief 獨立作業，code-reviewer 的 Spec 軸也以它為對照物。
---

# Brief 模板

每份 brief 固定八個欄位，照順序填。工人只憑這份文件獨立完成，不中途回來問；寫完自檢：「一個沒看過這個專案的人，只讀這份 brief 能不能動工？」

```markdown
## 目標

<一句話說清楚做什麼、為什麼>

## 範圍

<明確列出可以動的檔案；範圍外的檔案一律不碰>

## 工作環境

<工作目錄 = worktree 絕對路徑（大腦先依 /feature-flow 開好）、分支 = `wt/<feature>/<task-slug>`。
所有指令在該路徑下執行；commit 全留在該分支；不 merge、不 push、不切分支、不動 worktree 之外的目錄>

## Seam（測試邊界）

<在哪個公開介面上驗證行為 — 函式簽名 / API endpoint / CLI 指令。
測試只寫在這裡議定的 seam 上，不測內部實作細節。
至少一條測試走「真實組裝路徑」（App 根 widget / 真組態 / 真儲存的整合流程），
不能全部單元隔離；seam 的注入點不得在測試裡釘成常數，把待測的重讀/轉移邏輯遮掉>

## 驗收標準（可執行）

<盡量寫成「跑這個指令要看到什麼結果」：

- `go test ./internal/foo/...` 全綠，含新增的 <行為> 測試
- `npx vue-tsc --noEmit` 無錯誤
  寫不成可執行的（如文案、樣式），寫成可肉眼查核的具體描述>

## 紀律

<引用適用的 skill：

- 功能 / 修 bug 帶測試 → 測試紀律遵循 /tdd（red-green、只測 seam、垂直切片）
- bug 類任務 → 流程遵循 /diagnosing-bugs（先重現再動手，修完留回歸測試）
- 模組介面設計 → 參考 /codebase-design（deep module）
- Vue 專案任務 → 紀律遵循 /vue-dev（script setup + TS、只用 Pinia、走既有 axios 封裝、跟隨專案 CLAUDE.md），驗收標準必含 `vue-tsc --noEmit`（或內含它的 build）實際輸出
  以下常備紀律**依改動面選抄**（2026-08-11 起；後端-only brief 不抄前端條款，抄了是噪音）：
- 【每份 brief 都抄】範圍外既有問題一律不處理：任務途中發現的既有 bug、壞味道、lint 錯誤、過期依賴…只要不在本 brief 範圍內，一律不修、不順手重構，記下來放進回報的「順路發現」清單即可。唯一例外：該問題直接擋住驗收標準達成——此時停下用 SendMessage 回報，等指示，不得自行擴大範圍。（2026-08-05 起，防「做一做撈既有問題出來處理」的 scope creep）
- 【改動面含前端／任務含 UI 使用者操作才抄】非同步失敗路徑一律要處理：任何 await 使用者操作（存檔/登入/刪除）失敗時，UI 必須解除 loading 並浮出錯誤，不得 fire-and-forget、不得讓例外流成 uncaught async error；每條破壞性/寫入操作至少配一條失敗路徑測試。
- 【任務用狀態框架（Pinia / Riverpod 等）才抄】狀態快取生命週期要交代：寫明快取何時失效（watch vs read、invalidate 時機）；換帳號、登出、跨頁回訪、跨日不得看到過期資料。>

## 禁止事項

<此任務明確不做的事：不碰的檔案、不升級依賴、不順手重構、不 push …>

## 回報格式

done 時必附，缺一視同未完成：

1. commit hash + `git diff --stat`
2. 測試 / typecheck **實際執行輸出**（不是「已通過」三個字）
3. 驗收標準逐條對照：達成 / 未達成 / 部分達成＋原因
4. **規則張力與偏離清單**：brief 規定與實際需求衝突、或你偏離 brief 字面的每一處，寫明張力是什麼、你怎麼解、為什麼（**無則明寫「無」**）。發現張力當下就該 SendMessage 回報，不准自行解掉再事後補記。
5. **順路發現清單**：範圍外既有問題逐條列出，只列不修（**無則明寫「無」**）。
6. 完成時**必須用 SendMessage 主動送出完整報告**，idle 通知不算回報；送出後未獲回應就重送並標明重送。
```

## 給大腦

拆任務、寫 brief、派工前，先過 [BRAIN-CHECKLIST.md](BRAIN-CHECKLIST.md)（含 FAKE-GUARDS 與 VERIFICATION-TRAPS 兩本型錄的指引）。工人不需要讀它——模板以上就是工人的全部。
