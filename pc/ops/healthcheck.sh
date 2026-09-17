#!/bin/bash
# 三群健檢（波 7a）：對每個有宣告檔的群跑 ready_check.cmd（沒有就 commands.status.cmd），結果寫 state/health.json；
# systemd timer 每 5 分鐘跑；pc-deploy status 直接讀這個檔。exit 0 全綠、1 有紅。
set -uo pipefail
. "$(dirname "$0")/lib.sh"
tmp=$(mktemp); parts=$(mktemp); all_ok=1; : >"$parts"
for g in $(groups_list); do
  cmd=$(cmd_of "$g" '.ready_check.cmd'); [ -n "$cmd" ] || cmd=$(cmd_of "$g" '.commands.status.cmd')
  [ -n "$cmd" ] || continue
  out=$(run_in_group "$g" "$cmd" 2>&1); rc=$?
  [ "$rc" = 0 ] || all_ok=0
  printf '%s\n' "$out" >"$LOGS/health-$g.log"
  jq -n --arg g "$g" --argjson ok "$([ "$rc" = 0 ] && echo true || echo false)" --arg last "$(printf '%s\n' "$out" | tail -1)" \
    '{($g): {ok: $ok, last_line: $last}}' >>"$parts"
done
jq -s --arg ts "$(now)" --argjson ok "$([ "$all_ok" = 1 ] && echo true || echo false)" '{ts: $ts, ok: $ok, groups: add}' "$parts" >"$tmp" \
  && mv "$tmp" "$STATE/health.json"
rm -f "$parts"
[ "$all_ok" = 1 ]
