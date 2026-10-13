# 移植對照與裝置前提

本套完整清單住 [migration.json](migration.json)，validator 核對 skills、agents、Python 編譯與所有資產 Markdown 資源引用。ported 保留用途及必要約束；native-adapted 改用 Codex 機制。兩者均不代表外部服務、每種情境或每個平台已實跑。

## 核心對照

| 功能 | Codex 執行方式 |
|---|---|
| 分流、五點及四項狀態 | 全域 AGENTS；小改/單線由主代理完成 |
| brief 防錯 | 自足八欄、按需 checklist、brief-reviewer 影子並行 |
| 審查打回 | code/security/db 原生角色、固定 base/spec、嚴重度決定重審範圍 |
| Git 完整流程 | sync-dev + feature-flow；repo 記錄主幹，基底前進後整合重驗 |
| 前端實測 | verify + local-stack + browser-tools + vue-dev；Mike 手測與 review 會合 |
| API collection | API 改動且已有 bruno/ 才自動 bruno-sync 增量同步 |
| 決策及留存 | office-hours、ADR、wip、ledger、rejection log；已有共識不重問 |
| 操作保護 | 有限直接指令 guard + native sandbox/approval + 人類任務同意 |
| push | /ship 明確授權後普通 push，ls-remote 核對 hash |

## 裝置要補的前提

- 安裝器只管理自己的來源資產；40 skills 的 references/scripts 也一起部署，既有 skills 內其他資源保留。專案、外部依賴、MCP/plugin 連線與帳號各由裝置設定，不因 Git pull 或匯入自動建立。
- Package 是 Python 3.9+ 標準庫；外部工具可要求更高版本。依各 skill preflight 查可用工具、版本與 lockfile，不自動下載。
- 專案代號、本機路徑與地端宣告依模板或明示設定；真實帳密、資料快照與本機 override 不進 Git。Repo AGENTS 可保存共享主幹、驗證指令與基線；基線錯誤不等於驗收通過。
- local-stack 沿用 repo 明確宣告，兩個來源衝突時調解。lottery-proddata 只攜帶地端副本政策，連線、版本、鮮度與差異每次核實；不帶來源裝置的真值。
- PDF 需要本機 pymupdf4llm；Playwright 需要既有 runner/browser；graft 需要工具與有效圖；crawl4ai 需要既有 crwl。缺依賴明示，不能宣稱該能力已可執行。
- Hook 定義仍須目標 Codex review/trust，安裝不等於 active。有限 guard 不覆蓋任意 wrapper、MCP 或其他語言 I/O。

## 原生替代與限制

| Claude 角色 | Codex 對應 |
|---|---|
| implementer | worker，明確 ownership |
| scout-read／scout-trace | explorer，派工區分取值或呼叫鏈判讀 |
| janitor | 明確切片的機械工作；不強制多建常駐角色 |
| brief／code／security／DB reviewer | 各自 native TOML profile |
| ui-reviewer | on-demand auto-e2e／browser 工作流；本套未設獨立 TOML |

- [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents) 取代 Claude teammate/pane；依當回合工具與額度調度，沿用父模型，核實有效 sandbox。
- [Managed worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees) 優先，CLI 用 Git fallback；本機忽略檔是否會複製依工具與 repo 設定核實，不自動拷貝 secrets。
- CLI statusline 使用 [官方 /statusline](https://learn.chatgpt.com/docs/cli/slash-commands) 及 tui.status_line。App 使用原生進度及 commentary；不承諾 Claude 的 shell dispatcher 或 phase footer。
- 不搬 trust-dir、cmux 幾何、SendMessage 參數 guard、固定模型/cache 比例或強制圖片委派假設。
- Graft 用按需建圖與過期查核；原 Claude lifecycle 接線未照搬，不宣稱自動 Stop hook 重建已啟用。通知、寵物及 UI 偏好交各裝置原生功能。
- 原 mutate helper 改為保留原 bytes 的手工變異流程；mobile audit 改為原生取證與本機可用 scanners，不附舊四個簡單 regex scanner。兩者保留驗證目的，不宣稱原腳本已部署。
- macOS 資產檢查與臨時 fixtures 是本套證據範圍；Linux 未在本輪實跑，Windows 已補原生命令、ACL、備份還原與 formatter fixtures，邊界見 README Windows 節。實體 symlink privilege 與目標 Codex hooks trust/實際觸發仍須分別核實，Claude windows/ 不等於 Codex Windows 支援。
