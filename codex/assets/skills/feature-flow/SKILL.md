---
name: feature-flow
description: 管理工作流的 worktree、基底與本地提交，支援 Codex App 和 CLI。
---

# feature-flow

先讀 repo AGENTS/branch 記錄、git status 和已有 worktree。不要硬設 dev。App 優先 list_artifacts 並重用合適 managed worktree；create_worktree 明確指定已核實 ref，在返回目錄工作，避免 self handoff。CLI fallback 先確認基底與乾淨狀態，以 git worktree add 的具名 feature branch 建 checkout，不修改主 checkout。保留未提交改動。驗收、review 完成才提交；依 repo 政策整合，一個需求保持一顆整合 commit。清理先確認保存狀態；App archive_worktree 保存快照；CLI 只正常 remove 無未保存改動的精確路徑。不要 force remove。
