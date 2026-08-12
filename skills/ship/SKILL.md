---
name: ship
description: 把本地 dev 的累積成果推上 remote 的收尾流程：盤點 → Mike 批次手測 → 授權 → push → ls-remote 驗證。Mike 說「推」「上線」「ship」時使用；多需求並行下 Mike 的手動實測在此批次進行。
---

# /ship — push 前批次收尾

Push 是全域規則裡唯一必經 Mike 明確授權的動作；本 skill 把「Mike 手動實測」批次化在這個天然到場點，一次測 dev 上累積的組合態。

## 流程

1. **盤點**：`git -C <主checkout> log origin/dev..dev --oneline` 列出即將推上去的需求清單，逐條附一句改動摘要，回報 Mike。
2. **批次手測**（清單中有改動面含前端的需求才做）：/local-stack 起地端棧，把各需求的關鍵流程清單（brief 實測步驟彙整）交給 Mike 手動走**組合態**。
   - 這是唯一的**清單外探測**（實證：51-53 掛錯元件案三輪 review 都沒抓到、是 Mike 地端實測抓的）——不可為省時間省略；Mike 明示免測的需求才跳過。
   - Mike 不在 → 本步等人，不阻塞其他 repo 或本 repo 的下一個需求開工（它們只依賴本地 dev）。
3. **發現問題** → 依分流開 /bug 或 /quick 修復，修完回到步驟 1 重新盤點。
4. **push 前置 gate（2026-08-14 起，兩天部署事故的定則）**：
   - **每個要推的分支，推前在本地 build＋test 過**（`go build ./...`＋全套測試綠）——合併/解衝突後沒 build 就推是 CI 掛掉與壞版本上遠端的直接根因。
   - **feature 等級以上、或含 migration 的改動**：push 前必起 **/local-stack** 完整測過——宣告檔含 `prod_data` 的專案（如彩票）即以 prod 副本起棧，等同上線彩排；彩排不過不推。
5. **Mike 明確授權**後 push → `git ls-remote` 比對 hash 驗證落地。dev 推 remote 前務必問（全域規則）；feature 分支永不推。
6. **收尾**：改動涉及 API 且有 `bruno/` → /bruno-sync；順手檢查 wip.md「待 Mike 裁示」區——人都到場了，把攢的裁決題一次裁掉。
