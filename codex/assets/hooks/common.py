"""Canonical Codex hook inputs and safe patch paths (Python 3.9+)."""
import json
import os
import re
from pathlib import Path


class PolicyError(ValueError):
    pass


def read_event(stream, expected):
    try:
        event = json.load(stream)
    except (ValueError, UnicodeError) as exc:
        raise PolicyError("Invalid hook JSON: {}".format(exc))
    if not isinstance(event, dict) or event.get("hook_event_name") != expected:
        raise PolicyError("Expected {} event".format(expected))
    if event.get("tool_name") not in ("Bash", "apply_patch", "Edit", "Write"):
        raise PolicyError("Unsupported canonical tool name")
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        raise PolicyError("tool_input must be an object")
    if event["tool_name"] in ("Bash", "apply_patch"):
        if not isinstance(tool_input.get("command"), str) or not tool_input["command"].strip():
            raise PolicyError("tool_input.command must be a nonempty string")
    elif not isinstance(tool_input.get("file_path"), str):
        raise PolicyError("Edit/Write input needs file_path")
    cwd = event.get("cwd")
    if not isinstance(cwd, str) or not Path(cwd).is_absolute() or not Path(cwd).is_dir():
        raise PolicyError("cwd must be an existing absolute directory")
    return event


def safe_path(raw, cwd):
    if not raw or "\x00" in raw or "\n" in raw or "\r" in raw:
        raise PolicyError("Invalid file path")
    path = Path(raw)
    if ".." in path.parts:
        raise PolicyError("Parent traversal is forbidden: {}".format(raw))
    root = Path(cwd).resolve()
    candidate = path if path.is_absolute() else root / path
    try:
        candidate.relative_to(root)
    except ValueError:
        raise PolicyError("Path escapes cwd: {}".format(raw))
    cursor = candidate
    while cursor != root:
        if cursor.is_symlink() or (os.name == "nt" and cursor.exists() and
                getattr(cursor.lstat(), "st_file_attributes", 0) & 0x400):
            raise PolicyError("Symlink path is forbidden: {}".format(raw))
        cursor = cursor.parent
    return candidate


def patch_paths(command):
    lines = command.splitlines()
    if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise PolicyError("Invalid apply_patch envelope")
    paths = []
    active = None
    moved = False
    body_seen = False
    for line in lines[1:-1]:
        match = re.fullmatch(r"\*\*\* (Add|Update|Delete) File: (.+)", line)
        if match:
            active = match.group(1)
            moved = False
            body_seen = False
            paths.append((match.group(2), active))
        elif line.startswith("*** Move to: "):
            if active != "Update" or moved or body_seen:
                raise PolicyError("Move header must directly follow an Update header")
            paths.append((line[len("*** Move to: "):], "Move"))
            moved = True
        elif line.startswith("***") and line != "*** End of File":
            raise PolicyError("Unknown patch header")
        elif active is None or active == "Delete":
            raise PolicyError("Unexpected patch content")
        elif active == "Add" and not line.startswith("+"):
            raise PolicyError("Invalid Add patch content")
        elif active == "Update" and not (line.startswith(("+", "-", " ", "@@")) or line == "*** End of File"):
            raise PolicyError("Invalid Update patch content")
        else:
            body_seen = True
    if not paths:
        raise PolicyError("Patch has no file operations")
    return paths


def changed_paths(event):
    data = event["tool_input"]
    if event["tool_name"] == "apply_patch":
        return [(safe_path(raw, event["cwd"]), kind) for raw, kind in patch_paths(data["command"])]
    return [(safe_path(data["file_path"], event["cwd"]), "Update")]


def same_identity(left, right):
    try:
        return left.samefile(right)
    except (OSError, ValueError):
        return False


def within_namespace(path, root):
    candidate = tuple(part.casefold() for part in path.parts)
    protected = tuple(part.casefold() for part in root.parts)
    if candidate[:len(protected)] == protected:
        return True
    return any(same_identity(ancestor, root) for ancestor in (path,) + tuple(path.parents))


def sensitive(path, cwd):
    parts = tuple(part.casefold() for part in path.parts)
    name = path.name.casefold()
    if name == ".env" or name.startswith(".env.") and name not in (".env.example", ".env.sample", ".env.template"):
        return True
    if name in ("auth.json", "credentials", "credentials.json", "id_rsa", "id_ed25519"):
        return True
    if any(part in (".ssh", ".aws", ".gnupg") for part in parts):
        return True
    for index, namespace in enumerate(parts):
        if namespace != ".codex":
            continue
        rest = parts[index + 1:]
        if rest and (rest[0] in ("hooks", "hooks.json", "config.toml", "agents.md") or rest[:2] == ("workflow", "mike")):
            return True
    deployed = Path(__file__).resolve().parent
    protected_roots = [deployed]
    protected_files = list(deployed.glob("*.py"))
    if deployed.parent.name.casefold() == "mike" and deployed.parent.parent.name.casefold() == "workflow":
        home = deployed.parents[2]
        protected_roots.append(home / "workflow" / "mike")
        protected_files.extend(home / filename for filename in ("AGENTS.md", "hooks.json", "config.toml"))
    if any(within_namespace(path, root) for root in protected_roots):
        return True
    if any(tuple(part.casefold() for part in path.parts) == tuple(part.casefold() for part in protected.parts) or same_identity(path, protected) for protected in protected_files):
        return True
    # An ordinary-looking hardlink to an existing sensitive file shares its policy.
    root = Path(cwd).resolve()
    for folder in (root, root / ".codex", root / ".aws", root / ".ssh"):
        if not folder.is_dir():
            continue
        for existing in folder.iterdir():
            folded = existing.name.casefold()
            if (folded in ("auth.json", "credentials", "credentials.json", "id_rsa", "id_ed25519") or folded == ".env" or folded.startswith(".env.") and folded not in (".env.example", ".env.sample", ".env.template")) and same_identity(path, existing):
                return True
    return False
