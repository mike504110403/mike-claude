---
name: tmux-rename
description: 改 tmux session 或 window 名稱。Mike 說「改名」「rename tmux」或 /tmux-rename <新名字> 時使用；預設改當前 session 名稱，有提到 window／視窗才改視窗名。
---

# tmux 改名

把當前 tmux session（或 window）改成指定名稱。

## 參數解讀

- `/tmux-rename 新名字` → 改**當前 session** 名稱（狀態列左邊 `[xxx]` 那個）
- `/tmux-rename window 新名字`，或訊息裡提到「window／視窗」 → 改**當前 window** 名稱
- 沒給名字 → 用 AskUserQuestion 問 Mike 要改成什麼，不要自己猜

## 步驟

1. 先看目前叫什麼：`tmux display-message -p '#S / #I:#W'`
2. 執行改名（Claude Code 就跑在該 session 裡，不需要 `-t`）：
   - session：`tmux rename-session '新名字'`
   - window：`tmux rename-window '新名字'`
3. 驗證：`tmux display-message -p '#S / #I:#W'` 確認生效，回報一行「舊名 → 新名」。

## 注意

- session 名稱避免 `.` 和 `:`（tmux 定址保留字元）；含空白要加引號。
- `~/.tmux.conf` 已設 `allow-rename off`，手動改名不會被 shell 蓋回去。
- 若要改的是**別的** session／window（Mike 明講名字時），才用 `-t 目標` 指定。
