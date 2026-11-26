#!/usr/bin/env python3
"""PreToolUse hook（Bash）：硬擋危險命令、git push 強制詢問＋證據閘門、合併閘門、nginx/migration 強制詢問。
這裡沒有命令解析器：判定只靠 regex 與 shlex 切 token，看不懂的形狀一律 ask，例外不得放行。

時間預算：一次 hook 呼叫的所有子行程共用一條 deadline（模組載入時起算 GATE_BUDGET 秒），每個子行程
timeout＝min(3, 剩餘)，剩餘不足 MIN_SLICE 秒就 ask。進 reason 的子行程輸出一律跳脫控制字元，例外訊息截到
ERROR_LIMIT 字（逾時只寫秒數）。

repo 路徑：開頭 `cd <path> &&` 與 `-C <path>` 相對 payload cwd 解析；`cd -`、以 `~` 開頭（shlex 剝掉引號後分不出
shell 會不會展開）、沒有 cwd 而得不到絕對路徑 → 無法判定。

合併閘門（排在 push 閘門與唯讀免問之前）：只認 `[cd <path> &&] git [-C <path>] merge
[--ff-only|--no-ff|--no-edit|-m <msg>]... <branch>`。形狀對但 repo 無法判定或不是目錄、operand 不是恰好一個
（octopus）或是 `-` → ask。<branch> 的 refs/heads/、heads/ 前綴去掉後須是本地 refs/heads 分支，否則放行。
`verify-run --check-record --repo <repo> --ref refs/heads/<branch>`（同名 tag 不會蓋過分支）：exit 3（無設定）放行；目前分支不在它印的
PROTECTED 清單（verify.json 的 protected_branches，預設 main,master,dev）放行；1 deny；0 以外的其他 exit
→ ask（verify.json 壞掉時連合併到 feature 分支也會 ask）；0 但原 operand 解析到的 commit 不是
refs/heads/<branch>（refname 歧義，如同名 tag）→ ask；0 且帶 --no-ff → ask；0、沒帶 --ff-only 且
HEAD 不是 <branch> 的祖先（會產生未驗證的 merge commit）→ ask；其餘放行。
已知漏抓（一律照舊放行、不檢查）：非單純形式的 merge（管線、多指令、glob、其他旗標）、--squash、
`git -c ...`、remote-tracking ref 或 hash 當 <branch>、含 `$(...)` 的 -m、超過 MAX_CMD（8192）字元的指令、
git pull、rebase、reset、branch -f、checkout -B、cherry-pick、update-ref、`git fetch . x:dev`。

push 閘門判定順序：gate-evidence 先、push-plan 後，任一階段 deny 就 deny。
1. gate-evidence check（每個 src ref）：exit 1 且有輸出 → deny；例外記為無法判定，仍跑 push-plan。
2. push-plan（每個 refspec；沒指定 remote → ask）：目的端 HEAD 解析成目前分支、去掉 refs/heads/；
   其他 refs/ 或 tag → ask；沒有 refs/remotes/<remote>/<分支>（新分支、首推）→ ask；
   本次 src 的 commit 等於 refs/remotes/<remote>/<分支>（沒有要推的）→ 跳過；repo 為 stage: mvp
   （子行程載入 bin/gate-evidence 呼叫其 is_mvp）→ 跳過；目的端沒有本地分支、或 src 不是本地目的分支
   （改名推送）→ 該分支沒有快照就 deny 要求先 snapshot，有快照則 ask 並列出本次會推的 commit；其餘跑 `push-plan check --no-fetch --remote --src`：0 → 不擋，待推清單併入 reason；
   1 → deny（先把差異回報 Mike）；2 且「找不到快照」→ deny 要求先 snapshot；其他 → ask。
3. 沒被 deny → ask，兩階段的說明（含 push-plan 的待推清單與 ask 理由）併入 reason。"""
import json
import os
import re
import shlex
import subprocess
import sys
import time
from typing import NamedTuple

