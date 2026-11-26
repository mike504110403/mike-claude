#!/usr/bin/env python3
"""reviewer_gate 探針：以 subprocess 餵 PreToolUse payload，驗證放行／deny 與 stderr；
端到端案例在 mktemp git repo 真跑 bin/diff-surface --record，再把產出的 state 餵給閘門。"""
import datetime
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "reviewer_gate.py")
DIFF_SURFACE = os.path.join(os.path.dirname(HERE), "bin", "diff-surface")
REVIEWERS = ("code-reviewer", "security-reviewer", "db-reviewer")
NOW = datetime.datetime.now(datetime.timezone.utc)
FAILS = 0


def check(cond, label):
    global FAILS
    FAILS += not cond
    print(f"{'OK  ' if cond else 'FAIL'} {label}")


def iso(delta_seconds, tz=True):
    moment = NOW + datetime.timedelta(seconds=delta_seconds)
    if not tz:
        moment = moment.replace(tzinfo=None)
    return moment.isoformat(timespec="seconds")


def write_state(state_dir, name, repo, delta_seconds, raw=None, tz=True, checkout_head=None):
    os.makedirs(state_dir, exist_ok=True)
    with open(os.path.join(state_dir, name), "w", encoding="utf-8") as f:
        f.write(raw if raw is not None else json.dumps({
            "repo": repo, "base": "base", "head": "deadbeef", "checkout_head": checkout_head, "worktree": False, "reviewers": ["code-reviewer"],
            "lane_floor": "無", "categories": [], "time": iso(delta_seconds, tz)}))


def run_gate(payload, state_dir, raw_stdin=None, timeout=10):
    env = {**os.environ, "DIFF_SURFACE_STATE": state_dir}
    stdin = raw_stdin if raw_stdin is not None else json.dumps(payload)
    try:
        proc = subprocess.run([sys.executable, GATE], input=stdin, capture_output=True, text=True, env=env,
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "", "TIMEOUT"
    return proc.returncode, proc.stdout, proc.stderr


def agent(subagent_type, prompt, tool_name="Agent"):
    return {"tool_name": tool_name, "tool_input": {"subagent_type": subagent_type, "prompt": prompt}}


def is_deny(out):
    if not out:
        return False
    decision = json.loads(out)["hookSpecificOutput"]
    return decision["hookEventName"] == "PreToolUse" and decision["permissionDecision"] == "deny"


def deny_reason(out):
    return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]


def load_gate_module():
    spec = importlib.util.spec_from_file_location("reviewer_gate", GATE)
    module = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(module)
    return module


