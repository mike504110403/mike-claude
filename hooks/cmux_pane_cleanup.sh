#!/bin/bash
# PostToolUse(TaskStop) hook：TaskStop 不保證自動關 cmux pane（2026-09-01 實證），
# 這支在每次 TaskStop 後盤點殘留 pane，把盤點注入 context 讓大腦（有完整
# session 脈絡）判斷該關哪些。
#
# 【2026-09-01 事故改版】原版有「teams config 無存活 teammate → 全自動關
# 非主 pane」的快速檔位，同日誤殺三個剛 spawn 的活工人 pane——TaskStop
# 觸發 hook 的瞬間，新 spawn 的 teammate 可能尚未寫進 config.json（race），
# hook 誤判「無活工人」。教訓：config.json 在 spawn/stop 邊緣都不即時，
# 不可當自動銷毀的依據。本版永遠只盤點提醒、絕不自動 close-surface。
# 非 cmux 環境靜默跳過。規則源頭：~/.claude/CLAUDE.md「cmux pane 佈局紀律」。
set -u

INPUT=$(cat)

CLI="${CMUX_BUNDLED_CLI_PATH:-}"
[ -z "$CLI" ] || [ ! -x "$CLI" ] && exit 0
command -v jq >/dev/null 2>&1 || exit 0

CALLER=$("$CLI" identify 2>/dev/null | jq -r '.caller.pane_ref // empty')
[ -z "$CALLER" ] && exit 0

PANES_JSON=$("$CLI" list-panes --json 2>/dev/null) || exit 0
OTHER_PANES=$(printf '%s' "$PANES_JSON" | jq -r --arg c "$CALLER" '.panes[] | select(.ref != $c) | .ref' | tr '\n' ' ')
[ -z "${OTHER_PANES// /}" ] && exit 0  # 只剩主 pane，無事可做

jq -n --arg ctx "cmux pane 清理 hook：TaskStop 後仍有非主 pane：${OTHER_PANES}——對照你 session 中存活的 teammate，剛收掉者的殘殼用 close-surface 逐一清掉（surface refs 用 list-panes --json 查），活工人的 pane 勿動，清完 focus-pane 回主 pane。" \
  '{suppressOutput: true, hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $ctx}}'
exit 0
