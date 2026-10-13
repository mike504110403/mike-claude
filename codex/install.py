#!/usr/bin/env python3
"""Deploy only the versioned Mike workflow assets; default is a zero-write plan."""
import argparse
import copy
import hashlib
import json
import os
import shlex
import stat
import sys
import uuid
import subprocess
import base64
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "assets"
PACKAGE = "mike-codex-workflow-v1"


class InstallError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def checked(path):
    """Reject symlinks anywhere in a destination's lexical ancestry, before resolve."""
    path = Path(os.path.abspath(os.path.expanduser(str(path))))
    cursor = path
    while True:
        if cursor.is_symlink() or (os.name == "nt" and cursor.exists() and
                getattr(cursor.lstat(), "st_file_attributes", 0) & 0x400):
            raise InstallError("Symlink destination is forbidden: {}".format(cursor))
        if cursor.exists() and cursor != path and not cursor.is_dir():
            raise InstallError("Destination parent is not a directory: {}".format(cursor))
        if cursor == cursor.parent:
            break
        cursor = cursor.parent
    return path



def same_identity(left, right):
    try:
        return left.samefile(right)
    except (OSError, ValueError):
        return False


def overlaps(left, right):
    """Conservative casefold namespace plus existing endpoint/ancestor identity."""
    first = tuple(part.casefold() for part in left.parts)
    second = tuple(part.casefold() for part in right.parts)
    if first[:len(second)] == second or second[:len(first)] == first:
        return True
    return any(same_identity(ancestor, right) for ancestor in (left,) + tuple(left.parents)) or any(same_identity(left, ancestor) for ancestor in (right,) + tuple(right.parents))