def git_repo(root, name):
    path = os.path.join(root, name)
    os.makedirs(path)
    subprocess.run("git init -q && git config user.email t@example.com && git config user.name t"
                   " && printf 'x\\n' > a.go && git add a.go && git commit -q -m init && git tag base"
                   " && printf 'y\\n' > b.go && git add b.go && git commit -q -m b",
                   shell=True, cwd=path, check=True, capture_output=True,
                   env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"})
    return os.path.realpath(path)


def record_with_diff_surface(repo, state_dir, *extra):
    env = {**os.environ, "DIFF_SURFACE_STATE": state_dir}
    proc = subprocess.run([DIFF_SURFACE, "--repo", repo, "--base", "base", "--record", *extra],
                          capture_output=True, text=True, env=env, timeout=60)
    return proc.returncode, proc.stdout


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = os.path.realpath(tmp)
        missing = os.path.join(tmp, "no-such-state")
        repo = "/work/proj"
        prompt = f"審 {repo} 的改動"

        for reviewer in REVIEWERS:
            rc, out, err = run_gate(agent(reviewer, prompt), missing)
            check(rc == 0 and is_deny(out), f"state 目錄不存在 → {reviewer} deny")
        rc, out, err = run_gate(agent("code-reviewer", prompt), missing)
        check("diff-surface" in deny_reason(out) and "--record" in deny_reason(out), "deny reason 含 diff-surface 與 --record")

        state = os.path.join(tmp, "s-fresh")
        write_state(state, "a.json", repo, -60)
        for tool_name in ("Agent", "Task"):
            rc, out, err = run_gate(agent("code-reviewer", prompt, tool_name), state)
            check(rc == 0 and out == "" and err == "", f"3 小時內紀錄＋prompt 含 repo → {tool_name} 放行")
        rc, out, err = run_gate(agent("code-reviewer", "審 /other/place"), state)
        check(is_deny(out), "紀錄的 repo 不在 prompt → deny")
        rc, out, err = run_gate(agent("code-reviewer", "審 /work/proj-2 的改動"), state)
        check(is_deny(out), "prompt 只含同前綴的另一路徑 → deny")
        rc, out, err = run_gate(agent("code-reviewer", "審 /x/work/proj 的改動"), state)
        check(is_deny(out), "prompt 路徑只是尾段相同 → deny")
        rc, out, err = run_gate({"tool_name": "Agent", "tool_input": {"subagent_type": "code-reviewer"}}, state)
        check(is_deny(out), "無 prompt → deny")

        state = os.path.join(tmp, "s-old")
        write_state(state, "a.json", repo, -3 * 3600 - 5)
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(rc == 0 and is_deny(out), "超過 3 小時 → deny")

        state = os.path.join(tmp, "s-old-and-fresh")
        write_state(state, "old.json", repo, -5 * 3600)
        write_state(state, "new.json", repo, -30)
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(rc == 0 and out == "", "舊紀錄與新鮮紀錄並存 → 依新鮮者放行")

        state = os.path.join(tmp, "s-bad-alone")
        write_state(state, "bad.json", None, 0, raw="{not json")
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(rc == 0 and is_deny(out) and err.strip() != "", "只有壞檔 → 視為無紀錄 deny，stderr 有訊息")

        state = os.path.join(tmp, "s-bad-and-fresh")
        write_state(state, "bad.json", None, 0, raw="{not json")
        write_state(state, "good.json", repo, -30)
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(rc == 0 and out == "" and "bad.json" in err, "壞檔與新鮮有效檔並存 → 放行，stderr 點名壞檔")

        state = os.path.join(tmp, "s-notz")
        write_state(state, "a.json", repo, -30, tz=False)
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(is_deny(out) and err.strip() != "", "time 無時區 → 該筆無效，deny＋stderr")

        state = os.path.join(tmp, "s-garbage-time")
        write_state(state, "a.json", repo, 0, raw=json.dumps({"repo": repo, "time": "昨天"}))
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(is_deny(out) and err.strip() != "", "time 解析失敗 → 該筆無效，deny＋stderr")

        state = os.path.join(tmp, "s-missing-repo")
        write_state(state, "a.json", repo, 0, raw=json.dumps({"time": iso(-30)}))
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(is_deny(out) and err.strip() != "", "紀錄缺 repo → 該筆無效，deny＋stderr")

        state = os.path.join(tmp, "s-future-far")
        write_state(state, "a.json", repo, 10 * 60)
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(is_deny(out), "time 在未來超過 5 分鐘 → 無效 deny")
        state = os.path.join(tmp, "s-future-near")
        write_state(state, "a.json", repo, 2 * 60)
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(rc == 0 and out == "", "time 在未來 2 分鐘（時鐘誤差內）→ 放行")

        gate = load_gate_module()
        edge = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        check(gate.is_fresh(edge - datetime.timedelta(hours=3), edge), "恰好 3 小時 → 有效（≤ 含）")
        check(not gate.is_fresh(edge - datetime.timedelta(hours=3, seconds=1), edge), "3 小時又 1 秒 → 無效")
        check(gate.is_fresh(edge + datetime.timedelta(minutes=5), edge), "恰好未來 5 分鐘 → 有效")
        check(not gate.is_fresh(edge + datetime.timedelta(minutes=5, seconds=1), edge), "未來 5 分鐘又 1 秒 → 無效")

        for other in ("implementer", "general-purpose", "Explore"):
            rc, out, err = run_gate(agent(other, prompt), missing)
            check(rc == 0 and out == "", f"subagent_type={other} → 放行")

        rc, out, err = run_gate({"tool_name": "Agent"}, missing)
        check(rc == 0 and out == "" and "subagent_type" in err, "payload 無 tool_input → 放行＋stderr")
        rc, out, err = run_gate({"tool_name": "Agent", "tool_input": {"prompt": "x"}}, missing)
        check(rc == 0 and out == "" and "subagent_type" in err, "tool_input 無 subagent_type → 放行＋stderr")
        rc, out, err = run_gate({"tool_name": "Agent", "tool_input": "oops"}, missing)
        check(rc == 0 and out == "" and "subagent_type" in err, "tool_input 不是 dict → 放行＋stderr")
        rc, out, err = run_gate({"tool_name": "Agent", "tool_input": {"subagent_type": ["code-reviewer"]}}, missing)
        check(rc == 0 and out == "" and "subagent_type" in err, "subagent_type 不是字串 → 放行＋stderr")
        rc, out, err = run_gate(None, missing, raw_stdin="not json at all")
        check(rc == 0 and out == "" and err.strip() != "", "stdin 不是 JSON → 放行＋stderr")
        rc, out, err = run_gate(None, missing, raw_stdin="[1, 2]")
        check(rc == 0 and out == "" and err.strip() != "", "payload 不是 dict → 放行＋stderr")

        state_file = os.path.join(tmp, "state-is-a-file")
        with open(state_file, "w") as f:
            f.write("x")
        rc, out, err = run_gate(agent("code-reviewer", prompt), state_file)
        check(rc == 0 and out == "" and err.strip() != "", "state 路徑是檔案 → 未預期例外 → exit 0、stdout 空、stderr 有訊息")

        rc, out, err = run_gate(agent("code-reviewer", f"{prompt}\ndiff-surface: N/A（非 git）"), missing)
        check(rc == 0 and out == "" and "N/A" in err, "prompt 含 diff-surface: N/A（非 git） → 放行＋stderr 記一行")
        rc, out, err = run_gate(agent("code-reviewer", "diff-surface: N/A"), missing)
        check(is_deny(out), "只寫 N/A 沒有（非 git）字樣 → 不放行")

        state = os.path.join(tmp, "s-cjk")
        write_state(state, "a.json", "/Users/x/wt", -30)
        rc, out, err = run_gate(agent("code-reviewer", "審查/Users/x/wt的改動"), state)
        check(rc == 0 and out == "", "中文字緊貼路徑前後 → 仍認得，放行")
        rc, out, err = run_gate(agent("code-reviewer", "審查 `/Users/x/wt`，（/Users/x/wt）。"), state)
        check(rc == 0 and out == "", "路徑前後是標點 → 放行")

        state = os.path.join(tmp, "s-parent")
        write_state(state, "a.json", "/Users/mike/.claude", -30)
        rc, out, err = run_gate(agent("code-reviewer", "規格 /Users/mike/.claude/ledgers/briefs/x.md ；審 /Users/mike/wt-other"), state)
        check(is_deny(out), "上層 repo 紀錄不放行其下的路徑（引用 repo 內檔案）→ deny")
        state = os.path.join(tmp, "s-nested-wt")
        write_state(state, "a.json", "/a/repo", -30)
        rc, out, err = run_gate(agent("code-reviewer", "審 /a/repo/.worktrees/wt"), state)
        check(is_deny(out), "主 checkout 紀錄不放行其下的 worktree → deny")
        rc, out, err = run_gate(agent("code-reviewer", "審 /a/repo/ 的改動"), state)
        check(rc == 0 and out == "", "路徑後接斜線再接空白 → 仍是該路徑，放行")

        state = os.path.join(tmp, "s-root-repo")
        write_state(state, "a.json", "/", -30)
        rc, out, err = run_gate(agent("code-reviewer", "審 / 的改動"), state)
        check(is_deny(out) and err.strip() != "", "紀錄 repo 為 / → 無效，deny＋stderr")
        state = os.path.join(tmp, "s-relative-repo")
        write_state(state, "a.json", "work/proj", -30)
        rc, out, err = run_gate(agent("code-reviewer", "審 work/proj 的改動"), state)
        check(is_deny(out) and err.strip() != "", "紀錄 repo 非絕對路徑 → 無效，deny＋stderr")

        state = os.path.join(tmp, "s-dir")
        write_state(state, "good.json", repo, -30)
        os.makedirs(os.path.join(state, "dir.json"))
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(rc == 0 and out == "" and "dir.json" in err, "目錄名為 x.json → 略過，其餘紀錄決定（放行）＋stderr")

        state = os.path.join(tmp, "s-unreadable")
        write_state(state, "good.json", repo, -30)
        write_state(state, "locked.json", repo, -30)
        os.chmod(os.path.join(state, "locked.json"), 0)
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(rc == 0 and out == "" and "locked.json" in err, "不可讀的紀錄 → 略過＋stderr，其餘決定")
        os.chmod(os.path.join(state, "locked.json"), 0o600)

        state = os.path.join(tmp, "s-deep")
        write_state(state, "good.json", repo, -30)
        write_state(state, "deep.json", None, 0, raw="[" * 30000 + "]" * 30000)
        rc, out, err = run_gate(agent("code-reviewer", prompt), state)
        check(rc == 0 and out == "" and "deep.json" in err, "深巢狀 JSON → 略過＋stderr，其餘決定，不崩潰")

        state = os.path.join(tmp, "s-big")
        write_state(state, "good.json", repo, -30)
        write_state(state, "big.json", None, 0, raw=json.dumps({"repo": repo, "time": iso(-30), "pad": "x" * 70000}))
        rc, out, err = run_gate(agent("code-reviewer", "審 /nowhere/else"), state)
        check(is_deny(out) and "big.json" in err, "超過 64KB 的紀錄 → 無效")

        state = os.path.join(tmp, "s-fifo")
        write_state(state, "good.json", repo, -30)
        os.mkfifo(os.path.join(state, "pipe.json"))
        rc, out, err = run_gate(agent("code-reviewer", prompt), state, timeout=5)
        check(rc == 0 and out == "" and "pipe.json" in err, "FIFO → 不 hang、略過＋stderr，其餘決定")

        state = os.path.join(tmp, "s-symlink-fifo")
        write_state(state, "good.json", repo, -30)
        os.symlink(os.path.join(state, "pipe-target"), os.path.join(state, "link.json"))
        os.mkfifo(os.path.join(state, "pipe-target"))
        rc, out, err = run_gate(agent("code-reviewer", prompt), state, timeout=5)
        check(rc == 0 and out == "" and "link.json" in err, "符號連結（指向 FIFO）→ 不 hang、略過＋stderr")

        state = os.path.join(tmp, "s-symlink-valid")
        write_state(os.path.join(tmp, "elsewhere"), "real.json", repo, -30)
        os.makedirs(state)
        os.symlink(os.path.join(tmp, "elsewhere", "real.json"), os.path.join(state, "link.json"))
        rc, out, err = run_gate(agent("code-reviewer", prompt), state, timeout=5)
        check(is_deny(out) and "link.json" in err, "符號連結（指向有效紀錄）→ 略過，不放行")

        for odd in ("Code-Reviewer", "plugin:code-reviewer", "SECURITY-REVIEWER"):
            rc, out, err = run_gate(agent(odd, prompt), missing)
            check(is_deny(out), f"subagent_type={odd} 正規化後視為 reviewer → deny")

        state = os.path.join(tmp, "s-head-gone")
        write_state(state, "a.json", os.path.join(tmp, "no-such-repo"), -30, checkout_head="abc123")
        rc, out, err = run_gate(agent("code-reviewer", f"審 {os.path.join(tmp, 'no-such-repo')}"), state)
        check(rc == 0 and out == "" and err.strip() != "", "git 失敗 → 該筆視為符合（fail-open）＋stderr")

        e2e_state = os.path.join(tmp, "e2e-state")
        main_repo = git_repo(tmp, "e2e-main")
        code, out = record_with_diff_surface(main_repo, e2e_state)
        check(code == 0 and "RECORDED" in out, "端到端：diff-surface --record 成功")
        rc, out, err = run_gate(agent("code-reviewer", f"審 {main_repo}"), e2e_state)
        check(rc == 0 and out == "" and err == "", "端到端：diff-surface 產出的 state ＋ prompt 含該 repo → 放行")
        rc, out, err = run_gate(agent("code-reviewer", "審 別的地方"), e2e_state)
        check(is_deny(out), "端到端：prompt 沒有該 repo 路徑 → deny")

        worktree = os.path.join(tmp, "e2e-wt")
        subprocess.run(["git", "-C", main_repo, "worktree", "add", "-q", "-b", "wt-x", worktree], check=True,
                       capture_output=True)
        worktree = os.path.realpath(worktree)
        check(record_with_diff_surface(worktree, e2e_state)[0] == 0, "端到端：worktree 也能 --record")
        check(len(os.listdir(e2e_state)) == 2, "同 repo 兩個 worktree 的紀錄並存")
        for path in (main_repo, worktree):
            rc, out, err = run_gate(agent("code-reviewer", f"審 {path}"), e2e_state)
            check(rc == 0 and out == "", f"端到端：{os.path.basename(path)} 各自放行")

        head_state = os.path.join(tmp, "head-state")
        head_repo = git_repo(tmp, "e2e-head")
        record_with_diff_surface(head_repo, head_state)
        rc, out, err = run_gate(agent("code-reviewer", f"審 {head_repo}"), head_state)
        check(rc == 0 and out == "" and err == "", "HEAD 綁定：紀錄後未動 → 放行")
        subprocess.run("printf 'z\\n' > c.go && git add c.go && git commit -q -m c", shell=True, cwd=head_repo,
                       check=True, capture_output=True,
                       env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"})
        rc, out, err = run_gate(agent("code-reviewer", f"審 {head_repo}"), head_state)
        check(is_deny(out) and "HEAD 已變" in deny_reason(out), "HEAD 綁定（checkout_head）：紀錄後再 commit → deny，reason 提示重跑")
        record_with_diff_surface(head_repo, head_state)
        rc, out, err = run_gate(agent("code-reviewer", f"審 {head_repo}"), head_state)
        check(rc == 0 and out == "", "HEAD 綁定：重跑 --record 後 → 放行")

        null_state = os.path.join(tmp, "null-head-state")
        write_state(null_state, "a.json", head_repo, -30, checkout_head=None)
        rc, out, err = run_gate(agent("code-reviewer", f"審 {head_repo}"), null_state)
        check(rc == 0 and out == "" and err == "", "checkout_head 為 null → 跳過 HEAD 檢查，放行")


        old_format_state = os.path.join(tmp, "old-format-state")
        write_state(old_format_state, "a.json", head_repo, 0,
                    raw=json.dumps({"repo": head_repo, "head": "x", "time": iso(-30)}))
        rc, out, err = run_gate(agent("code-reviewer", f"審 {head_repo}"), old_format_state)
        check(rc == 0 and out == "" and "checkout_head" in err, "缺 checkout_head 欄的舊格式紀錄 → 跳過 HEAD 檢查＋stderr 一行")

        review_repo = git_repo(tmp, "e2e-review-head")
        subprocess.run(["git", "-C", review_repo, "branch", "other", "HEAD~1"], check=True, capture_output=True)
        for label, extra_args in (("--head HEAD~1", ("--head", "HEAD~1")), ("--head <另一個分支>", ("--head", "other"))):
            review_state = os.path.join(tmp, "review-state-" + label.split()[-1].strip("<>~"))
            code, out = record_with_diff_surface(review_repo, review_state, *extra_args)
            check(code == 0, f"端到端：{label} --record 成功")
            rc, out, err = run_gate(agent("code-reviewer", f"審 {review_repo}"), review_state)
            check(rc == 0 and out == "" and err == "", f"審歷史 head（{label}）：checkout 沒動 → 放行")

        nul_state = os.path.join(tmp, "nul-state")
        write_state(nul_state, "good.json", repo, -30)
        write_state(nul_state, "nul.json", None, 0, raw=json.dumps({"repo": "/work/pr\u0000oj", "time": iso(-30)}))
        rc, out, err = run_gate(agent("code-reviewer", prompt), nul_state)
        check(rc == 0 and out == "" and "nul.json" in err, "repo 含 NUL → 該筆無效＋stderr，其餘紀錄決定")

        state = os.path.join(tmp, "s-strip")
        rc, out, err = run_gate(agent("code-reviewer ", prompt), state)
        check(is_deny(out), "subagent_type 帶尾端空白 → strip 後視為 reviewer → deny")
        rc, out, err = run_gate(agent(" Security-Reviewer\n", prompt), state)
        check(is_deny(out), "subagent_type 前後空白與換行 → strip 後視為 reviewer → deny")
        check("單獨寫出" in deny_reason(run_gate(agent("code-reviewer", prompt), state)[1]) and
              "realpath" in deny_reason(run_gate(agent("code-reviewer", prompt), state)[1]), "deny reason 要求單獨寫出 worktree 根路徑（realpath）")

        rc, out, err = run_gate(agent("code-reviewer", f"審 {main_repo}"), os.path.join(tmp, "e2e-empty"))
        check(is_deny(out), "端到端：沒跑 diff-surface 的 state → deny")

    print(f"\n{'ALL PASS' if FAILS == 0 else str(FAILS) + ' FAILURES'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
