# Codex 原生工作流

這是 `~/.claude` repo 中獨立版控的 Codex package，Python 3.9+、標準庫，部署命令針對 macOS/Linux，不下載依賴。來源與部署分離：source 是 `codex/assets/`；安裝只管理 AGENTS.md、這套 skills、native agents、專用 `workflow/mike/hooks/` 和合併後的 hooks 定義。既有 config.toml、模型、MCP、auth、sessions 和 runtime state 不會複製或修改。

## 原生適配

| 原工作紀律 | Codex 的執行方式 |
|---|---|
| 五條 lane 與範圍鎖定 | 短 skills 按需載入；主代理直接完成小/單線工作 |
| 派工與審查 | Native subagents，TOML 角色沿用父模型；只有獨立切片才派工，額度依 runtime |
| Worktree | App managed worktree 優先，指定已核實基底；CLI 用 Git fallback，保留來源 dirty 狀態 |
| 驗收與 review | 固定基底的 diff+spec，主代理親跑適用 checks，再原生 reviewer/行內回饋 |
| 危險操作與批准 | Native sandbox/approval，加有限 hooks；技術權限不等於 Mike 的任務同意 |

`worker` 與 `explorer` 是本套刻意提供的 ownership/唯讀角色 profile，會覆蓋同名 built-in；沿用父模型。唯讀 reviewer 的 TOML 是角色預設，指令也禁止修改。父回合 live sandbox/approval override 可能覆蓋角色預設；派工時核實有效權限，不視 TOML 為絕對隔離。App 不做 self handoff，也不把 subtasks 變成 sidebar user chats。工具以當回合暴露的 API 為準，不依賴 Claude helper 或固定模型名。

## 完成回報與設定狀態