SP = r"(?:\s|\\\n)+"
VAL = r"""(?:[^\s"']|"[^"\n]*"|'[^'\n]*')+"""
VAL_OPTS = r"(?:-C|-c|--git-dir|--work-tree|--namespace|--config-env|--attr-source)"
WORD_END = r"""(?=[\s;&|)<>'"\\`$]|$)"""
GIT_GLOBAL = rf"(?:{SP}{VAL_OPTS}{SP}{VAL}|{SP}(?!{VAL_OPTS}(?:\s|\\\n|$))--?[A-Za-z][\w-]*(?:={VAL})?){{0,8}}"
PUSH_RE = r"\bgit" + GIT_GLOBAL + SP + "push" + WORD_END
FORCE_RE = PUSH_RE + r"(?:[^;&|\n]|\\\n)*(?:\s--force(?:-with-lease)?\b|\s-[A-Za-z0-9]*f[A-Za-z0-9]*" + WORD_END + r"|\s\+\S)"
MAX_CMD = 8192  # 超過就不跑上面的 regex 與 shlex 判定，只走 ask
PUSH_ASK = "Push 閘門：git push 需要 Mike 明確確認才能執行。"
UNDECIDED = PUSH_ASK + "\npush 閘門無法判定，請人工確認證據"
BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin")
GATE = os.path.join(BIN, "gate-evidence")
PUSH_PLAN = os.path.join(BIN, "push-plan")
VERIFY_RUN = os.path.join(BIN, "verify-run")
GATE_BUDGET = 6  # 秒，一次 hook 呼叫的所有子行程共用；settings.json 的 hook timeout 是 10 秒
CLI_TIMEOUT = 3
MIN_SLICE = 0.5
MODULE_START = time.monotonic()
MERGE_FLAGS = {"--ff-only", "--no-ff", "--no-edit"}
MERGE_REF_RE = re.compile(r"[A-Za-z0-9._/+@-]+")
MERGE_UNDECIDED = "合併閘門無法判定，請人工確認"
ERROR_LIMIT = 200
LIST_LIMIT = 50

READONLY_CMDS = {"grep", "rg", "ls", "cat", "head", "tail", "wc", "pwd", "which", "stat"}
READONLY_GIT = {"status", "log", "diff", "show", "blame", "ls-files", "rev-parse", "add", "commit"}
READONLY_BAD_FLAGS = ("--pre", "--hostname-bin", "--output", "--ext-diff", "--exec", "--textconv",
                      "--edit", "--show-signature")
GATE_CLIS = {"gate-evidence", "~/.claude/bin/gate-evidence",
             os.path.join(os.path.expanduser("~"), ".claude/bin/gate-evidence")}


def respond(decision, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def is_punct(token):
    return bool(token) and set(token) <= set("();<>|&")


def plain_tokens(cmd):
    """回傳 (開頭 cd 的路徑或 None, 其餘 token)；含 $、反引號、換行或 shlex 切不開回 None。"""
    if re.search(r"[$`\n]", cmd):
        return None
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    if len(tokens) >= 3 and tokens[0] == "cd" and tokens[2] == "&&" and not is_punct(tokens[1]):
        return tokens[1], tokens[3:]
    return None, tokens


class BudgetExhausted(Exception):
    pass


class Undetermined(Exception):
    pass


class Budget:
    def __init__(self, seconds):
        self.deadline = MODULE_START + seconds

    def timeout(self):
        left = self.deadline - time.monotonic()
        if left < MIN_SLICE:
            raise BudgetExhausted(f"hook 時間預算剩 {max(left, 0):.2f} 秒")
        return min(CLI_TIMEOUT, left)


def run_cli(argv, budget):
    """以 bytes 讀再解碼：text=True 的 universal newlines 會把輸出裡的 \\r 變成換行，跳脫就來不及了。"""
    p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, timeout=budget.timeout())
    return subprocess.CompletedProcess(argv, p.returncode, p.stdout.decode("utf-8", "replace"),
                                       p.stderr.decode("utf-8", "replace"))


