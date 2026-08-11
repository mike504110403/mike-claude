---
name: wip
description: 收斂現在進行中的工程（收回所有工人、盤點落地狀態、寫 .claude/wip.md），或從 wip.md 續作上次收斂的工程。Mike 說「收斂」「收工」「先停」「交接」或「繼續上次 / 接著做」時使用。
---

# /wip — 收斂與續作

一個 skill 兩個模式，先判斷再行動：

| 條件 | 模式 |
|------|------|
| args 是 `save`，或 TaskList 有 running / queued 工人 | 收斂模式 |
| args 是 `resume`，或無工人且專案根目錄有 `.claude/wip.md` | 續作模式 |
| 兩者都不成立 | 回報 Mike：沒有進行中的工程也沒有 wip.md，問要做什麼 |

## 收斂模式（收工人 → 盤點 → 落檔）

1. **盤點工人**：TaskList 列出所有 running / queued 工人。
2. **抓最後進度**：逐一 TaskOutput 看目前做到哪（不等它們完成）。
3. **收回工人**：逐一 TaskStop。全部收完才進下一步。
4. **盤點落地狀態**（每個工人的 worktree / 分支逐一查，不信工人回報）：
   - `git -C <worktree路徑> log --oneline -5`：有 commit 的記下 hash。
   - `git -C <worktree路徑> status --porcelain`：有未 commit 改動 → 在該 worktree 逐檔 `git add <明確路徑>` 後 `git commit -m "WIP: <說明>"` 落成 WIP commit（禁止 `git add .`）；改動意圖不明無法下 commit message 就原樣保留，在 wip.md 記「有未 commit 改動，原樣保留」。
5. **寫 `.claude/wip.md`**（專案根目錄，固定結構）：

   ```markdown
   # WIP — <工程名稱>
   更新：<絕對日期>

   ## 任務背景與目標
   <一段話，沒看過這個工程的 session 也能懂>

   ## 已完成
   <驗收 + review 通過、已合併的波次與分支，一項一行>

   ## 波次看板（/mega 多波 pipeline 進行中時必備，單波工程可省略）
   | 波次 | 階段 | feature 分支 | 依賴 | review 現況 |
   |------|------|-------------|------|------------|
   <階段取值：探路｜brief草稿｜實作中｜review｜待合併｜已合併。
   這張表是大腦的狀態外部化：pipeline 進行中，大腦寫任何註解／文件／裁示前先查表，
   不憑腦中狀態（多分支並存時「拿未合併分支狀態當現況」是已知複發錯誤族）。>

   ## 收斂時進行中的工人
   <每個工人一項：任務、分支、worktree 路徑、最後狀態（commit hash / WIP commit / 未動工）、brief 摘要或 brief 檔案路徑>

   ## 決策
   <已解：一項一行，附 ADR 路徑。未解：掛在「尚未明朗」，一項一行>

   ## 下一步
   <明確到新 session 讀完可以直接寫 brief 派工的程度>
   ```
6. **不做清理**：worktree、`wt/` 分支、feature 分支全部保留，留給續作。
7. **回報 Mike**：收了幾個工人、各自落地狀態、wip.md 路徑。

## 續作模式（讀檔 → 對帳 → 接手）

1. 讀 `.claude/wip.md`。
2. **對帳**：逐項驗證 wip.md 記的分支、worktree、commit hash 與現況相符（有波次看板的，逐波驗證分支存在與階段相符）；不符以現況為準，更新 wip.md 再繼續。
3. 向 Mike 摘要：之前做到哪、下一步是什麼。
4. 從「下一步」照全域工作流繼續（該討論的先討論、該派工的走 /feature-flow + /brief）。
5. 工程全部完成後刪除 wip.md（歷史已在 decisions/ 和 git log）。

## 禁止事項

- 收斂模式不 merge、不 push、不刪任何分支或 worktree。
- 不用 `git add .`、不用 `--force` 類參數。
