# Skills 目錄說明

## 第三方來源（mattpocock/skills）

以下 skills 取自 https://github.com/mattpocock/skills （挑零件安裝，只拷 `.md`，不拷 Codex 用的 `agents/openai.yaml`）：

- 2026-07-23：`writing-great-skills`（現 repo 內叫 writing-for-agents 系）、`codebase-design`、`code-review`（雙軸版）、`tdd`、`diagnosing-bugs`、`setup-pre-commit`（僅 npm 系專案）
- 2026-07-24：`improve-codebase-architecture`、`grilling`、`domain-modeling`、`grill-with-docs`
- 2026-08-07：`research`、`prototype`、`resolving-merge-conflicts`

**不採用整包／plugin**：他的體系以單 agent + issue tracker 為中心（ask-matt、triage、to-spec、to-tickets、implement、wayfinder、wizard），與大腦-工人架構衝突；plugin 是唯讀整包，與挑零件策略衝突。

**更新方式**：重新 clone repo 對照 diff 手動同步。

## 借鏡改造記錄

- `/office-hours` 併入 grilling 三原則（一次一題、附建議答案、事實自查）。
- `code-reviewer` agent 加入 Spec 軸 + Fowler 12 條 smell 基線。
- 「大工程先探路」（現 /mega lane）借鏡 wayfinder 概念；回報風格借鏡 i-have-adhd。
