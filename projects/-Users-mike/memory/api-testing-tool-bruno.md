---
name: api-testing-tool-bruno
description: API 測試工具定案用 Bruno（local-first 純檔案），不用 MCP、不用雲端 API（2026-07-21）
metadata: 
  node_type: memory
  type: project
  originSessionId: d6f702f1-51ec-48bf-9410-e1fe8df2543f
  modified: 2026-07-21T08:34:46.296Z
---

Mike 2026-07-21 定案 API 測試工具流程：用 **Bruno**（開源、local-first，collection 為純文字 `.bru` 檔）。演進過程：先評估 Postman MCP（否決）→ 改 Apidog + Open API（否決）→ 最終選 Bruno。共同前提：**不接 MCP、collection/spec 不進版控**。

**Why:** Bruno 的純檔案模式最符合 AI 工作流——大腦直接讀寫 `.bru` 檔即完成同步，不需要 API token、雲端帳號或 MCP；資料也完全不出本機。

**How to apply:**
- 同步流程：掃 code 找 API 改動 → 直接更新對應 `.bru` 檔 → 回報 endpoint 異動摘要。
- Collection 資料夾放 repo 內 `bruno/`，進版控（2026-07-21 Mike 的主管同意；原「不進版控」前提已作廢）。
- 更新前先讀既有 `.bru`，保守合併，不可蓋掉 Mike 手動維護的測試內容（斷言、範例資料）。
- 已落地為全域 skill `~/.claude/skills/bruno-sync/`（2026-07-21）：初次匯入 + 增量同步兩模式，規則集（全中文命名、folder 繼承 auth、登入 token 自動存、範例完整性自查、local/online 環境）都固化在 SKILL.md；收尾自動觸發規則寫在全域 CLAUDE.md。
- 待辦：Mike 安裝 Bruno app、指定第一個匯入的專案。
- 不要再主動推薦 Postman / Apidog / 任何 MCP 方案（相關：[[gitkraken-mcp-not-needed]]）。