def file_mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def windows_acl(path, value=None):
    """Read/apply a self-relative DACL; never treat chmod as Windows security."""
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    if value is None:
        size = wintypes.DWORD()
        api.GetFileSecurityW(str(path), 4, None, 0, ctypes.byref(size))
        buffer = ctypes.create_string_buffer(size.value)
        if not api.GetFileSecurityW(str(path), 4, buffer, size.value, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return base64.b64encode(buffer.raw).decode("ascii")
    raw = base64.b64decode(value, validate=True)
    buffer = ctypes.create_string_buffer(raw)
    protection = 0x80000000 if int.from_bytes(raw[2:4], "little") & 0x1000 else 0x20000000
    if not api.SetFileSecurityW(str(path), 4 | protection, buffer):
        raise ctypes.WinError(ctypes.get_last_error())


def private_acl():
    import ctypes
    from ctypes import wintypes
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    descriptor = ctypes.c_void_p()
    size = wintypes.DWORD()
    if not api.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            "D:P(A;;FA;;;OW)(A;;FA;;;SY)(A;;FA;;;BA)", 1,
            ctypes.byref(descriptor), ctypes.byref(size)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return base64.b64encode(ctypes.string_at(descriptor, size.value)).decode("ascii")
    finally:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(descriptor)


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "nt":
        windows_acl(path, private_acl())
    else:
        os.chmod(str(path), 0o700)


def atomic_write(path, data, mode, acl=None):
    """A partial write cannot truncate the destination; tmp starts private."""
    temporary = path.with_name(path.name + ".mike-" + uuid.uuid4().hex + ".tmp")
    try:
        descriptor = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        if os.name == "nt":
            windows_acl(temporary, private_acl())
        temporary.write_bytes(data)
        os.chmod(str(temporary), mode)
        if os.name == "nt":
            windows_acl(temporary, acl or (windows_acl(path) if path.exists() else
                        private_acl() if mode == 0o600 else windows_acl(path.parent)))
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        raise InstallError("Invalid JSON at {}: {}".format(path, exc))
    if not isinstance(value, dict):
        raise InstallError("JSON root must be an object: {}".format(path))
    return value


def validate_hooks(value):
    if not isinstance(value.get("hooks", {}), dict):
        raise InstallError("hooks must be an object")
    for event, groups in value.get("hooks", {}).items():
        if not isinstance(groups, list):
            raise InstallError("Hook event {} must contain a list".format(event))
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise InstallError("Invalid matcher group in {}".format(event))
            if "matcher" in group and not isinstance(group["matcher"], str):
                raise InstallError("Hook matcher must be a string")
            if not all(isinstance(handler, dict) for handler in group["hooks"]):
                raise InstallError("Hook handlers must be objects")


def owned_groups(home):
    hook_root = home / "workflow" / "mike" / "hooks"
    result = {}
    for event, script, matcher in (("PreToolUse", "guard.py", "^(Bash|apply_patch|Edit|Write)$"), ("PostToolUse", "format_changed.py", "^(apply_patch|Edit|Write)$")):
        # Use Windows command-line quoting; validate the target hook runtime separately.
        command = (subprocess.list2cmdline([sys.executable, str(hook_root / script)])
                   if os.name == "nt" else
                   "{} {}".format(shlex.quote(sys.executable), shlex.quote(str(hook_root / script))))
        result[event] = [{"matcher": matcher, "hooks": [{"type": "command", "command": command, "timeout": 90, "statusMessage": "Mike workflow: {}".format(script)}]}]
    return result


def plan(home, skills, replace):
    home, skills = checked(home), checked(skills)
    for root in (home, skills):
        if root.exists() and not root.is_dir():
            raise InstallError("Target root is not a directory: {}".format(root))
        if overlaps(root, SOURCE.parent):
            raise InstallError("Target must not overlap package source")
    if any(overlaps(skills, reserved) for reserved in (home / "agents", home / "workflow")):
        raise InstallError("Skills root overlaps reserved package destinations")
    if overlaps(skills, home):
        raise InstallError("Codex home and skills root must be separate namespaces")
    manifest_path = checked(home / "workflow" / "mike" / "manifest.json")
    manifest = read_json(manifest_path) if manifest_path.exists() else None
    if manifest is not None:
        if manifest.get("package") != PACKAGE or manifest.get("codex_home") != str(home) or manifest.get("skills_dir") != str(skills):
            raise InstallError("Manifest identity/target mismatch")
        if not isinstance(manifest.get("files"), dict) or not isinstance(manifest.get("hook_groups"), dict):
            raise InstallError("Malformed ownership manifest")
        validate_hooks({"hooks": manifest["hook_groups"]})
    checked(SOURCE)
    if SOURCE.is_symlink() or not SOURCE.is_dir():
        raise InstallError("Source assets must be a real directory")
    desired = {}
    for source in sorted(SOURCE.rglob("*")):
        if source.is_symlink() or (os.name == "nt" and
                getattr(source.lstat(), "st_file_attributes", 0) & 0x400):
            raise InstallError("Source symlink is forbidden: {}".format(source))
        if source.is_dir():
            continue
        if "__pycache__" in source.parts or source.suffix == ".pyc":
            continue
        relative = source.relative_to(SOURCE)
        if relative.parts[0] == "skills":
            target = skills.joinpath(*relative.parts[1:])
        elif relative.parts[0] == "agents":
            target = home / relative
        elif relative.parts[0] == "hooks":
            target = home / "workflow" / "mike" / relative
        elif relative == Path("AGENTS.md"):
            target = home / relative
        else:
            raise InstallError("Unexpected source asset: {}".format(relative))
        target = checked(target)
        if target in desired or target in (home / "hooks.json", manifest_path):
            raise InstallError("Overlapping destinations: {}".format(target))
        desired[target] = source.read_bytes()
    # Every previous owned file must still belong to this fixed package mapping.
    previous = manifest["files"] if manifest is not None else {}
    if set(previous) - {str(path) for path in desired}:
        raise InstallError("Manifest contains unrecognized/retired managed paths; reconcile manually")
    for path in desired:
        if path.exists() and not path.is_file():
            raise InstallError("Target file is not regular: {}".format(path))
        if str(path) in previous:
            if not isinstance(previous[str(path)], str) or len(previous[str(path)]) != 64:
                raise InstallError("Invalid managed file hash")
            if not path.exists() or digest(path.read_bytes()) != previous[str(path)]:
                if not replace:
                    raise InstallError("Managed asset changed/missing: {}; use --replace-existing after review".format(path))
        elif path.exists() and not replace:
            raise InstallError("Existing asset collision: {}; use --replace-existing after review".format(path))
    hook_path = checked(home / "hooks.json")
    hooks = read_json(hook_path) if hook_path.exists() else {"hooks": {}}
    validate_hooks(hooks)
    merged = copy.deepcopy(hooks)
    table = merged.setdefault("hooks", {})
    if manifest is not None:
        for event, groups in manifest["hook_groups"].items():
            for group in groups:
                matches = [i for i, existing in enumerate(table.get(event, [])) if existing == group]
                if len(matches) != 1:
                    raise InstallError("Owned hook definition changed/missing/duplicated; reconcile hooks.json manually")
                del table[event][matches[0]]
    generated = owned_groups(home)
    for event, groups in generated.items():
        table.setdefault(event, []).extend(groups)
    new_manifest = {"package": PACKAGE, "codex_home": str(home), "skills_dir": str(skills), "files": {str(path): digest(data) for path, data in desired.items()}, "hook_groups": generated}
    desired[hook_path] = encoded(merged) if merged != hooks else hook_path.read_bytes()
    desired[manifest_path] = encoded(new_manifest)
    changes = {path: data for path, data in desired.items() if not path.exists() or path.read_bytes() != data}
    # Preflight all bookkeeping targets before performing the first mutation.
    backup_root = checked(home / "workflow" / "mike" / "backups" / uuid.uuid4().hex)
    backup_items = {path: path.read_bytes() for path in changes if path.exists()}
    backup_paths = {path: checked(backup_root / "files" / (str(index) + ".bak")) for index, path in enumerate(backup_items)}
    backup_index = checked(backup_root / "index.json")
    unknown = sum(len(groups) for groups in table.values()) - sum(len(groups) for groups in generated.values())
    before_modes = {path: file_mode(path) for path in backup_items}
    installed_modes = {path: before_modes.get(path, 0o600 if path in (hook_path, manifest_path) else 0o644) for path in changes}
    if os.name == "nt":
        # Windows stat reports only the DOS writable flag, not POSIX permissions.
        installed_modes = {path: 0o666 if mode & 0o200 else 0o444 for path, mode in installed_modes.items()}
    receipt = {
        "package": PACKAGE, "codex_home": str(home), "skills_dir": str(skills),
        "files": {str(path): {
            "backup": str(backup_paths[path]) if path in backup_items else None,
            "installed_sha": digest(data), "before_sha": digest(backup_items[path]) if path in backup_items else None,
            "before_mode": before_modes.get(path), "installed_mode": installed_modes[path]
        } for path, data in changes.items() if path != hook_path},
        "hook_change": {
            "path": str(hook_path), "before_groups": manifest["hook_groups"] if manifest is not None else {},
            "installed_groups": generated, "before_mode": before_modes.get(hook_path), "installed_mode": installed_modes[hook_path]
        } if hook_path in changes else None
    }
    if os.name == "nt":
        receipt["windows_before_acls"] = {str(path): windows_acl(path) for path in backup_items}
    return changes, backup_items, backup_paths, backup_index, unknown, receipt


def apply(changes, backups, backup_paths, backup_index, receipt):
    for path, data in backups.items():
        private_directory(backup_paths[path].parent.parent)
        private_directory(backup_paths[path].parent)
        atomic_write(backup_paths[path], data, 0o600)
    if changes:
        private_directory(backup_index.parent)
        atomic_write(backup_index, encoded(receipt), 0o600)
    modes = {Path(raw): detail for raw, detail in receipt["files"].items()}
    if receipt["hook_change"]:
        modes[Path(receipt["hook_change"]["path"])] = receipt["hook_change"]
    completed = []
    try:
        for path, data in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            sensitive = path.name in ("hooks.json", "manifest.json")
            acl = (receipt.get("windows_before_acls", {}).get(str(path)) or
                   (private_acl() if sensitive and os.name == "nt" else None))
            atomic_write(path, data, modes[path]["installed_mode"], acl=acl)
            completed.append(path)
        if os.name == "nt" and changes:
            receipt["windows_installed_acls"] = {str(path): windows_acl(path) for path in changes}
            atomic_write(backup_index, encoded(receipt), 0o600)
    except OSError:
        for path in reversed(completed):
            if path in backups:
                atomic_write(path, backups[path], modes[path]["before_mode"])
            else:
                path.unlink()
        raise



def restore(index_file, apply_changes):
    index = checked(index_file)
    receipt = read_json(index)
    if receipt.get("package") != PACKAGE:
        raise InstallError("Unknown restore receipt")
    home, skills = checked(receipt["codex_home"]), checked(receipt["skills_dir"])
    if index.parent.parent != home / "workflow" / "mike" / "backups":
        raise InstallError("Receipt is outside its package backup location")
    allowed = {home / "AGENTS.md", home / "workflow" / "mike" / "manifest.json"}
    for source in SOURCE.rglob("*"):
        if source.is_file() and source.suffix != ".pyc" and "__pycache__" not in source.parts:
            rel = source.relative_to(SOURCE)
            if rel.parts[0] == "skills":
                allowed.add(skills.joinpath(*rel.parts[1:]))
            elif rel.parts[0] == "agents":
                allowed.add(home / rel)
            elif rel.parts[0] == "hooks":
                allowed.add(home / "workflow" / "mike" / rel)
    if not isinstance(receipt.get("files"), dict):
        raise InstallError("Invalid restore file table")
    changes = {}
    restored_modes = {}
    if os.name == "nt":
        installed_acls = receipt.get("windows_installed_acls")
        if not isinstance(installed_acls, dict):
            raise InstallError("Windows receipt lacks installed ACL evidence")
        for raw in receipt["files"]:
            if raw not in installed_acls or windows_acl(checked(raw)) != installed_acls[raw]:
                raise InstallError("Restore target ACL changed/missing: {}".format(raw))
    for raw, detail in receipt["files"].items():
        path = checked(raw)
        if path not in allowed or not isinstance(detail, dict):
            raise InstallError("Unexpected restore target")
        if not path.is_file() or digest(path.read_bytes()) != detail.get("installed_sha"):
            raise InstallError("Restore target changed/missing: {}".format(path))
        if file_mode(path) != detail.get("installed_mode"):
            raise InstallError("Restore target permissions changed: {}".format(path))
        restored_modes[path] = detail.get("before_mode")
        if restored_modes[path] is not None and (not isinstance(restored_modes[path], int) or not 0 <= restored_modes[path] <= 0o7777):
            raise InstallError("Invalid original file mode")
        backup = detail.get("backup")
        if backup is None:
            changes[path] = None
        else:
            saved = checked(backup)
            if saved.parent != index.parent / "files" or not saved.is_file():
                raise InstallError("Unsafe/missing backup file")
            data = saved.read_bytes()
            if digest(data) != detail.get("before_sha"):
                raise InstallError("Backup content hash mismatch")
            changes[path] = data
    hook_change = receipt.get("hook_change")
    if hook_change:
        path = checked(hook_change["path"])
        if path != home / "hooks.json":
            raise InstallError("Unexpected restore hooks path")
        if os.name == "nt" and windows_acl(path) != installed_acls.get(str(path)):
            raise InstallError("Restore hook ACL changed")
        if file_mode(path) != hook_change.get("installed_mode"):
            raise InstallError("Restore hook permissions changed")
        restored_modes[path] = hook_change.get("before_mode") if hook_change.get("before_mode") is not None else hook_change["installed_mode"]
        current = read_json(path)
        validate_hooks(current)
        before, installed = hook_change["before_groups"], hook_change["installed_groups"]
        validate_hooks({"hooks": before})
        validate_hooks({"hooks": installed})
        for event, groups in installed.items():
            for group in groups:
                matches = [i for i, existing in enumerate(current["hooks"].get(event, [])) if existing == group]
                if len(matches) != 1:
                    raise InstallError("Restore hook changed/missing/duplicated")
                del current["hooks"][event][matches[0]]
        for event, groups in before.items():
            current["hooks"].setdefault(event, []).extend(groups)
        changes[path] = encoded(current)
    print("{} RESTORE: {} files".format("APPLY" if apply_changes else "DRY-RUN", len(changes)))
    for path in changes:
        print(path)
    if apply_changes:
        originals = {path: path.read_bytes() for path in changes}
        original_modes = {path: file_mode(path) for path in changes}
        original_acls = {path: windows_acl(path) for path in changes} if os.name == "nt" else {}
        completed = []
        try:
            for path, data in changes.items():
                if data is None:
                    path.unlink()
                else:
                    atomic_write(path, data, restored_modes[path],
                                 acl=receipt.get("windows_before_acls", {}).get(str(path)))
                completed.append(path)
        except OSError:
            for path in reversed(completed):
                atomic_write(path, originals[path], original_modes[path], acl=original_acls.get(path))
            raise
        print("Restored package assets; unknown hooks preserved. Review/trust changed hooks with /hooks.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", help="Preview restoration from an installer backup index; combine with --apply to restore")
    parser.add_argument("--apply", action="store_true", help="Deploy after preflight (default: dry-run)")
    parser.add_argument("--replace-existing", action="store_true", help="Replace conflicting assets with scoped backups")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    parser.add_argument("--skills-dir", default=str(Path.home() / ".agents" / "skills"))
    args = parser.parse_args()
    try:
        if args.restore:
            return restore(args.restore, args.apply)
        changes, backups, backup_paths, backup_index, unknown, receipt = plan(args.codex_home, args.skills_dir, args.replace_existing)
        print("{}: {} file changes, {} backups".format("APPLY" if args.apply else "DRY-RUN", len(changes), len(backups)))
        for path in changes:
            print(path)
        if unknown:
            print("WARNING: {} unknown hook groups preserved; review for duplicates/legacy incompatibility in /hooks".format(unknown))
        if args.apply:
            apply(changes, backups, backup_paths, backup_index, receipt)
            if changes:
                print("Backup index: {}".format(backup_index))
            print("Deployed definitions; review/trust new or changed hooks via /hooks before they can run.")
        return 0
    except (InstallError, OSError, KeyError, TypeError) as exc:
        print("Installation refused: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
