#!/usr/bin/env python3
"""PreToolUse hook（Bash）：硬擋危險命令、git push 強制詢問＋證據閘門、nginx/migration 強制詢問。
這裡沒有命令解析器：判定只靠 regex 與 shlex 切 token，看不懂的形狀一律 ask，例外不得放行。"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

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
GATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "gate-evidence")
GATE_BUDGET = 6  # 秒，所有 ref 共用；settings.json 的 hook timeout 是 10 秒

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


def simple_push(cmd, cwd):
    """`[cd <path> &&] git [-C <path>] push [<remote>] [<ref>...]` 才回傳 (repo, remote, refs)，否則 None。"""
    plain = plain_tokens(cmd)
    if plain is None or plain[1][:1] != ["git"] or any(is_punct(t) for t in plain[1]):
        return None
    cd, tokens = plain[0], plain[1][1:]
    git_c = None
    if tokens[:1] == ["-C"] and len(tokens) >= 2:
        git_c, tokens = tokens[1], tokens[2:]
    if tokens[:1] != ["push"]:
        return None
    args = [t for t in tokens[1:] if t not in ("-u", "--set-upstream")]
    if any(not t or t.startswith(("-", ":", "^")) for t in args):
        return None
    repo = os.path.join(cwd if isinstance(cwd, str) else "", cd or "", git_c or "").rstrip("/")
    if not os.path.isabs(repo):
        return None
    return repo, (args[0] if args else None), [t.split(":", 1)[0] for t in args[1:]]


def push_gate(cmd, cwd):
    """回傳 (decision, reason)。任何例外都落到無法判定的 ask。"""
    try:
        target = simple_push(cmd, cwd)
        if target is None:
            return "ask", UNDECIDED
        repo, remote, refs = target
        deadline = time.monotonic() + GATE_BUDGET
        notes, unknown = [], False
        for ref in refs or [None]:
            argv = [sys.executable, GATE, "check", "--repo", repo] + (["--ref", ref] if ref else []) + \
                   (["--remote", remote] if remote else [])
            p = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=deadline - time.monotonic())
            out = p.stdout.strip()
            if p.returncode == 1 and out:
                return "deny", out
            unknown = unknown or p.returncode != 0
            notes += [out] if out else []
        return "ask", "\n".join([UNDECIDED if unknown else PUSH_ASK] + list(dict.fromkeys(notes)))
    except Exception:
        return "ask", UNDECIDED


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

    # 強制詢問：git push（Push 閘門），缺證據硬擋
    if too_long:
        if "git" in cmd and "push" in cmd:
            respond("ask", UNDECIDED)
    elif re.search(r"\bgit\s+push\b", cmd) or re.search(PUSH_RE, cmd):
        respond(*push_gate(cmd, data.get("cwd")))

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
