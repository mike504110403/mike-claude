#!/usr/bin/env python3
"""PostToolUse hook（matcher Edit|Write）：agent 寫完檔的當下，跑該檔所屬 repo 的本機寫入檢查，
違規時把指向根因的訊息回給 agent（檔案已寫入，不會回滾）。

只在該 repo 有設定時生效：
  設定檔 ${WRITE_CHECKS_DIR:-~/.claude/checks}/<key>/write-checks.json
  key＝主 checkout 目錄名去前導「.」（由 `git rev-parse --path-format=absolute --git-common-dir` 求得，
  所以同一 repo 的所有 worktree 共用一份設定）。設定檔不存在 → 直接 exit 0，不跑任何東西。
  規則與設定刻意放在本機、不進公司 repo；寫入 ~/.claude/checks/ 由 file_guard／bash_guard 轉 ask
  （新增自動執行入口需 Mike 確認）。

設定的信任條件（不符 → 不跑任何 check，systemMessage「write_checks：<key> 設定檔權限不安全，已略過（<細節>）」）：
  checks 根目錄、設定所在目錄與設定檔都不是 symlink、owner 都是本人 uid、都不是 group／world 可寫。
  設定檔以 os.open(O_RDONLY|O_NOFOLLOW|O_NONBLOCK) 開啟（FIFO 不會卡住）後 fstat 檢查再從同一個 fd 讀，檢查與讀取是同一個檔。
  可選欄位 "repo_path"（主 checkout 絕對路徑）存在時，realpath 後必須等於求得的主 checkout realpath，
  否則略過並以 systemMessage 說明（防同 basename 的別的目錄套用這份設定）。

設定變更可見：每次讀到受信任的設定，把設定檔 sha256 記到
  ${WRITE_CHECKS_STATE_DIR:-~/.claude/state/write-checks}/seen.json（{"<key>": "<sha256>"}）；
  與上次不同（含首次）→ 照常執行，另輸出 systemMessage「write_checks：<key> 設定已變更，將執行：<各 check 的 cmd>」。

設定格式：
  {"repo_path": "/abs/main/checkout",
   "checks": [{"name": "...", "include": ["services/*.go"], "exclude": ["*_test.go"],
               "cmd": ["python3", "~/.claude/bin/checks/go_call_allowlist.py", "--file", "{file}", "--repo", "{repo}", ...],
               "message": "給 agent 的根因說明（指向正確寫法）"}]}
  repo 相對路徑＝`git rev-parse --show-prefix`＋檔名（git 給的是磁碟上的真實大小寫，payload 路徑的目錄段
  大小寫與磁碟不同也求得對；仍求不出則 systemMessage 說明、不靜默略過）。include／exclude 以它做 fnmatchcase
  （darwin 的檔案系統不分大小寫，兩邊先 casefold；符合任一 include 且不符合任何 exclude 才跑）；
  cmd 以 argv 執行、不經 shell，cwd＝repo toplevel；token 內 {file}（toplevel＋相對路徑）、{repo}（toplevel）
  單次代換（代換進來的值不再被代換），`~` 開頭的 token 做 expanduser。

執行：符合的 check 依序各跑一次，單條 timeout 預設 5 秒、整體預算預設 6 秒，可由環境變數
  WRITE_CHECKS_TIMEOUT／WRITE_CHECKS_BUDGET（秒，正數）覆寫。逾時時對 check 的 process group 送 SIGKILL，
  再等至多 1 秒收尾；孫行程另開 session 握住 pipe 時直接關 pipe 不等。每條 check 啟動前從剩餘預算扣掉 1 秒收尾，
  所以收尾也落在預算內。時間上限：git 2 ＋ 預算 6（含收尾預留）＝ 8 ≤ settings 的 hook timeout 10；
  即使收尾 1 秒另計也是 2 ＋ 6 ＋ 1 ＝ 9 ≤ 10。hook 本身永遠 exit 0（PostToolUse 的 stdout JSON 只在 exit 0 時被處理）：
  - check exit 0：通過。
  - check exit 1 且 stdout 有 `VIOLATION ` 開頭的行：違規。所有違規合併為一個 reason，
    stdout 印 {"decision": "block", "reason": "<name>：<message>\\n<VIOLATION 行>"}；進 reason 的只有 VIOLATION 行，
    C0／C1 控制字元與 bidi 控制字元（U+202A–202E、U+2066–2069）跳脫成 `\\xNN`／`\\uNNNN`，每條 check 至多 20 行、2000 字。
  - 其他情況（exit 1 但沒有 VIOLATION 行、其他 exit、逾時、啟動失敗、預算用完）視為 check 本身失敗：不 block，
    stderr 一行說明，並在 stdout JSON 帶 {"systemMessage": "write_checks：<check> 檢查本身失敗：<一行原因>"}
    讓 Mike 看得到規則失效（同樣跳脫）。設定檔壞、不受信任與 hook 內部錯誤同樣走 systemMessage。
payload 缺 file_path、不是一般檔案、不在 git repo：exit 0、stdout 空。
這是寫入當下的輔助檢查，不得因自身錯誤干擾編輯。

已知限制：本 hook 與 format_on_save 同為 PostToolUse 並行執行，極小機率讀到 gofmt 寫到一半的檔而誤報；可接受。
"""
import errno
import fnmatch
import hashlib
import json
import os
import re
import signal
import stat
import subprocess
import sys
import time

