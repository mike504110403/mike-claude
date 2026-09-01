#!/bin/bash
# PostToolUse(TaskStop) hook：TaskStop 不保證自動關 cmux pane（2026-09-01 實證），
# 這支在每次 TaskStop 後盤點殘留 pane：
#   - session 已無存活 teammate → 自動關掉所有非主 pane 的 surface、焦點拉回主 pane
#   - 還有存活 teammate → 不動手（分不出哪個殼屬於誰），把盤點注入 context 讓大腦清
# 非 cmux 環境靜默跳過。規則源頭：~/.claude/CLAUDE.md「cmux pane 佈局紀律」第 3 條。
set -u

INPUT=$(cat)

CLI="${CMUX_BUNDLED_CLI_PATH:-}"
[ -z "$CLI" ] || [ ! -x "$CLI" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty')

# 主 pane（本 claude 進程所在 pane）
CALLER=$("$CLI" identify 2>/dev/null | jq -r '.caller.pane_ref // empty')
[ -z "$CALLER" ] && exit 0

PANES_JSON=$("$CLI" list-panes --json 2>/dev/null) || exit 0
OTHER_PANES=$(printf '%s' "$PANES_JSON" | jq -r --arg c "$CALLER" '.panes[] | select(.ref != $c) | .ref')
[ -z "$OTHER_PANES" ] && exit 0  # 只剩主 pane，無事可做

# 存活 teammate 數：teams config 的 members 裡非 team-lead 的成員
LIVE=0
if [ -n "$SESSION_ID" ]; then
  CFG=$(ls "$HOME/.claude/teams/session-${SESSION_ID:0:8}"*/config.json 2>/dev/null | head -1)
  if [ -n "${CFG:-}" ] && [ -f "$CFG" ]; then
    LIVE=$(jq -r '[.members[]? | select(.name != "team-lead")] | length' "$CFG" 2>/dev/null || echo 0)
  fi
fi

if [ "$LIVE" -eq 0 ]; then
  # 無存活 teammate：所有非主 pane 都是殘殼，逐一關 surface
  CLOSED=""
  for P in $OTHER_PANES; do
    SURFACES=$(printf '%s' "$PANES_JSON" | jq -r --arg p "$P" '.panes[] | select(.ref == $p) | .surface_refs[]?')
    for S in $SURFACES; do
      "$CLI" close-surface --surface "$S" >/dev/null 2>&1 && CLOSED="$CLOSED $P/$S"
    done
  done
  "$CLI" focus-pane --pane "$CALLER" >/dev/null 2>&1
  if [ -n "${CLOSED}" ]; then
    jq -n --arg msg "cmux pane 清理 hook：session 已無存活 teammate，自動關閉殘留殼:${CLOSED}；焦點已回主 pane" \
      '{systemMessage: $msg, suppressOutput: true, hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $msg}}'
  fi
else
  # 還有存活 teammate：不自動關（可能殺到活工人的 pane），交大腦判斷
  LIST=$(printf '%s' "$OTHER_PANES" | tr '\n' ' ')
  jq -n --arg ctx "cmux pane 清理 hook：TaskStop 後仍有 $LIVE 個存活 teammate 與非主 pane：$LIST——剛收掉的 teammate 若留有殘殼，立即用 close-surface 清掉（幾何以 list-panes --json 為準），活工人的 pane 勿動。" \
    '{suppressOutput: true, hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
fi
exit 0
