#!/usr/bin/env python3
"""Compile in memory and validate this package's intentionally limited asset schema."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def validate():
    coverage = json.loads((ROOT / "migration.json").read_text(encoding="utf-8"))
    if coverage.get("schema_version") != 1 or not isinstance(coverage.get("skills"), list):
        raise ValueError("Invalid migration coverage schema")
    skill_names = [entry["name"] for entry in coverage["skills"]]
    agent_names = coverage["agents"]
    if len(skill_names) != coverage.get("source_skill_count") or len(set(skill_names)) != len(skill_names):
        raise ValueError("Invalid migration skill count or duplicate names")
    if any(not re.fullmatch(r"[a-z0-9-]+", name) for name in skill_names + agent_names):
        raise ValueError("Invalid migration asset name")
    if any(entry.get("mode") not in ("ported", "native-adapted") for entry in coverage["skills"]):
        raise ValueError("Invalid migration mode")
    required = [ROOT / "assets" / "AGENTS.md", ROOT / "install.py", ROOT / "README.md", ROOT / "tests" / "test_workflow.py"]
    required += [ROOT / "assets" / "skills" / name / "SKILL.md" for name in skill_names]
    required += [ROOT / "assets" / "agents" / (name + ".toml") for name in agent_names]
    required += [ROOT / "assets" / "hooks" / name for name in ("common.py", "guard.py", "format_changed.py")]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise ValueError("Missing required assets: " + ", ".join(missing))
    if set(skill_names) != {path.parent.name for path in (ROOT / "assets" / "skills").glob("*/SKILL.md")}:
        raise ValueError("Skill inventory differs from migration coverage")
    if set(agent_names) != {path.stem for path in (ROOT / "assets" / "agents").glob("*.toml")}:
        raise ValueError("Agent inventory differs from migration coverage")
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
    for path in (ROOT / "assets").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if any(legacy in text for legacy in ("/Users/mike/", "~/.claude/", "TaskStop", "SendMessage", "CMUX_BUNDLED_CLI_PATH", "claude-fable")):
            raise ValueError("Nonportable Claude/device dependency in {}".format(path))
        for reference in re.findall(r"\]\(([^)]+)\)", text):
            if reference.startswith(("https://", "http://", "#")):
                continue
            target = (path.parent / reference.split("#", 1)[0]).resolve()
            if ROOT.joinpath("assets").resolve() not in target.parents or not target.is_file():
                raise ValueError("Missing or escaping reference: {}".format(reference))
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
    print("VALID: {} Python sources compiled in memory; {} skills, {} native agents and references validated".format(count, len(skill_names), len(agent_names)))


if __name__ == "__main__":
    try:
        validate()
    except (ValueError, OSError, SyntaxError, KeyError, TypeError) as exc:
        print("Validation failed: {}".format(exc), file=sys.stderr)
        sys.exit(1)
