---
name: browser-tools
description: 瀏覽器自動化工具選擇的唯一 source（playwright-cli／Playwright MCP／chrome-devtools MCP／cmux 內嵌瀏覽器 tab）。ui-reviewer、/auto-e2e、/bug、/verify、/local-stack、/crawl4ai 涉及瀏覽器時引用；大腦要開瀏覽器給 Mike 看、或選自動化工具時載入。
---

# /browser-tools — 瀏覽器工具鏈（2026-08-27 起；2026-09-18 自 CLAUDE.md 遷入）

三件自動化工具：**playwright-cli**（shell 指令、低 token、具名 session 可並行）、**Playwright MCP**（accessibility snapshot，探索用）、**chrome-devtools MCP**（僅剩效能診斷：performance trace／lighthouse／heap snapshot，同時 1 個 agent）；另一件**展示窗口**：**cmux 內嵌瀏覽器**（給 Mike 看與手測，不是 agent 驅動工具）。

## 選擇規則

- **預設 playwright-cli**：流程已知、要寫成可重跑的 test、CI 會執行、單純跑一次表單／頁面驗證。
- **改用 Playwright MCP**：不確定頁面結構、要來回試探元素、需要完整 accessibility tree 做 self-healing 或跨步驟 diff。探索完把步驟收斂回 playwright-cli script 或 Playwright Test，探索 session 不長期跑。
- 判斷不出 → 先 `playwright-cli snapshot` 看一次結構，真的需要即時推理再切 MCP。
- **截圖一律存檔、不進大腦 context**（唯一依據全域「Context 預算紀律」截圖列）：存檔後交 subagent 判讀。
- **大腦不呼叫 `playwright-cli show --annotate`**——標註截圖會直接回傳呼叫者，繞過上一條。要 UI 回饋：**請 Mike 給截圖檔案路徑**。不改派 subagent 跑它（互動式，要 Mike 在瀏覽器上畫框，subagent 背景跑 Mike 不會知道）。
- 測試帳號／登入 session：一律用獨立測試帳號的 storage state（`state-save`／`state-load`），不用 persistent profile 殘留登入態。
- 多 agent 並行各用具名 session（`playwright-cli -s=<agent名>`），不共用預設 session。

## cmux 內嵌瀏覽器（2026-08-31 起）

定位＝Mike 手測入口；/local-stack 起棧就緒後、/auto-e2e 開跑前，自動把地端前端 URL 開進 cmux，不叫 Mike 自己開瀏覽器。**每頁都是加 tab，永不開新 pane、永不搬動 pane**：

- 一律 `"$CMUX_BUNDLED_CLI_PATH" new-surface --type browser --pane <ref> --url <url> --focus false`。
- `<ref>` 選法：已有瀏覽器 tab → 加進它所在 pane；沒有 → 加進右欄最上的既有 pane（`list-panes --json` 的 `pixel_frame` 判定，非主 pane）。
- **禁用 `browser open`**（會開 split pane）；開完 `focus-pane --pane <主pane>` 拉回焦點；任務收尾 `close-surface --surface <ref>` 清掉自己開的 tab（pane 紀律唯一依據 /feature「派工紀律」）。
- 非 cmux 環境（無 `$CMUX_BUNDLED_CLI_PATH`）跳過、退回回報 URL。
