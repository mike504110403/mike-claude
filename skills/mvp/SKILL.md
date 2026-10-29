---
name: mvp
description: 新專案 MVP lane：專案未上線、無真實用戶、無真實資料（三條全成立）時，一切工程任務走這裡——目標是最快做出能跑能試用的東西，砍掉邊界卡／證據卡／影子審查／review chain／worktree 拓撲。第一次給真實用戶用或接真金流＝畢業，總審後回既有 lane。
---

# /mvp — 新專案快速成形

## 入選標準（三條全成立）

- 專案未上線（沒有任何正式環境在服務人）
- 無真實用戶
- 無真實資料（DB 裡沒有不能丟的東西）

**第一次判入**要問 Mike 一次（本 lane 豁免硬排除，實質是降級）；點頭後在專案 `CLAUDE.md` 頂部標一行 `stage: mvp` 作為記錄。標記只是記錄不是判準——**每次開工先重確認三條仍成立**，任一不成立即走「畢業」。之後該專案的工程任務一律走本 lane，不再逐次判 quick／solo／feature。

## 本 lane 覆寫的全域規則（2026-10-30 Mike 裁示）

| 全域規則 | MVP 期間 |
| --- | --- |
| 硬排除 | 只豁免 `金流`、`認證授權`、`DB migration`（無真實資料，hook 仍逐次詢問 migration）——直接寫，畢業總審補；`全域配置`、`不可逆操作` **照舊至少 /feature** |
| 邊界卡、A/B 方案、影響面證據卡 | 不出。需求不清才問，問完就做 |
| 改動面 × 驗證義務矩陣 | 改為：能 build、能跑起來＋Mike 試用一輪（前端不必 /local-stack、不記驗證債）。宣告仍帶改動面 |
| 主 checkout 恆 dev＋worktree 拓撲（/feature-flow） | 不走——直接在 `main` 上小顆 commit |
| brief 八欄＋影子 brief-reviewer | brief 四行：目標／路徑／驗收／回報（改動清單＋build 輸出、**不 commit**）。不派影子 |
| review chain | 不跑（畢業時一次總審） |
| 既有雷 ledger、/wip 看板、裁決攢批 | 不開；看到的範圍外問題丟 TODO 另開一片；裁決題即時問 |
| ADR | 不寫；技術選型一行寫進專案 `CLAUDE.md`（畢業時補必要 ADR） |
| 實作工人同時上限 5 | **上限 2**，大腦親寫優先；工人只寫檔不碰 git，**大腦逐一 commit**（共用 checkout，避免 index 互相污染）；兩工人改同檔則不並行 |
| Commit／Push 紀律、/ship | 自驗過就 commit 到 `main` 繼續下一片，不停下；push 不走 /ship：Mike 說「推」→ build 一次 → push → `git ls-remote` 比對 hash |
| 回報五點格式 | 一段式（見下） |

## 照舊不變（紅線）

- 第一句宣告「走 /mvp，因為…；改動面：…」。
- 未經 Mike 授權不 `git push`；hooks 全程生效。
- secrets 不進 git；不連任何正式環境、不動別的專案的資料。
- Context 預算紀律照舊。

## 流程

1. 宣告 lane、重確認三條件 → 理解要做的切片（一句話目標）。
2. 大腦直接寫；切片大且彼此獨立（不同檔）才派 implementer（≤2），brief 四行。
3. 自驗：build＋跑起來看到行為，附實際輸出；有 UI 就請 Mike 試用。
4. 小顆 commit 到 `main`，繼續下一片。

## 畢業（回到既有 lane）

觸發：第一次部署給真實用戶、或接上真金流（任一），或開工重確認時三條件不再全成立。大腦察覺即宣告「/mvp 畢業，因為…」：

1. 派 code-reviewer＋security-reviewer 對全 repo 總審（對照物＝專案 `CLAUDE.md`），BLOCKER 修完才部署。
2. 補 ADR（三條件）、開 `dev` 分支建立 /feature-flow 拓撲、開 ledger 收總審的非阻斷問題與 MVP 期間的 TODO。
3. 專案 `CLAUDE.md` 移除 `stage: mvp`。之後一律走 quick／solo／feature／bug／mega。

## 回報格式（一段式）

改了什麼＋證據（build／跑起來的實際輸出）＋下一片建議。不用五點回報。
