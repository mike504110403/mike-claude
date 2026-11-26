---
name: review-chain
description: Review chain 積木：reviewer 觸發（diff-surface）、review 對照物、打回重跑與收工規則。/feature 與 /solo 在 /verify 通過後呼叫。
---

# /review-chain — 審查鏈

> /mvp 專案不適用本積木：驗收與畢業總審以 /mvp 為準。

改動面含前端時，先過下方「Mike 手測站」，再派 reviewer。

## 所有 lane 的基線檢查

lane 只決定執行形態，不決定檢查強度：repo 有 `~/.claude/checks/<key>/verify.json` 時跑 `verify-run`（指令見 /verify 第 4 步）；一律跑 `diff-surface`（下節）。

## 派 reviewer 前：diff-surface

- 大腦對該 worktree 跑 `~/.claude/bin/diff-surface --repo <worktree realpath> --base <切自的 commit> --record`；**改動未 commit（直改 lane）時加 `--include-worktree`**。以它輸出的「命中類別／reviewer」為準；清單是**下限**（`--help`：「reviewer 段是下限，不是完整清單」），下方人工補充表可加派。
- 直改修復輪**每輪都重跑 `--record`**：HEAD 不變時舊紀錄仍放行，不重跑就審到過期內容（`reviewer_gate.py` 檔頭：「--record 之後才改的未 commit 內容不會使紀錄失效」）。重跑結果的 `lane 下限` 高於當前 lane → 依跳線升級。
- **/quick 例外**：不派 code-reviewer；DB schema 命中 → db-reviewer；nginx 命中 → code-reviewer 加 nginx 檢查項；其餘不派（金流／認證在 /quick 第 3 步已升級，到不了這裡）。
- reviewer prompt **單獨寫出 worktree 根路徑（realpath，前後以空白或標點分隔；只引用其下檔案不算）**，否則 `reviewer_gate.py` deny。
- 紀錄 3 小時內有效、綁記錄當下的 HEAD：修復輪 commit 後 HEAD 變了，重派新 reviewer 前重跑 `--record`；SendMessage 續審不受閘門約束，同樣重跑。
- 非 git 專案：prompt 寫字面「diff-surface: N/A（非 git）」。全 repo 總審：`--base` 給空樹 `git hash-object -t tree /dev/null`。

## 人工補充表（diff-surface 輸出稱「觸發表」）

模型選配唯一依據全域「模型選配」，不在此重抄。本表只用於兩件事：diff-surface 不輸出的檢查項（nginx 那列的 prompt 項）與大腦加派；其餘以 diff-surface 清單為準。

| Reviewer                      | 觸發                                                                             |
| ----------------------------- | -------------------------------------------------------------------------------- |
| code-reviewer                 | 每次都跑                                                                         |
| security-reviewer             | 金流 / 付款 / 認證授權 / secrets                                                 |
| db-reviewer                   | DB schema / migration                                                            |
| code-reviewer 加 nginx 檢查項 | 改到 nginx 設定（prompt 加：server_name／upstream／TLS／proxy header／重導迴圈） |

ui-reviewer 不在表內，僅 Mike 點名時 on-demand 派。

## 通過後記證據（push 閘門）

reviewer 通過且改動已 commit 後，大腦親跑（證據綁檔案內容，修復輪改到敏感檔要重記；沒 commit 時 exit 3）：

- db-reviewer 通過 → `~/.claude/bin/gate-evidence record --repo <worktree> --kind db-review --note '<結論>'`
- 改到 nginx 設定、code-reviewer 含 nginx 檢查項通過 → 同上，`--kind code-review`

## Mike 手測站（改動面含前端，先於 reviewer）

順序（純後端維持「/verify 通過即 review」）：

1. 工人完成 → /verify 機器證據。
2. 起 /local-stack，先驗前端 API 位址指向地端——判準與 env 分層查法**唯一依據 /vue-dev「瀏覽器實測」0-1 步**。
3. 通知 Mike：測試入口＋本次改動的重點路徑清單（brief 實測步驟彙整）。
4. **Mike 手測確認需求**。需求有調整 → 先同步更新 brief 與邊界卡（超出邊界卡的變動依 /feature 規則回 Mike 重議）→ 再改（派工或直改）→ 回 /verify → 再手測。
5. 需求定案後才跑 diff-surface `--record`、派 reviewer。Mike 未回覆手測 → reviewer 不先跑，停在第 4 步等人，不阻塞其他需求開工。

- **截圖處理**（唯一依據全域「Context 預算紀律」截圖列）：通知 Mike 時講明「畫面問題請給**截圖檔案路徑**」，不要直接貼圖；Mike 已貼進來的圖不重複 Read、不叫重貼；reviewer／工人側視覺證據存檔交 subagent 判讀。
- **等 Mike 手測的空檔**：大腦照同一份清單把 /auto-e2e 回放腳本寫好存進 feature worktree——**差異重測先回放，回放紅或新增流程才找 Mike**。

