#!/usr/bin/env python3
"""PreToolUse hook（Bash）：硬擋危險命令、git push 強制詢問、nginx/migration 強制詢問。"""
import json
import re
import sys


def respond(decision, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = (data.get("tool_input") or {}).get("command") or ""

    # 硬擋：rm 帶有 r+f 組合旗標（rm -rf / -fr / -r -f ...）
    if re.search(r"\brm\s+(-\w*r\w*\s+)*-\w*f", cmd) and re.search(r"\brm\s+(-\w*\s+)*-\w*r", cmd):
        respond("deny", "硬擋：rm -rf 被全域規則禁止。請改用精確路徑逐一刪除，或請 Mike 手動執行。")
    if re.search(r"\brm\s+-\w*(rf|fr)\w*\b", cmd):
        respond("deny", "硬擋：rm -rf 被全域規則禁止。請改用精確路徑逐一刪除，或請 Mike 手動執行。")

    # 硬擋：force push
    if re.search(r"\bgit\s+push\b", cmd) and re.search(r"(\s--force(-with-lease)?\b|\s-f\b)", cmd):
        respond("deny", "硬擋：force push 被全域規則禁止。")

    # 硬擋：git add . / -A / --all
    if re.search(r"\bgit\s+add\s+(\.(\s|$)|-A\b|--all\b)", cmd):
        respond("deny", "硬擋：git add . / -A 被禁止，請逐一指定要加入的檔案。")

    # 強制詢問：git push（Push 閘門）
    if re.search(r"\bgit\s+push\b", cmd):
        respond("ask", "Push 閘門：git push 需要 Mike 明確確認才能執行。")

    # 強制詢問：nginx / 執行 migration
    if re.search(r"\bnginx\b", cmd, re.IGNORECASE):
        respond("ask", "全域規則：nginx 相關操作需 Mike 確認。")
    if re.search(r"\b(migrate|alembic|flyway|goose)\b", cmd, re.IGNORECASE):
        respond("ask", "全域規則：DB migration 相關操作需 Mike 確認。")

    sys.exit(0)


if __name__ == "__main__":
    main()
