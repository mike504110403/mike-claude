import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
INSTALL = PACKAGE / "install.py"
HOOKS = PACKAGE / "assets" / "hooks"


def cli(*args):
    return subprocess.run([sys.executable, str(INSTALL)] + list(map(str, args)), text=True, capture_output=True)


def hook(script, cwd, command, tool="apply_patch", event=None, directory=HOOKS):
    payload = {"hook_event_name": event or ("PreToolUse" if script == "guard.py" else "PostToolUse"), "cwd": str(cwd), "tool_name": tool, "tool_input": {"command": command}}
    return subprocess.run([sys.executable, str(directory / script)], input=json.dumps(payload), text=True, capture_output=True)


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.home = self.root / "codex-home"
        self.skills = self.root / "skills"
        self.args = ["--codex-home", self.home, "--skills-dir", self.skills]

    def tearDown(self):
        self.temp.cleanup()

    def install(self, *args):
        result = cli(*self.args, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def receipt(self, result):
        return Path(next(line[len("Backup index: "):] for line in result.stdout.splitlines() if line.startswith("Backup index: ")))

    def test_dry_run_zero_writes_then_fresh_apply_and_idempotent(self):
        before = snapshot(self.root)
        self.install()
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(self.home.exists())
        result = self.install("--apply")
        self.assertTrue((self.skills / "feature" / "SKILL.md").is_file())
        self.assertTrue((self.home / "agents" / "code-reviewer.toml").is_file())
        self.assertTrue((self.home / "AGENTS.md").is_file())
        installed = snapshot(self.root)
        self.install("--apply")
        self.assertEqual(snapshot(self.root), installed)
        self.assertIn("0 file changes", self.install().stdout)
        receipt = self.receipt(result)
        self.assertEqual(stat.S_IMODE(receipt.stat().st_mode), 0o666 if os.name == "nt" else 0o600)
        self.assertEqual(stat.S_IMODE(receipt.parent.stat().st_mode), 0o777 if os.name == "nt" else 0o700)

    def test_unknown_hooks_config_auth_untouched_and_copied_hooks_work(self):
        self.home.mkdir()
        (self.home / "config.toml").write_bytes(b'model="private-existing"\n')
        (self.home / "auth.json").write_bytes(b'{"token":"fixture-only"}')
        unknown = {"matcher": "Bash", "hooks": [{"type": "command", "command": "old-independent-guard"}]}
        (self.home / "hooks.json").write_text(json.dumps({"description": "keep", "hooks": {"PreToolUse": [unknown]}}))
        self.install("--apply")
        self.assertEqual((self.home / "config.toml").read_bytes(), b'model="private-existing"\n')
        self.assertEqual((self.home / "auth.json").read_bytes(), b'{"token":"fixture-only"}')
        value=json.loads((self.home / "hooks.json").read_text())
        self.assertEqual(value["description"], "keep")
        self.assertIn(unknown, value["hooks"]["PreToolUse"])
        self.assertIn("unknown hook groups preserved", self.install().stdout)
        relocated = self.root / "moved-independent-hooks"
        shutil.copytree(self.home / "workflow" / "mike" / "hooks", relocated)
        response = hook("guard.py", self.root, "git status", tool="Bash", directory=relocated)
        self.assertEqual(json.loads(response.stdout), {})
        patch="*** Begin Patch\n*** Update File: codex-home/AGENTS.md\n@@\n-old\n+new\n*** End Patch"
        guarded=hook("guard.py",self.root,patch,directory=self.home / "workflow" / "mike" / "hooks")
        self.assertEqual(json.loads(guarded.stdout)["hookSpecificOutput"]["permissionDecision"],"deny")
        source_text = "\n".join(p.read_text() for p in relocated.glob("*.py"))
        self.assertNotIn(".claude", source_text)

    def test_collision_refusal_replace_restore_bytes_resources_and_new_hooks(self):
        self.home.mkdir()
        original = b"Original global guidance\n"
        (self.home / "AGENTS.md").write_bytes(original)
        resource = self.skills / "feature" / "references" / "existing.md"
        resource.parent.mkdir(parents=True)
        resource.write_bytes(b"Unrelated skill resource")
        (self.skills / "feature" / "SKILL.md").write_bytes(b"old skill")
        before = snapshot(self.root)
        result=cli(*self.args,"--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(snapshot(self.root), before)
        installed = self.install("--replace-existing", "--apply")
        self.assertEqual(resource.read_bytes(), b"Unrelated skill resource")
        new = {"matcher": "Bash", "hooks": [{"type": "command", "command": "new-unknown"}]}
        path=self.home / "hooks.json"
        value=json.loads(path.read_text())
        value["hooks"]["PreToolUse"].append(new)
        path.write_text(json.dumps(value))
        receipt=self.receipt(installed)
        current=snapshot(self.root)
        self.assertEqual(cli("--restore", receipt).returncode, 0)
        self.assertEqual(snapshot(self.root), current)
        result=cli("--restore",receipt,"--apply")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((self.home / "AGENTS.md").read_bytes(),original)
        self.assertEqual((self.skills / "feature" / "SKILL.md").read_bytes(),b"old skill")
        self.assertEqual(resource.read_bytes(),b"Unrelated skill resource")
        self.assertEqual(json.loads(path.read_text())["hooks"]["PreToolUse"], [new])
        self.assertFalse((self.home / "workflow" / "mike" / "manifest.json").exists())

    def test_managed_edits_refuse_then_explicit_replacement(self):
        first=self.install("--apply")
        path=self.home / "AGENTS.md"
        path.write_bytes(b"local modified")
        before=snapshot(self.root)
        self.assertNotEqual(cli(*self.args,"--apply").returncode,0)
        self.assertEqual(snapshot(self.root),before)
        restored=cli("--restore",self.receipt(first),"--apply")
        self.assertNotEqual(restored.returncode,0)
        self.assertEqual(snapshot(self.root),before)
        replaced=self.install("--replace-existing","--apply")
        result=cli("--restore",self.receipt(replaced),"--apply")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(path.read_bytes(),b"local modified")

    def test_malformed_json_and_modified_hook_refuse_before_write(self):
        self.home.mkdir()
        path=self.home / "hooks.json"
        for text in ('{', '[]', '{"hooks": {"PreToolUse": {}}}'):
            with self.subTest(text=text):
                path.write_text(text)
                before=snapshot(self.root)
                self.assertNotEqual(cli(*self.args,"--apply").returncode,0)
                self.assertEqual(snapshot(self.root),before)
        path.write_text('{"hooks": {}}')
        self.install("--apply")
        value=json.loads(path.read_text())
        value["hooks"]["PreToolUse"][0]["matcher"]="manually-modified"
        path.write_text(json.dumps(value))
        before=snapshot(self.root)
        self.assertNotEqual(cli(*self.args,"--replace-existing","--apply").returncode,0)
        self.assertEqual(snapshot(self.root),before)

    @unittest.skipIf(os.name == "nt", "Device lacks symlink privilege; mock reparse checks covered in test_windows")
    def test_source_symlink_refused_zero_write(self):
        copied=self.root / "source-copy"
        shutil.copytree(PACKAGE,copied,ignore=shutil.ignore_patterns("__pycache__"))
        (copied / "assets" / "symlink").symlink_to(self.root / "outside")
        result=subprocess.run([sys.executable,str(copied / "install.py")] + list(map(str,self.args)) + ["--apply"],text=True,capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("Source symlink",result.stderr)
        self.assertFalse(self.home.exists())
        self.assertFalse(self.skills.exists())

    def test_empty_manifest_and_tampered_backup_refuse_zero_write(self):
        self.home.mkdir()
        (self.home / "AGENTS.md").write_bytes(b"original")
        result=self.install("--replace-existing","--apply")
        receipt=self.receipt(result)
        saved=json.loads(receipt.read_text())
        backup=Path(saved["files"][str(self.home / "AGENTS.md")]["backup"])
        backup.write_bytes(b"tampered")
        before=snapshot(self.root)
        restore=cli("--restore",receipt,"--apply")
        self.assertNotEqual(restore.returncode,0)
        self.assertIn("hash mismatch",restore.stderr)
        self.assertEqual(snapshot(self.root),before)
        manifest=self.home / "workflow" / "mike" / "manifest.json"
        manifest.write_text("{}")
        before=snapshot(self.root)
        self.assertNotEqual(cli(*self.args,"--replace-existing","--apply").returncode,0)
        self.assertEqual(snapshot(self.root),before)

    @unittest.skipIf(os.name == "nt", "Device lacks symlink privilege; mock reparse checks covered in test_windows")
    def test_unsafe_symlinks_and_source_overlap_refused(self):
        outside=self.root / "outside"
        outside.mkdir()
        self.home.symlink_to(outside,target_is_directory=True)
        self.assertNotEqual(cli(*self.args,"--apply").returncode,0)
        self.assertEqual(list(outside.iterdir()),[])
        self.home.unlink()
        self.home.mkdir()
        (self.home / "AGENTS.md").symlink_to(outside / "secret")
        self.assertNotEqual(cli(*self.args,"--apply").returncode,0)
        result=cli("--codex-home",PACKAGE,"--skills-dir",self.skills,"--apply")
        self.assertNotEqual(result.returncode,0)
        self.assertIn("overlap",result.stderr)


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def assert_denied(self,command,tool="Bash"):
        result=hook("guard.py",self.root,command,tool)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"],"deny",command)

    def test_each_direct_hard_ban_family_never_executes_commands(self):
        denied=["rm -rf doomed", "rm -fr doomed", "rm -r -f doomed", "rm --recursive --force doomed", "rm --force --recursive doomed", "git push --force", "git -C /repo push -f", "git --git-dir=/repo/.git -c core.x=y push --force-with-lease", "git push origin +main:main", "git push --mirror", "git clean -fd", "git clean --force", "git -c clean.requireForce=false clean -d", "git branch -D old", "git branch --delete --force old", "git branch -df old", "git worktree remove --force /old", "git add .", "git add ./", "git -C /repo add -A", "git add --all", "pwd && git push -f"]
        for command in denied:
            with self.subTest(command=command): self.assert_denied(command)

    def test_safe_pairs_keep_native_approval(self):
        safe=["git push origin main", "git add src/main.py", "git clean -n", "git clean -nf", "git clean --dry-run --force", "git branch -d merged", "git worktree remove /old", "rm file", "git -C /repo status", "git log --format=%D", "printf 'rm -rf x'"]
        for command in safe:
            with self.subTest(command=command):
                result=hook("guard.py",self.root,command,"Bash")
                self.assertEqual(json.loads(result.stdout),{},command)

    def test_multifile_move_delete_and_sensitive_targets(self):
        patch="*** Begin Patch\n*** Add File: src/a.vue\n+ok\n*** Update File: src/b.ts\n*** Move to: src/c.ts\n@@\n-old\n+new\n*** Delete File: src/d.ts\n*** End Patch"
        self.assertEqual(json.loads(hook("guard.py",self.root,patch).stdout),{})
        for name in (".env", ".env.production", "auth.json", "credentials.json", ".aws/config", ".ssh/key", ".codex/hooks.json", ".codex/workflow/mike/hooks/guard.py", "../escape", "/outside/file"):
            with self.subTest(name=name):
                self.assert_denied("*** Begin Patch\n*** Add File: "+name+"\n+value\n*** End Patch","apply_patch")
        for name in (".env.example", ".env.sample", ".env.template"):
            patch="*** Begin Patch\n*** Add File: "+name+"\n+value\n*** End Patch"
            self.assertEqual(json.loads(hook("guard.py",self.root,patch).stdout),{})
        self.assert_denied("*** Begin Patch\n*** Update File: x\n*** Move to: .env\n@@\n-x\n+y\n*** End Patch","apply_patch")
        self.assert_denied("*** Begin Patch\n*** Delete File: auth.json\n*** End Patch","apply_patch")

    @unittest.skipIf(os.name == "nt", "Device lacks symlink privilege; mock reparse checks covered in test_windows")
    def test_bad_payload_patch_and_symlink_deny(self):
        for payload in ("garbage", "[]", '{"hook_event_name":"PreToolUse","tool_name":"apply_patch","tool_input":{"file_path":"a"}}'):
            result=subprocess.run([sys.executable,str(HOOKS / "guard.py")],input=payload,text=True,capture_output=True)
            self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"],"deny")
        for patch in ("not patch", "*** Begin Patch\n*** End Patch", "*** Begin Patch\n*** Move to: x\n*** End Patch", "*** Begin Patch\n*** Delete File: x\n+bad\n*** End Patch"):
            self.assert_denied(patch,"apply_patch")
        outside=self.root.parent / (self.root.name+"-outside")
        (self.root / "link").symlink_to(outside,target_is_directory=True)
        self.assert_denied("*** Begin Patch\n*** Add File: link/x\n+x\n*** End Patch","apply_patch")

    def fake_prettier(self, fail=False):
        binary=self.root / "node_modules" / ".bin" / "prettier"
        binary.parent.mkdir(parents=True)
        code='#!'+sys.executable+'\nimport pathlib,sys\n'
        if fail: code+='print("fixture formatter failed",file=sys.stderr)\nsys.exit(7)\n'
        else: code+='p=pathlib.Path(sys.argv[-1])\np.write_text(p.read_text()+"\\nFORMATTED")\n'
        binary.write_text(code)
        binary.chmod(0o755)
        return binary

    @unittest.skipIf(os.name == "nt", "POSIX executable/symlink fixture; Windows coverage in test_windows")
    def test_formatter_changed_files_vue_move_delete_with_local_binary(self):
        self.fake_prettier()
        for name in ("a.vue","new.ts","unchanged.ts"):
            (self.root / name).write_text("original")
        patch="*** Begin Patch\n*** Update File: a.vue\n@@\n-original\n+edit\n*** Update File: old.ts\n*** Move to: new.ts\n@@\n-old\n+new\n*** Delete File: deleted.ts\n*** End Patch"
        result=hook("format_changed.py",self.root,patch)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("FORMATTED",(self.root / "a.vue").read_text())
        self.assertIn("FORMATTED",(self.root / "new.ts").read_text())
        self.assertEqual((self.root / "unchanged.ts").read_text(),"original")

    @unittest.skipIf(os.name == "nt", "POSIX executable/symlink fixture; Windows coverage in test_windows")
    def test_formatter_failure_missing_and_escaping_symlink_visible(self):
        (self.root / "a.vue").write_text("value")
        patch="*** Begin Patch\n*** Update File: a.vue\n@@\n-value\n+edit\n*** End Patch"
        missing=hook("format_changed.py",self.root,patch)
        self.assertIn("unavailable",missing.stdout)
        binary=self.fake_prettier(fail=True)
        failed=hook("format_changed.py",self.root,patch)
        self.assertEqual(failed.returncode,2)
        self.assertIn("fixture formatter failed",failed.stderr)
        binary.unlink()
        binary.symlink_to("/usr/bin/true")
        escaped=hook("format_changed.py",self.root,patch)
        self.assertEqual(escaped.returncode,2)
        self.assertIn("escapes",escaped.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX executable/symlink fixture; Windows coverage in test_windows")
    def test_formatter_gofmt_and_unsafe_changed_paths(self):
        tools=self.root / "tools"
        tools.mkdir()
        binary=tools / "gofmt"
        binary.write_text("#!" + sys.executable + "\n" + 'import pathlib,sys\np=pathlib.Path(sys.argv[-1])\np.write_text(p.read_text()+"\\nGOFMT")\n')
        binary.chmod(0o755)
        (self.root / "x.go").write_text("package fixture")
        payload={"hook_event_name":"PostToolUse","tool_name":"apply_patch","cwd":str(self.root),"tool_input":{"command":"*** Begin Patch\n*** Update File: x.go\n@@\n-x\n+y\n*** End Patch"}}
        environment=dict(os.environ)
        environment["PATH"]=str(tools)+os.pathsep+environment.get("PATH","")
        result=subprocess.run([sys.executable,str(HOOKS / "format_changed.py")],input=json.dumps(payload),text=True,capture_output=True,env=environment)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("GOFMT",(self.root / "x.go").read_text())
        unsafe=hook("format_changed.py",self.root,"*** Begin Patch\n*** Add File: ../x.vue\n+x\n*** End Patch")
        self.assertEqual(unsafe.returncode,2)
        self.assertIn("traversal",unsafe.stderr)

    @unittest.skipIf(os.name == "nt", "POSIX executable/symlink fixture; Windows coverage in test_windows")
    def test_formatter_safe_local_symlink_and_legacy_alias(self):
        binary=self.fake_prettier()
        real=binary.parent / "formatter.py"
        binary.rename(real)
        binary.symlink_to(real)
        (self.root / "x.vue").write_text("x")
        payload={"hook_event_name":"PostToolUse","tool_name":"Edit","cwd":str(self.root),"tool_input":{"file_path":"x.vue"}}
        result=subprocess.run([sys.executable,str(HOOKS / "format_changed.py")],input=json.dumps(payload),text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("FORMATTED",(self.root / "x.vue").read_text())


class BuildTests(unittest.TestCase):
    def test_missing_required_asset_fails_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            copied=Path(temporary).resolve() / "package"
            shutil.copytree(PACKAGE,copied,ignore=shutil.ignore_patterns("__pycache__"))
            (copied / "assets" / "skills" / "quick" / "SKILL.md").unlink()
            result=subprocess.run([sys.executable,str(copied / "validate.py")],text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("Missing required assets",result.stderr)

    def test_package_validate(self):
        result=subprocess.run([sys.executable,str(PACKAGE / "validate.py")],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("VALID:",result.stdout)


if __name__ == "__main__":
    unittest.main()
