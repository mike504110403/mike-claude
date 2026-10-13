---
name: sync-dev
description: 同步專案已記錄的主幹到遠端最新；工程開工前或使用者要求拉最新時使用。
---

# 主幹同步

從參數或目前專案找 repo，讀 AGENTS.md／專案宣告以確定主幹名稱與 remote。主幹可能是 main、dev 或其他名稱；不得把技能名稱當分支事實。先查 `git -C <repo> status --porcelain`、目前分支、upstream、`git worktree list --porcelain` 與主幹 hash。

- dirty、已有 merge/rebase，或主幹／remote 未確定：回報具體狀態並停止；不 stash、不 reset、不猜分支。
- 主 checkout 應留在專案指定主幹。若主幹已由另一 worktree checkout，對該 worktree 操作；不得在 feature worktree 硬切主幹。找不到合適 checkout 時回報限制。
- 執行 `git -C <主幹checkout> fetch <remote> --prune`。網路或 sandbox 不可用就回報，不能把舊 remote ref 稱為最新。
- 先比較 `git rev-list --left-right --count <主幹>...<remote>/<主幹>`。local ahead 或分歧就停止，列出雙方 commit；讓使用者裁示，不自行 merge/rebase。
- 確認 remote 主幹存在後，在乾淨的主幹 checkout 執行 `git merge --ff-only <remote>/<主幹>`。本機缺主幹時先確定指定 checkout／分支建立策略，不自動切走使用者的分支。
- 回報前後 hash、拉進 commit 數與摘要；無變動說明已同步。若有 graft 圖且 code 改變，依 graft skill 核實版本後更新圖；圖重建失敗不否定 Git 同步，但標明圖已過期。

不 push；後續改動依 feature-flow 放隔離 worktree。