def printable(text):
    """控制字元一律跳脫（同 gate-evidence 的 clean）：commit 主旨、檔名不能在 reason 裡偽造一行。"""
    return "\n".join("".join(c if c.isprintable() else c.encode("unicode_escape").decode("ascii") for c in line)
                     for line in re.split(r"\r?\n", text))


def cli_output(p):
    return "\n".join(printable(s.strip()) for s in (p.stdout, p.stderr) if s.strip())


def error_summary(exc):
    if isinstance(exc, subprocess.TimeoutExpired):
        return f"子行程逾時（{exc.timeout:.1f} 秒）"
    return printable(f"{type(exc).__name__}: {exc}")[:ERROR_LIMIT]


def git_exit(repo, args, budget, meaning):
    """跑 git 並把 exit code 依 meaning（{code: 回傳值}）換成結果；其他 exit code 是 git 錯誤，raise。"""
    p = run_cli(["git", "-C", repo, *args], budget)
    if p.returncode not in meaning:
        raise RuntimeError(f"git {' '.join(args)} 失敗（exit {p.returncode}）：{p.stderr.strip()}")
    return meaning[p.returncode], p.stdout.strip()


def current_branch(repo, budget):
    return git_exit(repo, ["branch", "--show-current"], budget, {0: True})[1]


def ref_exists(repo, ref, budget):
    return git_exit(repo, ["show-ref", "--verify", "--quiet", ref], budget, {0: True, 1: False})[0]


def is_ancestor(repo, older, newer, budget):
    return git_exit(repo, ["merge-base", "--is-ancestor", older, newer], budget, {0: True, 1: False})[0]


def resolve_commit(repo, rev, budget):
    found, out = git_exit(repo, ["rev-parse", "--verify", "--quiet", "--end-of-options", f"{rev}^{{commit}}"],
                          budget, {0: True, 1: False})
    return out if found else None


def resolve_repo(cwd, cd, git_c):
    """shlex 已剝掉引號，`~` 分不出 shell 會不會展開，一律當無法判定（None）；`cd -` 同。"""
    if cd == "-" or any(p and p.startswith("~") for p in (cd, git_c)):
        return None
    repo = os.path.join(cwd if isinstance(cwd, str) else "", cd or "", git_c or "").rstrip("/")
    return repo if os.path.isabs(repo) else None


def git_invocation(cmd, cwd, subcommand):
    """`[cd <path> &&] git [-C <path>] <subcommand> ...` 才回傳 (repo 絕對路徑或 None, 其餘 token)，否則 None。"""
    plain = plain_tokens(cmd)
    if plain is None or plain[1][:1] != ["git"] or any(is_punct(t) for t in plain[1]):
        return None
    cd, tokens = plain[0], plain[1][1:]
    git_c = None
    if tokens[:1] == ["-C"] and len(tokens) >= 2:
        git_c, tokens = tokens[1], tokens[2:]
    if tokens[:1] != [subcommand]:
        return None
    return resolve_repo(cwd, cd, git_c), tokens[1:]


class MergeRequest(NamedTuple):
    repo: str
    operand: str
    branch: str
    ff_only: bool
    no_ff: bool


def merge_operands(tokens):
    """回傳 (旗標集合, operands)；有清單外的旗標回 None。"""
    flags, operands, rest = set(), [], list(tokens)
    while rest:
        token = rest.pop(0)
        if token == "-m" and rest:
            rest.pop(0)
        elif token == "-":
            operands.append(token)
        elif token.startswith("-"):
            if token not in MERGE_FLAGS:
                return None
            flags.add(token)
        else:
            operands.append(token)
    return flags, operands


