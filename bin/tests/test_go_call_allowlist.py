#!/usr/bin/env python3
"""go_call_allowlist 探針：在 mktemp 的 fixture git repo 真跑 CLI，驗證 exit code 與 VIOLATION 輸出。
fixture 一律走 TemporaryDirectory 內自建的 symlink 路徑，驗證相對路徑與 base 比對不受 symlink 影響（與 TMPDIR 本身是否 symlink 無關）。"""
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), "checks", "go_call_allowlist.py")
FAILS = 0

ALLOWLIST_TEST = '''package services

func TestGuard(t *testing.T) {
	allowedExponentUsers := map[string]bool{
		// "a.go:commented": true,
		/* "a.go:blocked": true, */
		"a.go:good": true,
		"a.go:falsy": false,
		`a.go:raw`: true,
	}
	_ = allowedExponentUsers
	otherFileUsers := map[string]bool{
		"x.go:good": true,
	}
	_ = otherFileUsers
}
'''


def check(cond, label):
    global FAILS
    FAILS += not cond
    print(f"{'OK  ' if cond else 'FAIL'} {label}")


def git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True)


def write(repo, rel, content):
    path = os.path.join(repo, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def make_repo(root):
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    write(repo, "services/guard_test.go", ALLOWLIST_TEST)
    write(repo, "README", "fixture\n")
    git(repo, "add", "services/guard_test.go", "README")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def commit(repo, rel, msg):
    git(repo, "add", rel)
    git(repo, "commit", "-q", "-m", msg)


def run(repo, path, var="allowedExponentUsers", base_ref=None):
    argv = [sys.executable, TOOL, "--file", path, "--repo", repo, "--call", "Exponent()",
            "--allowlist-from", "services/guard_test.go", "--allowlist-var", var]
    if base_ref:
        argv += ["--base-ref", base_ref]
    return subprocess.run(argv, capture_output=True, text=True, timeout=30)


def violations(proc):
    return sorted(line for line in proc.stdout.splitlines() if line.startswith("VIOLATION "))


def case_allowlisted_vs_not(repo):
    path = write(repo, "services/a.go", '''package services

func good(d decimal.Decimal) int32 {
	return d.Exponent()
}

func raw(d decimal.Decimal) int32 {
	return d.Exponent()
}

func bad(d decimal.Decimal) int32 {
	return d.Exponent()
}

func commented(d decimal.Decimal) int32 {
	return d.Exponent()
}

func blocked(d decimal.Decimal) int32 {
	return d.Exponent()
}

func falsy(d decimal.Decimal) int32 {
	return d.Exponent()
}
''')
    proc = run(repo, path)
    check(proc.returncode == 1, f"非白名單函式呼叫 → exit 1（got {proc.returncode}, stderr={proc.stderr.strip()!r}）")
    check(violations(proc) == ["VIOLATION a.go:bad", "VIOLATION a.go:blocked", "VIOLATION a.go:commented", "VIOLATION a.go:falsy"],
          f"只報非白名單；raw string key 算白名單、註解裡的 key 與值為 false 的 key 不算（got {violations(proc)}）")

    path = write(repo, "services/a.go", '''package services

func good(d decimal.Decimal) int32 {
	return d.Exponent()
}
''')
    proc = run(repo, path)
    check(proc.returncode == 0 and violations(proc) == [], f"只有白名單函式呼叫 → exit 0（got {proc.returncode}, {violations(proc)}）")

    proc = run(repo, path, var="otherFileUsers")
    check(proc.returncode == 1 and violations(proc) == ["VIOLATION a.go:good"],
          f"白名單 x.go:good 不放行 a.go:good（key 帶檔名不剝成裸名）（got {proc.returncode}, {violations(proc)}）")


def case_comments_and_literals(repo):
    path = write(repo, "services/b.go", '''package services

// d.Exponent() 只是註解
func lineComment() {
	x := 1 // d.Exponent()
	_ = x
}

func blockComment() {
	/* d.Exponent()
	   還是註解 */
}

func strings() string {
	return "d.Exponent()" + "\\"d.Exponent()\\""
}

func rawString() string {
	return `d.Exponent()
func fake() { d.Exponent() }`
}

func slashStarString() string {
	a, b, c := "/*", "d.Exponent()", "*/"
	return a + b + c
}

func runeLit() rune {
	return '"'
}

func afterRune(d decimal.Decimal) string {
	return "/* not a comment"
}

func commented() {
}
''')
    proc = run(repo, path)
    check(proc.returncode == 0 and violations(proc) == [],
          f"註解／字串／raw string／rune 裡的 Exponent() 不算（got {proc.returncode}, {violations(proc)}, {proc.stderr.strip()!r}）")


def case_lexer_edges(repo):
    path = write(repo, "services/f.go", '''package services

func urlThenCall(d decimal.Decimal) int32 {
	s := "http://x"; _ = s; return d.Exponent()
}

func slashStarString(d decimal.Decimal) string {
	return "/*"
}

func afterSlashStar(d decimal.Decimal) int32 {
	return d.Exponent()
}

func escapedQuote(d decimal.Decimal) int32 {
	s := "\\""; _ = s; return d.Exponent()
}

func runeQuote(d decimal.Decimal) int32 {
	r := '"'; _ = r; return d.Exponent()
}

func clean() {
}

var lateDecl = 1
''')
    proc = run(repo, path)
    check(violations(proc) == ["VIOLATION f.go:afterSlashStar", "VIOLATION f.go:escapedQuote",
                               "VIOLATION f.go:runeQuote", "VIOLATION f.go:urlThenCall"],
          f"\"http://x\" 同行呼叫、\"/*\" 字串之後、跳脫引號、rune '\"' 之後的真呼叫都要抓（got {violations(proc)}）")

    path = write(repo, "services/g.go", '''package services

var early = d.Exponent()

func first() {
}

var trailing = d.Exponent()

func second() {
}
''')
    proc = run(repo, path)
    check(violations(proc) == ["VIOLATION g.go:<檔案前置區>", "VIOLATION g.go:first"],
          f"前置區記 <檔案前置區>、函式後的 package-level 宣告歸前一塊（與守衛測試 topLevelFuncs 同）（got {violations(proc)}）")


def case_escaped_key(repo):
    path = write(repo, "services/k.go", "package services\n\nfunc evil\u202e\x1b(d D) int32 {\n\treturn d.Exponent()\n}\n")
    proc = run(repo, path)
    check(violations(proc) == ["VIOLATION k.go:evil\\u202e\\x1b"] and "\u202e" not in proc.stdout,
          f"key 內的 bidi／C0 控制字元跳脫（got {violations(proc)!r}）")


def case_method_key(repo):
    path = write(repo, "services/c.go", '''package services

func (r *T) m(d decimal.Decimal) int32 {
	return d.Exponent()
}

func (T[K]) generic(d decimal.Decimal) int32 {
	return d.Exponent()
}

func typed[K any](d decimal.Decimal) int32 {
	return d.Exponent()
}
''')
    proc = run(repo, path)
    check(violations(proc) == ["VIOLATION c.go:generic", "VIOLATION c.go:m", "VIOLATION c.go:typed[K any]"],
          f"method 取接收者之後的名稱；名稱取到第一個 ( 為止（與守衛測試 funcNameOf 同）（got {violations(proc)}）")


def case_base_ref(repo):
    rel = "services/d.go"
    path = write(repo, rel, '''package services

func old(d decimal.Decimal) int32 {
	return d.Exponent()
}
''')
    proc = run(repo, path)
    check(proc.returncode == 1 and violations(proc) == ["VIOLATION d.go:old"],
          f"新檔（base 不存在）→ 全部算新增（got {proc.returncode}, {violations(proc)}）")
    commit(repo, rel, "existing violation")

    proc = run(repo, path)
    check(proc.returncode == 0 and violations(proc) == [], f"base 已有同一違規 → exit 0（got {proc.returncode}, {violations(proc)}）")

    write(repo, rel, '''package services

func old(d decimal.Decimal) int32 {
	return d.Exponent() + 1
}

func fresh(d decimal.Decimal) int32 {
	return d.Exponent()
}
''')
    proc = run(repo, path)
    check(proc.returncode == 1 and violations(proc) == ["VIOLATION d.go:fresh"],
          f"base 沒有、現在新增 → 只報新增（got {proc.returncode}, {violations(proc)}）")

    proc = run(repo, path, base_ref="HEAD~1")
    check(proc.returncode == 1 and violations(proc) == ["VIOLATION d.go:fresh", "VIOLATION d.go:old"],
          f"--base-ref 下檔案不存在 → 全部算新增（got {proc.returncode}, {violations(proc)}）")

    proc = run(repo, path, base_ref="no-such-ref")
    check(proc.returncode == 2, f"--base-ref 不是有效 commit → exit 2（got {proc.returncode}）")


def case_arg_errors(repo):
    path = write(repo, "services/e.go", "package services\n")
    proc = run(repo, path, var="missingVar")
    check(proc.returncode == 2, f"白名單檔沒有該變數 → exit 2（got {proc.returncode}）")
    check(proc.stderr.strip() != "", "白名單解析失敗 stderr 有說明")

    proc = run(repo, os.path.join(repo, "services", "nope.go"))
    check(proc.returncode == 2, f"--file 讀不到 → exit 2（got {proc.returncode}）")

    proc = subprocess.run([sys.executable, TOOL, "--file", path], capture_output=True, text=True, timeout=30)
    check(proc.returncode == 2, f"缺參數 → exit 2（got {proc.returncode}）")


def case_unexpected_exception(repo):
    spec = importlib.util.spec_from_file_location("go_call_allowlist_under_test", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def explode(_args):
        raise RuntimeError("boom")

    module.new_violations = explode
    err = io.StringIO()
    with redirect_stderr(err):
        code = module.main(["--file", os.path.join(repo, "README"), "--repo", repo, "--call", "Exponent()",
                            "--allowlist-from", "services/guard_test.go", "--allowlist-var", "allowedExponentUsers"])
    check(code == 2 and "boom" in err.getvalue(), f"未預期例外 → exit 2、stderr 說明（got {code}, {err.getvalue()!r}）")


def case_no_lazy_fetch(root):
    repo = make_repo(os.path.join(root, "partial"))
    write(repo, "services/h.go", "package services\n\nfunc legacy(d D) int32 {\n\treturn d.Exponent()\n}\n")
    commit(repo, "services/h.go", "base")
    blob = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD:services/h.go"], check=True,
                          capture_output=True, text=True).stdout.strip()
    ssh_marker = os.path.join(root, "ssh-ran")
    fsmonitor_marker = os.path.join(root, "fsmonitor-ran")
    fsmonitor = write(root, "fsmonitor.sh", f"#!/bin/sh\ntouch '{fsmonitor_marker}'\nexit 1\n")
    os.chmod(fsmonitor, 0o755)
    for key, value in (("core.repositoryformatversion", "1"), ("extensions.partialClone", "origin"),
                       ("remote.origin.url", "ssh://example.invalid/x.git"), ("remote.origin.promisor", "true"),
                       ("core.sshCommand", f"touch '{ssh_marker}'; exit 1;"), ("core.fsmonitor", fsmonitor)):
        git(repo, "config", key, value)
    os.remove(os.path.join(repo, ".git", "objects", blob[:2], blob[2:]))

    proc = run(repo, os.path.join(repo, "services", "h.go"))
    check(not os.path.exists(ssh_marker), f"partial clone 缺 blob 時不觸發 lazy fetch（core.sshCommand 未執行）（stderr={proc.stderr.strip()[:200]!r}）")
    check(not os.path.exists(fsmonitor_marker), "core.fsmonitor 未執行")
    check(proc.returncode == 1 and violations(proc) == ["VIOLATION h.go:legacy"],
          f"base blob 取不到視為空檔、違規全算新增（got {proc.returncode}, {violations(proc)}）")


def main():
    with tempfile.TemporaryDirectory() as tmp:
        real = os.path.join(tmp, "real")
        os.makedirs(real)
        root = os.path.join(tmp, "link")
        os.symlink(real, root)
        check(os.path.realpath(root) != root, f"fixture 走自建 symlink 路徑（{root}）")
        repo = make_repo(root)
        case_allowlisted_vs_not(repo)
        case_comments_and_literals(repo)
        case_lexer_edges(repo)
        case_method_key(repo)
        case_escaped_key(repo)
        case_base_ref(repo)
        case_arg_errors(repo)
        case_unexpected_exception(repo)
        case_no_lazy_fetch(root)
    if FAILS:
        print(f"{FAILS} FAILED")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
