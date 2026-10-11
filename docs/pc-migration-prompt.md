# 任務：把 Mike 在 Mac 上的 Claude Code 工作流移植到這台 Windows PC

你在 Mike 的客廳 PC 上（Windows 11 家用版 25H2，帳號 `User`，管理員）。Mike 平常在 Mac 上用 Claude Code + cmux（Ghostty 核心的終端），整套習慣都版本控制在公開 repo：
https://github.com/mike504110403/mike-claude （main 分支，與 Mac 現況同步）

目標：讓這台 PC 上的 Claude Code 用起來「跟 Mac 一樣的大腦、一樣的規矩、一樣的手感」，但以 **Windows 原生**實現。

## 環境事實（已驗證，不用再查）

- Claude Code 原生版 2.1.296 已裝在 `C:\Users\User\.local\bin`，已用 Mike 的訂閱登入。
- Git for Windows 已裝（Git Bash 可用）；winget 可用。
- WezTerm 20240203 已裝在 `C:\Program Files\WezTerm`，作為 cmux 的替代品。
- **沒有 WSL、沒有 tmux**，也不要裝。不要建議走 WSL 路線（Mike 已裁示）。
- Python、Node 是否已裝：自己查，缺了用 winget 補（`Python.Python.3.12`、`OpenJS.NodeJS.LTS`）。

## 鐵則

1. **不要動登入憑證**：`C:\Users\User\.claude\.credentials.json`（以及任何 auth 相關檔）絕不覆蓋、不刪除。
2. **不要直接 clone 到 `~\.claude`**。先 clone 到暫存目錄（例如 `C:\Users\User\src\mike-claude`；本檔就在該 repo 的 `docs/pc-migration-prompt.md`），再把白名單資產複製過去。既有同名檔先備份成 `<名稱>.bak-<時間戳>`。
3. repo 的 `install.sh` 是給 macOS/Linux + tmux 的，**不要直接跑**；照它的白名單邏輯手動移植。
4. 每一大步做完都要實際驗證（跑一次、看輸出），不要只說「應該可以」。
5. 刪除任何東西前先列給 Mike 看。
6. 對 Mike 說話用繁體中文，技術名詞保留英文；結論先講、預設簡短、不用 emoji。

## 要帶過來的東西

### A. 大腦規則與流程（核心，原樣帶）
- `CLAUDE.md` → `~\.claude\CLAUDE.md`。保留全部規則（分流表、lane、不變式、回應風格、commit/push 紀律）。只做兩種修改：
  - 刪掉或註記純 Mac 專屬的段落（cmux pane、tmux、`~/.claude/PROJECTS.md` 代號表、`/local-stack` 起地端棧等這台 PC 沒有的東西）——在檔頭加一行「PC 版：以下 X、Y 段不適用」即可，不要大改語意。
  - 路徑 `~/.claude/...` 在 Windows 上照樣成立，不用改。
- `skills\` 全部、`agents\` 全部 → 原樣複製。不適用的 skill（`lottery-proddata`、`local-stack`、`statusline-switch` 等依賴 Mac 專案或 tmux 的）照樣放著，Mike 只是不會在 PC 觸發它們。

### B. settings.json（要改寫，不能原樣複製）
Mac 版的重點設定，移植時保留：
- `language: "chinese"`、`theme: "dark-ansi"`、`tui: "fullscreen"`、`effortLevel: "high"`、`model: "opus[1m]"`
- `attribution: { commit: "", pr: "", sessionUrl: false }`（commit/PR 不加署名）
- `permissions.defaultMode: "bypassPermissions"`、`skipDangerousModePermissionPrompt: true`
- `remoteControlAtStartup`、`inputNeededNotifEnabled`、`agentPushNotifEnabled` 都是 true
- `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"`（但 Windows 無 tmux → teammate 只會 in-process，**不要**設 tmux 相關 teammateMode）

