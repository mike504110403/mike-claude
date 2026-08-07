#!/usr/bin/env python3
"""PreToolUse hook（SendMessage）：字串訊息缺 summary 參數直接擋下——缺了會報錯卡死，小模型工人不會自行重試。"""
import json
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    ti = data.get("tool_input") or {}
    summary = ti.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "SendMessage 必須帶非空的 summary 參數（一句話摘要訊息內容），請補上 summary 後重送同一則訊息。",
            }
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
