#!/usr/bin/env python3
"""bash_guard 合併閘門與 push 閘門的 push-plan 段：在 tempfile 建的真 git repo＋本機 bare remote 上，
透過 subprocess 餵 hook payload 驗判定。verify-run 紀錄一律由真 `verify-run --record` 產生；
VERIFY_RUN_EVIDENCE、VERIFY_RUN_CHECKS、PUSH_PLAN_STATE、GATE_EVIDENCE_DIR、HOME 都指向臨時目錄。"""
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "hooks", "bash_guard.py")
VERIFY_RUN = os.path.join(ROOT, "bin", "verify-run")
PUSH_PLAN = os.path.join(ROOT, "bin", "push-plan")
PUSH = "git pu" + "sh"
REAL_GIT = shutil.which("git")
LINE_BREAKS = re.compile(r"\r\n|[\r\n\x0b\x0c\x1c-\x1e\x85\u2028\u2029]")


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        check=True, capture_output=True, text=True).stdout.strip()


class GateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.bare = os.path.join(self.tmp, "origin.git")
        self.repo = os.path.join(self.tmp, "app")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.bare], check=True)
        subprocess.run(["git", "init", "-q", "-b", "main", self.repo], check=True)
        git(self.repo, "remote", "add", "origin", self.bare)
        self.commit(self.repo, "README.md", "base")
        git(self.repo, "push", "-q", "origin", "main")
        self.extra_env = {}

    def env(self):
        return dict(os.environ, HOME=self.tmp, GATE_EVIDENCE_DIR=os.path.join(self.tmp, "gate"),
                    VERIFY_RUN_EVIDENCE=os.path.join(self.tmp, "evidence"),
                    VERIFY_RUN_CHECKS=os.path.join(self.tmp, "checks"),
                    PUSH_PLAN_STATE=os.path.join(self.tmp, "push-plan"),
                    GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
                    **self.extra_env)

    def commit(self, repo, path, body):
        with open(os.path.join(repo, path), "a", encoding="utf-8") as f:
            f.write(body + "\n")
        git(repo, "add", path)
        git(repo, "commit", "-qm", body)
        return git(repo, "rev-parse", "HEAD")

    def write_config(self, body, key="app"):
        os.makedirs(os.path.join(self.tmp, "checks", key), exist_ok=True)
        with open(os.path.join(self.tmp, "checks", key, "verify.json"), "w", encoding="utf-8") as f:
            f.write(body)

    def cli(self, *argv):
        return subprocess.run([sys.executable, *argv], capture_output=True, text=True, env=self.env())

    def hook(self, cmd, cwd=None, with_cwd=True):
        payload = {"tool_input": {"command": cmd}}
        if with_cwd:
            payload["cwd"] = cwd or self.repo
        started = time.monotonic()
        p = subprocess.run([sys.executable, GUARD], input=json.dumps(payload), capture_output=True, text=True,
                           env=self.env())
        self.elapsed = time.monotonic() - started
        self.assertEqual(p.returncode, 0, p.stderr)
        if not p.stdout.strip():
            return "allow", ""
        spec = json.loads(p.stdout)["hookSpecificOutput"]
        return spec["permissionDecision"], spec["permissionDecisionReason"]

    def slow_git(self, seconds):
        fake_bin = os.path.join(self.tmp, "fake-bin")
        os.makedirs(fake_bin, exist_ok=True)
        fake = os.path.join(fake_bin, "git")
        with open(fake, "w") as f:
            f.write(f"#!/bin/sh\nsleep {seconds}\nexec {REAL_GIT} \"$@\"\n")
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        self.extra_env = {"PATH": fake_bin + os.pathsep + os.environ["PATH"]}


