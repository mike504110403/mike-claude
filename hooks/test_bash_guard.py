#!/usr/bin/env python3
"""bash_guard 探針：餵已知 payload 驗證判定。push 閘門的真實 repo 組裝路徑在 test_gate_evidence.py。"""
import importlib.util
import json
import os
import subprocess
import sys
import time

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bash_guard.py")
FILE_GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "file_guard.py")
PUSH = "git pu" + "sh"
STASH = "sta" + "sh"
CLEAN = "git cle" + "an -fd"
LIMIT = 8192

CASES = [
    # 真 force 不因分段退到 ask；git -C 形式的 -f 屬別的指令時只問
    ("git pu" + "sh -o 'a;b' -" + "f o d", "deny"),
    ("git pu" + "sh o d && curl -" + "f x", "deny"),
    ("git -C /x pu" + "sh o d && curl -" + "f x", "ask"),
    ("git -C /x pu" + "sh\\\n -" + "f o d", "deny"),
    ("git -C /x pu" + "sh -" + "f\\\n o d", "deny"),
    ("`git -C /x pu" + "sh`", "ask"),
    ("git -C /x pu" + "sh$IFS-" + "f o d", "ask"),
    # commit 沒帶訊息會開編輯器；引號裡的 | 與 ~
    ("git commit nginx.conf", "ask"),
    ("git commit --amend -- nginx.conf", "ask"),
    ("git commit -m nginx", "allow"),
    ("git commit -am nginx", "allow"),
    ("git commit -cmain nginx.conf", "ask"),
    ("git commit -tmpl.txt nginx.conf", "ask"),
    ("git commit -Smain nginx.conf", "ask"),
    ("git commit -- -m nginx.conf", "ask"),
    ("git commit # -m nginx", "ask"),
    ("git commit -qm nginx", "allow"),
    ("git commit -m nginx -- a.txt", "allow"),
    ("~'/.claude/bin/gate-evidence' record --kind nginx-test", "ask"),
    ('~"/.claude/bin/gate-evidence" check nginx', "ask"),
    ("git add :/ nginx", "ask"),
    ("git add -u nginx", "ask"),
    ("git add --update nginx", "ask"),
    ("git add .. nginx", "ask"),
    ("git add ../.. nginx", "ask"),
    ("git -C /srv/nginx add ..", "ask"),
    ("git add --no-ignore-removal nginx", "ask"),
    ("git add ../nginx.conf", "allow"),
    ("git add nginx '|' cat .", "ask"),
    ("nginx -t '|' cat -s reload", "ask"),
    ("'~/.claude/bin/gate-evidence' record --kind nginx-test", "ask"),
    # 會開編輯器或跑 gpg 的 git 選項不算唯讀
    ("git commit -e -m nginx", "ask"),
    ("git commit --edit -m nginx", "ask"),
    ("git add -e nginx.conf", "ask"),
    ("git log --show-signature -- nginx", "ask"),
    ("grep -e nginx a", "allow"),
    ("git commit -m nginx", "allow"),
    # -C 路徑含空白、waive 引號變形
    ('git -C "/a b" pu' + 'sh origin dev', "ask"),
    ('git -C "/a b" pu' + 'sh -' + 'f origin dev', "deny"),
    ("git -C '/a b' pu" + "sh origin +dev", "deny"),
    ('gate-evidence "waive" --repo . --reason x', "ask"),
    ('"gate-evidence" waive --repo . --reason x', "ask"),
    ('gate-evidence -- waive --repo . --reason x', "ask"),
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

    # rm regex 改寫後判定不變
    ("rm " + "-fr /tmp/x", "deny"),
    ("rm " + "-r -f /tmp/x", "deny"),
    ("rm " + "-f -r /tmp/x", "deny"),
    ("rm " + "-rv -f /tmp/x", "deny"),
    ("rm -f a.txt", "allow"),
    ("rm a.txt", "allow"),

    # 單純唯讀免問
    ("grep -rn nginx deploy/", "allow"),
    ("cat db/migrate/1.sql", "allow"),
    ("ls db/migrate", "allow"),
    ("cd /x && grep migrate a.txt", "allow"),
    ("grep nginx a | head -5", "allow"),
    ("git log --oneline -- nginx", "allow"),
    ("git add deploy/nginx.conf", "allow"),
    ('git commit -m "fix nginx"', "allow"),
    ("git diff nginx.conf", "allow"),
    ("git -C /x log -- nginx", "allow"),
    ("grep 'a;b' nginx.conf", "allow"),
    ("nginx -t", "allow"),
    ("gate-evidence record --repo . --kind nginx-test", "allow"),
    ("gate-evidence check --repo /x/migrate", "allow"),
    ("~/.claude/bin/gate-evidence record --repo /x/nginx --kind nginx-test", "allow"),
    (os.path.expanduser("~") + "/.claude/bin/gate-evidence check --repo /x/nginx", "allow"),
    ("git log --pretty=oneline -- nginx", "allow"),
    ("git add -p nginx.conf", "allow"),
    ("cat a | grep --exclude=x nginx", "allow"),
    ("grep nginx " + "a" * (LIMIT - len("grep nginx ")), "allow"),

    # 不單純或非唯讀，nginx／migration 照問
    ("nginx -s reload", "ask"),
    ("nginx -T", "ask"),
    ("nginx -t -s reload", "ask"),
    ("nginx -t -c /x/nginx.conf", "ask"),
    ("nginx -t -c {f,-g,x}", "ask"),
    ("systemctl reload nginx", "ask"),
    ("migrate up", "ask"),
    ("goose up", "ask"),
    ("make migrate", "ask"),
    ("psql -f db/migrate/1.sql", "ask"),
    ("migrate -database postgres://u@localhost/db up", "ask"),
    ("grep nginx a > /etc/hosts", "ask"),
    ("GIT_EDITOR='goose up' git commit", "ask"),
    ("PAGER=goose git log", "ask"),
    ("git -c core.pager=goose log", "ask"),
    ("git rebase --exec 'migrate up' HEAD~1", "ask"),
    ("cat nginx.conf; sh x", "ask"),
    ("echo 'goose up' > a.sh; sh a.sh", "ask"),
    ("grep nginx $(cat f)", "ask"),
    ("./grep nginx a", "ask"),
    ("/tmp/cat nginx.conf", "ask"),
    ("git diff --output=/etc/nginx/a", "ask"),
    ("git diff --outpu=/etc/nginx/a", "ask"),
    ("git diff --ext-diff nginx.conf", "ask"),
    ("git show --textconv nginx.conf", "ask"),
    ("git log --exec=x -- nginx", "ask"),
    ("rg --pre=sh nginx a", "ask"),
    ("rg --pre sh nginx a", "ask"),
    ("rg --hostname-bin=x nginx a", "ask"),
    ("grep nginx a | sh", "ask"),
    ("grep nginx a || sh x", "ask"),
    ("grep nginx a || grep b c", "ask"),
    ("grep nginx a |& head", "ask"),
    ("grep nginx a |", "ask"),
    ("grep nginx a & sh x", "ask"),
    ("(grep nginx a)", "ask"),
    ("grep nginx < a", "ask"),
    ("grep 'nginx$' a", "ask"),
    ("grep nginx `cat f`", "ask"),
    ("grep nginx a\nsh x", "ask"),
    ("grep nginx 'a", "ask"),
    ("cd /x && cd /y && grep nginx a", "ask"),
    ("cd /x; grep nginx a", "ask"),
    ("cd -P /x && grep nginx a", "ask"),
    ("grep nginx a && cd /x", "ask"),
    ("gate-evidence record --repo /x --kind nginx-test && nginx -s reload", "ask"),
    ("/tmp/.claude/bin/gate-evidence record --repo /x/nginx", "ask"),
    ("~/.claude/bin/../../../tmp/bin/gate-evidence check --repo /x/nginx", "ask"),
    ("./bin/gate-evidence check --repo /x/nginx", "ask"),
    ("bin/gate-evidence check --repo /x/nginx", "ask"),
    ("/Users/Shared/.claude/bin/gate-evidence record --repo /x/nginx", "ask"),
    ("/home/other/.claude/bin/gate-evidence record --repo /x/nginx", "ask"),
    # 字元黑名單：shell 會展開、shlex 不會
    ("rg --p{r,r}e=./x nginx a", "ask"),
    ("git diff {--output=/etc/nginx/a,HEAD}", "ask"),
    ("rg nginx *", "ask"),
    ("cat nginx?conf", "ask"),
    ("cat nginx[a].conf", "ask"),
    ("cat nginx\\ a", "ask"),
    ("cat nginx\rgoose up", "ask"),
    ("grep 'a*' nginx.conf", "ask"),
    # file 不再算唯讀
    ("file -C -m nginx.magic", "ask"),
    ("file nginx.conf", "ask"),
    # 黑名單對全部 token，不看 | 分段
    ("rg nginx . '|' git log --pre=./m.sh", "ask"),
    ("rg nginx . '|' git log --hostname-bin=./m.sh", "ask"),
    ("git diff --no-index a b '|' cat --output=/etc/nginx/a", "ask"),
    ("git log -p '|' cat --ext-diff -- nginx", "ask"),
    ("cat nginx '|' cat --textconv", "ask"),
    ("cat nginx '|' cat --exec=x", "ask"),
    # git add 全量形式
    ("git -C /srv/nginx add .", "ask"),
    ("git -C /srv/nginx add -A", "ask"),
    ("git -C /srv/nginx add --all", "ask"),
    ("git -C /srv/nginx add --al", "ask"),
    ("git -C /srv/nginx add ./", "ask"),
    ("git add -Av nginx", "ask"),
    ("git add -vA nginx", "ask"),
    ("gate-evidence list --repo /x/nginx", "ask"),
    ("# " + "x" * LIMIT + " grep nginx a", "ask"),
    ("grep nginx " + "a" * (LIMIT - len("grep nginx ") + 1), "ask"),

    # 硬擋不被詢問遮蔽
    ('git -C "$R"/sub ' + STASH + " pop", "deny"),
    ("git -C $PWD " + STASH + " drop", "deny"),
    ("git -C '$R'/x " + STASH + " pop", "deny"),
    (f"git restore a && {CLEAN}", "deny"),
    ("git checkout -- a && git " + STASH + " pop", "deny"),
    (f"{PUSH} origin dev && {CLEAN}", "deny"),
    ("git restore a && npx x", "deny"),

    # force push 的全域選項形式
    (f"git -C /x pu" + "sh -f o d", "deny"),
    ('git -C "$R" pu' + "sh o +d", "deny"),
    ("git --no-pager pu" + "sh --force o d", "deny"),
    ("git -C /x pu" + "sh --force-with-lease o d", "deny"),
    ("git -C /x pu" + "sh -uf o d", "deny"),
    (f"{PUSH} origin +dev", "deny"),
    (f"{PUSH} origin dev; echo -f", "deny"),
    (f"{PUSH} o d && curl -f x", "deny"),
    (f"curl -f x && {PUSH} o d", "deny"),
    (f"{PUSH} o d && curl --force x", "deny"),
    ('git --work-tree="/a b/c" pu' + "sh -f o d", "deny"),
    ("git -C /x \\\npu" + "sh -f o d", "deny"),
    ("git -C /x pu" + "sh \\\n -f o d", "deny"),
    ('git -c core.sshCommand="ssh -i k" pu' + "sh -f origin main", "deny"),
    ("git -C /x pu" + "sh -4f o d", "deny"),
    (f"{PUSH} -4f o d", "deny"),
    ("sh -c 'git -C /x pu" + "sh -f'", "deny"),
    ("(git -C /x pu" + "sh -f)", "deny"),
    ('git commit -m "push -f"', "allow"),
    ("git -C /x log -f", "allow"),
    ("git -c pu" + "sh.default=x status", "allow"),
    ("git --git-dir pu" + "sh/.git log", "allow"),
    ("git -C pu" + "sh log -f", "allow"),
    ("git -C pu" + "sh log", "allow"),
    ("git -C /x pu" + "sh-foo a", "allow"),
    ("git --no-pager pu" + "sh.x a", "allow"),

    # 全域選項形式的 push 一律進閘門
    ("git -C /x pu" + "sh origin dev", "ask"),
    ("git --git-dir=/x pu" + "sh origin dev", "ask"),
    ("git --git-dir /x --work-tree /y pu" + "sh origin dev", "ask"),
    ("git --no-pager -c a.b=c pu" + "sh origin dev", "ask"),
    (f"{PUSH} -o f origin dev", "ask"),
    (f"{PUSH} origin :old", "ask"),
    (f"git commit -m '{PUSH} origin dev'", "ask"),
    ("git -C /x pu" + "sh -o f origin dev; echo", "ask"),
    ('git --git-dir="/a b" pu' + "sh o d", "ask"),
    ('git -C a"b c"/d pu' + "sh o d", "ask"),
    ("git --config-env a.b=HOME pu" + "sh o d", "ask"),
    ("git --attr-source HEAD pu" + "sh o d", "ask"),
    ("git \\\n pu" + "sh o d", "ask"),
    ("(git -C /x pu" + "sh)", "ask"),
    ("sh -c 'git -C /x pu" + "sh'", "ask"),
    (f"{PUSH} o ^d", "ask"),

    # supabase
    ("supabase db " + "push", "ask"),
    ("supabase --project-ref x db " + "push", "ask"),
    ("pnpm exec supabase db " + "push --linked", "ask"),
    ("supabase db pull", "allow"),
    ("supabase status; db " + "push", "allow"),
    ("grep 'supabase db " + "push' a", "allow"),

    # waive
    ("gate-evidence waive --repo . --reason r", "ask"),
    ("~/.claude/bin/gate-evidence waive --repo . --reason r", "ask"),
    (f"gate-evidence waive --repo . --reason r && {PUSH} origin dev", "ask"),
    ("gate-evidence waive --repo . --reason r; git " + STASH, "deny"),
]


