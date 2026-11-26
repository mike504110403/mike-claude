#!/usr/bin/env python3
"""某個呼叫字面（如 `Exponent()`）只准白名單函式使用；只報相對 base 版本「新增」的違規。

用法：
  go_call_allowlist.py --file <絕對路徑.go> --repo <repo toplevel> --call <字面> \
      --allowlist-from <repo 內相對路徑的 Go 測試檔> --allowlist-var <變數名> [--base-ref HEAD]

權威與差異：
  守衛測試（lottery-platform services/rebate_decimal_places_test.go 的 allowedExponentUsers 段）是權威，
  本工具只是寫入當下的早期警示。切塊與取名逐條對齊該測試的 topLevelFuncs／funcNameOf，與守衛的差異有兩類：
  (a) 字串／rune／raw string 字面值裡的呼叫字面不算（守衛只去註解，會把字串裡的也算進去）——本工具較寬。
  (b) 守衛的 stripGoComments 較樸素：先全檔找 `/*` 到 `*/`、再逐行砍 `//` 之後，不認字串與行註解的邊界。
      行註解內含 `/*`（如 lottery-platform services/line_entry.go:204 的 `// ... /logos/*，...`）會讓守衛
      從那裡一路吃到下一個 `*/`；字串含 `//`（如 `"http://x"; d.Exponent()`）會讓守衛砍掉同行後段。
      這兩種形狀下守衛看不到真呼叫，本工具看得到——本工具判定比守衛嚴。以守衛為準時，應先修守衛再對齊。

判定：
  - 單趟 lexer 遮掉 `//`、`/* */` 註解與字串／rune／raw string 字面值，換行一律保留。
  - 以 `\\nfunc ` 切塊：第一塊是 `<檔案前置區>`；函式之後的 package-level 宣告歸前一塊。
  - 函式名：以 `(` 開頭先剝到第一個 `)`（receiver），再取到第一個 `(` 為止並去空白
    （所以泛型函式名含型參，如 `typed[K any]`，與測試同）。
  - 函式本體含 --call 字面且 `<檔案 basename>:<函式名>` 不在白名單者為違規。
  - 白名單只有一個 source：--allowlist-from 檔中 `<allowlist-var> := map[string]bool{ ... }` 區塊
    （去註解後以配對的 `}` 結束）裡值為 `true` 的字串 key。
  - 同一判定套在 `git -C <repo> show <base-ref>:<相對路徑>`（該 ref 下檔案不存在或 blob 取不到視為空檔），
    輸出「現在違規 − base 已違規」。git 一律帶 GIT_NO_LAZY_FETCH=1、`-c core.fsmonitor=false -c protocol.allow=never`：
    寫入當下的檢查不得因 repo 設定（partial clone 的 promisor、core.sshCommand、fsmonitor）而連網或執行任意指令。

輸出每條新增違規一行 `VIOLATION <檔名:函式名>`；key 內的 C0／C1 與 bidi（U+202A–202E、U+2066–2069）控制字元
跳脫成 `\\xNN`／`\\uNNNN`，確保一條違規恰一行、終端不被改寫。
exit 0＝無新增違規；1＝有；2＝參數錯、檔案讀不到、--base-ref 不是有效 commit、白名單解析失敗、任何未預期例外。
只用 Python 3.9 標準庫。
"""
import argparse
import json
import os
import re
import subprocess
import sys

PREAMBLE = "<檔案前置區>"
LITERAL_MARK = "\x00"
FUNC_SEPARATOR = "\nfunc "
GIT_HARDENING = ("-c", "core.fsmonitor=false", "-c", "protocol.allow=never")
CONTROL_CHARS = re.compile("[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")


def escape_char(match):
    code = ord(match.group(0))
    return f"\\x{code:02x}" if code <= 0xFF else f"\\u{code:04x}"


class CheckError(Exception):
    pass


def mask_source(src):
    code = []
    literals = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            end = src.find("\n", i)
            i = n if end < 0 else end
        elif ch == "/" and nxt == "*":
            end = src.find("*/", i + 2)
            stop = n if end < 0 else end + 2
            code.append(" " + "\n" * src.count("\n", i, stop))
            i = stop
        elif ch in "\"'`":
            stop = literal_end(src, i)
            code.append(f"{LITERAL_MARK}{len(literals)}{LITERAL_MARK}" + "\n" * src.count("\n", i, stop))
            literals.append(src[i:stop])
            i = stop
        else:
            code.append(ch)
            i += 1
    return "".join(code), literals


