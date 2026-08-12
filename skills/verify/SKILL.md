---
name: verify
description: done≠done 驗收積木：工人回報後大腦親驗的固定步驟＋依改動面的可執行證據要求。所有 lane 的驗收（quick/solo 的自驗、feature/bug 的工人驗收）一律走這裡。
---

# /verify — done ≠ done 驗收

工人的回報只是宣稱，驗收看的是**檔案實況與 commit 內容**。

## 派工 lane（/feature、/bug 大修）四步

0. **（多需求／多波並行時）先查看板**：wip.md 有看板就先查——本次驗的是哪個需求、哪條分支、對照哪份 brief，不憑腦中狀態。單需求無看板則略過。
1. **確認 commit 存在**：`git -C <worktree> log --oneline -5`。要驗的是「即將被合併的那個 commit 裡有什麼」——用 `git show <branch>:<path>` 或 `git diff <base>..<branch>`，**不要 grep worktree 現況**（工作目錄可能有未 commit 的內容，合併進去的分支不含它）。
2. **範圍對帳**：`git diff --stat` 對 brief 範圍欄——多改的（scope creep）與少改的都要追。
3. **抽讀關鍵檔**：不信回報宣稱的規格版本，以 commit 內容為準。
4. **親跑可執行證據**：跑什麼**唯一依據全域 CLAUDE.md「改動面 × 驗證義務」矩陣**（本檔不重抄，防漂移）；指令形式與已知基線先查 CONTEXT.md「驗證指令與已知基線」表——**基線只決定歸屬、不決定豁免**，基線紅照列順路發現，新增紅才擋驗收；表沒有的 repo 順手補一行。
   - 工人未附實際執行輸出，視同未完成。
   - 帶變異證明的：抽查時**選工人沒做過的變異**，並先確認變異真的套上（diff 有輸出）再看紅綠。
   - **多工人同時待驗**：編譯級證據可 `run_in_background` 同時發起（同時最多 3 條，RAM 考量）——背景平行只重疊等待，**merge／進下一站前必須逐一讀回每個背景任務的完整輸出**，不看 exit code（下方 gate 紀律的 FAILED-but-exit-0 實例同樣適用）。

## 直改 lane（/quick、/solo）裁剪

沒有工人回報，1-3 免；自我 `git diff` 過一眼範圍 ＋ 執行第 4 步親跑證據。

## 操作紀律

- **gate 指令不鏈複合指令**：「跑測試 → merge」分開下、看完結果再走——測試印 FAILED 但 exit 0 時 `&&` 擋不住。
- git 一律 `git -C <絕對路徑>` 顯式指路徑。
- 不符 → 重寫 brief 重派，並記退件（全域退件迴饋迴路：memory/rejection-log 一行）。

## 通過之後

派工 lane → 呼叫 /review-chain；直改 /solo → 呼叫 /review-chain；直改 /quick → 不 review，直接收尾。
