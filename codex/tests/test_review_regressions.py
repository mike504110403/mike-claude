"""Portable regressions for review findings; all mutations are temporary fixtures."""
import importlib.util
import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from test_workflow import PACKAGE, cli, hook, snapshot


def installer():
    spec=importlib.util.spec_from_file_location("fixture_installer",PACKAGE / "install.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name).resolve()
        self.home=self.root / "custom-home"
        self.skills=self.root / "skills"
        self.args=["--codex-home",self.home,"--skills-dir",self.skills]

    def tearDown(self):
        self.temp.cleanup()

    def test_casefold_namespaces_and_deployed_package_paths(self):
        for name in (".CODEX/HOOKS.JSON", ".CoDeX/WORKFLOW/MIKE/HOOKS/GUARD.PY", ".AWS/config", ".SSH/key"):
            with self.subTest(name=name):
                patch="*** Begin Patch\n*** Add File: "+name+"\n+x\n*** End Patch"
                result=hook("guard.py",self.root,patch)
                self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"],"deny")
        result=cli(*self.args,"--apply")
        self.assertEqual(result.returncode,0,result.stderr)
        deployed=self.home / "workflow" / "mike" / "hooks"
        patch="*** Begin Patch\n*** Update File: CUSTOM-HOME/WORKFLOW/MIKE/HOOKS/GUARD.PY\n@@\n-x\n+y\n*** End Patch"
        result=hook("guard.py",self.root,patch,directory=deployed)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"],"deny")
        # Actual samefile identity via a hardlink remains portable across case-sensitive FS.
        alias=self.root / "harmless.py"
        os.link(deployed / "guard.py",alias)
        patch="*** Begin Patch\n*** Update File: harmless.py\n@@\n-x\n+y\n*** End Patch"
        result=hook("guard.py",self.root,patch,directory=deployed)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"],"deny")

    def test_nested_managed_worktree_project_policy_namespace(self):
        cwd=self.root / ".codex" / "worktrees" / "fixture" / "repo"
        cwd.mkdir(parents=True)
        for name in (".codex/hooks.json", ".codex/config.toml", ".codex/AGENTS.md", ".CoDeX/HoOkS.JsOn", ".CODEX/CONFIG.TOML", ".CODEX/agents.MD"):
            with self.subTest(name=name):
                patch="*** Begin Patch\n*** Add File: "+name+"\n+x\n*** End Patch"
                result=hook("guard.py",cwd,patch)
                self.assertEqual(json.loads(result.stdout).get("hookSpecificOutput",{}).get("permissionDecision"),"deny")

    def test_newline_shell_boundaries_and_quotes_continuation(self):
        for command in ("git status\nrm -rf doomed", "git status\ngit push --force"):
            with self.subTest(command=command):
                result=hook("guard.py",self.root,command,"Bash")
                self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"],"deny")
        for command in ("printf 'git status\nrm -rf doomed'", 'printf "git status\nrm -rf doomed"', "printf safe\\\nrm -rf doomed"):
            with self.subTest(command=command):
                value = json.loads(hook("guard.py",self.root,command,"Bash").stdout)
                if os.name == "nt" and command.startswith("printf safe"):
                    self.assertEqual(value["hookSpecificOutput"]["permissionDecision"], "deny")
                else:
                    self.assertEqual(value,{})

    def test_clean_exclude_values_and_pathspec_are_not_options(self):
        for command in ("git clean -fd -- -n doomed", "git clean -fd -e -n", "git clean -fd --exclude -n", "git clean -fde-n", "git clean -fd --exclude=-n"):
            with self.subTest(command=command):
                result=hook("guard.py",self.root,command,"Bash")
                self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"],"deny")
        for command in ("git clean -nf", "git clean --dry-run --force", "git clean -n -e '*.log'"):
            self.assertEqual(json.loads(hook("guard.py",self.root,command,"Bash").stdout),{})

    def prepare_restore(self):
        self.home.mkdir()
        (self.home / "AGENTS.md").write_bytes(b"original guidance")
        (self.home / "AGENTS.md").chmod(0o640)
        path=self.home / "hooks.json"
        path.write_text('{"hooks":{}}')
        path.chmod(0o600)
        self.skills.mkdir()
        feature=self.skills / "feature"
        feature.mkdir()
        (feature / "SKILL.md").write_bytes(b"old feature")
        result=cli(*self.args,"--replace-existing","--apply")
        self.assertEqual(result.returncode,0,result.stderr)
        receipt=Path(next(line[14:] for line in result.stdout.splitlines() if line.startswith("Backup index: ")))
        return receipt

    @unittest.skipIf(os.name == "nt", "POSIX modes; Windows DACL coverage in test_windows")
    def test_install_restore_preserve_existing_permissions_and_fresh_sensitive_modes(self):
        receipt=self.prepare_restore()
        self.assertEqual(stat.S_IMODE((self.home / "hooks.json").stat().st_mode),0o600)
        self.assertEqual(stat.S_IMODE((self.home / "AGENTS.md").stat().st_mode),0o640)
        self.assertEqual(cli("--restore",receipt,"--apply").returncode,0)
        self.assertEqual(stat.S_IMODE((self.home / "AGENTS.md").stat().st_mode),0o640)
        self.assertEqual(stat.S_IMODE((self.home / "hooks.json").stat().st_mode),0o600)
        fresh=self.root / "fresh"
        result=cli("--codex-home",fresh,"--skills-dir",self.root / "fresh-skills","--apply")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(stat.S_IMODE((fresh / "hooks.json").stat().st_mode),0o600)

    def test_restore_partial_current_and_later_failure_roll_back_bytes_modes(self):
        receipt=self.prepare_restore()
        module=installer()
        targets=[self.home / "AGENTS.md",self.skills / "feature" / "SKILL.md"]
        for target in targets:
            with self.subTest(target=target):
                before=snapshot(self.root)
                modes={str(p):stat.S_IMODE(p.stat().st_mode) for p in self.root.rglob('*') if p.is_file()}
                original=Path.write_bytes
                fired=[]
                def failing(path,data):
                    if not fired and (path==target or path.name.startswith(target.name+".mike-") and path.parent==target.parent):
                        fired.append(True)
                        original(path,b"partial")
                        raise OSError("injected partial write failure")
                    return original(path,data)
                with mock.patch.object(Path,"write_bytes",failing), contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(OSError):module.restore(receipt,True)
                self.assertTrue(fired)
                self.assertEqual(snapshot(self.root),before)
                self.assertEqual({str(p):stat.S_IMODE(p.stat().st_mode) for p in self.root.rglob('*') if p.is_file()},modes)

    def test_atomic_temporary_creation_and_apply_rollback_preserve_modes(self):
        self.home.mkdir()
        guidance=self.home / "AGENTS.md"
        guidance.write_bytes(b"existing")
        guidance.chmod(0o640)
        module=installer()
        changes,backups,backup_paths,index,unknown,receipt=module.plan(self.home,self.skills,True)
        original=Path.write_bytes
        modes=[]
        fired=[]
        def failing(path,data):
            if ".mike-" in path.name:
                modes.append(stat.S_IMODE(path.stat().st_mode))
                if not fired and path.name.startswith("db-reviewer.toml.mike-"):
                    fired.append(True)
                    original(path,b"partial")
                    raise OSError("injected apply failure")
            return original(path,data)
        with mock.patch.object(Path,"write_bytes",failing):
            with self.assertRaises(OSError):module.apply(changes,backups,backup_paths,index,receipt)
        self.assertTrue(fired)
        self.assertTrue(modes)
        self.assertEqual(set(modes),{0o666} if os.name == "nt" else {0o600})
        self.assertEqual(guidance.read_bytes(),b"existing")
        self.assertEqual(stat.S_IMODE(guidance.stat().st_mode),0o666 if os.name == "nt" else 0o640)
        self.assertFalse((self.home / "agents" / "code-reviewer.toml").exists())
        self.assertFalse((self.home / "agents" / "db-reviewer.toml").exists())

    def test_overlap_uses_existing_ancestor_identity_portably(self):
        module=installer()
        alias=self.root / "virtual-filesystem-alias"
        protected=self.root / "protected"
        original=Path.samefile
        def identity(path,other):
            if path==alias and other==protected or path==protected and other==alias:
                return True
            return original(path,other)
        with mock.patch.object(Path,"samefile",identity):
            self.assertTrue(module.overlaps(alias / "not-created-yet",protected))
            self.assertTrue(module.overlaps(protected,alias / "not-created-yet"))

    def test_source_reserved_and_target_case_alias_overlap_refused(self):
        result=cli("--codex-home",PACKAGE.parent / "CODEX", "--skills-dir",self.skills)
        self.assertNotEqual(result.returncode,0)
        result=cli("--codex-home",self.home,"--skills-dir",self.root / "CUSTOM-HOME" / "AGENTS")
        self.assertNotEqual(result.returncode,0)
        result=cli("--codex-home",self.home,"--skills-dir",self.root / "CUSTOM-HOME")
        self.assertNotEqual(result.returncode,0)


if __name__ == "__main__": unittest.main()
