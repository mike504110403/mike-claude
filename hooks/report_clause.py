#!/usr/bin/env python3
"""SubagentStart hook：對每個 subagent 注入回報條款（橫切條款，臨時 prompt 派工也生效）。

單一 source 在 brief/SKILL.md 回報格式段；本檔只是它的機械投放器。
"""
import json
import sys

# 唯讀型內建 agent 不需要回報條款
EXCLUDE_TYPES = {"claude-code-guide", "statusline-setup"}

CLAUSE = (
    "【回報條款（全域 hook 注入）】完成時必須用 SendMessage 把完整報告主動送給 main，"
    "idle 通知不算回報；送出後未獲回應就重送並標明重送。"
    "報告附實際執行輸出與證據（引用程式碼一律附 檔案:行號，行號以 Read/sed 讀出為準），"
    "只送摘要或把報告寫在最終輸出而不 SendMessage，一律視同未回報。"
)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if (data.get("agent_type") or "") in EXCLUDE_TYPES:
        sys.exit(0)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": CLAUSE,
        }
    }, ensure_ascii=False))
    sys.exit(0)


main()
