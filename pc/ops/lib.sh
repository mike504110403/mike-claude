# shellcheck shell=bash
# PC 端維運共用（波 7）：由 healthcheck.sh／deploy.sh source。所有專案知識來自各群 .claude/localstack.json（已由 pc-sync-stack 改成 PC 路徑）。
GW="$HOME/ai-gateway"; STATE="$GW/state"; PENDING="$STATE/deploy-pending"; LOGS="$STATE/logs"
mkdir -p "$STATE" "$PENDING" "$LOGS" "$STATE/deploy" "$STATE/deploy-hold"
export PATH="$PATH:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin"
groups_list() { ls "$GW" | while read -r g; do [ -f "$GW/$g/.claude/localstack.json" ] && echo "$g"; done; }
decl_of() { echo "$GW/$1/.claude/localstack.json"; }
env_of() { jq -r '.pc.env // {} | to_entries[] | "\(.key)=\(.value)"' "$(decl_of "$1")" | tr '\n' ' '; }
cmd_of() { jq -r "$2 // empty" "$(decl_of "$1")"; }   # cmd_of <group> '.commands.up.cmd'
run_in_group() { # run_in_group <group> <cmd...>：cd 到群根、帶 pc.env
  local g="$1"; shift
  ( cd "$GW/$g" && eval "env $(env_of "$g") $*" )
}
now() { date -u +%Y-%m-%dT%H:%M:%SZ; }
