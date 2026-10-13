"""Format only existing changed files using already installed local tools."""
import json
import shutil
import subprocess
import sys
import os
from pathlib import Path
from common import PolicyError, changed_paths, read_event, safe_path, sensitive


PRETTIER_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".vue", ".json", ".css", ".scss", ".md", ".html", ".yaml", ".yml"}


def main():
    try:
        event = read_event(sys.stdin, "PostToolUse")
        if event["tool_name"] == "Bash":
            raise PolicyError("Formatter expects apply_patch/Edit/Write")
        root = Path(event["cwd"]).resolve()
        paths = sorted({path for path, kind in changed_paths(event) if kind != "Delete" and path.exists()})
        messages = []
        for path in paths:
            if not path.is_file() or sensitive(path, event["cwd"]):
                raise PolicyError("Refusing to format unsafe file: {}".format(path))
            if path.suffix == ".go":
                binary = shutil.which("gofmt")
                args = [binary, "-w", str(path)] if binary else None
            elif path.suffix in PRETTIER_SUFFIXES:
                if os.name == "nt":
                    # Run the local package's JS entry through Node; never execute
                    # a .cmd shim or search a global/downloaded prettier.
                    package = root / "node_modules" / "prettier"
                    metadata = package / "package.json"
                    node = shutil.which("node")
                    args = None
                    if metadata.is_file():
                        metadata.resolve().relative_to(root)
                        value = json.loads(metadata.read_text(encoding="utf-8"))
                        entry = value.get("bin")
                        entry = entry.get("prettier") if isinstance(entry, dict) else entry
                        if not isinstance(entry, str) or not entry:
                            raise PolicyError("Local prettier has no valid bin entry")
                        binary = (package / entry).resolve()
                        binary.relative_to(root)
                        if binary.is_file() and node:
                            args = [node, str(binary), "--write", str(path)]
                else:
                    binary = root / "node_modules" / ".bin" / "prettier"
                    resolved = binary.resolve()
                    try:
                        resolved.relative_to(root)
                    except ValueError:
                        raise PolicyError("Formatter symlink escapes cwd")
                    args = [str(binary), "--write", str(path)] if binary.is_file() else None
            else:
                continue
            if args is None:
                messages.append("Formatter unavailable; unchanged: {}".format(path))
                continue
            result = subprocess.run(args, cwd=str(root), text=True, capture_output=True, timeout=60)
            if result.returncode:
                raise PolicyError("Formatter failed ({}) for {}: {}".format(result.returncode, path, (result.stderr or result.stdout).strip()))
            messages.append("Formatted {}".format(path))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(messages)}}))
        return 0
    except (PolicyError, OSError, ValueError, subprocess.SubprocessError) as exc:
        reason = "Formatting incomplete: {}".format(exc)
        print(json.dumps({"decision": "block", "reason": reason, "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": reason}}))
        print(reason, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
