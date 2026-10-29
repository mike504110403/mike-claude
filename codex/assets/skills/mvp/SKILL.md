---
name: mvp
description: 新專案 MVP lane：未上線、無真實用戶、無真實資料時最快做出能跑能試用的東西；畢業後回既有 lane。
---

# mvp

入選：專案未上線、無真實用戶、無真實資料，三條全成立。第一次判入先問 Mike 一次，點頭後在專案 AGENTS 標 `stage: mvp` 作記錄；標記不是判準，每次開工重確認三條件，任一不成立即畢業。

期間覆寫全域規則：硬排除只豁免金流、認證授權、DB migration（migration 執行仍先問），全域配置、secrets、不可逆操作照舊至少 /feature；不出邊界卡、A/B、影響面證據卡；不走 worktree 拓撲，直接在 main 小顆 commit；不跑 review chain、不派影子、不開 ledger/wip 看板，範圍外問題丟 TODO，裁決題即時問；不寫 ADR，選型一行記專案 AGENTS；驗收＝build＋跑起來＋Mike 試用；subagent 至多 2、主代理親寫優先，brief 四行（目標/路徑/驗收/回報），subagent 只寫檔不碰 git，主代理逐一 commit，改同檔不並行；自驗過即 commit 繼續，push 不走 /ship：Mike 明確說推 → build → push → ls-remote 比對。

紅線照舊：第一句宣告 lane 與改動面；push 需 Mike 明確授權；secrets 不進 Git；不連正式環境或他專案資料。

畢業（首次給真實用戶、接真金流或三條件不再成立）：宣告畢業→全 repo code review＋security review，BLOCKER 修完才部署→補必要 ADR、建 dev 與 /feature-flow 拓撲、開 ledger 收非阻斷問題與 TODO→移除 `stage: mvp`，之後走既有 lane。回報一段式：改動、build/執行證據、下一片建議。
