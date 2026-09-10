---
name: wip
description: 收斂現在進行中的工程（收回所有工人、盤點落地狀態、寫 .claude/wip.md），或從 wip.md 續作上次收斂的工程。Mike 說「收斂」「收工」「先停」「交接」或「繼續上次 / 接著做」時使用。
---

# /wip — 收斂與續作

一個 skill 兩個模式，先判斷再行動：

| 條件                                                      | 模式                                                 |
| --------------------------------------------------------- | ---------------------------------------------------- |
| **階段轉換點自主觸發**（見下節；**限 Mike 未明示**——args 非 `save`／`resume`）——**本列優先於以下各列** | 見下節：**先盤點、再依盤點結果二分**——全部為空→只提示不落檔；存在未竟事項→收斂模式落檔（工人已收完時跳過步驟 1-3） |
| args 是 `save`，或 teams config.json 有存活 teammate、或 TaskList 有跑中的 subagent | 收斂模式 |
| args 是 `resume`，或（**非自主觸發時**）無工人且專案根目錄有 `.claude/wip.md` | 續作模式                                             |
| 以上皆不成立                                              | 回報 Mike：沒有進行中的工程也沒有 wip.md，問要做什麼 |

## 自主收斂觸發（2026-09-10 起，Context 預算紀律）

不等 Mike 開口，大腦在下列**階段轉換點**主動判斷要不要收斂（唯一依據全域 CLAUDE.md「Context 預算紀律」階段轉換點列）。**限 Mike 未明示**——他明講 `/wip save`／`resume` 時照他的走，本節不介入：

- 一個 feature 波次合併回 dev 且**階段四全數走完（含三清）**——此時工程已死亡、無未竟事項，**不落 wip.md**（落了也會與三清打架：階段四步驟 5 清 worktree、步驟 7 刪 wip.md，見 /feature-flow）
- 一波派工全部驗收＋review 通過、下一波 brief 尚未動筆
- 同一 session 內已完成 ≥2 個獨立需求（**同 repo 內計數**；跨 repo 的需求各自落各自專案的 `.claude/wip.md`）

判定依據是**盤點出來的實際狀態**，不是觸發點編號（觸發點只是「什麼時候該去盤」），據此二分、不默默繼續堆 context。

**盤點＝三查**（觸發點 1 的情境 worktree 已被三清刪除，所以查的是分支與帳面，不是 worktree）：

1. `git -C <主checkout> branch --list 'feature/*'` — 有無殘留 feature 分支；
2. `.claude/wip.md` 的「待 Mike 裁示」區與波次看板 — 有無未結項；
3. 本 session 有無**已議定但未動筆**的下一波。

1. **盤點後全部為空**——無未合併分支、無未竟波次、無未結裁示（典型：觸發點 1，階段四含三清走完；觸發點 3 的兩個需求也都收尾了）→ **只提示、不落檔**：「本 session 已跑 <N> 個波次、工程已收尾，**建議開新 session 再開下一件**」。此時沒有東西要交接，落 wip.md 只會製造空殼並讓下次誤判成有進行中工程。
2. **盤點後存在未竟事項**——任一未合併分支／未動筆的下一波／未結裁示（典型：觸發點 2，或另一需求仍進行中）→ 照下方收斂模式落 `.claude/wip.md`（工人還在就先收工人），再回報路徑並建議開新 session 續作。

**大腦無法自主觸發 compact，也讀不到自己當前的 context 大小**——所以觸發靠上列階段事件、不靠感覺；動作止於落檔＋提示，切不切由 Mike 決定。

## 收斂模式（收工人 → 盤點 → 落檔）

1. **盤點工人**：具名 teammate（implementer）讀 `~/.claude/teams/session-<id>/config.json` 的 `members[]`（含每個工人的完整 prompt，可直接當 brief 摘要引用；**TaskList 看不到具名工人**，2026-08-12 實測）；subagent（reviewer／scout 等）用 TaskList 盤。
2. **抓最後進度**：teammate 逐一 SendMessage 要目前進度（TaskOutput 對具名工人無效）；subagent 用 TaskOutput；有報告落檔的直接讀檔。
3. **收回工人**：teammate 逐一 TaskStop（吃工人名字）；跑中的 subagent TaskStop 帶 id（讀報型角色沒有落地物，直接停即可）。全部收完才進下一步。
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

   ## 需求／波次看板（多需求或多波並行時必備，單需求單波可省略）

   | 需求/波次 | 階段 | feature 分支 | 切自 dev | 依賴 | review 現況 |
   | --------- | ---- | ------------ | -------- | ---- | ----------- |

   <階段取值：探路｜brief草稿｜實作中｜review｜待合併｜已合併。
   「切自 dev」記 hash（/feature-flow 階段一產生），供階段四合併後重驗與探路情報時效判定。
   這張表是大腦的狀態外部化：並行進行中，大腦寫任何註解／文件／裁示前先查表，
   不憑腦中狀態（多分支並存時「拿未合併分支狀態當現況」是已知複發錯誤族）。>

   ## 收斂時進行中的工人

   <每個工人一項：任務、分支、worktree 路徑、最後狀態（commit hash / WIP commit / 未動工）、brief 摘要或 brief 檔案路徑>

   ## 決策

   <已解：一項一行，附 ADR 路徑。未解：掛在「尚未明朗」，一項一行>

   ## 待 Mike 裁示

   <裁決題攢批：一題一行，附大腦建議答案＋各選項後果對照（白話寫「選 A 會發生什麼／選 B 會發生什麼」，全域回應風格第 6 條）。只有阻塞當前關鍵路徑的才即時開口問；
   同題型出現 ≥2 次 → 提案轉預授權規則。/ship 時人已到場，順手一次裁掉>

   ## 下一步

   <明確到新 session 讀完可以直接寫 brief 派工的程度>
   ```

6. **不做清理**：worktree、`wt/` 分支、feature 分支全部保留，留給續作。
7. **回報 Mike**：收了幾個工人、各自落地狀態、wip.md 路徑。

## 續作模式（讀檔 → 對帳 → 接手）

1. 讀 `.claude/wip.md`。
2. **撞車檢查（對帳前必做，2026-08-11 兩 session 互踩定則）**：先 ListAgents 查有無 busy 的 peer session；比對 wip.md 記載進度 vs 磁碟實況的**時間線**——實況超前交接檔＝可能有人正在做，先問 Mike 再接手。「幫我看 X」這類措辭在有進行中 session 時優先解讀為「查看回報」而非「接手執行」。
3. **對帳**：逐項驗證 wip.md 記的分支、worktree、commit hash 與現況相符（有波次看板的，逐波驗證分支存在與階段相符）；不符以現況為準，更新 wip.md 再繼續。
4. 向 Mike 摘要：之前做到哪、下一步是什麼。
5. 從「下一步」照全域工作流繼續（該討論的先討論、該派工的走 /feature-flow + /brief）。
6. 工程全部完成後刪除 wip.md（歷史已在 decisions/ 和 git log）。

## 禁止事項

- 收斂模式不 merge、不 push、不刪任何分支或 worktree。
- 不用 `git add .`、不用 `--force` 類參數。