def literal_end(src, start):
    quote = src[start]
    i = start + 1
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "\\" and quote != "`":
            i += 2
            continue
        if ch == quote:
            return i + 1
        if ch == "\n" and quote != "`":
            return i
        i += 1
    return n


def func_name(chunk):
    name = chunk
    if name.startswith("("):
        close = name.find(")")
        if close >= 0:
            name = name[close + 1:].strip()
    paren = name.find("(")
    if paren >= 0:
        name = name[:paren]
    return name.strip()


def top_level_funcs(code):
    chunks = ("\n" + code).split(FUNC_SEPARATOR)
    return [(PREAMBLE, chunks[0])] + [(func_name(chunk), chunk) for chunk in chunks[1:]]


def callers(src, basename, call):
    code, _ = mask_source(src)
    return {f"{basename}:{name}" for name, body in top_level_funcs(code) if call in body}


def string_value(literal):
    if literal.startswith("`"):
        return literal[1:-1]
    if literal.startswith('"') and len(literal) >= 2 and literal.endswith('"'):
        try:
            return json.loads(literal)
        except ValueError as exc:
            raise CheckError(f"白名單 key 無法解碼：{literal}") from exc
    return None


def parse_allowlist(src, var, source_label):
    code, literals = mask_source(src)
    header = re.search(rf"(?<!\w){re.escape(var)}\s*:=\s*map\[string\]bool\s*\{{", code)
    if not header:
        raise CheckError(f"{source_label} 找不到 `{var} := map[string]bool{{`")
    depth = 1
    pos = header.end()
    while pos < len(code) and depth:
        depth += {"{": 1, "}": -1}.get(code[pos], 0)
        pos += 1
    if depth:
        raise CheckError(f"{source_label} 的 {var} 區塊沒有閉合的 }}")
    keys = set()
    for index in re.findall(rf"{LITERAL_MARK}(\d+){LITERAL_MARK}\s*:\s*true\b", code[header.end():pos]):
        value = string_value(literals[int(index)])
        if value is not None:
            keys.add(value)
    return keys


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as exc:
        raise CheckError(f"讀不到 {path}：{exc.strerror}") from exc


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *GIT_HARDENING, *args], capture_output=True, text=True, errors="replace",
                          env=dict(os.environ, GIT_NO_LAZY_FETCH="1"))


def base_source(repo, base_ref, rel):
    if git(repo, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}").returncode != 0:
        raise CheckError(f"--base-ref {base_ref} 不是 {repo} 的有效 commit")
    shown = git(repo, "show", f"{base_ref}:{rel}")
    return shown.stdout if shown.returncode == 0 else ""


def repo_relative(repo, path):
    rel = os.path.relpath(os.path.realpath(path), os.path.realpath(repo))
    if rel == os.pardir or rel.startswith(os.pardir + os.sep):
        raise CheckError(f"{path} 不在 --repo {repo} 之下")
    return rel


def new_violations(args):
    current_src = read_text(args.file)
    rel = repo_relative(args.repo, args.file)
    allowlist_path = os.path.join(args.repo, args.allowlist_from)
    allowed = parse_allowlist(read_text(allowlist_path), args.allowlist_var, args.allowlist_from)
    basename = os.path.basename(args.file)
    current = callers(current_src, basename, args.call) - allowed
    existing = callers(base_source(args.repo, args.base_ref, rel), basename, args.call) - allowed
    return sorted(current - existing)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="呼叫字面只准白名單函式使用（只報新增違規）")
    parser.add_argument("--file", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--call", required=True)
    parser.add_argument("--allowlist-from", required=True)
    parser.add_argument("--allowlist-var", required=True)
    parser.add_argument("--base-ref", default="HEAD")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    try:
        violations = new_violations(args)
    except CheckError as exc:
        print(f"go_call_allowlist: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"go_call_allowlist: 未預期例外 {type(exc).__name__}：{exc}", file=sys.stderr)
        return 2
    for key in violations:
        print("VIOLATION " + CONTROL_CHARS.sub(escape_char, key))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