DEFAULT_CHECK_TIMEOUT = 5.0
DEFAULT_TOTAL_BUDGET = 6.0
GIT_TIMEOUT = 2.0
DRAIN_TIMEOUT = 1.0
MAX_REASON_LINES = 20
MAX_REASON_CHARS = 2000
GIT_HARDENING = ("-c", "core.fsmonitor=false", "-c", "protocol.allow=never")
PREFIX = "write_checks："
VIOLATION_PREFIX = "VIOLATION "
CONTROL_CHARS = re.compile("[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")
PLACEHOLDER = re.compile(r"\{(file|repo)\}")
CASE_INSENSITIVE_FS = sys.platform == "darwin"


def escape_char(match):
    code = ord(match.group(0))
    return f"\\x{code:02x}" if code <= 0xFF else f"\\u{code:04x}"


def visible(text):
    return CONTROL_CHARS.sub(escape_char, text)


def one_line(text):
    return visible(re.sub(r"[ \t\r\n]+", " ", str(text)).strip())


def warn(message):
    print(PREFIX + one_line(message), file=sys.stderr)


def violation_lines(out):
    return [line.rstrip("\r") for line in out.split("\n") if line.startswith(VIOLATION_PREFIX)]


def capped_violations(out):
    lines = [visible(line) for line in violation_lines(out)]
    text = "\n".join(lines[:MAX_REASON_LINES])
    notes = []
    if len(lines) > MAX_REASON_LINES:
        notes.append(f"另有 {len(lines) - MAX_REASON_LINES} 行未列")
    if len(text) > MAX_REASON_CHARS:
        text = text[:MAX_REASON_CHARS]
        notes.append("輸出過長已截斷")
    if notes:
        text += "\n…（" + "，".join(notes) + "）"
    return text


class Report:
    def __init__(self):
        self.blocks = []
        self.messages = []

    def violation(self, name, message, output):
        self.blocks.append(f"{name}：{message}\n{capped_violations(output)}")

    def check_failed(self, name, reason):
        self.failure(f"{name} 檢查本身失敗：{reason}")

    def failure(self, text):
        warn(text)
        self.notice(text)

    def notice(self, text):
        self.messages.append(PREFIX + one_line(text))

    def emit(self):
        out = {}
        if self.blocks:
            out["decision"] = "block"
            out["reason"] = "\n\n".join(self.blocks)
        if self.messages:
            out["systemMessage"] = "\n".join(self.messages)
        if out:
            print(json.dumps(out, ensure_ascii=False))


def seconds_from_env(name, default, report):
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        value = 0.0
    if value <= 0:
        report.failure(f"{name}={raw!r} 不是正數秒數，改用預設 {default:g}")
        return default
    return value


def target_file(raw):
    try:
        payload = json.loads(raw)
    except ValueError:
        warn("stdin 不是 JSON，略過")
        return None
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(path, str) or not os.path.isfile(path):
        return None
    return os.path.realpath(path)


