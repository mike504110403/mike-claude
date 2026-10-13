"""Native Windows fixtures: no real destructive commands or real formatters."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from test_workflow import cli, hook, HOOKS, snapshot
from test_review_regressions import installer


@unittest.skipUnless(os.name == "nt", "Windows runtime required")
class WindowsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mike windows ")
        self.root = Path(self.temp.name)
        self.home = self.root / "home with spaces"
        self.skills = self.root / "skills"

    def tearDown(self):
        self.temp.cleanup()

    def test_cmd_hook_quoting_acl_backup_restore_and_idempotency(self):
        self.home.mkdir()
        original = self.home / "AGENTS.md"
        original.write_bytes(b"old guidance")
        module = installer()
        before_acl = module.windows_acl(original)
        args = ["--codex-home", self.home, "--skills-dir", self.skills, "--replace-existing"]
        result = cli(*args, "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(module.windows_acl(original), before_acl)
        receipt = Path(next(line[14:] for line in result.stdout.splitlines() if line.startswith("Backup index: ")))
        self.assertEqual(module.windows_acl(receipt), module.private_acl())
        self.assertEqual(module.windows_acl(receipt.parent), module.private_acl())
        self.assertEqual(module.windows_acl(self.home / "hooks.json"), module.private_acl())
        groups = json.loads((self.home / "hooks.json").read_text())["hooks"]
        command = groups["PreToolUse"][0]["hooks"][0]["command"]
        payload = {"hook_event_name": "PreToolUse", "cwd": str(self.root), "tool_name": "Bash", "tool_input": {"command": "git.exe status"}}
        launched = subprocess.run(command, shell=True, input=json.dumps(payload), text=True, capture_output=True)
        self.assertEqual(launched.returncode, 0, launched.stderr)
        self.assertEqual(json.loads(launched.stdout), {})
        before = snapshot(self.root)
        self.assertIn("0 file changes", cli(*args).stdout)
        self.assertEqual(snapshot(self.root), before)
        restored = cli("--restore", receipt, "--apply")
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(original.read_bytes(), b"old guidance")
        self.assertEqual(module.windows_acl(original), before_acl)

    def test_native_shell_direct_bans_and_safe_paths(self):
        for command in ('git.exe push --force', '"C:\\Program Files\\Git\\cmd\\git.exe" push -f', 'Remove-Item -LiteralPath C:\\scratch -Recurse -Force', 'rmdir /s /q C:\\scratch', 'git status; git.exe clean -fd', 'git status`nRemove-Item x -Recurse -Force'):
            result = hook("guard.py", self.root, command, "Bash")
            self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny", command)
        for command in ('git.exe status', 'git -C "C:\\repo with spaces" status', 'Remove-Item -LiteralPath one.txt', 'git clean -nf'):
            self.assertEqual(json.loads(hook("guard.py", self.root, command, "Bash").stdout), {}, command)

    def test_acl_edit_refuses_restore(self):
        result = cli("--codex-home", self.home, "--skills-dir", self.skills, "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = Path(next(line[14:] for line in result.stdout.splitlines() if line.startswith("Backup index: ")))
        module = installer()
        module.windows_acl(self.home / "AGENTS.md", module.private_acl())
        before = snapshot(self.root)
        restored = cli("--restore", receipt, "--apply")
        self.assertNotEqual(restored.returncode, 0)
        self.assertIn("ACL changed", restored.stderr)
        self.assertEqual(snapshot(self.root), before)

    def test_local_node_formatter_success_failure_and_escape(self):
        if not shutil.which("node"):
            self.skipTest("Node unavailable")
        package = self.root / "node_modules" / "prettier"
        package.mkdir(parents=True)
        metadata = package / "package.json"
        metadata.write_text(json.dumps({"bin": "fixture.cjs"}))
        script = package / "fixture.cjs"
        script.write_text("const fs=require('fs'); const p=process.argv.at(-1); fs.appendFileSync(p,'FORMATTED');")
        changed = self.root / "x.vue"
        changed.write_text("x")
        patch = "*** Begin Patch\n*** Update File: x.vue\n@@\n-x\n+y\n*** End Patch"
        result = hook("format_changed.py", self.root, patch)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("FORMATTED", changed.read_text())
        script.write_text("console.error('fixture failure');process.exit(7)")
        self.assertEqual(hook("format_changed.py", self.root, patch).returncode, 2)
        metadata.write_text(json.dumps({"bin": "../../../escape.cjs"}))
        self.assertEqual(hook("format_changed.py", self.root, patch).returncode, 2)

    def test_reparse_destination_is_rejected_before_write(self):
        module = installer()
        self.home.mkdir()
        original = Path.lstat
        def reparse(path, *args, **kwargs):
            if path == self.home:
                return mock.Mock(st_file_attributes=0x400)
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, "lstat", reparse), mock.patch.object(Path, "is_symlink", return_value=False):
            with self.assertRaises(module.InstallError):
                module.checked(self.home / "AGENTS.md")
        self.assertEqual(list(self.home.iterdir()), [])
