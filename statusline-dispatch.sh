#!/bin/bash
# statusline 總機：settings.json 固定指到這裡，實際顯示哪條看 ~/.claude/statuslines/.active
# 切換用 /statusline-switch（只改 .active，不動 settings.json）；指標無效時退回 mike
dir="$HOME/.claude/statuslines"
active=$(cat "$dir/.active" 2>/dev/null)
{ [ -n "$active" ] && [ -x "$dir/$active" ]; } || active=mike
exec "$dir/$active"
