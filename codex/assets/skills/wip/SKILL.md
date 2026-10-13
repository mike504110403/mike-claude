---
name: wip
description: 收斂未完工程或依 repo .codex/wip.md 續作。
---

# wip

收回正在編輯的 agents、確認狀態再盤點實際 git diff/已驗證據。私人交接不進 Git；寫入前用 git check-ignore 確認 .codex/wip.md/.codex/ledger.md 被忽略，缺少時在 git rev-parse --git-path info/exclude 回傳的檔案加精確條目（支援 worktree 的 .git 檔）。未竟工作寫 repo .codex/wip.md：目標/範圍、worktree/branch/base、落地狀態、已驗命令、未驗與驗證債、待 Mike 裁示（建議+後果）、下一步/回復方式。只記續作必需資訊，不寫 secrets。續作先重新核實檔案與 git 狀態；不要把檔案當當前有效授權。全數完成無需新增交接檔，只提示新 chat。
