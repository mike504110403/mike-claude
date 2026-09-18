---
name: feature
description: 標準工程 lane：範圍明確、超出 /solo（多線意圖、需派工、跨 repo）、技術路線清楚的新功能或修改。brief 派工、驗收、review chain 的完整流程在此。
---

# /feature — 新功能 / 修改

## 入選標準

- 範圍明確、超出 /solo（多線意圖、需派工、跨 repo、>8 檔，或命中硬排除）
- 技術路線清楚，不需要先解決策（需要探路 → /mega）

## 流程

### 1. 需求對齊

- **改動面與邊界在此定案**：宣告的改動面（後端／前端／前後端）具體化成「動哪些 repo、哪些層」，寫進每份 brief 的範圍欄；對應驗證義務依全域「改動面 × 驗證義務」矩陣，後面各站照表執行。
- 符合任一：`跨服務`、`涉及金流`、`不可逆操作`、`全域配置`、`範圍明顯大於直覺` → 先提 **A/B 兩方案**（各含取捨與風險）給 Mike 選，等點頭才動工。
- 新專案 / 新需求第一次動工前：與 Mike 討論需求與寫法，結論落檔專案 `CLAUDE.md`；重大決策依三條件（難回頭、不看脈絡會奇怪、真有取捨）補 ADR（新專案 `docs/adr/` Matt 格式；有 `.claude/decisions/` 的舊專案沿用原路徑與四段格式）。
- 已有共識 → 明講「共識已存在（出處），跳過討論」直接動工。
- **邊界卡（每個 /feature 必出，2026-08-20 起）**：需求對齊的交付物是一張 ≤5 行的卡給 Mike 點頭：`目標（一句話）／改動面（repo×層）／非目標（含 ledger 既有雷處置）／影響面（每條標已驗＋證據 or 待驗）／待裁示`。**點頭＝邊界鎖定**——之後任何超出卡面的範圍變動都回來重議，不得默默吸收。影響面欄只放已驗事實（全域「影響面證據卡」不變式）；非目標欄先讀 `~/.claude/ledgers/<repo>.md` 把相關既有雷列入。A/B 方案觸發時，方案附在卡下一起給。

### 2. 拆任務 ＋ 派工

- 每個子任務用 /brief 八欄模板寫自足 brief；seam 沒議定不派工。
- **拆分粒度（2026-08-20 起）**：盡可能拆細——一個工人一個單一意圖的小切片（一個 seam），壓低每個 agent 的 context、讓它只看得到自己的事。細拆的下限是**切工硬規則：共用元件／檔案與其全部消費者必須劃給同一個工人**（拆開會讓 reviewer 只見半成品、報幻影問題——返點案四次實證）；做不到同工人時，reviewer 的 prompt 必須明寫「另一半在別的 worktree，以下項目不要報」。
- **brief 寫完直接派工＋影子審查並行**（2026-09-02 起，取代 08-24 的純自檢制）：前提是邊界卡已給 Mike 點頭；BRAIN-CHECKLIST 自檢照做、事實斷言照舊動筆前開檔驗。派 implementer 的**同一則訊息**並行派 brief-reviewer（影子，in-process subagent，報告＝最終回覆）審同一份 brief——影子報 **BLOCKER** → 立即 TaskStop 該工人、修 brief 重派；MAJOR/minor → 攢到該工人 /verify 驗收時一併處理，不中斷工人。影子屬「不必逐個親驗」類（上限 8），不佔實作工人名額；延遲趨近零，換回 08-24 砍閘門後失去的第二道防線（停用期間大腦自檢漏檢實證見 rejection-log）。
- **派工前環境前提親驗**：brief 工作環境欄引用的環境事實（DB／容器／服務位址）派工當下驗一次——環境狀態要驗不要記；前提已失效就先修環境或改 brief，別讓工人自行起 infra。
- 分支與 worktree 一律走 /feature-flow（先 /sync-dev）。
- `run_in_background: true` 平行派工；**派工形式（implementer 具名 teammate、其餘 subagent）**、命名、單波上限、模型選配依本 skill「派工紀律」節與全域「模型選配」。

### 3. 驗收（done ≠ done）

一律走 **/verify**（四步親驗＋改動面證據）；不符 → 重寫 brief 重派並記退件。

**Per-worker pipeline（不空等）**：工人 A 進驗收／review 時，大腦立刻接工人 B 的回報、或寫下一份 brief、或處理下一個需求——驗收攤平到工人執行期間，不等整波齊。並行超過 2 工人（或多需求並行）時 /wip 看板必開，寫任何裁示前先查表。

### 4. Review chain（驗收通過後）

一律走 **/review-chain**（觸發表、對照物 = brief、按嚴重度分層重跑、通過 TaskStop 收工）。**改動面含前端** → 派 reviewer 的同一時刻起 /local-stack 讓 Mike 並行手測（站點細節在 /review-chain）。

### 5. 收尾

- 合併依 /feature-flow 階段三、四（階段四含合併後重驗與三清）。
- **改動面含前端**：合併回 dev 的前提是 review chain 的「Mike 手測並行站」已過（依全域矩陣；/auto-e2e 僅 on-demand，用於 Mike 點名代測或 /bug runtime 重現）。API 合約以 bruno collection 為對照（有 bruno/ 的專案先 /bruno-sync 增量同步再驗）。
- commit 後停下；push 走 /ship。

