#!/bin/bash
# cmux-pet-notify.sh — cmux notification hook: policy 原樣 passthrough，
# 順手把通知轉寫成 claude-pet 的 status.jsonl Notification 行。
# 合約：stdin 收 notification policy JSON，stdout 必須吐回有效 policy JSON；
# 任何附帶動作失敗都不得影響 passthrough（否則 cmux 會跳 hook failure alert）。
# status.jsonl 格式見 ~/claude-pet/CLAUDE.md（此輸入不受信，pet 端會跳過壞行）。

set -u

INPUT="$(cat)"
printf '%s' "$INPUT"

PET_DIR="${CLAUDE_PET_DIR:-$HOME/.claude-pet}"
STATUS_FILE="$PET_DIR/status.jsonl"

extract_field() {
    printf '%s' "$INPUT" \
        | grep -o "\"$1\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
        | head -n 1 \
        | sed -E "s/\"$1\"[[:space:]]*:[[:space:]]*\"//; s/\"\$//"
}

json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\t'/\\t}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\n'/\\n}"
    printf '%s' "$s"
}

{
    TITLE="$(extract_field title)"
    BODY="$(extract_field body)"
    MESSAGE="$TITLE"
    [ -n "$BODY" ] && MESSAGE="${MESSAGE:+$MESSAGE — }$BODY"
    [ -z "$MESSAGE" ] && MESSAGE="cmux notification"
    mkdir -p "$PET_DIR" 2>/dev/null \
        && printf '{"ts": %s, "event": "Notification", "session_id": "cmux", "message": "%s"}\n' \
            "$(date +%s)" "$(json_escape "$MESSAGE")" >> "$STATUS_FILE"
} 2>/dev/null || true

exit 0
