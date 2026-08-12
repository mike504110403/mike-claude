#!/usr/bin/env python3
"""bash_guard 探針：餵已知 payload 驗證判定。"""
import json
import subprocess

GUARD = "/Users/mike/.claude/hooks/bash_guard.py"

CASES = [
    # (command, expected)
    ("rm " + "-rf /tmp/x", "deny"),
    ("git add " + ".", "deny"),
    ("git branch " + "-D wt/foo", "deny"),
    ("git clean " + "-fd", "deny"),
    ("git clean " + "-n", "allow"),
    ("git reset " + "--hard HEAD", "ask"),
    ("rm -r somedir", "ask"),
    ("find . -name '*.tmp' " + "-delete", "ask"),
    ("npm run " + "commit", "ask"),
    ("npm run build", "allow"),
    ("pnpm run " + "deploy", "ask"),
    ("make " + "deploy", "ask"),
    ("git push " + "origin dev", "ask"),
    ("go test ./...", "allow"),
    ("git status", "allow"),
]

fails = 0
for cmd, expected in CASES:
    payload = json.dumps({"tool_input": {"command": cmd}})
    out = subprocess.run(["python3", GUARD], input=payload, capture_output=True, text=True).stdout.strip()
    actual = json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"
    ok = "OK " if actual == expected else "FAIL"
    if actual != expected:
        fails += 1
    print(f"{ok} {cmd!r} => {actual} (expected {expected})")

print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURES'}")
