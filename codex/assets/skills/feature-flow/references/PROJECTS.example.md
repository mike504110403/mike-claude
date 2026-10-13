# 本機專案路由範本

全域 registry 放在 CODEX_HOME（未設才 ~/.codex）下的 `PROJECTS.local.md`；repo 內的 fallback 放在 `.codex/projects.local.md`，大小寫須依此精確命名。填本機真值，不提交；位於 Git repo 的真值檔先設精確 ignore，Git repo 外的 registry 留本機即可。路徑在每台重填，命令與主幹再向 repo 本身核實。下列 placeholders 不是可直接執行命令。

| 專案代號 | 本機 repo 絕對路徑 | repo 主幹 | remote | repo 規則/宣告 |
|---|---|---|---|---|
| <project-code> | <local-absolute-repo> | <verified-main-branch> | <verified-remote> | AGENTS.md / <existing-declaration> |

## 驗證指令與已知基線

| 專案代號 | check | 指令 | 環境/工具前提 | 已知紅/歸屬 | 核對 commit | 輸出位置 |
|---|---|---|---|---|---|---|
| <project-code> | build/typecheck/appropriate-test | <verified-command> | <available-local-runtime> | <failure-family-or-none> | <verified-hash> | <local-log-path> |

已知紅只決定歸屬，不能豁免必要驗證。不要把 auth、secrets、帳號或機器專屬 port 寫進版控範本。