Hooks：Mac 版指令是 `python3 ~/.claude/hooks/xxx.py`。在 Windows 上：
- **要帶**：`bash_guard.py`（擋 `rm -rf`、force push、`git add .` 等危險指令）、`file_guard.py`、`format_on_save.py`、`report_clause.py`、`send_guard.py`。把指令改成這台機器能跑的形式（確認是 `python` 還是 `py`，以及 Claude Code 在 Windows 跑 hook 用的是哪個 shell），並逐支用假輸入實測會擋／會放。若 hook 內有 macOS 專屬假設（路徑、`sips`、`osascript`），改成跨平台或跳過該分支。
- **不要帶**：`claude-pet` 系列（`/Users/mike/claude-pet/...`）、`cmux_pane_cleanup.sh`、graft 相關 hook（`helpers/graft-hooks-global.cjs`，除非 Mike 之後在 PC 裝 graft）。

### C. Statusline
Mac 用 `statusline-dispatch.sh` → `statuslines/mike`（bash）。在 Windows 上二選一，先做最簡可用版再問 Mike：
- 用 Git Bash 跑原腳本（看依賴 `jq`、`bc` 是否可補）；或
- 改寫成 PowerShell 版，顯示同樣資訊（模型、目錄、git 分支、context 用量）。

### D. bin 工具
`bin\` 裡多是 bash/python 小工具。只移植**跨平台有意義**的：`pdf2md`（讀 PDF 用，要 Python 依賴）、`lint-rules`、`mutate`。`cmux-*`、`phase`、`ccbar`、`trust-dir`、`usage-diag` 先跳過，列清單告訴 Mike 哪些沒帶、為什麼。

### E. 終端手感：WezTerm 設定（對齊 Mac 的 Ghostty/cmux）
寫 `C:\Users\User\.wezterm.lua`，對齊以下 Mac 設定（原檔在 repo `terminal/mac/`：`ghostty.config` 字型／間距／透明、`cmux-theme.ghostty` 主題、`cmux.json` cmux 行為與註解裡的設計理由；背景圖未入 repo，WezTerm 先不設背景圖）：
- 字型 **JetBrainsMono Nerd Font**（沒裝就用 winget 或從 nerdfonts.com 裝），字級 Mac 上是 12（再乘 cmux 全域 120%）；Windows 先試 12，請 Mike 看了再調。
- 行高 +15%（`line_height = 1.15`）。
- 配色 **Catppuccin Macchiato**（WezTerm 內建 `color_scheme = "Catppuccin Macchiato"`），背景 `#1e2030`。
- 背景透明 0.85 + 模糊（Windows 用 `win32_system_backdrop = "Acrylic"`）。
- 聚焦 pane 邊框/強調色用 mauve `#c6a0f6`；非聚焦 pane 稍微變暗（`inactive_pane_hsb`）。
- 預設 shell：PowerShell（`default_prog`）。
- cmux 的工作習慣是「一個 workspace＝一個任務，開新 workspace 自動進 `claude`」、多個 pane 並排看 agent。用 WezTerm 實現：
  - leader key（建議 `Ctrl+a`），leader + `|` 左右分割、leader + `-` 上下分割、leader + 方向鍵切 pane、leader + `z` 放大單一 pane。
  - leader + `w` 列出／切換 workspace（`ShowLauncherArgs { flags = "FUZZY|WORKSPACES" }`），leader + `n` 開新 workspace 並在其中直接啟動 `claude`。
  - 分頁列顯示 workspace 名稱。
- 寫完要求 Mike 開 WezTerm 實際看一眼，依回饋調整；設定檔改了 WezTerm 會自動重載。

### F. 不要帶的東西（明確排除）
- Mac 的 memory（`~/.claude/projects/*/memory/`）、`PROJECTS.md`、`ledgers/`、`wip.md`、`plans/`：都是 Mac 專案狀態，PC 用不到。
- claude-pet、cmux 專屬腳本、tmux.conf。
- 任何 Mac 絕對路徑（`/Users/mike/...`）——移植後 grep 一遍確認 `~\.claude` 底下的設定與 hook 沒殘留會被執行到的 Mac 路徑。

## 交付時回報

1. 帶過來的清單、改寫了什麼、跳過了什麼（附理由）。
2. 每支 hook 的實測結果（擋什麼、放什麼）。
3. `claude doctor` 輸出無錯誤。
4. 開一個新 session 自我驗證：用繁中回答、結論先行；跑一個 `rm -rf C:\tmp\不存在` 之類的指令確認 bash_guard 會擋。
5. 尚未完成或需要 Mike 裁示的事項（附建議答案與各選項後果）。