# 超長命令：不跑 FORCE_RE／PUSH_RE／simple_push；git、push 字串都在就問，既有 regex 照跑
PAD = " # " + "x" * 9000
LONG_CASES = [
    ("grep nginx " + "a" * 9000, "ask", "全域規則"),
    (f"{PUSH} origin dev{PAD}", "ask", "無法判定"),
    ("git -C /x pu" + f"sh origin dev{PAD}", "ask", "無法判定"),
    ("git -C /x pu" + f"sh -f origin dev{PAD}", "ask", "無法判定"),
    ("echo git; echo pu" + f"sh{PAD}", "ask", "無法判定"),
    (f"{PUSH} -f origin dev{PAD}", "deny", "force push"),
    (f"{PUSH} origin dev; curl -f x{PAD}", "deny", "force push"),
    ("rm " + f"-rf /tmp/x{PAD}", "deny", "rm -rf"),
    (f"git status{PAD}", "allow", ""),
    (f"echo pu" + f"sh{PAD}", "allow", ""),
]

# hook 收到壞 payload：崩潰一律 ask，不得放行
BAD_PAYLOADS = ["not json", "[]", '"x"', '{"tool_input":"x"}', "null", "{}", '{"tool_input":null}']
BAD_COMMANDS = ['{"tool_input":{"command":123}}', '{"tool_input":{"command":null}}', '{"tool_input":{"command":[]}}']
BAD_PATHS = ['{"tool_input":{"file_path":123}}', '{"tool_input":{"file_path":null}}']

