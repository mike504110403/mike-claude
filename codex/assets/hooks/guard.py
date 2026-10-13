"""Finite direct-command guard; native sandbox remains the security boundary."""
import json
import re
import shlex
import sys
import os
from pathlib import Path
from common import PolicyError, changed_paths, read_event, sensitive


def shell_boundaries(command):
    """Preserve quoted newlines; drop continuations; expose real command boundaries."""
    result = []
    quote = None
    index = 0
    while index < len(command):
        char = command[index]
        if os.name != "nt" and char == "\\" and quote != "'" and index + 1 < len(command):
            following = command[index + 1]
            if following != "\n":
                result.extend((char, following))
            index += 2
            continue
        if quote is None and char == "#" and (index == 0 or command[index - 1].isspace() or command[index - 1] in ";&|()"):
            while index < len(command) and command[index] != "\n":
                index += 1
            continue
        if char in ("'", '\"'):
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        result.append(";" if char == "\n" and quote is None else char)
        index += 1
    return "".join(result)


def command_segments(command):
    if os.name == "nt" and "`" in command:
        raise PolicyError("PowerShell backtick expansion requires native review")
    lexer = shlex.shlex(shell_boundaries(command), posix=os.name != "nt", punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    current = []
    try:
        for token in lexer:
            if token and all(c in ";&|()" for c in token):
                if current:
                    yield current
                    current = []
            else:
                current.append(token.strip("\"'") if os.name == "nt" else token)
        if current:
            yield current
    except ValueError as exc:
        raise PolicyError("Unparseable shell command: {}".format(exc))


def clean_dry_run(args):
    index = 0
    dry_run = False
    while index < len(args):
        option = args[index]
        if option == "--":
            break
        if option == "--dry-run":
            dry_run = True
        elif option in ("-e", "--exclude"):
            index += 1  # An exclude pattern may itself be spelled -n.
        elif option.startswith("--exclude="):
            pass
        elif option.startswith("-") and not option.startswith("--"):
            for position, flag in enumerate(option[1:], 1):
                if flag == "e":
                    if position == len(option) - 1:
                        index += 1
                    break  # Remaining characters belong to the exclude value.
                if flag == "n":
                    dry_run = True
        index += 1
    return dry_run


def prohibited(tokens):
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return None
    executable = Path(tokens[0]).name
    if os.name == "nt":
        executable = executable.lower()
        for suffix in (".exe", ".cmd", ".bat", ".ps1"):
            if executable.endswith(suffix):
                executable = executable[:-len(suffix)]
                break
    args = tokens[1:]
    if os.name == "nt" and executable in ("remove-item", "ri", "del", "erase", "rd", "rmdir", "rm"):
        options = {arg.lower() for arg in args}
        if any(arg.startswith("-r") or arg == "/s" for arg in options) and any(arg.startswith("-f") or arg == "/q" for arg in options):
            return "Direct recursive forced deletion is forbidden"
    if executable == "npx":
        return "npx is forbidden; use an installed project binary or the lockfile's package manager"
    if executable == "rm":
        flags = []
        for item in args:
            if item == "--":
                break
            if item.startswith("-"):
                flags.append(item)
        recursive = any(x == "--recursive" or x.startswith("-") and not x.startswith("--") and "r" in x.lower() for x in flags)
        force = any(x == "--force" or x.startswith("-") and not x.startswith("--") and "f" in x for x in flags)
        if recursive and force:
            return "Direct recursive forced deletion is forbidden"
    if executable != "git":
        return None
    # Git global options before the subcommand, including value-bearing options.
    index = 0
    while index < len(args) and args[index].startswith("-"):
        option = args[index]
        if option in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env"):
            index += 2
        else:
            index += 1
    if index >= len(args):
        return None
    action, rest = args[index], args[index + 1:]
    if action == "stash" and (not rest or rest[0] not in ("list", "show")):
        return "Stash mutations are forbidden: the stack is shared across worktrees; use a scoped backup"
    if action == "push" and any(x.startswith(("--force", "--mirror")) or x.startswith("-") and not x.startswith("--") and "f" in x or x.startswith("+") for x in rest):
        return "Force/mirror push is forbidden"
    if action == "clean" and not clean_dry_run(rest):
        return "Non-dry-run git clean is forbidden (repository config may disable requireForce)"
    delete_branch = any(x == "--delete" or x.startswith("-") and not x.startswith("--") and "d" in x for x in rest)
    force_branch = any(x == "--force" or x.startswith("-") and not x.startswith("--") and "f" in x for x in rest)
    if action == "branch" and (any(x.startswith("-") and not x.startswith("--") and "D" in x for x in rest) or delete_branch and force_branch):
        return "Forced branch deletion is forbidden"
    if action == "worktree" and rest and rest[0] == "remove" and any(x == "--force" or x.startswith("-") and not x.startswith("--") and "f" in x for x in rest[1:]):
        return "Forced worktree removal is forbidden"
    if action == "add" and any(x in (".", "./", "--all") or x.startswith("-") and not x.startswith("--") and "A" in x for x in rest):
        return "Stage explicitly named paths instead of git add . or --all"
    return None


def main():
    try:
        event = read_event(sys.stdin, "PreToolUse")
        if event["tool_name"] == "Bash":
            for tokens in command_segments(event["tool_input"]["command"]):
                reason = prohibited(tokens)
                if reason:
                    raise PolicyError(reason)
        else:
            for path, _ in changed_paths(event):
                if sensitive(path, event["cwd"]):
                    raise PolicyError("Sensitive/policy file protected: {}".format(path))
        # No allow decision: leave native approvals and other hooks in control.
        print(json.dumps({}))
    except (PolicyError, OSError) as exc:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": str(exc)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