class MergeGate(GateCase):
    def setUp(self):
        super().setUp()
        self.write_config('{"commands":[{"name":"ok","cmd":"true"}]}')
        self.wt = os.path.join(self.tmp, "app-feature")
        git(self.repo, "worktree", "add", "-q", "-b", "feature/x", self.wt)
        self.commit(self.wt, "a.txt", "feature work")

    def record(self, worktree):
        p = self.cli(VERIFY_RUN, "--repo", worktree, "--record")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("RECORDED ", p.stdout)

    def test_main_without_record_is_denied(self):
        decision, reason = self.hook("git merge feature/x")
        self.assertEqual(decision, "deny")
        self.assertIn("verify-run --repo <wt> --record", reason)
        self.assertIn("feature/x", reason)

    def test_main_with_matching_record_is_allowed(self):
        self.record(self.wt)
        self.assertEqual(self.hook("git merge -m 'merge x' feature/x"), ("allow", ""))
        self.assertEqual(self.hook(f"cd {self.repo} && git merge --ff-only feature/x", cwd=self.tmp),
                         ("allow", ""))
        self.assertEqual(self.hook(f"git -C {self.repo} merge --no-edit feature/x", cwd=self.tmp), ("allow", ""))

    def test_no_ff_asks(self):
        self.record(self.wt)
        self.assertMergeAsks("git merge --no-ff feature/x", "--no-ff")

    def test_non_fast_forward_asks_unless_ff_only(self):
        self.record(self.wt)
        self.commit(self.repo, "m.txt", "main moved")
        self.assertMergeAsks("git merge feature/x", "merge commit")
        self.assertEqual(self.hook("git merge --ff-only feature/x"), ("allow", ""))

    def test_tilde_and_unresolvable_paths_ask(self):
        self.record(self.wt)
        elsewhere = os.path.join(self.tmp, "plain")
        os.makedirs(elsewhere)
        for cmd in ("git -C ~/app merge feature/x", "cd ~/app && git merge feature/x",
                    f"cd {self.tmp}/no-such-dir && git merge feature/x", "cd - && git merge feature/x"):
            self.assertMergeAsks(cmd, "無法判定", cwd=elsewhere)

    def test_missing_payload_cwd_asks(self):
        decision, reason = self.hook("git merge feature/x", with_cwd=False)
        self.assertEqual(decision, "ask", reason)

    def test_branch_spelled_as_full_ref_is_checked(self):
        for spelled in ("refs/heads/feature/x", "heads/feature/x"):
            self.assertEqual(self.hook(f"git merge {spelled}")[0], "deny", spelled)
        self.record(self.wt)
        self.assertEqual(self.hook("git merge refs/heads/feature/x"), ("allow", ""))

    def test_full_branch_ref_wins_over_a_same_named_tag(self):
        self.record(self.wt)
        git(self.repo, "tag", "amb", "feature/x")
        amb = os.path.join(self.tmp, "app-amb")
        git(self.repo, "worktree", "add", "-q", "-b", "amb", amb, "main")
        self.commit(amb, "amb.txt", "unverified")
        decision, reason = self.hook("git merge refs/heads/amb")
        self.assertEqual(decision, "deny", reason)

    def test_bare_name_resolving_to_a_tag_asks(self):
        amb = os.path.join(self.tmp, "app-amb")
        git(self.repo, "worktree", "add", "-q", "-b", "amb", amb, "main")
        self.commit(amb, "amb.txt", "verified branch")
        self.record(amb)
        other = os.path.join(self.tmp, "app-tagsrc")
        git(self.repo, "worktree", "add", "-q", "-b", "tagsrc", other, "main")
        git(self.repo, "tag", "amb", self.commit(other, "t.txt", "unverified tag target"))
        decision, reason = self.hook("git merge amb")
        self.assertEqual(decision, "ask", reason)
        self.assertIn("歧義", reason)

    def test_octopus_and_previous_branch_ask(self):
        self.record(self.wt)
        git(self.repo, "branch", "other")
        self.assertMergeAsks("git merge feature/x other", "無法判定")
        self.assertMergeAsks("git merge -", "無法判定")

    def assertMergeAsks(self, cmd, word, cwd=None):
        decision, reason = self.hook(cmd, cwd)
        self.assertEqual(decision, "ask", (cmd, reason))
        self.assertIn(word, reason, cmd)

    def test_record_for_an_older_tree_is_denied(self):
        self.record(self.wt)
        self.commit(self.wt, "a.txt", "more work")
        self.assertEqual(self.hook("git merge feature/x")[0], "deny")

    def test_repo_without_verify_config_is_allowed(self):
        os.remove(os.path.join(self.tmp, "checks", "app", "verify.json"))
        self.assertEqual(self.hook("git merge feature/x"), ("allow", ""))

    def test_merge_into_a_feature_branch_is_not_checked(self):
        other = os.path.join(self.tmp, "app-other")
        git(self.repo, "worktree", "add", "-q", "-b", "wt/z", other)
        self.commit(other, "b.txt", "worker")
        self.assertEqual(self.hook("git merge wt/z", cwd=self.wt), ("allow", ""))

    def test_remote_tracking_ref_is_not_checked(self):
        self.assertEqual(self.hook("git merge --ff-only origin/main"), ("allow", ""))

    def test_protected_branches_come_from_config(self):
        self.write_config('{"protected_branches":["develop"],"commands":[{"name":"ok","cmd":"true"}]}')
        self.assertEqual(self.hook("git merge feature/x"), ("allow", ""))
        develop = os.path.join(self.tmp, "app-develop")
        git(self.repo, "worktree", "add", "-q", "-b", "develop", develop, "main")
        self.assertEqual(self.hook("git merge feature/x", cwd=develop)[0], "deny")

    def test_check_record_error_asks(self):
        self.write_config("{not json")
        decision, reason = self.hook("git merge feature/x")
        self.assertEqual(decision, "ask")
        self.assertIn("合併閘門無法判定", reason)

    def test_slow_git_asks_within_budget(self):
        self.slow_git(2)
        decision, reason = self.hook("git merge feature/x")
        self.assertEqual(decision, "ask", reason)
        self.assertLess(self.elapsed, 9)


