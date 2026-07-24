#!/usr/bin/env python3
"""PreToolUse hook（Edit|Write）：改到 nginx 設定或 migration 檔案時強制詢問。"""
import json
import re
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    path = (data.get("tool_input") or {}).get("file_path") or ""

    if re.search(r"nginx", path, re.IGNORECASE) or re.search(r"migrations?/", path) or re.search(r"[._-]migration", path, re.IGNORECASE):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "全域規則：nginx 設定 / DB migration 檔案的修改需 Mike 確認。",
            }
        }))

    sys.exit(0)


if __name__ == "__main__":
    main()
