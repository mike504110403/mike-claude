---
name: auto-e2e
description: on-demand 瀏覽器自動化實測：Mike 說「自動測」「幫我測」、或 /bug 診斷需要 runtime 重現證據時使用。2026-08-20 起不再是前端驗證的必經閘門（前端驗證改為 review chain 期間 Mike 地端手測）。
---

# auto-e2e — Chrome MCP 代測

**on-demand 證據產生器**（2026-08-20 起不在任何驗證站的必經清單）：大腦親自用 Chrome DevTools MCP 把關鍵流程走一遍，留下可抽查的證據。用於 Mike 點名代測、/bug 的 runtime 重現（runtime 行為斷言只有 runtime 證據能定案）。瀏覽器 agent 同時僅 1。

## 步驟

### 1. 環境就緒

- 地端棧未起 → 先走 /local-stack 起（後端＋infra＋前端 dev server，dev server 一律帶該專案 `.claude/localstack.json` 宣告的 API 位址覆蓋參數）。
- **開測門檻**：在 network 面板確認第一個 API 請求打向地端位址才開始測。多個專案 `.env` 預設指正式線上，這一步是唯一防線。
- 測試帳號取自該專案 `.claude/localstack.json`。

完成判準：瀏覽器已登入地端環境，network 面板顯示請求指向地端。

### 2. 測試計畫

從 brief 的實測步驟（或 Mike 交代的流程）列出**流程清單**，每條含：操作路徑、預期畫面結果、預期 API（endpoint ＋關鍵 payload 欄位）。沒有 brief 也沒有交代時，依本次改動面自行列出清單並在回報開頭附上，讓 Mike 事後能對照「測了什麼」。

完成判準：清單成形，每條都有預期結果可比對。

### 3. 逐條走流程

每條流程：

1. MCP 操作（snapshot → click / fill → wait_for）走完操作路徑。
2. 畫面驗證：實際結果對預期，截圖存 scratchpad。
3. API 驗證：network 面板核對 endpoint、payload、回應（API 合約有 bruno/ 時以 bruno collection 為對照）。
4. console 檢查：無新增錯誤。

fail 不中斷整輪——記錄現場（截圖＋console＋network dump）後繼續下一條，測完一次回報。

完成判準：清單上**每條**流程都有 pass / fail 與證據，沒有「大致正常」。

### 4. 回報與留痕

- 回報格式：每條流程一行（流程名、pass/fail、證據截圖路徑）；fail 條目附現場摘要與初判原因。
- 在 wip.md 或驗收記錄記一筆「聯測 = auto-e2e 代測」，Mike 回來可憑截圖抽查。
- fail 的處置（退工人重修或另開單）回到所屬 lane 的流程決定，本 skill 只產證據不修碼。