class PushPlanGate(GateCase):
    def setUp(self):
        super().setUp()
        self.head = self.commit(self.repo, "a.txt", "pending")

    def snapshot(self, branch="main", repo=None):
        p = self.cli(PUSH_PLAN, "snapshot", "--repo", repo or self.repo, "--branch", branch, "--no-fetch")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def assertNotBlockedByPushPlan(self, cmd):
        decision, reason = self.hook(cmd)
        self.assertEqual(decision, "ask", (cmd, reason))
        self.assertNotIn("push-plan", reason, cmd)

    def assertDeniedByPushPlan(self, cmd, *words):
        decision, reason = self.hook(cmd)
        self.assertEqual(decision, "deny", (cmd, reason))
        for word in words:
            self.assertIn(word, reason, cmd)

    def assertPushPlanAsks(self, cmd, word):
        decision, reason = self.hook(cmd)
        self.assertEqual(decision, "ask", (cmd, reason))
        self.assertIn(word, reason, cmd)

    def test_no_snapshot_is_denied_with_snapshot_hint(self):
        self.assertDeniedByPushPlan(f"{PUSH} origin main", "push-plan snapshot", f"--repo {self.repo}",
                                    "--branch main")

    def test_matching_snapshot_is_not_blocked(self):
        self.snapshot()
        self.assertNotBlockedByPushPlan(f"{PUSH} origin main")
        self.assertIn("快照一致（main），待推 commit：\n" + git(self.repo, "log", "-1", "--format=%h %s"),
                      self.hook(f"{PUSH} origin main")[1])

    def test_commit_after_snapshot_is_denied(self):
        self.snapshot()
        self.commit(self.repo, "a.txt", "sneaked in")
        self.assertDeniedByPushPlan(f"{PUSH} origin main", "不一致", "回報 Mike", "新增")

    def test_hash_refspec_targets_its_destination(self):
        self.assertDeniedByPushPlan(f"{PUSH} origin {self.head}:main", "--branch main")
        self.snapshot()
        self.assertNotBlockedByPushPlan(f"{PUSH} origin {self.head}:main")
        self.assertNotBlockedByPushPlan(f"{PUSH} origin {self.head}:refs/heads/main")

    def test_head_destination_resolves_to_current_branch(self):
        self.assertDeniedByPushPlan(f"{PUSH} origin HEAD", "--branch main")
        self.snapshot()
        self.assertNotBlockedByPushPlan(f"{PUSH} origin HEAD")
        self.assertNotBlockedByPushPlan(f"{PUSH} origin HEAD:main")

    def test_rename_push_with_snapshot_asks_with_commit_list(self):
        git(self.repo, "branch", "feature/x", "main~1")
        self.commit_on_branch("feature/x")
        self.snapshot()
        decision, reason = self.hook(f"{PUSH} origin feature/x:main")
        self.assertEqual(decision, "ask", reason)
        self.assertIn("改名推送", reason)
        self.assertIn(git(self.repo, "log", "-1", "--format=%h %s", "feature/x"), reason)

    def test_rename_push_without_snapshot_is_denied(self):
        git(self.repo, "branch", "feature2", "main~1")
        self.commit_on_branch("feature2")
        self.assertDeniedByPushPlan(f"{PUSH} origin feature2:main", "push 前先跑", "--branch main")

    def test_src_ahead_of_an_up_to_date_branch_without_snapshot_is_denied(self):
        git(self.repo, "reset", "-q", "--hard", "origin/main")
        git(self.repo, "branch", "feature/x")
        self.commit_on_branch("feature/x")
        self.assertDeniedByPushPlan(f"{PUSH} origin feature/x:main", "push 前先跑", "--branch main")

    def test_worktree_head_to_main_without_snapshot_is_denied(self):
        side = os.path.join(self.tmp, "side-w")
        git(self.repo, "worktree", "add", "-q", "-b", "feature/w", side, "main~1")
        self.commit(side, "w.txt", "worktree work")
        decision, reason = self.hook(f"{PUSH} origin HEAD:main", cwd=side)
        self.assertEqual(decision, "deny", reason)
        self.assertIn("push 前先跑", reason)

    def test_destination_without_local_branch_and_snapshot_is_denied(self):
        git(self.repo, "push", "-q", "origin", "main~1:refs/heads/online")
        git(self.repo, "fetch", "-q", "origin")
        self.assertDeniedByPushPlan(f"{PUSH} origin main:online", "push 前先跑", "--branch online")

    def test_destination_without_local_branch_but_with_snapshot_asks_with_commit_list(self):
        git(self.repo, "push", "-q", "origin", "main~1:refs/heads/online")
        git(self.repo, "fetch", "-q", "origin")
        git(self.repo, "branch", "online", "main")
        self.snapshot("online")
        git(self.repo, "update-ref", "-d", "refs/heads/online")
        decision, reason = self.hook(f"{PUSH} origin main:online")
        self.assertEqual(decision, "ask", reason)
        self.assertIn("目的端沒有本地分支", reason)
        self.assertIn(git(self.repo, "log", "-1", "--format=%h %s", "main"), reason)

    def test_hash_other_than_local_destination_without_snapshot_is_denied(self):
        git(self.repo, "push", "-q", "origin", "main~1:refs/heads/online")
        git(self.repo, "fetch", "-q", "origin")
        git(self.repo, "branch", "online", "main~1")
        self.assertDeniedByPushPlan(f"{PUSH} origin {self.head}:online", "push 前先跑", "--branch online")

    def test_control_characters_in_subjects_are_escaped(self):
        self.commit(self.repo, "a.txt", "evil\x1b[31m subject")
        self.snapshot()
        decision, reason = self.hook(f"{PUSH} origin main")
        self.assertEqual(decision, "ask", reason)
        self.assertNotIn("\x1b", reason)
        self.assertIn("evil\\x1b[31m subject", reason)

    def test_line_breaking_characters_cannot_forge_a_line(self):
        for evil in ("evil\rforged line", "evil\u2028forged line", "evil\x0bforged line", "evil\x85forged line"):
            self.commit(self.repo, "a.txt", evil)
        self.snapshot()
        decision, reason = self.hook(f"{PUSH} origin main")
        self.assertEqual(decision, "ask", reason)
        for escaped in ("evil\\rforged", "evil\\u2028forged", "evil\\x0bforged", "evil\\x85forged"):
            self.assertIn(escaped, reason)
        self.assertFalse(any(line.startswith("forged") for line in LINE_BREAKS.split(reason)), reason)

    def tree_with_gate(self, script):
        tree = os.path.join(self.tmp, "tree")
        os.makedirs(os.path.join(tree, "hooks"))
        os.makedirs(os.path.join(tree, "bin"))
        guard = shutil.copy(GUARD, os.path.join(tree, "hooks"))
        shutil.copy(PUSH_PLAN, os.path.join(tree, "bin"))
        with open(os.path.join(tree, "bin", "gate-evidence"), "w") as f:
            f.write(script)
        return guard

    def hook_with(self, guard, cmd):
        payload = {"tool_input": {"command": cmd}, "cwd": self.repo}
        p = subprocess.run([sys.executable, guard], input=json.dumps(payload), capture_output=True, text=True,
                           env=self.env())
        spec = json.loads(p.stdout)["hookSpecificOutput"]
        return spec["permissionDecision"], spec["permissionDecisionReason"]

    def test_gate_evidence_failure_still_runs_push_plan(self):
        guard = self.tree_with_gate("import time\n\ndef open_repo(path):\n    return path\n\n\n"
                                    "def is_mvp(repo, commit):\n    return False\n\n\n"
                                    "if __name__ == \"__main__\":\n    time.sleep(30)\n")
        decision, reason = self.hook_with(guard, f"{PUSH} origin main")
        self.assertEqual(decision, "deny", reason)
        self.assertIn("push-plan snapshot", reason)

    def test_probe_timeout_reason_is_short_and_has_no_probe_source(self):
        guard = self.tree_with_gate("import time\ntime.sleep(30)\n")
        decision, reason = self.hook_with(guard, f"{PUSH} origin main")
        self.assertEqual(decision, "ask", reason)
        self.assertIn("逾時", reason)
        self.assertNotIn("SourceFileLoader", reason)

    def test_probe_error_reason_is_truncated(self):
        guard = self.tree_with_gate("raise RuntimeError('x' * 5000)\n")
        decision, reason = self.hook_with(guard, f"{PUSH} origin main")
        self.assertEqual(decision, "ask", reason)
        self.assertNotIn("x" * 300, reason)
        self.assertNotIn("SourceFileLoader", reason)

    def test_other_remote_than_snapshot_is_denied(self):
        other = os.path.join(self.tmp, "other.git")
        subprocess.run(["git", "init", "-q", "--bare", other], check=True)
        git(self.repo, "remote", "add", "other", other)
        git(self.repo, "push", "-q", "other", "main~1:refs/heads/main")
        git(self.repo, "fetch", "-q", "other")
        self.snapshot()
        self.assertDeniedByPushPlan(f"{PUSH} other main", "快照=origin 本次=other")

    def test_tag_destination_asks(self):
        git(self.repo, "tag", "v1")
        self.assertPushPlanAsks(f"{PUSH} origin v1", "不是可比對的分支")

    def test_refs_outside_heads_ask(self):
        self.assertPushPlanAsks(f"{PUSH} origin main:refs/tags/v2", "不是可比對的分支")

    def test_new_branch_without_tracking_ref_asks(self):
        git(self.repo, "branch", "newb")
        self.assertPushPlanAsks(f"{PUSH} origin newb", "新分支或首推")

    def test_nothing_to_push_skips_push_plan(self):
        git(self.repo, "reset", "-q", "--hard", "origin/main")
        self.assertNotBlockedByPushPlan(f"{PUSH} origin main")

    def test_mvp_repo_skips_push_plan(self):
        self.commit(self.repo, "CLAUDE.md", "stage: mvp")
        self.assertNotBlockedByPushPlan(f"{PUSH} origin main")

    def test_missing_remote_asks(self):
        self.assertPushPlanAsks(PUSH, "沒指定 remote")

    def test_unresolvable_src_asks(self):
        self.snapshot()
        self.assertPushPlanAsks(f"{PUSH} origin nosuchref:main", "push-plan 無法判定")

    def test_snapshot_of_another_repo_with_the_same_name_asks(self):
        twin_root = os.path.join(self.tmp, "twin")
        twin = os.path.join(twin_root, "app")
        os.makedirs(twin_root)
        subprocess.run(["git", "clone", "-q", self.bare, twin], check=True, capture_output=True)
        self.commit(twin, "t.txt", "twin pending")
        self.snapshot(repo=twin)
        self.assertPushPlanAsks(f"{PUSH} origin main", "快照 repo 與主 checkout 不一致")

    def test_slow_git_asks_within_budget(self):
        self.snapshot()
        self.slow_git(2)
        decision, reason = self.hook(f"{PUSH} origin main")
        self.assertEqual(decision, "ask", reason)
        self.assertLess(self.elapsed, 9)

    def commit_on_branch(self, branch):
        side = os.path.join(self.tmp, "side-" + branch.replace("/", "_"))
        git(self.repo, "worktree", "add", "-q", side, branch)
        self.commit(side, "s.txt", "side work")


if __name__ == "__main__":
    unittest.main(verbosity=2)