def local_branch_name(ref):
    for prefix in ("refs/heads/", "heads/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def simple_merge(cmd, cwd):
    """`[cd <path> &&] git [-C <path>] merge [--ff-only|--no-ff|--no-edit|-m <msg>]... <branch>` 回傳 MergeRequest；
    不是這個形狀回 None；形狀對但目標無法判定（octopus、`-`、repo 路徑）raise Undetermined。"""
    invocation = git_invocation(cmd, cwd, "merge")
    parsed = merge_operands(invocation[1]) if invocation else None
    if parsed is None:
        return None
    flags, operands = parsed
    if not all(op == "-" or MERGE_REF_RE.fullmatch(op) for op in operands):
        return None
    if len(operands) != 1 or operands[0] == "-":
        raise Undetermined(f"merge 的 operand 須恰好一個分支，實際：{operands}")
    repo = invocation[0]
    if repo is None or not os.path.isdir(repo):
        raise Undetermined(f"repo 路徑無法判定：{repo}")
    return MergeRequest(repo, operands[0], local_branch_name(operands[0]), "--ff-only" in flags, "--no-ff" in flags)


def protected_branches(check_output):
    for line in check_output.splitlines():
        if line.startswith("PROTECTED "):
            return set(line[len("PROTECTED "):].split(","))
    return None


def merge_undecided(detail):
    return "ask", f"{MERGE_UNDECIDED}\n{detail}".rstrip()


def merge_verdict(request, budget):
    repo, branch = request.repo, request.branch
    if not ref_exists(repo, f"refs/heads/{branch}", budget):
        return None
    p = run_cli([sys.executable, VERIFY_RUN, "--check-record", "--repo", repo, "--ref", f"refs/heads/{branch}"],
                budget)
    if p.returncode == 3:
        return None
    protected = protected_branches(p.stdout)
    if protected is None:
        return merge_undecided(cli_output(p))
    if current_branch(repo, budget) not in protected:
        return None
    if p.returncode == 1:
        return "deny", (f"合併閘門：{branch} 沒有 verify-run 通過紀錄（tree 須與 {branch} 相符）。"
                        f"合併前先在 {branch} 的 worktree 跑 `verify-run --repo <wt> --record`")
    if p.returncode != 0:
        return merge_undecided(cli_output(p))
    if resolve_commit(repo, request.operand, budget) != resolve_commit(repo, f"refs/heads/{branch}", budget):
        return merge_undecided(f"refname 有歧義：{request.operand} 解析到的 commit 不是 refs/heads/{branch}（同名 tag 等）")
    if request.no_ff:
        return merge_undecided("--no-ff 會產生 merge commit，合併結果沒有經過 verify-run 驗證")
    if not request.ff_only and not is_ancestor(repo, "HEAD", f"refs/heads/{branch}", budget):
        return merge_undecided(f"{branch} 不能 fast-forward，合併會產生 merge commit，合併結果沒有經過 verify-run 驗證")
    return None


def merge_gate(cmd, cwd, budget):
    """回傳 None（不擋）或 (decision, reason)。任何例外都落到 ask。"""
    try:
        request = simple_merge(cmd, cwd)
        return merge_verdict(request, budget) if request else None
    except Exception as exc:
        return merge_undecided(error_summary(exc))


def push_target(cmd, cwd):
    """單純 push 才回傳 (repo, remote, [(src, dst)...])，否則 None。"""
    invocation = git_invocation(cmd, cwd, "push")
    if invocation is None or invocation[0] is None:
        return None
    repo, tokens = invocation
    args = [t for t in tokens if t not in ("-u", "--set-upstream")]
    if any(not t or t.startswith(("-", ":", "^")) for t in args):
        return None
    pairs = [(t.split(":", 1)[0], t.split(":", 1)[-1]) for t in args[1:]]
    return repo, (args[0] if args else None), pairs


MVP_PROBE = """
import contextlib, importlib.machinery, importlib.util, io, sys
sys.dont_write_bytecode = True
loader = importlib.machinery.SourceFileLoader("gate_evidence", sys.argv[1])
module = importlib.util.module_from_spec(importlib.util.spec_from_loader("gate_evidence", loader))
with contextlib.redirect_stdout(io.StringIO()):
    loader.exec_module(module)
    mvp = module.is_mvp(module.open_repo(sys.argv[2]), sys.argv[3])
print("mvp" if mvp else "not-mvp")
"""


def is_mvp(repo, commit, budget):
    p = run_cli([sys.executable, "-I", "-c", MVP_PROBE, GATE, repo, commit], budget)
    verdict = p.stdout.strip()
    if p.returncode != 0 or verdict not in ("mvp", "not-mvp"):
        raise RuntimeError(f"stage: mvp 判定失敗（exit {p.returncode}）：{cli_output(p)}")
    return verdict == "mvp"


def push_plan_check(repo, remote, branch, src, budget):
    """回傳 (ok|changed|no-snapshot|error, 輸出)。"""
    p = run_cli([sys.executable, PUSH_PLAN, "check", "--repo", repo, "--branch", branch, "--no-fetch",
                 "--remote", remote, "--src", src], budget)
    out = cli_output(p)
    if p.returncode == 0:
        return "ok", out
    if p.returncode == 1:
        return "changed", out
    if p.returncode == 2 and "找不到快照" in out:
        return "no-snapshot", out
    return "error", out


def snapshot_command(repo, branch):
    return f"push-plan snapshot --repo {repo} --branch {branch}"


def no_snapshot_denial(repo, branch):
    return "deny", f"push 前先跑 `{snapshot_command(repo, branch)}`"


def push_plan_verdict(repo, remote, branch, src, budget):
    status, out = push_plan_check(repo, remote, branch, src, budget)
    if status == "ok":
        return "note", out
    if status == "changed":
        return "deny", (f"push-plan：{branch} 的待推內容與快照不一致：\n{out}\n"
                        f"先把上列差異回報 Mike，經同意後才重跑 `{snapshot_command(repo, branch)}`")
    if status == "no-snapshot":
        return no_snapshot_denial(repo, branch)
    return "ask", f"push-plan 無法判定：\n{out}".rstrip()


def outgoing_commits(repo, tracking, src_commit, budget):
    if tracking is None:
        argv, header = ["--max-count=20", src_commit], "本次 src 起最多 20 筆 commit（remote 沒有這個分支，無法算差集）："
    else:
        argv, header = [f"--max-count={LIST_LIMIT + 1}", f"{tracking}..{src_commit}"], "本次會推的 commit："
    p = run_cli(["git", "-C", repo, "log", "--format=%h %s", *argv], budget)
    if p.returncode != 0:
        raise RuntimeError(f"git log 失敗：{p.stderr.strip()}")
    lines = cli_output(p).splitlines()
    more = [f"…（只列前 {LIST_LIMIT} 筆）"] if tracking is not None and len(lines) > LIST_LIMIT else []
    return "\n".join([header] + lines[:LIST_LIMIT] + more)


def unverifiable_push(repo, remote, branch, src_commit, tracking, reason, budget):
    status, _ = push_plan_check(repo, remote, branch, src_commit, budget)
    if status == "no-snapshot":
        return no_snapshot_denial(repo, branch)
    return "ask", f"push-plan：{reason}，無法比對快照\n{outgoing_commits(repo, tracking, src_commit, budget)}"


def destination_branch(repo, dst, budget):
    branch = current_branch(repo, budget) if dst == "HEAD" else dst
    return branch[len("refs/heads/"):] if branch.startswith("refs/heads/") else branch


def refspec_verdict(repo, remote, src, dst, budget):
    """回傳 None（跳過）或 (deny|ask|note, 文字)。"""
    branch = destination_branch(repo, dst, budget)
    if not branch or branch.startswith("refs/") or ref_exists(repo, f"refs/tags/{branch}", budget):
        return "ask", f"push-plan：目的端 {dst} 不是可比對的分支"
    tracking = resolve_commit(repo, f"refs/remotes/{remote}/{branch}", budget)
    if tracking is None:
        return "ask", f"push-plan：沒有 refs/remotes/{remote}/{branch}（新分支或首推），無法比對快照"
    src_commit = resolve_commit(repo, src, budget)
    if src_commit == tracking:
        return None
    if src_commit is None:
        return push_plan_verdict(repo, remote, branch, src, budget)
    if is_mvp(repo, src_commit, budget):
        return None
    local = resolve_commit(repo, f"refs/heads/{branch}", budget)
    if local is None:
        return unverifiable_push(repo, remote, branch, src_commit, tracking, f"目的端沒有本地分支 {branch}", budget)
    if src_commit != local:
        return unverifiable_push(repo, remote, branch, src_commit, tracking,
                                 f"改名推送（src {src} 不是本地 {branch}）", budget)
    return push_plan_verdict(repo, remote, branch, src_commit, budget)


def push_plan_phase(repo, remote, pairs, budget):
    """回傳 (deny reason 或 None, notes, unknown)；任何例外都落到 unknown。"""
    try:
        if remote is None:
            return None, ["push-plan：沒指定 remote，無法比對快照"], True
        notes, unknown = [], False
        for src, dst in pairs or [("HEAD", "HEAD")]:
            verdict = refspec_verdict(repo, remote, src, dst, budget)
            if verdict and verdict[0] == "deny":
                return verdict[1], notes, unknown
            notes += [verdict[1]] if verdict else []
            unknown = unknown or bool(verdict and verdict[0] == "ask")
        return None, notes, unknown
    except Exception as exc:
        return None, [f"push-plan 無法判定（{error_summary(exc)}）"], True


def gate_evidence_phase(repo, remote, refs, budget):
    """回傳 (deny reason 或 None, notes, unknown)；任何例外都落到 unknown。"""
    notes, unknown = [], False
    try:
        for ref in refs or [None]:
            argv = [sys.executable, GATE, "check", "--repo", repo] + (["--ref", ref] if ref else []) + \
                   (["--remote", remote] if remote else [])
            p = run_cli(argv, budget)
            out = p.stdout.strip()
            if p.returncode == 1 and out:
                return out, notes, unknown
            unknown = unknown or p.returncode != 0
            notes += [out] if out else []
    except Exception:
        return None, notes, True
    return None, notes, unknown


def push_gate(cmd, cwd, budget=None):
    """回傳 (decision, reason)。gate-evidence 先、push-plan 後，任一 deny 就 deny；解析失敗落到無法判定的 ask。"""
    budget = budget or Budget(GATE_BUDGET)
    try:
        target = push_target(cmd, cwd)
    except Exception:
        return "ask", UNDECIDED
    if target is None:
        return "ask", UNDECIDED
    repo, remote, pairs = target
    notes, unknown = [], False
    for phase in (lambda: gate_evidence_phase(repo, remote, [src for src, _ in pairs], budget),
                  lambda: push_plan_phase(repo, remote, pairs, budget)):
        denied, phase_notes, phase_unknown = phase()
        if denied:
            return "deny", denied
        notes, unknown = notes + phase_notes, unknown or phase_unknown
    return "ask", "\n".join([UNDECIDED if unknown else PUSH_ASK] + list(dict.fromkeys(notes)))


def has_flag(args, flags):
    """args 含 flags 之一（含 =值 與 git 接受的縮寫，`--pretty` 不算 `--pre`）。裸 `--` 不算。"""
    names = [a.split("=", 1)[0] for a in args if a.startswith("--") and a != "--"]
    return any(f.startswith(n) for n in names for f in flags)


def adds_everything(args):
    return has_flag(args, ("--all", "--update", "--no-ignore-removal")) or \
        any(set(os.path.normpath(a).split("/")) <= {".", ".."} or re.match(r":|-[A-Za-z0-9]*[Au][A-Za-z0-9]*$", a) for a in args)


def readonly_segment(tokens):
    head, args = (tokens[0], tokens[1:]) if tokens else ("", [])
    if head == "git":
        args = args[2:] if args[:1] == ["-C"] else args
        opens_editor = args[:1] in (["add"], ["commit"]) and \
            any(re.fullmatch(r"-[A-Za-z0-9]*e[A-Za-z0-9]*", a) for a in args[1:])
        no_message = args[:1] == ["commit"] and not any(  # 只看 `--` 前；-cmain、-tmpl 的 m 是值不是旗標
            re.match(r"-[aiopqsvnz]*[mF]|--message|--file", a) for a in args[1:(args + ["--"]).index("--", 1)])
        return bool(args) and args[0] in READONLY_GIT and not opens_editor and not no_message and \
            not (args[0] == "add" and adds_everything(args[1:]))
    if head == "nginx":
        return args == ["-t"]
    return head in READONLY_CMDS or (head in GATE_CLIS and args[:1] in (["record"], ["check"]))


def simple_readonly(cmd):
    """每一段都是唯讀指令才回 True；只用來免除 nginx／migration／supabase 的 ask。
    黑名單看全部 token：引號裡的 `|` 與真管線切出來一樣，分段判定會被 `'|'` 騙過。"""
    try:
        if len(cmd) > MAX_CMD or re.search(r"[{}*?\[\]\\\r]", cmd):  # shell 會展開、shlex 不會
            return False
        if re.search(r"""['"]\||\|['"]|['"]~|~['"]|\s#""", cmd):  # 引號裡的 | 和 ~ 與真的切出來一樣；# 後是註解
            return False
        plain = plain_tokens(cmd)
        if plain is None or any(is_punct(t) and t != "|" for t in plain[1]) or has_flag(plain[1], READONLY_BAD_FLAGS):
            return False
        segments = [[]]
        for token in plain[1]:
            segments.append([]) if token == "|" else segments[-1].append(token)
        return all(readonly_segment(s) for s in segments)
    except Exception:
        return False


def main():
    data = json.load(sys.stdin)  # 壞 payload 一路 raise，由 __main__ 轉 ask
    cmd = data["tool_input"]["command"]
    too_long = len(cmd) > MAX_CMD

    # 硬擋：rm 帶有 r+f 組合旗標（rm -rf / -fr / -r -f ...）
    if re.search(r"\brm\s+(-[^\Wr]*r\w*\s+)*-\w*f", cmd) and re.search(r"\brm\s+(-\w*\s+)*-\w*r", cmd):
        respond("deny", "硬擋：rm -rf 被全域規則禁止。請改用精確路徑逐一刪除，或請 Mike 手動執行。")
    if re.search(r"\brm\s+-\w*(rf|fr)\w*\b", cmd):
        respond("deny", "硬擋：rm -rf 被全域規則禁止。請改用精確路徑逐一刪除，或請 Mike 手動執行。")

    # 硬擋：force push
    if (re.search(r"\bgit\s+push\b", cmd) and re.search(r"(\s--force(-with-lease)?\b|\s-f\b)", cmd)) or \
            (not too_long and re.search(FORCE_RE, cmd)):
        respond("deny", "硬擋：force push 被全域規則禁止。")

    # 硬擋：git add . / -A / --all
    if re.search(r"\bgit\s+add\s+(\.(\s|$)|-A\b|--all\b)", cmd):
        respond("deny", "硬擋：git add . / -A 被禁止，請逐一指定要加入的檔案。")

    # 硬擋：強制刪分支 / 強制移除 worktree（/feature-flow：清理只用 -d / remove）
    if re.search(r"\bgit\s+branch\s+(-\w+\s+)*-D\b", cmd):
        respond("deny", "硬擋：git branch -D 被禁止——分支未完全合併就先查明差在哪些 commit，清理只用 -d（/feature-flow）。")
    if re.search(r"\bgit\s+worktree\s+remove\b", cmd) and re.search(r"(\s--force\b|\s-f\b)", cmd):
        respond("deny", "硬擋：git worktree remove --force 被禁止——先查明未 commit 改動是什麼再處置（/feature-flow）。")

    # 硬擋：git clean 帶清除旗標（會洗掉未 commit / untracked 改動，含工人未回報的修正）
    if re.search(r"\bgit\s+clean\b", cmd) and re.search(r"\s-\w*[fdxX]", cmd):
        respond("deny", "硬擋：git clean -f/-d/-x 會洗掉未 commit 與 untracked 改動。先 git status 查明，逐一處置。")

    # 硬擋：git stash 變更操作（stash 堆疊跨 worktree 共用；乾淨樹上 push 是 no-op、pop 會彈出別人的 stash——2026-08-12/08-19 三起）
    if re.search(r"\bgit\s+(-C\s+\S+\s+)?stash\b", cmd) and not re.search(r"\bstash\s+(list|show)\b", cmd):
        respond("deny", "硬擋：git stash 變更操作被禁止（堆疊跨 worktree 共用，pop 會彈出別人的 WIP）。暫存改動用 cp 備份；取舊版用 git show <ref>:<path>；baseline 比對用 git diff <ref>。")

    # 硬擋：裸 npx（無 node_modules 時靜默抓 registry 新版產出假結果——/vue-dev 禁令）
    if re.search(r"(^|[;&|]\s*)npx\s", cmd):
        respond("deny", "硬擋：裸 npx 被禁止——沒裝依賴時會靜默抓 registry 新版產出假結果。改用 pnpm exec <tool> 或 ./node_modules/.bin/<tool>（先確認依賴已依 lock 檔安裝）。")

    # 強制詢問：覆蓋工作區未 commit 改動（退件教訓：曾洗掉工人未 commit 的修正）
    if re.search(r"\bgit\s+checkout\s+--\s", cmd):
        respond("ask", "警示：git checkout -- 會覆蓋未 commit 改動（變異還原請改用 cp 備份）。確定要丟棄？")
    if re.search(r"\bgit\s+restore\b", cmd) and not re.search(r"--staged\b", cmd):
        respond("ask", "警示：git restore 會覆蓋未 commit 改動。確定要丟棄？")

    # 強制詢問：waive 是略過閘門，排在 push 判定之前，waive && git push 才會講明
    if re.search(r"gate-evidence\s+(--\s+)?waive", re.sub(r"[\"'\\]", "", cmd)):
        respond("ask", "警示：gate-evidence waive 是略過閘門，需 Mike 確認。")

    budget = Budget(GATE_BUDGET)
    merge_decision = None if too_long else merge_gate(cmd, data.get("cwd"), budget)
    if merge_decision:
        respond(*merge_decision)

    # 強制詢問：git push（Push 閘門），缺證據硬擋
    if too_long:
        if "git" in cmd and "push" in cmd:
            respond("ask", UNDECIDED)
    elif re.search(r"\bgit\s+push\b", cmd) or re.search(PUSH_RE, cmd):
        respond(*push_gate(cmd, data.get("cwd"), budget))

    # 強制詢問：git reset --hard（丟棄工作區與 index）
    if re.search(r"\bgit\s+reset\s+(-\w+\s+)*--hard\b", cmd):
        respond("ask", "警示：git reset --hard 會丟棄未 commit 改動。確定？")

    # 強制詢問：遞迴刪除（rm -r 不帶 -f 也要問）與 find -delete
    if re.search(r"\brm\s+(-\w*\s+)*-\w*r", cmd):
        respond("ask", "警示：遞迴刪除。目標路徑確認過了嗎？")
    if re.search(r"\bfind\b.*\s-delete\b", cmd):
        respond("ask", "警示：find -delete 批次刪除。先跑一次不帶 -delete 確認清單。")

    # 強制詢問：名稱疑似含 commit/push/部署的 script（hook 看不進 script 內容）
    if re.search(r"\b(npm|pnpm|yarn)\s+run\s+(commit|push|deploy|release|publish)\b", cmd) or \
       re.search(r"\bmake\s+(deploy|release|publish|push)\b", cmd):
        respond("ask", "警示：此 script 名稱疑似含 commit/push/部署動作，hook 看不進內容。先讀 script 確認實際做什麼。")

    # 強制詢問：nginx / 執行 migration（單純唯讀免問）
    if simple_readonly(cmd):
        sys.exit(0)
    if re.search(r"\bnginx\b", cmd, re.IGNORECASE):
        respond("ask", "全域規則：nginx 相關操作需 Mike 確認。")
    if re.search(r"\b(migrate|alembic|flyway|goose)\b", cmd, re.IGNORECASE) or \
       re.search(r"\bsupabase\b[^\n;&|]{0,200}\bdb\s+push\b", cmd):
        respond("ask", "全域規則：DB migration 相關操作需 Mike 確認。")

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # hook 崩潰等於放行，一律轉 ask
        respond("ask", f"bash_guard 無法判定（{type(e).__name__}），請人工確認。")
