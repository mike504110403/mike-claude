---
name: local-stack
description: 起／停／查地端全棧環境（後端＋周邊 infra），供前端瀏覽器實測與跨端聯測用。專案無關：只讀該專案的 .claude/localstack.json 宣告檔照著操作。Mike 說「起地端」「起後端」「地端環境」，或 /verify 的前端驗證義務需要真環境時使用。
---

# /local-stack — 地端全棧環境

**這個 skill 不知道任何專案的細節，也不准知道。** 它只做四件事：找到宣告檔 → 照著起 → 確認就緒 → 回報怎麼用。專案差異全部住在該專案的 `.claude/localstack.json`。

## 參數

| 輸入                   | 動作                                    |
| ---------------------- | --------------------------------------- |
| `/local-stack` 或 `up` | 啟動並等待就緒                          |
| `/local-stack down`    | 停止（預設保留資料）                    |
| `/local-stack status`  | 只查狀態，不動任何東西                  |
| `/local-stack wipe`    | 停止並清空資料（**破壞性，先問 Mike**） |

## 步驟

### 0. 執行位置判定（PC 延伸機，2026-09-16 起；2026-09-17 起一律經 `pc-deploy`）

宣告檔有 `pc` 區塊時，**不手工串 pc-reach／pc-push／pc-sync-stack／ssh**，一律一個指令：

```
~/.claude/bin/pc-deploy <group> [up|push|down|status|frontend-up|frontend-down] [--skip-push] [--skip-sync]
```

