---
name: mattpocock-skills-adopted
description: 2026-07-23 從 mattpocock/skills 安裝三個 skills 並借鏡兩處改造；來源 repo 與後續更新方式
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8a2dab7b-2efc-490f-b2b4-c03d45fc39d5
  modified: 2026-07-23T10:14:26.381Z
---

2026-07-23 從 https://github.com/mattpocock/skills 採用：

- 直接安裝到 `~/.claude/skills/`（只拷 .md，不拷 Codex 用的 agents/openai.yaml）：`writing-great-skills`、`codebase-design`、`code-review`（Matt 的雙軸審查版）；同日稍晚追加 `tdd`（含 tests.md、mocking.md）、`diagnosing-bugs`（含 hitl-loop.template.sh）——由自建的 `/brief` skill（brief 七欄模板）在「紀律」欄引用；再追加 `setup-pre-commit`（Husky/lint-staged，**只適用 npm 系專案**，Go 專案首次使用時要另寫 plain git hook 變體，尚未在任何專案試跑）。
- 借鏡改造：`/office-hours` 併入 grilling 三原則（一次一題、附建議答案、事實自查）；`code-reviewer` agent 加入 Spec 軸 + Fowler 12 條 smell 基線。
- 未採用整包：他的體系以單 agent + issue tracker 為中心，與大腦-工人架構衝突（如他的 implement 由 agent 自己寫 code）。
- 日後更新：重新 clone repo 對照 diff 手動同步，或改用他的 Claude Code plugin（`/plugin marketplace add mattpocock/skills`）——但 plugin 是唯讀整包，會與現有挑零件策略衝突。
