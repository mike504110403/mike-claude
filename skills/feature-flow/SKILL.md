---
name: feature-flow
description: agent 工程派工的分支與 worktree 生命週期：最新 dev 切 feature → 每個工人一個 worktree（wt/ 分支）→ 合併回 feature 即清 worktree → 合併回 dev 即清 feature。所有同 repo 的工程派工都走這個流程。
---

# /feature-flow — 派工分支 / worktree 生命週期

同 repo 的 agent 工程一律走這四個階段。派 Agent 時**不再帶 `isolation: "worktree"`**——worktree 由本 skill 手動開、手動收，生命週期才可控。

## 階段一：開 feature（工程開始）

1. 先跑 /sync-dev 把 dev 拉到最新。
2. `git checkout -b feature/<名稱> dev`。
3. feature 分支不推 remote（全域規則）。

## 階段二：每個工人開一個 worktree（派工前）

不論單工人或多工人，一律每個工人一個 worktree：

```
git worktree add ../<repo名>-wt-<task-slug> -b wt/<feature名>/<task-slug> feature/<名稱>
```

- worktree 放在 repo 外側的 sibling 目錄，命名 `<repo名>-wt-<task-slug>`，不污染 repo。
- brief 的「工作環境」欄（/brief 八欄模板）必寫：worktree 絕對路徑、`wt/<feature名>/<task-slug>` 分支、commit 全留在此分支、不 merge / 不 push / 不切分支 / 不動 worktree 之外的目錄。

## 階段三：合併回 feature + 自動清理 worktree（單一工人驗收 + review chain 通過後即做，不等整波）

1. 在主 checkout：`git checkout feature/<名稱>` → `git merge wt/<feature名>/<task-slug>`。
   - 有衝突：依 /resolving-merge-conflicts 逐塊解；解不掉回報 Mike。
2. 合併成功後**立即清理**，三步一組不拆開：
   ```
   git worktree remove ../<repo名>-wt-<task-slug>
   git branch -d wt/<feature名>/<task-slug>
   git worktree prune
   ```
   - `worktree remove` 被未 commit 改動擋下 → 不用 `--force`，先查明那些改動是什麼再處置。
   - `branch -d` 被擋（未完全合併）→ 不用 `-D`，先查明差在哪些 commit。

## 階段四：合併回 dev + 自動清理 feature（整個 feature 完成、全部驗收 + review chain 通過後）

1. `git checkout dev` → `git merge --no-ff feature/<名稱>`。
2. 合併成功後**立即清理**：`git branch -d feature/<名稱>`。
3. 停下。push dev 依全域規則必先問 Mike。

## 異常路徑

- 工程做到一半要暫停 → 改走 /wip 收斂：**收斂時不做任何清理**，worktree 與分支原樣保留給續作。
- 工人的 wt 分支被驗收退回 → 重派工可沿用同一個 worktree；任務整個作廢才走階段三的清理三步（先確認分支內容確定不要）。

## 禁止事項

- 大腦所有 git 操作一律 `git -C <絕對路徑>` 顯式指明 checkout——多 worktree 併行時 `cd` 殘留狀態曾讓 reset/commit 打錯 checkout、連丟兩發 commit；破壞性指令（reset/merge/branch）前先確認該 checkout 的 HEAD 是預期分支。
- 不 push 任何分支。
- 清理只用 `-d` / `remove`，絕不 `-D` / `--force`（bash_guard hook 硬擋）。
- 不在 dev 或 feature 主 checkout 上直接改 code——改動一律發生在工人的 worktree。
