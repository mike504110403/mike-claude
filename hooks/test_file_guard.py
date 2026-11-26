#!/usr/bin/env python3
"""file_guard 探針：以 subprocess 餵 PreToolUse payload（HOME 指向臨時目錄），驗證 ~/.claude/checks/ 寫入轉 ask，
且既有的系統 nginx 判定與壞 payload 轉 ask 不變。"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "file_guard.py")
FAILS = 0
CHECKS_REASON = "寫入 checks 設定＝新增自動執行入口，需 Mike 確認"


def check(cond, label):
    global FAILS
    FAILS += not cond
    print(f"{'OK  ' if cond else 'FAIL'} {label}")


def run_guard(home, payload, **extra_env):
    env = {k: v for k, v in os.environ.items() if k != "WRITE_CHECKS_DIR"}
    env.update(HOME=home, **extra_env)
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run([sys.executable, GUARD], input=data, capture_output=True, text=True, env=env, timeout=30)


def decision(proc):
    try:
        out = json.loads(proc.stdout)
    except ValueError:
        return None, ""
    spec = out.get("hookSpecificOutput", {})
    return spec.get("permissionDecision"), spec.get("permissionDecisionReason", "")


def payload(tool, path):
    return {"tool_name": tool, "tool_input": {"file_path": path}}


def main():
    with tempfile.TemporaryDirectory() as home:
        checks = os.path.join(home, ".claude", "checks")
        for tool in ("Edit", "Write"):
            for path, label in ((os.path.join(checks, "lottery-platform", "write-checks.json"), "設定檔"),
                                (os.path.join(checks, "new"), "checks 下任一檔"),
                                (os.path.join(home, ".claude", "hooks", "..", "checks", "x.json"), "經 .. 繞進 checks"),
                                (os.path.join(home, ".claude", "CHECKS", "x.json"), "大小寫變形")):
                proc = run_guard(home, payload(tool, path))
                verdict, reason = decision(proc)
                check(proc.returncode == 0 and verdict == "ask" and reason == CHECKS_REASON,
                      f"{tool} {label} → ask（got {verdict}, {reason!r}）")

        for path, label in ((os.path.join(home, ".claude", "checkſ", "x"), "U+017F 長 s（checks 尚不存在）"),
                            ("~/.claude/checks/x", "字面 ~ 路徑（checks 尚不存在）")):
            check(decision(run_guard(home, payload("Write", path)))[0] == "ask", f"{label} → ask")

        os.makedirs(os.path.join(checks, "lottery-platform"))
        alias = os.path.join(home, "alias")
        os.symlink(checks, alias)
        real_home = os.path.realpath(home)
        st = os.stat(checks)
        vol = f"/.vol/{st.st_dev}/{st.st_ino}"
        cases = [(os.path.join(alias, "x", "write-checks.json"), "經 symlink 指向 checks"),
                 (os.path.join(home, ".claude", "checkſ", "x"), "U+017F 長 s（checks 已存在）"),
                 ("~/.claude/checks/x", "字面 ~ 路徑（checks 已存在）"),
                 (os.path.join(checks, "lottery-platform", "verify.json"), "verify.json"),
                 ("/System/Volumes/Data" + real_home + "/.claude/checks/x", "/System/Volumes/Data 前綴"),
                 (os.path.join(vol, "x"), "/.vol/<dev>/<ino> 路徑")]
        for path, label in cases:
            if path.startswith(("/System/Volumes/Data", "/.vol/")) and not os.path.exists(os.path.dirname(path)):
                print(f"SKIP {label}：本機無法構造（{os.path.dirname(path)} 不存在）")
                continue
            verdict, reason = decision(run_guard(home, payload("Write", path)))
            check(verdict == "ask" and reason == CHECKS_REASON, f"{label} → ask（got {verdict}, {reason!r}）")

        custom = os.path.join(home, "custom-checks")
        os.makedirs(custom)
        verdict, _ = decision(run_guard(home, payload("Write", os.path.join(custom, "k", "write-checks.json")), WRITE_CHECKS_DIR=custom))
        check(verdict == "ask", f"WRITE_CHECKS_DIR 指向的根也 ask（got {verdict}）")
        proc = run_guard(home, payload("Write", os.path.join(custom, "k", "write-checks.json")))
        check(proc.stdout == "", "未設 WRITE_CHECKS_DIR 時該目錄放行")

        for path, label in ((os.path.join(home, ".claude", "checksfoo", "x.json"), "前綴相同的兄弟目錄"),
                            (os.path.join(home, ".claude", "checkſfoo", "x.json"), "長 s 的兄弟目錄"),
                            (os.path.join(home, ".claude", "hooks", "write_checks.py"), "~/.claude 其他檔"),
                            ("/x/nginx.conf", "repo 內 nginx 檔")):
            proc = run_guard(home, payload("Edit", path))
            check(proc.returncode == 0 and proc.stdout == "", f"{label} → 放行（got {proc.stdout!r}）")

        verdict, reason = decision(run_guard(home, payload("Edit", "/etc/nginx/nginx.conf")))
        check(verdict == "ask" and "nginx" in reason, f"系統 nginx 路徑仍問（got {verdict}, {reason!r}）")

        for bad in ("not json", json.dumps({"tool_input": {}})):
            check(decision(run_guard(home, bad))[0] == "ask", f"壞 payload {bad!r} 仍轉 ask")

    if FAILS:
        print(f"{FAILS} FAILED")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