def repo_of(path):
    proc = subprocess.run(
        ["git", "-C", os.path.dirname(path), *GIT_HARDENING,
         "rev-parse", "--show-toplevel", "--show-prefix", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, timeout=GIT_TIMEOUT, env=dict(os.environ, GIT_NO_LAZY_FETCH="1"))
    lines = proc.stdout.rstrip("\n").split("\n")
    if proc.returncode != 0 or len(lines) != 3:
        return None
    toplevel, prefix, common_dir = lines
    common_dir = os.path.realpath(common_dir)
    main_checkout = os.path.dirname(common_dir) if os.path.basename(common_dir) == ".git" else common_dir
    return os.path.realpath(toplevel), prefix, main_checkout, os.path.basename(main_checkout).lstrip(".")


def relative_in_repo(prefix, path):
    rel = os.path.normpath(prefix + os.path.basename(path))
    if os.path.isabs(rel) or rel == os.pardir or rel.startswith(os.pardir + os.sep):
        return None
    return rel


def stat_problem(info, kind, path, uid, is_kind):
    if not is_kind(info.st_mode):
        return f"{kind} {path} 不是一般{'檔案' if is_kind is stat.S_ISREG else '目錄'}（可能是 symlink）"
    if info.st_uid != uid:
        return f"{kind} {path} 的 owner uid {info.st_uid} 不是本人 {uid}"
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return f"{kind} {path} 是 group／world 可寫（{oct(info.st_mode & 0o777)}）"
    return None


def read_trusted_config(config_path, checks_root, uid):
    for path, kind in ((checks_root, "checks 根目錄"), (os.path.dirname(config_path), "設定目錄")):
        problem = stat_problem(os.lstat(path), kind, path, uid, stat.S_ISDIR)
        if problem:
            return None, problem
    try:
        fd = os.open(config_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return None, f"設定檔 {config_path} 是 symlink"
        raise
    with os.fdopen(fd, "rb") as f:
        problem = stat_problem(os.fstat(f.fileno()), "設定檔", config_path, uid, stat.S_ISREG)
        if problem:
            return None, problem
        return f.read(), None


def state_path():
    state_dir = os.environ.get("WRITE_CHECKS_STATE_DIR") or os.path.expanduser("~/.claude/state/write-checks")
    return os.path.join(state_dir, "seen.json")


def load_seen(path):
    try:
        with open(path, encoding="utf-8") as f:
            seen = json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        warn(f"{path} 讀取失敗，視為首次：{exc}")
        return {}
    return seen if isinstance(seen, dict) else {}


def save_seen(path, seen):
    try:
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(seen, f, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)
    except OSError as exc:
        warn(f"{path} 寫入失敗：{exc}")


def note_config_change(key, data, checks, report):
    digest = hashlib.sha256(data).hexdigest()
    path = state_path()
    seen = load_seen(path)
    if seen.get(key) == digest:
        return
    commands = "；".join(" ".join(entry["cmd"]) for entry in checks)
    report.notice(f"{key} 設定已變更，將執行：{commands or '（無有效 check）'}")
    seen[key] = digest
    save_seen(path, seen)


def load_checks(key, main_checkout, report):
    checks_root = os.path.abspath(os.environ.get("WRITE_CHECKS_DIR") or os.path.expanduser("~/.claude/checks"))
    config_path = os.path.join(checks_root, key, "write-checks.json")
    if not os.path.lexists(config_path):
        return []
    try:
        data, problem = read_trusted_config(config_path, checks_root, os.getuid())
        if problem:
            report.failure(f"{key} 設定檔權限不安全，已略過（{problem}）")
            return []
        config = json.loads(data.decode("utf-8"))
    except (OSError, ValueError) as exc:
        report.failure(f"設定檔 {config_path} 讀取失敗，規則全數未執行：{exc}")
        return []
    if not isinstance(config, dict) or not isinstance(config.get("checks"), list):
        report.failure(f"設定檔 {config_path} 缺 checks 陣列，規則全數未執行")
        return []
    if "repo_path" in config:
        declared = config["repo_path"]
        if not isinstance(declared, str) or os.path.realpath(declared) != main_checkout:
            report.failure(f"{key} 設定檔 repo_path {declared!r} 與實際主 checkout {main_checkout} 不符，已略過")
            return []
    valid = []
    for entry in config["checks"]:
        if valid_entry(entry):
            valid.append(entry)
        else:
            report.failure(f"設定檔 {config_path} 有格式不符的 check，略過：{json.dumps(entry, ensure_ascii=False)[:200]}")
    note_config_change(key, data, valid, report)
    return valid


def valid_entry(entry):
    return (isinstance(entry, dict)
            and isinstance(entry.get("name"), str)
            and isinstance(entry.get("message"), str)
            and is_str_list(entry.get("include"))
            and is_str_list(entry.get("exclude", []))
            and is_str_list(entry.get("cmd")) and len(entry["cmd"]) > 0)


def is_str_list(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def path_matches(rel, pattern):
    if CASE_INSENSITIVE_FS:
        return fnmatch.fnmatchcase(rel.casefold(), pattern.casefold())
    return fnmatch.fnmatchcase(rel, pattern)


def applies(entry, rel):
    included = any(path_matches(rel, pattern) for pattern in entry["include"])
    excluded = any(path_matches(rel, pattern) for pattern in entry.get("exclude", []))
    return included and not excluded


def build_argv(cmd, path, repo):
    values = {"file": path, "repo": repo}
    argv = []
    for token in cmd:
        token = PLACEHOLDER.sub(lambda m: values[m.group(1)], token)
        argv.append(os.path.expanduser(token) if token.startswith("~") else token)
    return argv


def stop_after_timeout(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()
    try:
        proc.communicate(timeout=DRAIN_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.stdout.close()
        proc.stderr.close()


def run_check(argv, repo, timeout):
    proc = subprocess.Popen(argv, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, errors="replace", start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stop_after_timeout(proc)
        raise
    return proc.returncode, out, err


def last_line(text):
    lines = [line for line in text.split("\n") if line.strip()]
    return lines[-1].strip()[:300] if lines else "（無 stderr）"


def run_checks(checks, path, repo, report):
    check_timeout = seconds_from_env("WRITE_CHECKS_TIMEOUT", DEFAULT_CHECK_TIMEOUT, report)
    budget = seconds_from_env("WRITE_CHECKS_BUDGET", DEFAULT_TOTAL_BUDGET, report)
    deadline = time.monotonic() + budget
    for entry in checks:
        name = entry["name"]
        remaining = deadline - time.monotonic() - DRAIN_TIMEOUT
        if remaining <= 0:
            report.check_failed(name, f"整體預算 {budget:g} 秒已用完（每條預留 {DRAIN_TIMEOUT:g} 秒收尾），未執行")
            continue
        timeout = min(check_timeout, remaining)
        try:
            code, out, err = run_check(build_argv(entry["cmd"], path, repo), repo, timeout)
        except subprocess.TimeoutExpired:
            report.check_failed(name, f"逾時（{timeout:.1f} 秒），未判定")
            continue
        except OSError as exc:
            report.check_failed(name, f"無法執行：{exc}")
            continue
        if code == 1 and violation_lines(out):
            report.violation(name, entry["message"], out)
        elif code == 1:
            report.check_failed(name, f"exit 1 但沒有 VIOLATION 行：{last_line(err)}")
        elif code != 0:
            report.check_failed(name, f"exit {code}：{last_line(err)}")


def main(report):
    path = target_file(sys.stdin.read())
    if path is None:
        return
    found = repo_of(path)
    if found is None:
        return
    repo, prefix, main_checkout, key = found
    if not key:
        return
    checks = load_checks(key, main_checkout, report)
    if not checks:
        return
    rel = relative_in_repo(prefix, path)
    if rel is None:
        report.failure(f"{path} 求不出 repo 相對路徑（git prefix {prefix!r}），規則未執行")
        return
    matched = [entry for entry in checks if applies(entry, rel)]
    run_checks(matched, os.path.join(repo, rel), repo, report)


if __name__ == "__main__":
    REPORT = Report()
    try:
        main(REPORT)
    except Exception as exc:
        REPORT.failure(f"內部錯誤 {type(exc).__name__}：{exc}")
    REPORT.emit()
    sys.exit(0)
