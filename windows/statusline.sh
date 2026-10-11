#!/bin/bash
# Claude Code statusline：模型 | 專案 | context 用量 | 5h/週 rate limit
# 配色對齊 ~/.tmux.conf 的 Tokyo Night：藍膠囊、灰階分層、用量條依負載變色
input=$(cat)

# PC 版：Windows 上每開一個 process 都貴，jq 只叫一次（原版 10 次約 1s）；用 0x1F（Unit Separator）分隔才能保留空欄
IFS=$'\x1f' read -r model cur_dir ctx_pct ctx_size ctx_used five_pct five_at week_pct week_at < <(
  printf '%s' "$input" | jq -r '[
    (.model.display_name // "?"), (.workspace.current_dir // "?"),
    (.context_window.used_percentage // 0 | floor), (.context_window.context_window_size // 0),
    (.context_window.total_input_tokens // 0),
    (.rate_limits.five_hour.used_percentage // "" | if . == "" then . else floor end), (.rate_limits.five_hour.resets_at // 0),
    (.rate_limits.seven_day.used_percentage // "" | if . == "" then . else floor end), (.rate_limits.seven_day.resets_at // 0)
  ] | map(tostring) | join("\u001f")' | tr -d '\r')

# ── Tokyo Night Moon 色票（true color ANSI）────────────
RESET=$'\033[0m'
PILL=$'\033[48;2;130;170;255m\033[38;2;30;32;48m\033[1m'   # 藍底深字 #82aaff
FG_TEXT=$'\033[1m\033[38;2;200;211;245m'                   # 主文字 亮紫白 #c8d3f5 粗體
FG_DIM=$'\033[38;2;99;109;166m'                            # 次要資訊 #636da6
FG_DIR=$'\033[1m\033[38;2;134;225;252m'                    # 專案名 亮青 #86e1fc 粗體
C_GREEN=$'\033[38;2;195;232;141m'                          # 用量低 #c3e88d
C_YELLOW=$'\033[38;2;255;199;119m'                         # 用量中 #ffc777
C_RED=$'\033[38;2;255;117;127m'                            # 用量高 #ff757f
C_TRACK=$'\033[38;2;47;51;77m'                             # 條的空軌 / 分隔線 #2f334d
SEP=" ${C_TRACK}│${RESET} "

dir=$(basename "$cur_dir")


fmt_tok() {
  local n=$1
  if [ "$n" -ge 1000000 ]; then awk -v n="$n" 'BEGIN{printf "%.1fM", n/1000000}'
  elif [ "$n" -ge 1000 ]; then printf '%dk' $((n / 1000))
  else printf '%d' "$n"; fi
}

bar() { # 用量條：<60% 綠、60–84% 黃、≥85% 紅；空軌深灰；八分格精度（每格 20%、細分 2.5%）
  local pct=$1 width=5 i col
  if [ "$pct" -ge 85 ]; then col=$C_RED
  elif [ "$pct" -ge 60 ]; then col=$C_YELLOW
  else col=$C_GREEN; fi
  local eighths=$(( (pct * width * 8 + 50) / 100 ))
  [ "$eighths" -gt $((width * 8)) ] && eighths=$((width * 8))
  [ "$pct" -gt 0 ] && [ "$eighths" -eq 0 ] && eighths=1
  [ "$pct" -lt 100 ] && [ "$eighths" -eq $((width * 8)) ] && eighths=$((width * 8 - 1))
  local full=$((eighths / 8)) part=$((eighths % 8))
  local partials=('' '▏' '▎' '▍' '▌' '▋' '▊' '▉')
  printf '%s' "$col"
  for ((i = 0; i < width; i++)); do
    if ((i < full)); then printf '█'
    elif ((i == full)) && ((part > 0)); then printf '%s' "${partials[part]}"
    else printf '%s░' "$C_TRACK"; fi
  done
  printf '%s' "$RESET"
}

remain() { # epoch → "2h15m" / "5d2h"
  local now diff d h m
  now=$(date +%s); diff=$(( $1 - now ))
  [ "$diff" -lt 0 ] && diff=0
  d=$((diff / 86400)); h=$((diff % 86400 / 3600)); m=$((diff % 3600 / 60))
  if [ "$d" -gt 0 ]; then printf '%dd%dh' "$d" "$h"; else printf '%dh%02dm' "$h" "$m"; fi
}

line="${PILL} $model ${RESET} ${FG_DIR}${dir}${RESET}${SEP}${FG_DIM}Ctx${RESET} $(bar "$ctx_pct") ${FG_TEXT}${ctx_pct}%${RESET} ${FG_DIM}($(fmt_tok "$ctx_used")/$(fmt_tok "$ctx_size"))${RESET}"

if [ -n "$five_pct" ]; then
  five_reset=$(remain "$five_at")
  line="$line${SEP}${FG_DIM}5h${RESET} $(bar "$five_pct") ${FG_TEXT}${five_pct}%${RESET} ${FG_DIM}(${five_reset}後重置)${RESET}"
fi

if [ -n "$week_pct" ]; then
  week_reset=$(remain "$week_at")
  line="$line${SEP}${FG_DIM}週${RESET} $(bar "$week_pct") ${FG_TEXT}${week_pct}%${RESET} ${FG_DIM}(${week_reset})${RESET}"
fi

echo "$line"
