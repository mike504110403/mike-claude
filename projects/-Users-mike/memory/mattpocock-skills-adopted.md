---
name: mattpocock-skills-adopted
description: 2026-07-23 從 mattpocock/skills 安裝三個 skills 並借鏡兩處改造；來源 repo 與後續更新方式
metadata: 
  node_type: memory
  type: reference
  originSessionId: 8a2dab7b-2efc-490f-b2b4-c03d45fc39d5
  modified: 2026-08-07T07:16:45.126Z
---

2026-07-23 從 https://github.com/mattpocock/skills 採用：

- 直接安裝到 `~/.claude/skills/`（只拷 .md，不拷 Codex 用的 agents/openai.yaml）：`writing-great-skills`、`codebase-design`、`code-review`（Matt 的雙軸審查版）；同日稍晚追加 `tdd`（含 tests.md、mocking.md）、`diagnosing-bugs`（含 hitl-loop.template.sh）——由自建的 `/brief` skill（brief 七欄模板）在「紀律」欄引用；再追加 `setup-pre-commit`（Husky/lint-staged，**只適用 npm 系專案**，Go 專案首次使用時要另寫 plain git hook 變體，尚未在任何專案試跑）。2026-07-24 追加 `improve-codebase-architecture`（架構大掃除，user-invoked）及其依賴 `grilling`、`domain-modeling`，同日再加 `grill-with-docs`（grilling+domain-modeling 的包裝指令，user-invoked）（皆只拷 .md）。Mike 定調：domain 專有名詞屬於專案，`CONTEXT.md` 跟著各專案根目錄走。
- 借鏡改造：`/office-hours` 併入 grilling 三原則（一次一題、附建議答案、事實自查）；`code-reviewer` agent 加入 Spec 軸 + Fowler 12 條 smell 基線。
- 未採用整包：他的體系以單 agent + issue tracker 為中心，與大腦-工人架構衝突（如他的 implement 由 agent 自己寫 code）。
- 2026-08-07（lane 化改版同日）再追加：`research`（/mega 探路段的研究零件，發現落檔 repo）、`prototype`（含 LOGIC.md、UI.md，一次性原型解設計決策）、`resolving-merge-conflicts`（/feature-flow 階段三衝突時引用）（皆只拷 .md）。issue-tracker 系（ask-matt、triage、to-spec、to-tickets、implement、wayfinder、wizard）依舊不採，與大腦-工人架構衝突。
- 日後更新：重新 clone repo 對照 diff 手動同步，或改用他的 Claude Code plugin（`/plugin marketplace add mattpocock/skills`）——但 plugin 是唯讀整包，會與現有挑零件策略衝突。
