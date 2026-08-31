#!/bin/bash
# statusline 總機：settings.json 固定指到這裡，實際顯示哪條看 ~/.claude/statuslines/.active
# 切換用 /statusline-switch（只改 .active，不動 settings.json）；指標無效時退回 mike
# phase 段統一在此附加到第一行尾（~/.claude/bin/phase，key＝claude session_id），
# 不依賴各註冊項自己實作，切哪條 statusline 都會顯示。
dir="$HOME/.claude/statuslines"
active=$(cat "$dir/.active" 2>/dev/null)
{ [ -n "$active" ] && [ -x "$dir/$active" ]; } || active=mike

input=$(cat)
out=$(printf '%s' "$input" | "$dir/$active")

sid=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
ph=$("$HOME/.claude/bin/phase" show "$sid" 2>/dev/null)

if [ -n "$ph" ]; then
  printf '%s \033[1;38;2;255;199;119m%s\033[0m\n' "$(printf '%s\n' "$out" | head -1)" "$ph"
  printf '%s\n' "$out" | tail -n +2
else
  printf '%s\n' "$out"
fi
