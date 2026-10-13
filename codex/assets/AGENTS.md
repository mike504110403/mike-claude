# Mike 的 Codex 工作流

使用繁體中文，結論先行、短回報。先讀當前 repo 的 AGENTS.md 與必要的設定；工具與權限以本回合實際提供為準。不要假設全域 PROJECTS.md、helper、模型或 Claude 工具存在。

## 分流

純查詢直接回答。工程第一句說「走 /X，因為…；改動面：…」。

- /quick：一眼可界定的小改，主代理做。
- /solo：單一意圖、技術路線清楚的中型改動，主代理做。
- /feature：多個可獨立切片，或需專門審查的變更；只有獨立工作才派 native subagents。
- /bug：根因未知的故障，先重現/定位再選實作 lane。
- /mega：未決選型或多波工作，先解關鍵決策再逐波 /feature。

金流、認證授權、secrets、DB migration、全域配置或不可逆操作至少 /feature。升級立即宣告；降級先取得 Mike 同意。只載入當下需要的 skill，勿要求讀完所有技能。

## 工作與授權

開工固定任務範圍、基底、ownership 與驗收。私人交接與雷紀錄不進 Git，寫入前用 git check-ignore 確認 .codex/wip.md 與 .codex/ledger.md 被忽略；缺少時只在 git rev-parse --git-path info/exclude 回傳的檔案加精確條目（支援 worktree 的 .git 檔）。既有問題只登記 repo .codex/ledger.md；金流、認證或外洩問題另記 .codex/wip.md 待裁示，不擴大當前工作。新增影響面先附呼叫鏈的檔案/行號證據。

改動在 worktree。App 優先 managed worktree，明確指定 repo 記錄的基底；CLI 用 Git fallback。保留來源未提交工作。單 repo 一個主控 chat；沒有 self handoff。派工寫自足 brief，明確檔案 ownership 與勿覆蓋他人修改；並行取決於 runtime 額度與工作是否獨立。角色沿用父模型，唯讀角色派出前確認有效 sandbox，完成後由主代理親驗。

驗收對照實際 diff 與需求。後端提供適用測試/build；前端提供 typecheck、地端 API 環境與 Mike 手測；自動瀏覽器驗證依明確授權執行。地端不足時記驗證債與補驗方式；不得對預設正式 API 送出測試資料。金流/認證/secrets 加 security review，schema/migration 加 DB review。流程與審查按 verify/review-chain 載入。

驗收與 review 通過後，本地 commit，停在 push 前。push 必須有 Mike 明確授權且使用 /ship；推 repo 主幹前明確問。nginx、DB migration 執行前明確問。刪除與 reset --hard 先確認實際授權與影響。技術 sandbox 核准不等於任務同意；hook 不能代替人類批准。

禁止直接 rm -rf、force push、git clean -f、git branch -D、git worktree remove --force、git add . 或 -A/--all。精確逐檔 stage；讀清間接 script 的副作用。Hooks 是有限 guardrail，必須經 /hooks trust 才會執行，沒有執行證據不得宣稱防護 active。

未完成工作記 repo .codex/wip.md，交接含已驗與未驗項、回復/續作步驟及待裁示；全部完成時只提示新 chat，不增加持久交接檔。模型與 Context 的取捨依實際量測，不預設固定 cache 比例或圖片必須委派。


## 工程收尾

/feature 完成回報第一句包含 lane、結論與改動面，接著依序用五點：

1. **改了什麼**：列出實際變更。
2. **為什麼**：說明對應需求與理由。
3. **影響面**：指出受影響的模組、介面或工作流。
4. **驗證證據**：列出實際 tests、build/validate、review 結果與必要限制；未跑或未通過要明示。
5. **還可以做什麼**：給下一步建議，待授權事項明列，不自動擴大 scope。

五點後另附四項實際狀態，每項標「已／未／不適用」：commit（已提交才附 hash）、本地合併（目標 branch）、push（remote/branch；執行 push 後以 ls-remote 比對 hash 一致才能寫已推）、套用設定（適用時列部署目標與證據）。commit、本地合併、push 與套用設定各自獨立，不能用「完成」暗示其他階段已做或其他裝置已同步；詢問「推了嗎」不等於 push 授權。/quick、/solo 保留短段式回報例外。
