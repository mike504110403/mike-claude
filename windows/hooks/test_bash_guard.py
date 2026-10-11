#!/usr/bin/env python3
"""bash_guard 探針：餵已知 payload 驗證判定。"""
import json
import os
import subprocess
import sys

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bash_guard.py")

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
    ("git push " + "--force origin dev", "deny"),
    ("git stash " + "pop", "deny"),
    ("git stash list", "allow"),
    ("npx " + "prettier .", "deny"),
    # PC 版：PowerShell / cmd 刪除
    ("Remove-Item " + r"-Recurse -Force C:\tmp\x", "deny"),
    (r"remove-item C:\tmp\x " + "-force -recurse", "deny"),
    ("rm " + r"-r -fo C:\tmp\x", "deny"),
    ("ri " + r"-Rec -Fo .\build", "deny"),
    ("Get-Item x; Remove-Item " + "-Recurse -Force y", "deny"),
    ("rd " + r"/s /q C:\tmp\x", "deny"),
    ("cmd /c rmdir " + "/s /q build", "deny"),
    ("del " + "/s /q *.log", "deny"),
    ("Remove-Item " + r"-Recurse C:\tmp\x", "ask"),
    ("rd " + "/s build", "ask"),
    (r"Remove-Item C:\tmp\a.txt", "allow"),
    (r"Remove-Item -Force C:\tmp\a.txt", "allow"),
    ("Get-ChildItem -Recurse -Force", "allow"),
    ("Get-ChildItem -Recurse | Remove-Item " + "-Force", "ask"),
    (r"Test-Path C:\tmp\rd", "allow"),
    # review 回歸（2026-10-11）：ask 不得蓋掉後面的 deny；引號包住、/s/q 連寫、ForEach-Object 管線
    ("rm -r build && git stash " + "pop", "deny"),
    ("Remove-Item -Recurse dist; npx " + "prettier .", "deny"),
    ("rm -r x; git clean " + "-fdx", "deny"),
    ('powershell -Command "Remove-Item ' + r'C:\x -Recurse -Force"', "deny"),
    ("pwsh -c 'Remove-Item x " + "-Recurse -Force'", "deny"),
    ('cmd /c "rd ' + r'/s /q C:\x"', "deny"),
    ('cmd.exe /c "rmdir ' + '/s /q build"', "deny"),
    ("rd " + r"/s/q C:\x", "deny"),
    ("rd " + r"/S/Q C:\x", "deny"),
    ("Get-ChildItem -Recurse | ForEach-Object { Remove-Item $_.FullName " + "-Force }", "ask"),
    ("gci -r -Directory | " + "rmdir", "ask"),
    ("docker rm -f web", "allow"),
    ("grep -rn foo src | head", "allow"),
    ("Get-ChildItem -Recurse -Filter *.py", "allow"),
    ("cd /c/Users/User/src && ls", "allow"),
    # 複審回歸：管線後只有「指令位置」的刪除才算，參數／路徑裡出現 rd、del 不算
    ("grep -rn TODO src | grep -v rd", "allow"),
    ('grep -rl old src | xargs sed -i "s/del/x/"', "allow"),
    ("ls -R | tee /tmp/rd/out.log", "allow"),
    ("grep -r foo . | grep git-rm", "allow"),
    ("sort -r a.txt | grep remove-item", "allow"),
    ("grep -r x . | wc -l > rd.txt", "allow"),
    ("rg -r x foo | grep del", "allow"),
    ("grep -rl foo . | xargs " + "rm", "ask"),
    ("gci -r | % { ri $_ }", "ask"),
    ("gci -r | " + "rd", "ask"),
]

fails = 0
for cmd, expected in CASES:
    payload = json.dumps({"tool_input": {"command": cmd}})
    out = subprocess.run([sys.executable, GUARD], input=payload, capture_output=True, text=True).stdout.strip()
    actual = json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"
    ok = "OK " if actual == expected else "FAIL"
    if actual != expected:
        fails += 1
    print(f"{ok} {cmd!r} => {actual} (expected {expected})")

print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURES'}")
