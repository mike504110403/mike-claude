---
name: push
description: 把本地 dev 的累積成果推上 remote 的收尾流程：盤點 → 授權 → push → ls-remote 驗證。Mike 說「推」「上線」「push」時使用。
---

# /push — push 前批次收尾

Push 是全域規則裡唯一必經 Mike 明確授權的動作。（各需求的 Mike 手動實測已在 review chain 手測並行站完成——2026-08-20 起本 skill 不再設批次手測站；多需求並行時 Mike 可自行決定在此加測一輪**組合態**，大腦盤點時主動提醒「本批含 N 個前端需求，要不要組合態走一輪」即可，不強制。）

## 流程

1. **盤點**：`~/.claude/bin/push-plan snapshot --repo <主checkout> --branch <分支>` 列出即將推上去的 commit 並存快照（最後一行是建議的 push 指令，以 hash 為 src），逐條附一句改動摘要，回報 Mike；含前端需求 ≥2 個時附一句組合態加測提醒。push 閘門（bash_guard）會在 push 前跑 `push-plan check`：快照後分支又前進 → deny，**把差異回報 Mike、經同意才重跑 snapshot**，不得自行重拍快照繞過。
2. **發現問題** → 依分流開 /bug 或 /quick 修復，修完回到步驟 1 重新盤點。
3. **push 前置 gate（2026-08-14 起，兩天部署事故的定則）**：
   - **每個要推的分支，推前在本地 build＋test 過**（`go build ./...`＋全套測試綠）——合併/解衝突後沒 build 就推是 CI 掛掉與壞版本上遠端的直接根因。
   - **feature 等級以上、或含 migration 的改動**：push 前必起 **/local-stack** 完整測過——宣告檔含 `prod_data` 的專案（如彩票）即以 prod 副本起棧，等同上線彩排；彩排不過不推。
   - **push 閘門證據**（hook 只對單純形式 `[cd <path> &&] git [-C <path>] push [<remote>] [<ref>...]`，選項只接受 `-u`，驗內容綁定的紀錄，缺就硬擋；hook 抓得到的其他形式 ask 並標「無法判定」，不代表證據已驗；漏抓形式見下方已知限制）：/local-stack 通過後 `~/.claude/bin/gate-evidence record --repo <主checkout> --kind local-stack --note '<結論>'`；`nginx -t` 通過後同上 `--kind nginx-test`。migration 檔要 `db-review`（專案有 `.claude/localstack.json` 才另要 `local-stack`），nginx 檔要 `code-review`＋`nginx-test`；`stage: mvp` 專案不驗。
   - **被閘門擋 → 補證據，不得繞過**（換寫法、包一層、改 ref 都算繞過）。`~/.claude/bin/gate-evidence waive --repo <主checkout> --reason '<理由>'` 只有 Mike 裁示才用（直接形式 hook 一律 ask）。hook 回「無法判定」時先跑 `~/.claude/bin/gate-evidence check --repo <repo> --ref <ref> --remote <remote>` 人工確認證據，再請 Mike 決定。
   - **push 單獨一次 Bash 呼叫，`git ls-remote` 另一次**：串接時 hook 只會 ask、不驗證據。`-C`、`cd` 路徑不可用 `~`（hook 不展開，判不單純，只 ask 不驗證據）。
   - **hook 已知漏抓**（字串比對，判定等於放行，靠本節紀律守）：全域選項超過 8 個、`git -C /a\ b push` 這類反斜線跳脫空白、`push*`／`push(N)`／`push{,}` 這類 glob 與大括號展開、`pu''sh` 這類引號拆字、`git commit --trailer -m nginx` 這類把 `-m` 當前一選項值的形狀（只影響 nginx／migration 免問，不影響 push）、包一層（script、alias）。超過 8192 字元的命令不跑閘門，含 `git`、`push` 字樣就 ask。
   - **已知限制**：只由 merge commit 帶入、且內容等於該 remote 追蹤分支同路徑的檔不要求證據；本地 commit 寫下的內容（含 squash、cherry-pick、回滾成舊內容）與刪除項一律要證據。Mike 裁示接受的殘留：`--no-ff` 合遠端未審分支、merge commit 內改成過時分支的舊內容，這兩種不會被擋。證據與遠端追蹤 ref 都不防偽造。`--remotes` 範圍不分目的分支，commit 已在同 remote 任一分支時不再驗（dev 合到 online 依賴 dev 當時的把關）。比對成本約「merge 帶入的敏感檔數 × 該 remote 追蹤 ref 數」，實測約 2.5 萬組（400 檔 × 62 refs，5.1 秒）逼近 6 秒預算，超過時退回「無法判定」的 ask。
4. **Mike 明確授權**後 push（單獨一次呼叫，用步驟 1 snapshot 印出的 `git -C <主checkout> push <remote> <hash>:<分支>`）→ 另一次呼叫 `git ls-remote` 比對 hash 驗證落地。dev 推 remote 前務必問（全域規則）；feature 分支永不推。
5. **收尾**：改動涉及 API 且有 `bruno/` → /bruno-sync；順手檢查 wip.md「待 Mike 裁示」區與 `~/.claude/ledgers/` 相關 repo 的標紅既有雷——人都到場了，把攢的裁決題一次裁掉；順帶核一次**模型重測門檻**（判定與門檻唯一依據全域「模型選配」大腦列，不在此重抄）；`~/.claude/maps/` 有該 repo map 的順帶過一眼「最後核對」戳，明顯過期（落後本批改動）就補 delta。
