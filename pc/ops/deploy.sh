#!/bin/bash
# push 即部署（波 7c）：接收端 hook 收到 pc-test 推送就 touch state/deploy-pending/<group>；systemd path unit 看到目錄非空就跑本腳本。
# 先等 DEBOUNCE 秒讓同群多個 repo 的連續推送到齊，再對每個旗標群跑宣告檔 commands.up.cmd（帶 pc.env），結果寫 state/deploy/<group>.json；
# 跑的期間新來的旗標留在目錄，本輪結束後 path unit 會再觸發一輪。log 在 state/logs/deploy-<group>.log。
set -uo pipefail
. "$(dirname "$0")/lib.sh"
DEBOUNCE="${DEPLOY_DEBOUNCE:-15}"
sleep "$DEBOUNCE"
for f in "$PENDING"/*; do
  [ -e "$f" ] || continue
  g=$(basename "$f"); rm -f "$f"
  # pc-deploy 的同步動作（up／frontend-up）自己會在 PC 跑 up，推碼前先放 hold：這裡看到 hold 就丟掉旗標不重跑，避免兩份 up.sh 對撞
  if [ -e "$STATE/deploy-hold/$g" ]; then echo "$(now) $g: hold 中（pc-deploy 同步動作進行中），略過" >>"$LOGS/deploy-$g.log"; continue; fi
  cmd=$(cmd_of "$g" '.commands.up.cmd')
  [ -n "$cmd" ] || { jq -n --arg g "$g" --arg ts "$(now)" '{group:$g, ts:$ts, ok:false, error:"宣告檔無 commands.up.cmd"}' >"$STATE/deploy/$g.json"; continue; }
  revs=$(for d in "$GW/$g"/*/; do [ -f "$d.ai-gateway-rev" ] && printf '%s=%.10s ' "$(basename "$d")" "$(cat "$d.ai-gateway-rev")"; done)
  started=$(now)
  run_in_group "$g" "$cmd" >"$LOGS/deploy-$g.log" 2>&1; rc=$?
  jq -n --arg g "$g" --arg started "$started" --arg ts "$(now)" --argjson ok "$([ "$rc" = 0 ] && echo true || echo false)" --arg rc "$rc" --arg revs "$revs" --arg log "$LOGS/deploy-$g.log" --arg tail "$(tail -5 "$LOGS/deploy-$g.log")" \
    '{group:$g, started:$started, ts:$ts, ok:$ok, rc:($rc|tonumber), revs:$revs, log:$log, tail:$tail}' >"$STATE/deploy/$g.json"
  # 部署完立刻健檢一次，讓 health.json 反映新狀態
  "$(dirname "$0")/healthcheck.sh" >/dev/null 2>&1 || true
done
