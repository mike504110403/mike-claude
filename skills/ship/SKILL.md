---
name: ship
description: 把本地 dev 的累積成果推上 remote 的收尾流程：盤點 → 授權 → push → ls-remote 驗證。Mike 說「推」「上線」「ship」時使用。
---

# /ship — push 前批次收尾

Push 是全域規則裡唯一必經 Mike 明確授權的動作。（各需求的 Mike 手動實測已在 review chain 手測並行站完成——2026-08-20 起本 skill 不再設批次手測站；多需求並行時 Mike 可自行決定在此加測一輪**組合態**，大腦盤點時主動提醒「本批含 N 個前端需求，要不要組合態走一輪」即可，不強制。）

## 流程

1. **盤點**：`git -C <主checkout> log origin/dev..dev --oneline` 列出即將推上去的需求清單，逐條附一句改動摘要，回報 Mike；含前端需求 ≥2 個時附一句組合態加測提醒。
2. **發現問題** → 依分流開 /bug 或 /quick 修復，修完回到步驟 1 重新盤點。
3. **push 前置 gate（2026-08-14 起，兩天部署事故的定則）**：
   - **每個要推的分支，推前在本地 build＋test 過**（`go build ./...`＋全套測試綠）——合併/解衝突後沒 build 就推是 CI 掛掉與壞版本上遠端的直接根因。
   - **feature 等級以上、或含 migration 的改動**：push 前必起 **/local-stack** 完整測過——宣告檔含 `prod_data` 的專案（如彩票）即以 prod 副本起棧，等同上線彩排；彩排不過不推。
4. **Mike 明確授權**後 push → `git ls-remote` 比對 hash 驗證落地。dev 推 remote 前務必問（全域規則）；feature 分支永不推。
5. **收尾**：改動涉及 API 且有 `bruno/` → /bruno-sync；順手檢查 wip.md「待 Mike 裁示」區與 `~/.claude/ledgers/` 相關 repo 的標紅既有雷——人都到場了，把攢的裁決題一次裁掉；順帶核一次**模型重測門檻**（判定與門檻唯一依據全域「角色 × 模型矩陣」大腦列，不在此重抄）；`~/.claude/maps/` 有該 repo map 的順帶過一眼「最後核對」戳，明顯過期（落後本批改動）就補 delta。