/feature 的五點收尾格式以來源 [assets/AGENTS.md「工程收尾」](assets/AGENTS.md#工程收尾) 為唯一規則；feature skill 引用全域 AGENTS 的該節，拆開部署後仍可使用。/quick、/solo 保留短段式例外。回報依實際 Git 狀態與執行證據，分別說明 commit、本地合併、push、套用設定；只有 push 後 remote hash 核對一致才能寫已推。

來源 repo `~/.claude/codex/` 的提交或本地合併不代表遠端已更新，也不代表已套用到 Codex home/skills 目標。套用設定須實際執行安裝並核對部署結果，hooks 還需 review/trust；回報不得假設其他裝置已同步。詢問 push 狀態不改變既有授權要求。

## 安裝與檢查

本套包含 40 個 skills 與 6 個 native agent profiles。對照、原生替代與裝置前提見 [MIGRATION.md](MIGRATION.md)，清單由 [migration.json](migration.json) 與 validator 核對。可攜 skills 不代表外部工具、地端棧、帳號或資料副本已建立。

在 source repo 執行：

```sh
python3 codex/validate.py
python3 -m unittest discover -s codex/tests -v
python3 codex/install.py
python3 codex/install.py --codex-home /path/to/codex-home --skills-dir /path/to/skills
python3 codex/install.py --codex-home /path/to/codex-home --skills-dir /path/to/skills --apply
```

預設 dry-run：完整 preflight、不建立目錄、不備份、不寫檔。CODEX_HOME 可決定預設 Codex home，skills 預設 `~/.agents/skills`。現有同名檔案即使 bytes 相同，第一次安裝也拒絕，避免靜默認領。

需要替換既有資產時，先檢查預覽，再明確使用：

```sh
python3 codex/install.py --replace-existing
python3 codex/install.py --replace-existing --apply
```

替換只覆寫本套對應檔案，同名 skill 內其他 resources 保留。修改過的 managed assets 預設拒絕；`--replace-existing` 允許明確替換並備份。hooks.json 中未知群組與 metadata 保留，可能重複或存在 legacy 不相容時提示，請自行透過 `/hooks` 檢視；不刪除他人的 guard。已知自己上一版群組用 manifest 精確匹配才更新；手改/刪除/重複後拒絕，要求先調解。重跑相同來源 idempotent。

所有 source/target/JSON/collision/symlink 檢查先完成才寫入，source/target 不可重疊。Namespace 比對保守採 casefold 並核對既存 endpoint/祖先的 samefile identity；即使是大小寫敏感檔案系統，也拒絕大小寫 alias 目標。Codex home 與 skills root 使用分開 namespace。寫入、還原與 rollback 都採單檔 atomic replace；temporary 從建立起為 0600，替換保留既有 mode，receipt 記錄原/部署 mode，還原前核對目標 mode。新 hooks.json/manifest 為 0600，source assets 預設 0644。失敗回復當次已寫檔案；空目錄與備份保留供檢查。這不是抵禦同時惡意更換 symlink 的 transaction，安裝/還原期間請勿並行改同一組目標。

部署的 hook command 指向 target 中 Python script，使用安裝時的 Python 絕對路徑；移動 source 不影響 hooks，該 Python runtime 仍需存在。安裝器不配置或啟用模型/MCP/permissions。

## 備份與還原

每次有變更會輸出 `Backup index`，位於 target `workflow/mike/backups/<id>/index.json`。目錄 0700、receipt/備份 0600。只備份被改的 workflow 檔與 hooks 定義，不掃描/備份 auth/state；hooks 命令可能有個人資訊，receipt 不應提交。

```sh
python3 codex/install.py --restore /path/to/codex-home/workflow/mike/backups/ID/index.json
python3 codex/install.py --restore /path/to/codex-home/workflow/mike/backups/ID/index.json --apply
```

還原預設預覽；`--apply` 恢復原 bytes、刪除當次新增且 hash 未變的 package 檔。只有 receipt 所列目標會還原，改過或不見的 assets 會拒絕避免蓋掉新工作。hooks 只撤回當次 package 群組並恢復原 package 群組，保留安裝後新增未知 hooks。舊 hooks.json 快照只供查閱，不整檔覆蓋；空 hooks table、空目錄與 receipts 可保留，不是全面 uninstall。多次更新從最新 receipt 逆序還原。備份是本機可信操作記錄，請保留原位置並避免手改。

## Hooks 的實際邊界

安裝完成仍須在 Codex CLI 用 `/hooks` 檢視新/變更 definitions、review 並 trust；新版 hash 需重新 trust。App 依其可用介面管理；不能因檔案存在就宣稱防護 active。安裝不修改 trust，也不使用 bypass。

PreToolUse 吃 stdin JSON，canonical `Bash` 與 `apply_patch` 的 `tool_input.command`；Edit/Write matcher aliases 受支援，亦接受 legacy file_path input。成功只回 `{}`，保留 native approval；拒絕回 supported deny，從不回 unsupported ask。普通 push 可通過，仍須 Mike 明確授權 /ship。nginx/migration 人類 gate 在 AGENTS/skills，不能由 hook 產生批准。

Guard 阻擋直接 rm recursive+force、force/mirror push（含 `+refspec`）、destructive git clean、branch -D、forced worktree remove、git add ./-A/--all、stash 變更操作與 npx，接受 Git global options；stash list/show 可讀。git clean dry-run（含 -nf）可以通過；所有非 dry-run clean 視為有刪除風險，因 repo 可以設定 requireForce=false。真實未引用 newline 視為 command boundary，引用內 newline 與 escaped continuation 保留 shell 意義；clean 的 -- 後 pathspec 與 -e/--exclude 值不當作 dry-run options。patch 解析 multi-file Add/Update/Delete/Move，檢查 traversal、cwd escape、symlink 與 `.env` 真值/credentials/auth/private keys、大小寫一致的 `.codex` policy 與 deployed custom home 自保；核對實際 file/ancestor identity 及 hook hardlinks；`.env.example/sample/template` 可改。畸形輸入與 unsafe patch 會 deny。

這是有限 direct-command guardrail，**不是完整 shell 安全邊界**。變數、別名、wrapper、shell scripts、Python/其他語言 I/O、MCP 與 Bash 寫敏感檔等繞行不保證攔截；需靠 sandbox、approval、任務授權與審查。讀清間接 scripts 才執行。

PostToolUse 只 format 已存在的 changed files，包括 Vue，delete 不執行，move 只 format 仍存在的目標。使用現有 gofmt 或 repo cwd 的 node_modules/.bin/prettier，允許 formatter symlink 解析在 cwd 內；不使用 npx、下載或 global prettier。從子目錄開 Codex 時，只會尋找該 cwd 中的 local formatter，缺工具明確回報；失敗輸出可見的 block feedback 與 exit 2，無法撤回已完成 edits。changed file 不跟 symlink，formatter 不跨 cwd 界限。

## 官方契約

本版核對日期：2026-10-14。[Hooks](https://learn.chatgpt.com/docs/hooks)、[native subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)、[managed worktrees](https://learn.chatgpt.com/docs/environments/git-worktrees)、[code review](https://learn.chatgpt.com/docs/code-review?surface=app)、[skills 指令設計](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)。Python 3.9 缺 tomllib 時 validator 使用本套有限 schema，不假裝提供通用 TOML parser；Python 3.11+ 另用 tomllib 核對。
