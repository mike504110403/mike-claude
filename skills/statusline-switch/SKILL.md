---
name: statusline-switch
description: 一鍵切換 Claude Code statusline。/statusline-switch <名字> 直接切換；不帶參數列出所有已註冊項並標示當前使用中。Mike 說「切 statusline」「換狀態列」時使用。
---

# /statusline-switch — statusline 切換器

## 架構

- settings.json 的 `statusLine.command` **固定**指向 `~/.claude/statusline-dispatch.sh`（總機），切換時不動 settings.json。
- 總機讀 `~/.claude/statuslines/.active`（內容 = 註冊名），exec 對應的 `~/.claude/statuslines/<名字>`；指標無效時退回 `mike`。
- 每次狀態列刷新都重跑總機，所以**切換即時生效，不需重啟**。

## 流程

1. `ls ~/.claude/statuslines/` 取得全部註冊項（隱藏檔不算），`cat ~/.claude/statuslines/.active` 取得當前項。
2. **帶參數**：確認 `~/.claude/statuslines/<名字>` 存在且可執行 → 把名字寫入 `.active` → 煙霧測試：`echo '{}' | ~/.claude/statusline-dispatch.sh` 確認 exit 0 且有輸出 → 回報「已切到 <名字>」。名字不存在時列出可用項請 Mike 選。
3. **不帶參數**：列出全部註冊項、標示當前使用中，問 Mike 要切哪個。

## 註冊新 statusline

寫一個可執行檔丟進 `~/.claude/statuslines/`（檔名即註冊名）：

- stdin 吃 Claude Code 的 statusline JSON，stdout 吐狀態列文字（可含 ANSI 色碼、可多行）。
- 外部程式（npm 包等）用薄 wrapper 包一層再放進來，參考現有的 `ccstatusline` wrapper（含 PATH 找不到時的 fallback 與友善錯誤訊息）。
- `chmod +x` 後即出現在切換清單，無需其他登記。
