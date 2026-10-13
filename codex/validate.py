#!/usr/bin/env python3
"""Compile in memory and validate this package's intentionally limited asset schema."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate():
    required = [ROOT / "assets" / "AGENTS.md", ROOT / "install.py", ROOT / "README.md", ROOT / "tests" / "test_workflow.py"]
    required += [ROOT / "assets" / "skills" / name / "SKILL.md" for name in ("quick", "solo", "feature", "bug", "mega", "feature-flow", "verify", "review-chain", "brief", "wip", "ship")]
    required += [ROOT / "assets" / "agents" / (name + ".toml") for name in ("code-reviewer", "security-reviewer", "db-reviewer", "worker", "explorer")]
    required += [ROOT / "assets" / "hooks" / name for name in ("common.py", "guard.py", "format_changed.py")]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise ValueError("Missing required assets: " + ", ".join(missing))
    count = 0
    for path in ROOT.rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
        count += 1
    for path in ROOT.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    for path in (ROOT / "assets" / "skills").glob("*/SKILL.md"):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"---\nname: ([a-z0-9-]+)\ndescription: ([^\n]+)\n---\n", text)
        if not match or match[1] != path.parent.name:
            raise ValueError("Invalid skill frontmatter: {}".format(path))
        for reference in re.findall(r"\]\(([^)]+)\)", text):
            if not reference.startswith("https://") and not (path.parent / reference).is_file():
                raise ValueError("Missing reference: {}".format(reference))
    # Python 3.9 has no tomllib: validate only our deliberately small TOML schema.
    for path in (ROOT / "assets" / "agents").glob("*.toml"):
        text = path.read_text(encoding="utf-8")
        pattern = r'name = "([a-z0-9-]+)"\ndescription = "([^"\n]+)"\n(?:sandbox_mode = "(read-only)"\n)?developer_instructions = """\n([^"\x00]+)\n"""\n'
        match = re.fullmatch(pattern, text)
        if not match or match[1] != path.stem or path.stem != "worker" and match[3] != "read-only":
            raise ValueError("Invalid native agent schema: {}".format(path))
        try:
            import tomllib
        except ImportError:
            pass  # The fixed schema above is sufficient and rejects unknown keys.
        else:
            tomllib.loads(text)
    print("VALID: {} Python sources compiled in memory; skills, native agent TOML and references validated".format(count))


if __name__ == "__main__":
    try:
        validate()
    except (ValueError, OSError, SyntaxError) as exc:
        print("Validation failed: {}".format(exc), file=sys.stderr)
        sys.exit(1)
