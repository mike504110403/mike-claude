#!/bin/bash
# Claude Code statusline：模型 | 專案 | context 用量 | 5h/週 rate limit
input=$(cat)

j() { echo "$input" | jq -r "$1"; }

model=$(j '.model.display_name // "?"')
dir=$(basename "$(j '.workspace.current_dir // "?"')")

ctx_pct=$(j '.context_window.used_percentage // 0' | cut -d. -f1)
ctx_size=$(j '.context_window.context_window_size // 0')
ctx_used=$(j '.context_window.total_input_tokens // 0')

fmt_tok() {
  local n=$1
  if [ "$n" -ge 1000000 ]; then printf '%.1fM' "$(echo "$n/1000000" | bc -l)"
  elif [ "$n" -ge 1000 ]; then printf '%dk' $((n / 1000))
  else printf '%d' "$n"; fi
}

bar() {
  local pct=$1 width=5 filled i out=""
  filled=$((pct * width / 100))
  [ "$filled" -gt "$width" ] && filled=$width
  for ((i = 0; i < width; i++)); do
    if ((i < filled)); then out+="█"; else out+="░"; fi
  done
  printf '%s' "$out"
}

remain() { # epoch → "2h15m" / "5d2h"
  local now diff d h m
  now=$(date +%s); diff=$(( $1 - now ))
  [ "$diff" -lt 0 ] && diff=0
  d=$((diff / 86400)); h=$((diff % 86400 / 3600)); m=$((diff % 3600 / 60))
  if [ "$d" -gt 0 ]; then printf '%dd%dh' "$d" "$h"; else printf '%dh%02dm' "$h" "$m"; fi
}

line="[$model] $dir | Ctx $(bar "$ctx_pct") ${ctx_pct}% ($(fmt_tok "$ctx_used")/$(fmt_tok "$ctx_size"))"

five_pct=$(j '.rate_limits.five_hour.used_percentage // empty' | cut -d. -f1)
if [ -n "$five_pct" ]; then
  five_reset=$(remain "$(j '.rate_limits.five_hour.resets_at // 0')")
  line="$line | 5h $(bar "$five_pct") ${five_pct}% (${five_reset}後重置)"
fi

week_pct=$(j '.rate_limits.seven_day.used_percentage // empty' | cut -d. -f1)
if [ -n "$week_pct" ]; then
  week_reset=$(remain "$(j '.rate_limits.seven_day.resets_at // 0')")
  line="$line | 週 $(bar "$week_pct") ${week_pct}% (${week_reset})"
fi

echo "$line"
