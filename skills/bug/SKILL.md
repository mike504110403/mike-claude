---
name: bug
description: 診斷 lane：壞了、錯了、變慢且根因未知。先重現定根因，再跳線 /quick 或 /feature 收尾；根因已知的修復直接走該二 lane。
---

# /bug — 診斷優先

## 入選標準

- 行為壞了 / 結果錯了 / 變慢了，且**根因未知**。
- 根因已知、只剩修 → 不進此 lane，直接判 /quick 或 /feature。

## 流程

1. **宣告**：第一句「走 /bug，因為…」。
2. **診斷段**：依 /diagnosing-bugs — 先重現、再縮小範圍、定位根因，重現成功才進入修改。
   - 驗證指令先用控制檔證明測得到（防假陰性）；影響面宣稱要先讀程式碼再說出口。
   - 互動式瀏覽器診斷（逐步看 network/console）用 **playwright-cli**（`goto`／`snapshot`／`console`／`requests`，具名 session）；頁面結構試探不出才切 Playwright MCP、效能類（trace／lighthouse／heap）才用 chrome-devtools MCP——選擇依全域「Browser 自動化工具鏈」。
3. **根因宣告**：向 Mike 講清楚根因＋證據，**同時宣告修法大小、改動面（後端／前端／前後端）與跳線去向**——診斷入口時改動面常未知，最遲此刻定案，收尾 lane 的驗證義務照全域矩陣。
4. **跳線收尾**：
   - 小修（符合 /quick 入選標準）→ 接 /quick 流程收尾（大腦直改＋自驗）。
   - 中修（符合 /solo 入選標準）→ 接 /solo 流程收尾（大腦直改＋code-reviewer）。
   - 大修 → 轉 /feature（brief 裡帶上診斷段的完整情報）。
5. 不論走哪條，驗收照所跳 lane 走 /verify；**修完必留回歸測試**（重現步驟固化成測試；Vue 專案固化成 /auto-e2e 的 Playwright spec，可回放）。

## 跳線

- 診斷到一半發現是設計層問題、要動架構 → 宣告升級 /mega。
- 診斷結果「不是 bug 是預期行為」→ 回報收工，不進修復。

## 回報格式

根因段：症狀 → 根因 → 證據（可重現步驟）。修復段：依所跳 lane 的回報格式（/quick 一段式或 /feature 五點）。