它自己讀宣告檔的 `pc` 區塊（host、root、repos、env、extra_sync、rewrites）與 `commands.*`，做完 pc-reach → 逐 repo pc-push（工作樹快照，含未 commit 改動）→ pc-sync-stack → ssh 帶 `pc.env` 在 `pc.root` 執行對應指令。**輸出第一行就是回報要用的「棧：PC（host）」或「棧：Mac（原因）」**，exit 1＝PC 不可達或無 pc 區塊→退回下方 Mac 流程（原流程不變，不重試、不等 PC），exit 0＝該動作在 PC 完成，exit 3＝推碼／同步失敗（不會在 PC 起舊碼），其餘＝遠端指令的 exit code。`up` 推全部 repo 並同步等 PC 起完；`push` 推全部 repo 後不等（PC 端 systemd 收到 hook 旗標約 15 秒後自動跑該群 up.sh，2026-09-17 波 7c）——改完程式碼要看畫面用 `push`，要立即拿到就緒證據用 `up`；`frontend-up` 只推宣告檔 frontend 區塊的前端 repo；`down`／`status`／`frontend-down` 不推碼——但**每個動作都同步 localstack/**（腳本住那裡，Mac 改了 PC 才跑得到新版）。`status` 先印 PC 端狀態檔（health.json 每 5 分鐘 timer 健檢、deploy/<group>.json 最近一次自動部署）再跑宣告檔 `ready_check.cmd`（與下方步驟 4 同源）。

回報時所有 port、前端 URL、`env_override` 裡的 `localhost`／`127.0.0.1` 一律換成 PC 的 Tailscale IP（pc-deploy 就緒行會印；或 `ssh -G <pc.host> | awk '/^hostname /{print $2}'`），port 以 `pc.env` 為準（三群在 PC 同時常駐靠它錯埠：貴金屬 API 8180／WS 8181、回收群 PG 5433／Redis 6380、彩票不變），cmux 瀏覽器 tab 也開這個位址。Mac 端 Docker Desktop 不需開著。

- 三群（彩票、貴金屬、回收）2026-09-17 起全容器化：up.sh 收尾自帶前端 dev server、status 納入判準、主機重開後靠 restart policy 自己回來（docker daemon 重啟實測三群全綠）。status 不綠才重跑 up。
- 無 `pc` 區塊 → Mac 模式。**回報第一行固定寫「棧：PC（<host>）」或「棧：Mac（<原因>）」**，讓 Mike 與 /verify 知道證據來自哪台。PC 模式的 `wipe` 同樣先問 Mike（pc-deploy 不提供 wipe，要 wipe 就 ssh 手跑 `down.sh --wipe`）。

### 1. 找宣告檔

從當前工作目錄逐層往上找 `.claude/localstack.json`，找到第一個就用。

**找不到就停下來回報，不准猜、不准套用別的專案的做法**：

> 這個專案沒有宣告地端棧（找不到 `.claude/localstack.json`）。
> 要建的話需要先盤點：infra 怎麼起、服務怎麼起、就緒判準是什麼、測試帳號哪來、哪些功能地端不會動。
> 要我現在做嗎？

宣告檔**不進版控**（本機環境宣告，非專案共享設定），所以「換一台機器、新 clone 的專案沒有它」是常態，不是異常。

### 2. 讀取並驗證

`json.load` 讀進來。缺 `commands.up` / `ready_check` 這類必要欄位就明講缺什麼、停下，不要半猜半做。

### 3. 執行

照 `commands.<動作>.cmd` 執行（注意 `path_type` 是絕對還相對）。

- **非 0 結束就是失敗**：把 stdout/stderr 原文貼出來，不要自己編一句「可能是……」。
- 破壞性動作（wipe／清資料）先問 Mike，除非他這一輪已明講。

### 4. 確認就緒

跑 `ready_check.cmd`，用宣告檔自己的 `success_criteria` 判定（通常是 exit code ＋ 特定字串）。**用它宣告的判準，不要自創**。

沒過就重試幾次（服務啟動有先後），仍不過就把 `ready_check` 的完整輸出貼出來、停下回報，**不要宣告成功**。

### 5. 回報

**在 cmux 內時（`$CMUX_BUNDLED_CLI_PATH` 存在）先把前端位址開成內嵌瀏覽器 tab**，作為 Mike 手測入口——開法（加 tab、不開新 pane）唯一依據全域 CLAUDE.md「Browser 自動化工具鏈」末條；前端 URL 取自宣告檔的 `frontend` 區塊。

接著給出使用者接下來需要的東西，全部取自宣告檔：

- 各服務的 port 與健康狀態
- 測試帳號（`credentials`）
- 前端要怎麼指過來（`frontend.env_override`）
- **已知限制**（`known_limitations`）——哪些功能地端不會動，這條一定要講，否則使用者會把地端的限制誤判成 bug
- **對外連線**（`isolation`）——地端仍然會出去的連線有哪些

## 紀律

- **宣告檔是唯一事實來源。** 它與現況不符時（服務起不來、port 不對、帳號登不進去），修的是宣告檔或環境，不是在 skill 裡加專案分支。
- **不要把專案知識寫進這個檔案。** 任何「如果是 X 專案就……」的判斷都是設計失敗的訊號。
- **PC 模式不是專案知識。** `pc` 區塊是宣告檔的一部分，skill 只做 `root`→`pc.root` 前綴替換與 host 替換；up.sh 在 PC 跑不動時修的是該群 localstack 腳本或宣告檔，不在 skill 加分支。工具與 spec：`~/.claude/plans/pc-offload.md`。
- **不要為了讓就緒判準過而放寬它。** 判準過不了代表環境真的沒好。
- 地端環境的目的是**任何操作都不外溢到真實世界**。發現宣告檔的 `isolation` 漏列了對外連線，或有指向正式服務的開關預設開著，當場回報 Mike。

## prod 資料副本（宣告檔有 `prod_data` 區塊時）

專案若在宣告檔標明 `prod_data`（地端持有生產資料副本），**起棧一律以該副本為 DB**——feature 等級以上或含 migration 的改動，起棧測試就同時是「prod 的下一次啟動」彩排（2026-08-14 兩天部署事故的定則：online 看沒問題 ≠ prod 能上，差的就是資料與環境）。照宣告執行：

- `prod_data.equivalence_cmds`：起棧後逐條執行（如補 GLOBAL sql_mode——容器重啟就失效的環境等價設定）。
- `prod_data.rehearsal_checks`：就緒後逐項驗證並納入回報（如 migration 全過、健檢告警符合已知清單）。
- `prod_data.refresh_skill`：副本血統/刷新程序住在該 skill，過期時提示 Mike 刷新。
- 副本是真實用戶資料：輸出遮罩、不外流。

## 與 workflow 的關係

改動面含前端時，驗證義務的環境前提就是這個 skill（見 /verify）。降級階梯：

| 階  | 環境                 | 能驗到什麼                             |
| --- | -------------------- | -------------------------------------- |
| 1   | 地端全棧（本 skill） | 完整前後端行為、跨端聯測               |
| 2   | 只起後端、前端接它   | 前端行為＋真實 API 合約                |
| 3   | 靜讀＋跨端對照表     | 型別與合約一致性，**驗不到執行期行為** |

**降到第 2 階以下一律要在 wip.md 記一筆驗證債**：為什麼降級、已有的替代證據是什麼、還沒驗的具體清單、補驗的腳本在哪。沒記＝那筆驗證會永遠消失。