## 派工紀律（全域唯一 source，2026-09-18 自 CLAUDE.md 遷入；/review-chain、/bug、/mega 只引用）

- **派工形式（2026-09-07 起）**：**只有 implementer 派具名 teammate**（`name`「任務-角色」風格，開 split pane、SendMessage 回報）；**其餘角色一律 in-process subagent**——scout-read／scout-trace／janitor／brief-reviewer／四個 reviewer／bruno-sync 工人／臨時 prompt 診斷，Agent 呼叫**不帶 `name`**、`description` 寫「任務-角色」、`run_in_background: true`。subagent 的**最終回覆就是報告**；續聊用 SendMessage 帶 agent id；急停 TaskStop 帶 id；盤點 TaskList／TaskOutput 對 subagent 有效。理由：這些角色讀完回報、不需中途互動，pane、重載 context、inbox 往返全是純成本。
- **同時上限**按「大腦要不要逐個親驗」分（真瓶頸是大腦串行驗收）：要逐個親驗（實作工人）**5**，隊列積壓就降；不必逐個親驗（探路／掃描／文件）**8**；動用 chrome-devtools MCP 的 agent **同時 1**（共用選頁指標）。
- **探路要不要派**（2026-09-07 起）：改動面 ≤3 檔、本 session 已讀過相關碼、或單一 grep 可得答案 → **大腦直讀**（片段形式，證據卡格式同 agent 檔）；跨模組呼叫鏈、不熟的 repo、要枚舉多處消費者 → 派 **scout-read**（取值）／**scout-trace**（判讀）。派了的報告仍是線索不是事實，brief 引用前只驗它引用的 `檔案:行號`。**有 graft 圖的 repo 探路一律先查圖**（`graft callers`／`graft grep`／`graft skeleton`，見 /graft）——「枚舉多處消費者」不再是派 scout-read 的理由；派 scout-trace 時把 graft 輸出附進 prompt。
- **未動工即死**：背景具名工人零 commit、inbox 未讀，同工程累計 ≥2 次 → 視同派工基礎設施異常，停止再派背景工人，改同步派工或大腦親實作，不第三次重試（2026-08-14 定則）。
- **cmux pane 紀律（2026-09-07 修訂，pane 操作唯一 source）**：pane 至多一個（implementer），**不跑任何 `resize-pane`**。指令全用 `"$CMUX_BUNDLED_CLI_PATH"`，非 cmux 環境跳過；幾何事實一律取 `list-panes --json` 的 `pixel_frame`（`tree` 順序≠畫面順序）。瀏覽器一律是既有 pane 裡的 tab，**永不為瀏覽器搬動任何 pane**（開法見 /browser-tools）。只做兩件事：
  1. **焦點拉回主 pane**：每次開／關 teammate pane、開瀏覽器 tab 之後 `focus-pane --pane <主pane>`（`identify | jq -r .caller.pane_ref` 取 ref）；開瀏覽器 tab 一律帶 `--focus false`。
  2. **清殘殼**：**TaskStop 不保證自動關 pane**——收工後 `list-panes --json` 盤點，殘留用 `close-surface --surface <ref>` 清；大腦自己開的瀏覽器 tab 同樣要清。清完焦點拉回主 pane。
- **收工**：teammate 驗收後用 **TaskStop**（吃工人名字）收掉。具名 teammate 的盤點讀 `~/.claude/teams/session-<id>/config.json`、進度用 SendMessage 問（TaskList/TaskOutput 對具名工人無效）；subagent 做完自行結束。
- **done ≠ done**：工人回報後大腦必親自抽查＋親跑證據（/verify）。
- **退件回饋迴路**：驗收不符或 reviewer 打回 → memory `rejection-log` 記一行（任務、原因、家族）；同家族累積成 pattern → 修規則源頭，修完刪記錄。

## 領域插件

- Go：brief 紀律欄引 /tdd；碰 schema 觸發 db-reviewer。
- Vue：brief 紀律欄引 /vue-dev、/vue-ui-patterns（不寫測試檔，詳見 /vue-dev）。
- 驗收證據不在此重抄——唯一依據全域「改動面 × 驗證義務」矩陣（棧別具體指令住在 /tdd、/vue-dev）。

## 跳線

- 途中冒出未決技術選型 → 宣告升級 /mega（先解決策再回來拆工）。
- 發現根因不明的壞行為 → 宣告轉 /bug。
- 發現其實極簡單 → **先問 Mike** 才降 /solo 或 /quick（降級不得自主）。
- 要中途暫停 / 交接 → /wip 收斂。

## 回報格式（五點）

1. 改了什麼 2. 為什麼 3. 影響面 4. 驗證證據（測試輸出、diff stat）5. 還可以做什麼（不擅自執行）。
   答案先行、次要問題只在第 5 點列一行、多波任務帶進度重述（N 波完成 M）。

**影響面（第 3 點）的紀律**：寫「改 A 會導致 B」之前把 B 那段程式碼讀到底（守衛條件、early return、迴圈取的是哪一層）——grep 到欄位被讀只證明被讀，不證明在哪個分支對誰生效；先搜同專案有沒有人論證過同一件事；「完全相同／不變」要帶值域條件；影響面宣稱在 brief 裡標成待驗假設交 reviewer 查證。錯的影響面會寫進 commit message 變成下一個人的錯誤前提。
