# Mike 的 Codex 工作流

繁體中文、答案先行、短回報。先讀 repo AGENTS 與必要宣告，能力以本回合暴露的 tools、sandbox、approval 為準；不要假設全域 registry/helper 或固定模型存在。

## 分流

純問答/查詢直接答；「該不該/要不要」決策用 /office-hours；收斂/續作用 /wip。已授權且已形成共識的裁決引用出處直接做，不重問、不為已知答案硬問固定題數。工程第一句「走 /X，因為…；改動面：…」。

- /quick：小而可界定，主代理做；/solo：路線清楚的中型單線，主代理做。
- /feature：可獨立切片、跨 repo 或需專門審查；有獨立工作才派 native subagents。
- /bug：未知根因先定位；/mega：未知選型/多波先解關鍵決策再逐波 /feature。
- /mvp：新專案未上線、無真實用戶、無真實資料時一律走它；本檔其餘全域規則以 /mvp 覆寫清單為準，畢業後回上列 lane。

金流、認證授權、secrets、DB migration、全域配置或不可逆操作至少 /feature；升級即宣告，降級先取得同意。只載入當下需要的技能，缺技能/工具明示 fallback與限制，不假稱成功。代號/跨裝置路由按 /feature-flow 本機範本，不依賴不存在的全域 PROJECTS。

## 範圍與紀錄

/feature 的 ≤5 行邊界卡、未決 A/B、已授權共識例外及派工細節住該技能。裁示攢批，只有阻塞關鍵路徑即時問；可逆純 UI 呈現取捨已預授權。重大/難回頭/有真實取捨的決定留既有 ADR，無則 docs/adr。

既有問題不擴當前 scope，只記 repo .codex/ledger.md；金流/認證/外洩另在 .codex/wip.md 待裁示。新增影響面先有 producer/consumer 呼叫鏈 file:line。裁示前提被本次改動打破就重新評估，不能把舊 accepted risk 當永久豁免。

私人 wip/ledger/rejection-log、projects.local.md 不進 Git。寫前 git check-ignore 核實精確檔；缺 ignore 用 git rev-parse --git-path info/exclude 回傳檔加精確條目，支援 worktree .git 檔，不覆蓋既有 excludes。CODEX_HOME 下私人 PROJECTS.local.md 留在本機；public ADR/範本/可攜規則才版控。

## 執行與驗收

主 checkout 保持 repo 已核實主幹；先 /sync-dev fetch/ff-only，保留 dirty/ahead 工作。改動在 worktree，多實作者分開，整合主控串行；App managed worktree 與 detached HEAD 保存按 /feature-flow，不 self handoff。派工自足 brief及唯讀影子與工人並行，BLOCKER 才停依賴工作，runtime 額度不足明示 fallback。

證據與驗收住 /verify，review 觸發與複審住 /review-chain。後端適用 tests+build；前端 typecheck+地端 API+Mike 手測與 review 並行且皆過。自動瀏覽器驗證需明確授權，不能在預設正式 API 送測試資料；依賴/工具不足記驗證債。金流/付款/認證/secrets 加 security review，schema/migration 加 DB review。

驗收/review 過才 commit；push 另 /ship，必須 Mike 明確授權，主幹推送前明確問。「推了嗎」是查狀態。nginx/DB migration 執行先明確問；刪除/reset --hard 核實實際授權及影響。Sandbox 核准不等於任務同意，hook 不能合成人類批准。

禁止直接 rm -rf、force push、非 dry-run git clean、branch -D、forced worktree remove、git add .或-A/--all、裸 npx（不得臨時下載）；禁止修改 stash（push/save/pop/apply/drop/clear/branch 等），唯讀查詢可用。逐檔 stage，間接 scripts先讀副作用。Hooks 是有限 guardrail，須 /hooks trust，不以檔案存在宣稱已生效。

續作撞車檢查、保存與本需求清理依 /wip 和 /feature-flow。未結裁示/accepted risks 先留 ADR，不能廣泛刪 memory、別人的檔或共享產物。模型/Context依實際量測，不強制圖片委派或固定 cache 比例。

## 工程收尾

/feature 完成回報第一句包含 lane、結論與改動面，接著依序用五點：

1. **改了什麼**：列出實際變更。
2. **為什麼**：說明對應需求與理由。
3. **影響面**：指出受影響的模組、介面或工作流。
4. **驗證證據**：列出實際 tests、build/validate、review 結果與必要限制；未跑或未通過要明示。
5. **還可以做什麼**：給下一步建議，待授權事項明列，不自動擴大 scope。

五點後另附四項實際狀態，每項標「已／未／不適用」：commit（已提交才附 hash）、本地合併（目標 branch）、push（remote/branch；執行 push 後以 ls-remote 比對 hash 一致才能寫已推）、套用設定（適用時列部署目標與證據）。commit、本地合併、push 與套用設定各自獨立，不能用「完成」暗示其他階段已做或其他裝置已同步；詢問「推了嗎」不等於 push 授權。/quick、/solo、/mvp 保留短段式回報例外。
