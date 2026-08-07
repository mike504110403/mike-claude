# mike-claude

Claude Code + tmux 的個人工作流設定：lane 化派工流程（quick/solo/feature/bug/mega）、review agents、防護 hooks、tmux 狀態列整合 phase 顯示、自訂 statusline。這份 repo 是可攜的安裝來源，任何人都能一鍵裝到自己的機器上並客製化。

## 一鍵安裝

macOS 或 Linux/WSL：

```bash
curl -fsSL https://raw.githubusercontent.com/mike504110403/mike-claude/main/install.sh | bash
```

腳本會：
- 檢查並（在 macOS 上透過 Homebrew）補齊依賴：`git`、`tmux`、`python3`、`jq`、`bc`
- 把工作流資產裝進 `~/.claude`（`CLAUDE.md`、`settings.json`、`statusline.sh`、`skills/`、`agents/`、`hooks/`、`bin/`）
- 裝 `~/.tmux.conf`（含 tmux 狀態列的 phase 顯示）
- 對既有同名檔案/目錄自動備份成 `<名稱>.bak-<時間戳記>`，不覆蓋、不刪除

裝完機器是全新 `~/.claude`（未曾裝過）時，來源會直接 `git clone` 落地，之後要更新只需：

```bash
cd ~/.claude && git pull
```

若 `~/.claude` 已存在（例如手動建立過或裝過其他設定），腳本只會複製上面列的白名單資產，其他既有檔案完全不動。

### 環境變數

| 變數 | 用途 | 預設 |
|------|------|------|
| `INSTALL_NAME` | 把落地後 `CLAUDE.md` 裡的「Mike」全部換成你的名字 | 不設就保留原文，裝完提示手動改 |
| `MIKE_CLAUDE_FULL` | 設為 `1` 時安裝完整版 `settings.json`（含 `permissions.defaultMode`、`skipDangerousModePermissionPrompt`、`model` 三鍵） | 不設 = 安裝前先過濾掉這三鍵（見下方安全預設） |
| `MIKE_CLAUDE_REPO` | 安裝來源覆寫（git URL 或本地路徑）；只要設了這個變數，一律真的 `git clone` 該來源，不會用本機捷徑；開發/測試用 | 不設時：若腳本本身在 repo checkout 內（同目錄有 `.gitignore` 與 `skills/`）直接用該 checkout、跳過 clone；否則 clone `https://github.com/mike504110403/mike-claude.git` |

範例：

```bash
INSTALL_NAME=小華 curl -fsSL https://raw.githubusercontent.com/mike504110403/mike-claude/main/install.sh | bash
```

## 內容物

- **Lane 化工作流 skills**（`skills/`）：quick / solo / feature / bug / mega 五條派工 lane，加上 brief、verify、review-chain 等流程積木
- **Review agents**（`agents/`）：code-reviewer、security-reviewer、db-reviewer、ui-reviewer 等
- **防護 hooks**（`hooks/`）：危險指令攔截、敏感檔案攔截、回報格式檢查、存檔自動 format
- **tmux 狀態列 + phase 顯示**（`tmux.conf`、`bin/phase`）：目前工程進度即時顯示在 tmux 狀態列
- **statusline**（`statusline.sh`）：Claude Code 內建狀態列客製化

## 需求

- **macOS**：需要 [Homebrew](https://brew.sh)（腳本不會幫你裝 Homebrew 本身，缺少時會印出官方安裝指令並中止，請自行安裝後重跑）
- **Linux / WSL**：缺依賴時腳本會印出 `sudo apt install ...` 指令，需自行執行後重跑（腳本本身不會呼叫 `sudo`）

### Windows 使用者

tmux 只存在於 WSL（Windows 原生沒有 tmux），Claude Code 與這整套工作流都必須跑在 **WSL 內部**，不是 Windows 原生終端機。

1. 安裝 WSL（PowerShell 系統管理員模式）：
   ```powershell
   wsl --install
   ```
2. 重開機後進入 WSL（預設 Ubuntu），在 WSL 內部照上面的一鍵安裝指令執行。
3. Claude Code 也要裝在 WSL 內部執行，不要在 Windows 原生終端機跑。

## 安全預設

一鍵安裝**預設會過濾掉** `settings.json` 裡的：

- `permissions.defaultMode`
- `skipDangerousModePermissionPrompt`
- `model`

這三個鍵是 Mike 自己機器上的個人化設定（跳過權限確認、指定特定模型），對其他人來說風險與需求都不同，所以預設拿掉，改用 Claude Code 的預設行為。想要一字不改裝進 Mike 的完整設定（風險自負），安裝時加上：

```bash
MIKE_CLAUDE_FULL=1 curl -fsSL https://raw.githubusercontent.com/mike504110403/mike-claude/main/install.sh | bash
```

## 更新

乾淨安裝（`~/.claude` 本身就是這個 repo 的 clone）的機器：

```bash
cd ~/.claude && git pull
```

由於安裝時 `settings.json` 已被過濾掉三個個人化鍵（見上方「安全預設」），`~/.claude` 這個 clone 對 `settings.json` 會有一筆本地變更，屬正常現象。多數情況下 `git pull` 仍會成功；如果上游剛好也改到 `settings.json` 導致 `git pull` 被本地差異擋下，用這組指令復原（重跑安裝腳本會重新套用過濾邏輯）：

```bash
git -C ~/.claude checkout -- settings.json && git -C ~/.claude pull && bash ~/.claude/install.sh
```

（`MIKE_CLAUDE_FULL=1` 安裝的使用者沒有這個本地差異，不受影響。）

若當初是裝在既有的 `~/.claude` 上（白名單複製模式），沒有內建更新指令，重跑一次安裝腳本即可（既有檔案會自動備份後覆蓋成最新版）。

## 裝完之後

- 手動確認 `CLAUDE.md` 開頭的名字（若未設 `INSTALL_NAME`，仍是原文）
- 視需求在 `settings.json` 手動加回 `permissions.defaultMode` / `model`（或直接用 `MIKE_CLAUDE_FULL=1` 重裝）
- `/config` 內可開手機推播通知
- Windows 使用者：Claude Code 需要在 WSL 內執行，不是 Windows 原生終端機
