# windows/ — PC（Windows 11 原生）版

規則（`CLAUDE.md`、`skills/`、`agents/`）兩邊共用；**腳本與程式一律分流**：本目錄是 PC 專用副本，原則與 Mac 版相同，Mac 版（repo 根目錄）不受影響。改其中一邊時，另一邊要不要跟，逐案判斷。

不走 WSL、不用 tmux（2026-10-11 Mike 裁示）。終端用 WezTerm。

## 安裝（落地到 `~\.claude`）

前提：Claude Code 原生版、Git for Windows（Git Bash）、WezTerm。依賴用 winget 補：

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id jqlang.jq
winget install -e --id DEVCOM.JetBrainsMonoNerdFont
```

**winget 裝完先關掉終端重開**（PATH 才吃得到新裝的 python／jq；沒重開的話 `python` 會打到 Store stub），再開 Git Bash 執行（`$R` = 本 repo checkout；既有 `settings.json` 先備份，**不要動 `.credentials.json`**）：

```bash
R=~/src/mike-claude; C=~/.claude
cp $C/settings.json $C/settings.json.bak-$(date +%Y%m%d%H%M%S)
cp -R $R/skills/. $C/skills/ && cp -R $R/agents $C/
{ cat $R/windows/CLAUDE.pc-header.md; echo; cat $R/CLAUDE.md; } > $C/CLAUDE.md
cp $R/windows/settings.json $R/windows/statusline.sh $R/windows/statusline-dispatch.sh $C/
cp -R $R/windows/hooks $R/windows/bin $R/windows/statuslines $C/
cp $R/windows/wezterm.lua ~/.wezterm.lua
python -m venv $C/pdf-env && $C/pdf-env/Scripts/python -m pip install pymupdf4llm
```

寫死帳號名 `User` 的地方（帳號不同要改）：`settings.json`（hook、statusline 路徑）、`bin/pdf2md` 第 1 行 shebang、`bin/lint-rules` 的 memory 路徑 `projects/C--Users-User`。

`bin/mutate` 只支援從 Git Bash 執行：PowerShell 的 PATH 沒有 sed／patch／diff，跑到變異項目會失敗。

驗證：

```bash
python ~/.claude/hooks/test_bash_guard.py      # ALL PASS
bash ~/.claude/bin/lint-rules                  # PASS
bash ~/.claude/bin/tests/test_mutate_batch.sh  # 0 FAIL（i2 一項 SKIP）
```

### 選配：CC 以管理員執行（離座可操作，2026-10-12 Mike 裁示 UAC 方案 A）

UAC 視窗在安全桌面，CC 與手機都按不到。改成登入即以最高權限開 WezTerm，系統權限動作（安裝軟體、HKLM、系統 PATH、服務、帳號、防火牆、憑證、系統目錄、排程工作、防護設定等）由 `bash_guard` 的 `SYSTEM_ADMIN` 規則在 CC 內 ask；改 `~/.claude` 的 settings.json／hooks 也會 ask。

**代價（security review 2026-10-12，Mike 裁示接受才裝）**：
- CC 全程是管理員，hook 是唯一防線；先寫 `.ps1` 再執行之類「包一層」的指令 hook 看不進。
- 本帳號的 UAC 實質弱化：提權 WezTerm 已改讀管理員專用設定（`C:\ProgramData\wezterm-admin\wezterm.lua`）、shell 加 `-NoProfile`、工作只有管理員能 `/run`，但 claude 執行檔與 `~/.claude` 仍在使用者可寫目錄——任何以你身分執行的非提權程式改了它們，下次登入就以管理員執行。

```powershell
# 管理員 PowerShell 執行一次（跳一次 UAC）；改了 ~/.wezterm.lua 後要重跑才會同步到管理員設定
powershell -ExecutionPolicy Bypass -File $HOME\src\mike-claude\windows\admin-wezterm.ps1
schtasks /run /tn WezTerm-Admin   # 同一個管理員 PowerShell 裡跑，立刻開一個管理員 WezTerm
```

確認：管理員 WezTerm 裡跑 `net session`，不報「存取被拒」即是管理員。

## 與 Mac 版的差異

| 檔案 | 差異 | 原因 |
|---|---|---|
| `settings.json` | hook 指令用 `python` + 絕對路徑；bash_guard matcher 加 `PowerShell`；statusline 用 Git Bash 完整路徑；`env.PYTHONUTF8=1` | `python3` 在 Windows 是 Store stub；`bash` 會打到 `System32\bash.exe`（WSL stub）；Python 預設 cp950 |
| `settings.json` | model `opus[1m]` | Mike 2026-10-11 裁示（見 `CLAUDE.pc-header.md`） |
| `settings.json` | 拿掉 claude-pet、cmux、graft hook；拿掉 gitkraken／swift-lsp／gopls-lsp plugin 與 marketplace；allow 拿掉未移植工具（`phase`、`trust-dir`、graft 4 條）；`python3` allow 改 `python`；拿掉空的 `footerLinksRegexes` | 工具或路徑在 PC 不存在 |
| `settings.json` | 保留 `autoUpdatesChannel: "latest"` | PC 原本 settings.json 就有，移植時沿用 |
| `hooks/bash_guard.py` | 加 `Remove-Item -Recurse -Force`（含縮寫）、`rd/del /s /q`（含 `/s/q` 連寫、引號包住）硬擋；`-Recurse`、`gci -Recurse \| Remove-Item`／`ForEach-Object { Remove-Item }` 詢問；Windows 的詢問排在所有 deny 之後；rm 旗標不分大小寫、認長旗標與縮寫（`-fR`、`--recursive --force`）；`SYSTEM_ADMIN` 系統權限動作詢問（安裝軟體與安裝檔、HKLM／HKCR／HKU、系統 PATH、服務、帳號、防火牆、根憑證、系統目錄寫入、排程工作、防護與開機設定）；改 `~/.claude` settings.json／hooks 詢問 | PowerShell 工具也要守；詢問不能蓋掉 stash／clean／npx 的硬擋；CC 以管理員執行時 UAC 不把關（Mac 版 rm 漏擋未修，見 ledger） |
| `hooks/file_guard.py` | migrations 路徑也認 `\`；系統目錄（`C:\Windows`、`Program Files`、`ProgramData`）與 `~/.claude` settings.json／hooks 詢問 | Windows 路徑；CC 以管理員執行時 hosts 等系統檔無 UAC 把關 |
| `hooks/format_on_save.py` | 用 `shutil.which` 完整路徑叫 formatter | prettier／npx 是 `.cmd` shim，裸名稱叫不起來且錯誤被吞 |
| `hooks/report_clause.py` | stdout 強制 UTF-8 | 預設 cp950，中文條款送到 Claude 變亂碼 |
| `hooks/test_bash_guard.py` | 路徑相對本檔、`sys.executable`、失敗時 exit 1；加 PowerShell／cmd 案例、review 回歸案例，另補 force push／stash／npx 等 Mac 版沒測的既有規則 | Mac 版寫死 `/Users/mike` 路徑；PC 新規則要有探針 |
| `statusline.sh` | `bc` 改 `awk`；jq 合併成一次呼叫（約 1s → 0.5s） | Git Bash 無 `bc`；Windows 開 process 貴 |
| `bin/pdf2md` | shebang 指 `pdf-env/Scripts/python.exe`；stdout 強制 UTF-8 | venv 結構與 cp950 |
| `bin/lint-rules` | memory 路徑 `C--Users-User`；`python`；跳過 `skills/synced` | Claude Code 的專案目錄名隨帳號路徑；`skills/synced` 是內建 skills 同步快取，不是 skill |
| `bin/mutate` | 偵測 GNU sed（`sed -i` 不帶 `''`）；`python` | Git Bash 是 GNU sed |
| `bin/mutate-batch.py` | 找 Git Bash（排除 WSL stub，找不到明確報錯）；Windows 用 `taskkill /T /F` 收行程樹；GNU sed 偵測；清單檔內 `/c/...` 路徑經 `cygpath` 轉換；cygpath／sed 不在 PATH 時不崩 | WSL stub、無 `killpg`、MSYS 路徑、從 PowerShell 呼叫 |
| `bin/tests/` | i2 的 exit 斷言在 Windows SKIP；dogfood 清單移除 3 條 POSIX 訊號變異、M-shell-not-bash 改守 WSL stub | MSYS 送不了 SIGINT 給原生行程。已知缺口：`_kill_group` 的 taskkill 分支無測試守 |
| `wezterm.lua` | 新增 | Mac 用 cmux／Ghostty（見 `terminal/mac/`），PC 用 WezTerm 對齊同樣的配色、字型與 workspace 手感 |

沒帶的 Mac 工具：`cmux-claude-launcher`、`cmux-pet-notify.sh`、`phase`、`ccbar`、`trust-dir`、`usage-diag`、`hooks/cmux_pane_cleanup.sh`、claude-pet、graft hooks、`tmux.conf`。

`.gitattributes` 讓本目錄一律 LF——Git for Windows 預設 `core.autocrlf=true`，CRLF 會讓 shebang 失效。
