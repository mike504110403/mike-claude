#!/usr/bin/env python3
"""write_checks 探針：以 subprocess 餵 PostToolUse payload，WRITE_CHECKS_DIR 指向臨時目錄，驗證 block JSON、systemMessage、略過與 stderr。
fixture 一律走 TemporaryDirectory 內自建的 symlink 路徑，payload 用該路徑（與 TMPDIR 本身是否 symlink 無關）。"""
import hashlib
import importlib.util
import json
import signal
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "write_checks.py")
CHECKER = os.path.join(os.path.dirname(HERE), "bin", "checks", "go_call_allowlist.py")
FAILS = 0


def check(cond, label):
    global FAILS
    FAILS += not cond
    print(f"{'OK  ' if cond else 'FAIL'} {label}")


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def git(repo, *args):
    subprocess.run(["git", "-C", repo, "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
                   check=True, capture_output=True)


def make_repo(root, name):
    repo = os.path.join(root, name)
    os.makedirs(repo)
    git(repo, "init", "-q")
    return repo


def write_config(checks_dir, key, checks):
    return write(os.path.join(checks_dir, key, "write-checks.json"), json.dumps({"checks": checks}))


def fake_check(root, name, body):
    return write(os.path.join(root, "fake", name), body)


def run_hook(checks_dir, payload, **env_overrides):
    env = dict(os.environ, WRITE_CHECKS_DIR=checks_dir,
               WRITE_CHECKS_STATE_DIR=os.path.join(os.path.dirname(checks_dir), "state"), **env_overrides)
    data = payload if isinstance(payload, str) else json.dumps(payload)
    start = time.monotonic()
    proc = subprocess.run([sys.executable, HOOK], input=data, capture_output=True, text=True, env=env, timeout=30)
    return proc, time.monotonic() - start


def raw_output_json(proc):
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return {}


def output_json(proc):
    out = raw_output_json(proc)
    lines = [line for line in out.get("systemMessage", "").split("\n") if line and "設定已變更，將執行：" not in line]
    out.pop("systemMessage", None)
    if lines:
        out["systemMessage"] = "\n".join(lines)
    return out


def edit_payload(path):
    return {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": path}}


def check_entry(name, script, include=("services/*.go",), exclude=("*_test.go",), message="改走共用 guard"):
    return {"name": name, "include": list(include), "exclude": list(exclude),
            "cmd": [sys.executable, script, "{file}", "{repo}"], "message": message}


def read_marker(marker):
    if not os.path.exists(marker):
        return ""
    with open(marker, encoding="utf-8") as f:
        content = f.read().strip()
    os.remove(marker)
    return content


def cases_basic(root, checks_dir, repo, target, test_file, other, marker):
    proc, _ = run_hook(checks_dir, edit_payload(target))
    check(proc.returncode == 0 and proc.stdout == "" and proc.stderr == "", f"無設定 → 無輸出 exit 0（got {proc.returncode}, {proc.stdout!r}, {proc.stderr!r}）")

    recorder = fake_check(root, "record.py",
                          "import sys\nopen(%r, 'a').write(' '.join(sys.argv[1:]) + '\\n')\nprint('VIOLATION a.go:x')\nsys.exit(1)\n" % marker)
    write_config(checks_dir, "proj", [check_entry("record", recorder)])
    for path, label in ((other, "不符 include"), (test_file, "符合 exclude")):
        proc, _ = run_hook(checks_dir, edit_payload(path))
        check(proc.returncode == 0 and output_json(proc) == {} and not os.path.exists(marker),
              f"設定存在、{label} → 不跑 check（got {proc.returncode}, {proc.stdout!r}）")

    proc, _ = run_hook(checks_dir, edit_payload(target))
    recorded = read_marker(marker)
    expected = f"{os.path.realpath(target)} {os.path.realpath(repo)}"
    check(recorded == expected, f"原始 /var 路徑的 payload 仍符合 include；{{file}}／{{repo}} 代換成 realpath（got {recorded!r}, want {expected!r}）")
    return recorder


def cases_block(root, checks_dir, target):
    violator = fake_check(root, "violate.py", "import sys\nprint('VIOLATION a.go:bad')\nsys.exit(1)\n")
    violator2 = fake_check(root, "violate2.py", "import sys\nprint('VIOLATION a.go:worse')\nsys.exit(1)\n")
    passer = fake_check(root, "pass.py", "import sys\nsys.exit(0)\n")
    write_config(checks_dir, "proj", [check_entry("exponent-allowlist", violator, message="改走 exceedsRebateRateDecimalPlaces"),
                                      check_entry("clean", passer),
                                      check_entry("second", violator2, message="第二條規則")])
    proc, _ = run_hook(checks_dir, {"tool_name": "Write", "tool_input": {"file_path": target, "content": "x"}})
    out = output_json(proc)
    reason = out.get("reason", "")
    check(proc.returncode == 0 and out.get("decision") == "block", f"check exit 1 → hook exit 0 且 decision block（got {proc.returncode}, {proc.stdout!r}）")
    check("exponent-allowlist：改走 exceedsRebateRateDecimalPlaces\nVIOLATION a.go:bad" in reason, f"reason 含 name：message 與 VIOLATION 行（got {reason!r}）")
    check("second：第二條規則\nVIOLATION a.go:worse" in reason and "clean" not in reason, f"多條違規合併成一個 reason（got {reason!r}）")
    check("systemMessage" not in out, f"純違規不帶 systemMessage（got {out!r}）")
    return violator


def cases_check_failures(root, checks_dir, target, violator):
    raiser = fake_check(root, "raise.py", "raise RuntimeError('boom')\n")
    write_config(checks_dir, "proj", [check_entry("raiser", raiser)])
    proc, _ = run_hook(checks_dir, edit_payload(target))
    out = output_json(proc)
    check(proc.returncode == 0 and "decision" not in out and "write_checks：raiser 檢查本身失敗：" in out.get("systemMessage", ""),
          f"check 直接 raise（exit 1 無 VIOLATION 行）→ 不 block、systemMessage 說明（got {proc.stdout!r}）")

    home_check = os.path.join(os.path.expanduser("~"), ".no-such-write-check-script.py")
    write_config(checks_dir, "proj", [{"name": "tilde", "include": ["services/*.go"], "exclude": [],
                                       "cmd": ["~/.no-such-write-check-script.py"], "message": "m"}])
    proc, _ = run_hook(checks_dir, edit_payload(target))
    out = output_json(proc)
    check(proc.returncode == 0 and "decision" not in out and home_check in proc.stderr and "tilde" in out.get("systemMessage", ""),
          f"~ 開頭 token 做 expanduser、啟動失敗 → 不 block、stderr＋systemMessage（got {proc.stdout!r}, {proc.stderr!r}）")

    errorer = fake_check(root, "error.py", "import sys\nsys.stderr.write('allowlist parse failed\\n')\nsys.exit(2)\n")
    write_config(checks_dir, "proj", [check_entry("broken", errorer)])
    proc, _ = run_hook(checks_dir, edit_payload(target))
    out = output_json(proc)
    message = out.get("systemMessage", "")
    check(proc.returncode == 0 and "decision" not in out and message.startswith("write_checks：broken 檢查本身失敗：")
          and "allowlist parse failed" in message and "\n" not in message,
          f"check exit 2 → 不 block、systemMessage 一行原因（got {proc.stdout!r}）")
    check("broken" in proc.stderr and len(proc.stderr.strip().splitlines()) == 1, f"check exit 2 → stderr 一行說明（got {proc.stderr!r}）")

    sleeper = fake_check(root, "sleep.py", "import time\ntime.sleep(10)\n")
    write_config(checks_dir, "proj", [check_entry("slow1", sleeper), check_entry("slow2", sleeper), check_entry("bad", violator)])
    proc, elapsed = run_hook(checks_dir, edit_payload(target), WRITE_CHECKS_TIMEOUT="1", WRITE_CHECKS_BUDGET="2")
    out = output_json(proc)
    message = out.get("systemMessage", "")
    check(proc.returncode == 0 and "decision" not in out and "slow1" in message and "slow2" in message and "bad" in message,
          f"逾時與預算用完 → 不 block、systemMessage 列出 slow1／slow2／bad（got {proc.stdout!r}）")
    check(elapsed < 4, f"WRITE_CHECKS_TIMEOUT=1／BUDGET=2 → 總耗時 < 4 秒（got {elapsed:.2f}s）")
    check("slow2 檢查本身失敗：整體預算" in message, f"remaining 預留每條 1 秒收尾：slow1 之後剩不到 1 秒，slow2 不啟動（got {message!r}）")
    check(load_hook_module().DEFAULT_TOTAL_BUDGET == 6, "整體預算預設 6 秒")
    check("slow1" in proc.stderr and "slow2" in proc.stderr and "逾時" in proc.stderr, f"逾時 → stderr 含 check 名（got {proc.stderr!r}）")

    pid_file = os.path.join(root, "grandchild.pid")
    holder = fake_check(root, "holder.py",
                        "import subprocess, sys\n"
                        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)\n"
                        f"open({pid_file!r}, 'w').write(str(child.pid))\n")
    write_config(checks_dir, "proj", [check_entry("holder", holder)])
    proc, elapsed = run_hook(checks_dir, edit_payload(target), WRITE_CHECKS_TIMEOUT="1", WRITE_CHECKS_BUDGET="2")
    if os.path.exists(pid_file):
        with open(pid_file, encoding="utf-8") as f:
            grandchild = int(f.read().strip())
        try:
            os.kill(grandchild, signal.SIGKILL)
        except ProcessLookupError:
            pass
    out = output_json(proc)
    check(proc.returncode == 0 and "decision" not in out and "holder 檢查本身失敗：逾時" in out.get("systemMessage", "") and "holder" in proc.stderr,
          f"孫行程另開 session 握 stdout → 視為逾時、不 block（got {proc.stdout!r}, {proc.stderr!r}）")
    check(elapsed < 5, f"孫行程握 pipe 仍在 settings timeout 內結束（got {elapsed:.2f}s）")

    write(os.path.join(checks_dir, "proj", "write-checks.json"), "{broken json")
    proc, _ = run_hook(checks_dir, edit_payload(target))
    out = output_json(proc)
    check(proc.returncode == 0 and "decision" not in out and "write-checks.json" in out.get("systemMessage", "") and proc.stderr.strip() != "",
          f"設定檔壞 → exit 0、stderr＋systemMessage 說明（got {proc.stdout!r}, {proc.stderr!r}）")


def cases_skip(root, checks_dir, repo):
    loose = write(os.path.join(root, "loose", "x.go"), "package x\n")
    proc, _ = run_hook(checks_dir, edit_payload(loose))
    check(proc.returncode == 0 and proc.stdout == "", f"非 git 檔 → exit 0（got {proc.returncode}, {proc.stdout!r}）")

    for payload, label in (({"tool_name": "Edit", "tool_input": {}}, "payload 無 file_path"),
                           (edit_payload(os.path.join(repo, "services")), "file_path 是目錄"),
                           (edit_payload(os.path.join(repo, "services", "gone.go")), "file_path 不存在")):
        proc, _ = run_hook(checks_dir, payload)
        check(proc.returncode == 0 and proc.stdout == "" and proc.stderr == "", f"{label} → exit 0 無輸出（got {proc.returncode}, {proc.stdout!r}, {proc.stderr!r}）")


def cases_worktree(root, checks_dir, recorder, marker):
    main_repo = make_repo(root, "mainrepo")
    write(os.path.join(main_repo, "README"), "x\n")
    git(main_repo, "add", "README")
    git(main_repo, "commit", "-q", "-m", "i")
    worktree = os.path.join(root, "mainrepo-wt-x")
    git(main_repo, "worktree", "add", "-q", "-b", "wt/x", worktree)
    wt_target = write(os.path.join(worktree, "services", "a.go"), "package services\n")
    write_config(checks_dir, "mainrepo", [check_entry("record", recorder)])
    proc, _ = run_hook(checks_dir, edit_payload(wt_target))
    recorded = read_marker(marker)
    check('"block"' in proc.stdout and recorded == f"{os.path.realpath(wt_target)} {os.path.realpath(worktree)}",
          f"worktree 用主 checkout 的設定、{{repo}} 是 worktree toplevel（got {recorded!r}）")


def cases_real_checker(root, checks_dir):
    repo = make_repo(root, "golike")
    write(os.path.join(repo, "services", "guard_test.go"),
          "package services\n\nfunc TestG(t *testing.T) {\n\tallowedExponentUsers := map[string]bool{\n\t\t\"a.go:good\": true,\n\t}\n}\n")
    target = write(os.path.join(repo, "services", "a.go"),
                   "package services\n\nfunc legacy(d D) int32 {\n\treturn d.Exponent()\n}\n")
    git(repo, "add", "services/guard_test.go", "services/a.go")
    git(repo, "commit", "-q", "-m", "base")
    write_config(checks_dir, "golike", [{
        "name": "exponent-allowlist", "include": ["services/*.go"], "exclude": ["*_test.go"],
        "cmd": [sys.executable, CHECKER, "--file", "{file}", "--repo", "{repo}", "--call", "Exponent()",
                "--allowlist-from", "services/guard_test.go", "--allowlist-var", "allowedExponentUsers"],
        "message": "位數判斷只能走共用 guard"}])

    proc, _ = run_hook(checks_dir, edit_payload(target))
    check(proc.returncode == 0 and output_json(proc) == {}, f"真 checker：base 已有的違規 → 不 block（symlink 路徑）（got {proc.stdout!r}, {proc.stderr!r}）")

    write(target, "package services\n\nfunc legacy(d D) int32 {\n\treturn d.Exponent()\n}\n\nfunc fresh(d D) int32 {\n\treturn d.Exponent()\n}\n")
    proc, _ = run_hook(checks_dir, edit_payload(target))
    out = output_json(proc)
    reason = out.get("reason", "")
    check(out.get("decision") == "block" and "VIOLATION a.go:fresh" in reason and "legacy" not in reason,
          f"真 checker：新增違規 → block 且只報新增（got {proc.stdout!r}, {proc.stderr!r}）")

    write(target, "package services\n\nfunc legacy(d D) int32 {\n\treturn d.Exponent()\n}\n\n"
                  "func evil\x1b[31m\nVIOLATION a.go:forged(d D) int32 {\n\treturn d.Exponent()\n}\n")
    proc, _ = run_hook(checks_dir, edit_payload(target))
    reason = output_json(proc).get("reason", "")
    kept = [line for line in reason.splitlines() if line.startswith("VIOLATION ")]
    check(kept == ["VIOLATION a.go:evil\\x1b[31m\\x0aVIOLATION a.go:forged"] and "\x1b" not in reason,
          f"真 checker：跨行且含 ESC 的 func 名 → 一條違規一行、控制字元跳脫（got {kept!r}）")


def cases_sanitize(root, checks_dir, target):
    noisy = fake_check(root, "noisy.py",
                       "import sys\n"
                       "lines = ['VIOLATION a.go:\\x1b[31mevil', 'not a violation', 'VIOLATION a.go:c1\\x85end']"
                       " + ['VIOLATION a.go:f%d' % i for i in range(30)]\n"
                       "print('\\n'.join(lines))\nsys.exit(1)\n")
    write_config(checks_dir, "proj", [check_entry("noisy", noisy)])
    proc, _ = run_hook(checks_dir, edit_payload(target))
    reason = output_json(proc).get("reason", "")
    kept = [line for line in reason.splitlines() if line.startswith("VIOLATION ")]
    check("\\x1b[31mevil" in reason and "\x1b" not in reason and "\\x85end" in reason and "\x85" not in reason,
          f"reason 的控制字元（ESC、C1）跳脫成可見形式（got {reason[:200]!r}）")
    check("not a violation" not in reason, "reason 只保留 VIOLATION 行")
    check(len(kept) == 20, f"reason 至多 20 行 VIOLATION（got {len(kept)}）")
    check("另有 12 行未列" in reason, f"行數截斷提示剩餘行數（got {reason[-80:]!r}）")

    long_line = fake_check(root, "long.py", "import sys\nprint('VIOLATION a.go:' + 'x' * 3000)\nsys.exit(1)\n")
    write_config(checks_dir, "proj", [check_entry("long", long_line, message="m")])
    proc, _ = run_hook(checks_dir, edit_payload(target))
    reason = output_json(proc).get("reason", "")
    check(len(reason) <= 2100, f"reason 的 check 輸出上限 2000 字（got {len(reason)}）")
    check("（輸出過長已截斷）" in reason and "另有 0 行" not in reason, f"只因字數截斷 → 提示「輸出過長已截斷」（got {reason[-60:]!r}）")

    bidi = fake_check(root, "bidi.py", "import sys\nprint('VIOLATION a.go:\\u202eevil\\u2066x\\u2069\\u202a')\nsys.exit(1)\n")
    write_config(checks_dir, "proj", [check_entry("bidi", bidi)])
    proc, _ = run_hook(checks_dir, edit_payload(target))
    reason = output_json(proc).get("reason", "")
    check("\\u202eevil\\u2066x\\u2069\\u202a" in reason and not any(ch in reason for ch in "\u202a\u202e\u2066\u2069"),
          f"bidi 控制字元（U+202A–202E、U+2066–2069）跳脫（got {reason!r}）")

    escaper = fake_check(root, "esc-error.py", "import sys\nsys.stderr.write('\\x1b[2Jboom\\x9b\\n')\nsys.exit(2)\n")
    write_config(checks_dir, "proj", [check_entry("esc", escaper)])
    proc, _ = run_hook(checks_dir, edit_payload(target))
    message = output_json(proc).get("systemMessage", "")
    check("\\x1b[2Jboom\\x9b" in message and "\x1b" not in message and "\x9b" not in message,
          f"systemMessage 的控制字元跳脫（got {message!r}）")


def cases_match_rules(root, checks_dir, repo, recorder, marker):
    write_config(checks_dir, "proj", [check_entry("record", recorder)])
    braces = write(os.path.join(repo, "services", "{repo}.go"), "package services\n")
    run_hook(checks_dir, edit_payload(braces))
    recorded = read_marker(marker)
    check(recorded == f"{os.path.realpath(braces)} {os.path.realpath(repo)}", f"{{file}}／{{repo}} 單次代換：檔名 {{repo}}.go 不被二次代換（got {recorded!r}）")

    if sys.platform == "darwin":
        write(os.path.join(repo, "services", "b.go"), "package services\n")
        upper = os.path.join(repo, "SERVICES", "b.go")
        if os.path.isfile(upper):
            run_hook(checks_dir, edit_payload(upper))
            check(read_marker(marker) != "", "darwin：SERVICES/b.go 以 casefold 命中 services/*.go")
        else:
            print("SKIP 檔案系統區分大小寫，略過 casefold 案例")

        upper_repo = os.path.join(os.path.dirname(repo), os.path.basename(repo).upper(), "services", "a.go")
        if os.path.isfile(upper_repo):
            proc, _ = run_hook(checks_dir, edit_payload(upper_repo))
            recorded = read_marker(marker)
            canonical = os.path.join(os.path.realpath(repo), "services", "a.go")
            check(recorded == f"{canonical} {os.path.realpath(repo)}",
                  f"repo 目錄段大小寫不同 → rel 由 git show-prefix 求得、{{file}} 用正規路徑（got {recorded!r}, {proc.stdout!r}）")
        else:
            print("SKIP 檔案系統區分大小寫，略過 repo 段大小寫案例")


def cases_change_notice(root, checks_dir, target, recorder, marker):
    state_file = os.path.join(root, "state", "seen.json")
    config_path = write_config(checks_dir, "proj", [check_entry("notice-a", recorder)])
    proc, _ = run_hook(checks_dir, edit_payload(target))
    message = raw_output_json(proc).get("systemMessage", "")
    check(read_marker(marker) != "" and f"write_checks：proj 設定已變更，將執行：{sys.executable} {recorder} {{file}} {{repo}}" in message,
          f"設定首次出現／變更 → 照常執行並以 systemMessage 列出 cmd（got {message!r}）")

    proc, _ = run_hook(checks_dir, edit_payload(target))
    read_marker(marker)
    check("設定已變更" not in raw_output_json(proc).get("systemMessage", ""), f"設定未變 → 不再提示（got {proc.stdout!r}）")

    with open(state_file, encoding="utf-8") as f:
        seen = json.load(f)
    with open(config_path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    check(seen.get("proj") == digest, f"seen.json 記錄設定檔 sha256（got {seen!r}）")

    write_config(checks_dir, "proj", [check_entry("notice-a", recorder), check_entry("notice-b", recorder)])
    proc, _ = run_hook(checks_dir, edit_payload(target))
    read_marker(marker)
    message = raw_output_json(proc).get("systemMessage", "")
    check(message.count(f"{recorder} {{file}} {{repo}}") == 2 and "設定已變更" in message and "\n" not in message.split("設定已變更")[1],
          f"設定再變更 → 再提示，各 check 的 cmd 列在同一行（got {message!r}）")

    home = os.path.join(root, "fakehome")
    os.makedirs(home)
    env = {k: v for k, v in os.environ.items() if k != "WRITE_CHECKS_STATE_DIR"}
    env.update(HOME=home, WRITE_CHECKS_DIR=checks_dir)
    subprocess.run([sys.executable, HOOK], input=json.dumps(edit_payload(target)), capture_output=True, text=True, env=env, timeout=30)
    read_marker(marker)
    check(os.path.isfile(os.path.join(home, ".claude", "state", "write-checks", "seen.json")),
          "預設記錄位置 ~/.claude/state/write-checks/seen.json")


def write_raw_config(checks_dir, key, config):
    return write(os.path.join(checks_dir, key, "write-checks.json"), json.dumps(config))


def load_hook_module():
    spec = importlib.util.spec_from_file_location("write_checks_under_test", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cases_config_trust(root, checks_dir, repo, target, recorder, marker):
    config_path = write_raw_config(checks_dir, "proj", {"checks": [check_entry("record", recorder)]})
    config_dir = os.path.dirname(config_path)
    for path, mode, label in ((config_path, 0o666, "設定檔 world 可寫"), (config_path, 0o664, "設定檔 group 可寫"),
                              (config_dir, 0o777, "設定目錄 world 可寫"), (checks_dir, 0o777, "checks 根目錄 world 可寫"),
                              (checks_dir, 0o775, "checks 根目錄 group 可寫")):
        original = os.stat(path).st_mode & 0o777
        os.chmod(path, mode)
        proc, _ = run_hook(checks_dir, edit_payload(target))
        os.chmod(path, original)
        message = output_json(proc).get("systemMessage", "")
        check(read_marker(marker) == "" and "decision" not in output_json(proc) and "write_checks：proj 設定檔權限不安全，已略過" in message,
              f"{label} → 不跑任何 check、systemMessage 說明（got {proc.stdout!r}）")

    real_config = os.path.join(root, "elsewhere.json")
    os.rename(config_path, real_config)
    os.symlink(real_config, config_path)
    proc, _ = run_hook(checks_dir, edit_payload(target))
    os.remove(config_path)
    os.rename(real_config, config_path)
    check(read_marker(marker) == "" and "設定檔權限不安全" in output_json(proc).get("systemMessage", ""),
          f"設定檔是 symlink → 不跑（got {proc.stdout!r}）")

    root_alias = os.path.join(root, "checks-alias")
    os.symlink(checks_dir, root_alias)
    proc, _ = run_hook(root_alias, edit_payload(target))
    check(read_marker(marker) == "" and "設定檔權限不安全" in output_json(proc).get("systemMessage", ""),
          f"checks 根目錄是 symlink → 不跑（got {proc.stdout!r}）")

    hook = load_hook_module()
    _, problem = hook.read_trusted_config(config_path, checks_dir, os.getuid() + 1)
    check(problem is not None, "設定檔 owner 不是本人 uid → 判不安全")
    data, problem = hook.read_trusted_config(config_path, checks_dir, os.getuid())
    check(problem is None and data is not None and b'"checks"' in data, f"owner 本人且非 group／world 可寫 → 安全並讀出內容（got {problem!r}）")
    check(hook.relative_in_repo("../", "/x/a.go") is None and hook.relative_in_repo("services/", "/x/a.go") == "services/a.go",
          "relative_in_repo：prefix 以 .. 開頭 → None；一般 prefix＋basename")

    write_raw_config(checks_dir, "proj", {"repo_path": os.path.join(root, "other", ".proj"), "checks": [check_entry("record", recorder)]})
    proc, _ = run_hook(checks_dir, edit_payload(target))
    message = output_json(proc).get("systemMessage", "")
    check(read_marker(marker) == "" and "repo_path" in message and "已略過" in message,
          f"repo_path 與主 checkout 不符（同 basename 目錄）→ 不跑、systemMessage 說明（got {proc.stdout!r}）")

    for repo_path, label in ((os.path.realpath(repo), "realpath"), (repo, "symlink 路徑")):
        write_raw_config(checks_dir, "proj", {"repo_path": repo_path, "checks": [check_entry("record", recorder)]})
        run_hook(checks_dir, edit_payload(target))
        check(read_marker(marker) != "", f"repo_path 等於主 checkout（{label}）→ 照常執行")


def main():
    os.umask(0o022)
    with tempfile.TemporaryDirectory() as tmp:
        real = os.path.join(tmp, "real")
        os.makedirs(real)
        root = os.path.join(tmp, "link")
        os.symlink(real, root)
        check(os.path.realpath(root) != root, f"fixture 走自建 symlink 路徑（{root}）")
        checks_dir = os.path.join(root, "checks")
        os.makedirs(checks_dir)
        repo = make_repo(root, ".proj")
        target = write(os.path.join(repo, "services", "a.go"), "package services\n")
        test_file = write(os.path.join(repo, "services", "a_test.go"), "package services\n")
        other = write(os.path.join(repo, "cmd", "main.go"), "package main\n")
        marker = os.path.join(root, "ran.txt")

        recorder = cases_basic(root, checks_dir, repo, target, test_file, other, marker)
        violator = cases_block(root, checks_dir, target)
        cases_check_failures(root, checks_dir, target, violator)
        cases_sanitize(root, checks_dir, target)
        cases_match_rules(root, checks_dir, repo, recorder, marker)
        cases_config_trust(root, checks_dir, repo, target, recorder, marker)
        cases_change_notice(root, checks_dir, target, recorder, marker)
        cases_skip(root, checks_dir, repo)
        cases_worktree(root, checks_dir, recorder, marker)
        cases_real_checker(root, checks_dir)

    if FAILS:
        print(f"{FAILS} FAILED")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