## Review 對照物（Spec 軸拿什麼審）

- /feature、/bug 大修：該工人的 **brief**。
- /solo：大腦的**任務描述**（宣告文擴寫成 2-4 句：要做什麼、為什麼、預期行為邊界）。
- 沒給對照物，reviewer 會明講「Spec 軸跳過」——那是大腦漏給，不是 reviewer 的錯。

## 派工紀律

- diff-surface 命中（含人工加派）的 reviewer **一律同一則訊息一波派完**（多個 Agent 呼叫放同一 block），不逐個等回報；打回修復後重跑全鏈同樣一波派。唯一例外：動用 chrome-devtools MCP 的 agent（僅剩效能診斷）同時僅 1；ui-reviewer 與 /bug 診斷已改 playwright-cli 具名 session、/auto-e2e 是 Playwright 腳本，皆不受此限。
- reviewer 一律 in-process subagent（/feature「派工紀律」），**報告＝最終回覆**；prompt 必帶回報條款（/brief 的 BRAIN-CHECKLIST）：沒發現問題也要回「審了哪些重點項」。
- **reviewer prompt 必附 `diff --stat` 檔案清單，並明寫「審查以 diff 涉及檔與其直接呼叫端為界，不做全 repo 探索」**——消費者枚舉已由大腦在寫 brief 時做掉（BRAIN-CHECKLIST），review 端重做是冗餘讀檔（opus 價）。
- reviewer 只讀不改；發現的既有問題照「既有問題不處理」判準，列一行即可。
- **reviewer prompt 常備一句「不跑任何 router／DB 整合測試、不對測試庫下 SQL」（2026-09-18 N 家族五犯定則）**：工人與大腦的專屬測試庫同時只能有一個 `go test`，reviewer 在工人 worktree 跑 router 測試會撞掉大腦的全套件驗收（52 假紅實證）。reviewer 要 runtime 證據 → 標 PLAUSIBLE 並向大腦要；gofmt／build／vet／純單元包（無 TestMain 的 package）可跑。
- **reviewer prompt 必內聯 `~/.claude/ledgers/<repo>.md` 裡與本次改動面相關、且已標「Mike 裁示不修／非雷／勿再報」的條目**（2026-09-10 定則）：reviewer 看不到 ledger，漏內聯就會把已裁定項當新發現重報，浪費一輪複核。**但裁示的前提若被本次改動改變（例：GA 拿掉後，原本只是第二層的 fail-open 變成唯一授權層），該條要重新上 Mike 討論桌，不是照舊沉默。**
- **runtime 行為斷言只能標 PLAUSIBLE**：reviewer 說「這個錯不會影響流程」這類 runtime 行為判斷，推得再細都不得作為放行理由——要 runtime 證據（實跑重現）才算定案（2026-08-06 GA spinner 案教訓）。

## 打回與收工

- 任一 reviewer 打回 → 退回修復（重派或直改，依 lane）。修復輪指令紀律：帶測試的 major 一律要求附雙向變異輸出（移除修復→紅）；reviewer 的 MINOR 備註若指向輸入空間缺口或 30 秒可查證的邊界值，當場升級成明確要求，不放行帶病合併。
- **修復輪跨軸指派**：發給每個 reviewer 的複確認訊息附**全部指派項清單**（標明各項屬哪軸、由誰確認）——只給單軸自己的條目會造成資訊差誤報 scope creep。
- **重審與複確認一律 SendMessage 原 reviewer 續聊**（帶該 subagent 的 agent id；context 已熱、免全量重讀 repo）；原 reviewer 續聊失敗才開新 agent。
- **重跑範圍按嚴重度分層（2026-08-20 起）**：修的含 **MAJOR/BLOCKER** → 修完重跑**整條觸發鏈**（修復輪是新錯高發區，退件 log 實證：重構蒸發防護、修復再收 5 MAJOR）；修的**只有 MINOR** → 只重跑打回的那隻確認修復。
- **Mike 手測的差異重測**：修復含 MAJOR/BLOCKER 且碰前端檔 → 給 Mike「只需重測這幾條路徑」的差異清單＋該 fix 的 `git diff --stat`（檔名讓 Mike 可自行覆核大腦的判斷）；只修 MINOR 或純後端修復 → 不回頭找 Mike，沿用原手測結果。
- reviewer 全數通過 → 該 implementer **TaskStop** 收掉（派工 lane；reviewer 是 subagent，做完自行結束不需收）；記退件依全域迴饋迴路。
