---
name: sync-dev
description: 把要改動的專案的 dev 分支同步到 remote 最新（fetch + ff-only），是每次工程派工前的前置步驟。Mike 說「拉最新 dev」「同步 dev」或 /feature-flow 開工前使用。
---

# /sync-dev — 拉目標專案最新 dev

## 目標專案

args 有給路徑就用該路徑；沒給就用當前專案根目錄。多 repo 任務對每個要改動的 repo 各跑一次。

## 步驟

1. **確認乾淨**：`git -C <repo> status --porcelain` 有輸出 → **停下**，回報 Mike 有未 commit 改動，等指示。不自動 stash、不硬切分支。
2. **記下現況**：目前分支、`git rev-parse dev`（local dev 的 hash，若存在）。
3. **抓遠端**：`git -C <repo> fetch origin --prune`。
4. **切到 dev**：`git checkout dev`；local 沒有 dev → `git checkout -b dev origin/dev`。
   - **local 和 origin 都沒有 dev**（部分 repo 主幹不叫 dev，而是 main / prod / online 等）→ **停下問 Mike** 這個 repo 以哪條分支為主幹，不自行猜；得到答案後本次以該分支代入「dev」執行,並建議在該專案 CLAUDE.md 記下主幹分支。
5. **快轉更新**：`git merge --ff-only origin/dev`。
   - ff 不了（local dev 有 origin 沒有的 commit）→ **停下**，回報分歧狀況（雙方各多幾個 commit、`git log --oneline` 摘要），等 Mike 決定。不自行 merge / rebase / reset。
6. **回報**：更新前後 hash、拉進幾個 commit、`git log --oneline <舊hash>..dev` 摘要；沒有新 commit 就說「已是最新」。
7. **graft 圖同步**（2026-09-08 起，repo 有 `graft/.graph/wiring.json` 才做）：拉進新 commit 後圖已過期 → `graft build --lsp --no-gitignore --no-ignore .`（增量、秒級），貼 `✓ wiring` 那行；沒有新 commit 跳過。

## 禁止事項

- 絕不 push、絕不 `reset --hard`、絕不自動 stash、絕不動 dev 以外的分支。