# 病態輸入：8192 字元以內也要快（6 秒閘門之外 regex 自己不得吃掉 hook 的 10 秒）
PATHOLOGICAL = [
    (PUSH + " ") * 900,
    ("git -C /x pu" + "sh a ") * 450,
    "git" + " -C -C -C -C -C -C -C -C -C" * 300,
    "git" + ' -c "a" -c "a" -c "a" -c "a"' * 280,
    "git" + " --a=b" * 1300,
    "git" + " \\\n" * 2000,
    ("git " + "-c a\\\n " * 9) * 90,
    ("git pu" + "sh \\\n ") * 600,
]


def run_hook(hook, payload):
    return subprocess.run([sys.executable, hook], input=payload, capture_output=True, text=True).stdout.strip()


def decide(cmd):
    out = run_hook(GUARD, json.dumps({"tool_input": {"command": cmd}}))
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else "allow"


def decide_with_reason(cmd):
    out = run_hook(GUARD, json.dumps({"tool_input": {"command": cmd}}))
    if not out:
        return "allow", ""
    spec = json.loads(out)["hookSpecificOutput"]
    return spec["permissionDecision"], spec["permissionDecisionReason"]


def load_guard():
    spec = importlib.util.spec_from_file_location("bash_guard_probe", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(passed, label):
    print(f"{'OK ' if passed else 'FAIL'} {label}")
    return 0 if passed else 1


def main():
    fails = 0
    for cmd, expected in CASES:
        actual = decide(cmd)
        ok = "OK " if actual == expected else "FAIL"
        if actual != expected:
            fails += 1
        print(f"{ok} {cmd[:120]!r} => {actual} (expected {expected})")

    # rm 接大量 -rr 不得指數回溯：live 版 30 組就跑不完，timeout 當失敗
    cmd = "rm " + "-rr " * 5000 + "x"
    started = time.monotonic()
    try:
        actual = subprocess.run([sys.executable, GUARD], input=json.dumps({"tool_input": {"command": cmd}}),
                                capture_output=True, text=True, timeout=5).stdout
        elapsed = time.monotonic() - started
        passed = '"ask"' in actual and elapsed < 3
    except subprocess.TimeoutExpired:
        elapsed, passed = 5.0, False
    fails += not passed
    print(f"{'OK ' if passed else 'FAIL'} rm 大量 -rr 判 ask 且 {elapsed:.2f}s < 3s")

    for cmd, expected, word in LONG_CASES:
        actual, reason = decide_with_reason(cmd)
        fails += check(actual == expected and word in reason, f"超長 {cmd[:40]!r} => {actual} (expected {expected} {word})")

    for payload in BAD_PAYLOADS + BAD_COMMANDS:
        out = run_hook(GUARD, payload)
        fails += check('"ask"' in out, f"bash_guard 壞 payload {payload} 判 ask")
    for payload in BAD_PAYLOADS + BAD_PATHS:
        out = run_hook(FILE_GUARD, payload)
        fails += check('"ask"' in out, f"file_guard 壞 payload {payload} 判 ask")
    fails += check(run_hook(FILE_GUARD, json.dumps({"tool_input": {"file_path": "/x/nginx.conf"}})) == "",
                   "file_guard repo 內 nginx 檔仍不問")
    fails += check('"ask"' in run_hook(FILE_GUARD, json.dumps({"tool_input": {"file_path": "/etc/nginx/a"}})),
                   "file_guard 系統 nginx 路徑仍問")

    bg = load_guard()
    fails += check(bg.simple_readonly("cat a#;sh b") is False, "simple_readonly('cat a#;sh b') is False")
    fails += check(bg.simple_push(f"{PUSH} o ^d", "/r") is None, "simple_push 拒 ^ref")

    for cmd in PATHOLOGICAL:
        started = time.monotonic()
        decide(cmd)
        elapsed = time.monotonic() - started
        fails += check(len(cmd) <= LIMIT and elapsed < 2, f"病態 {cmd[:24]!r} len={len(cmd)} {elapsed:.2f}s < 2s")

    print(f"\n{'ALL PASS' if fails == 0 else str(fails) + ' FAILURES'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
