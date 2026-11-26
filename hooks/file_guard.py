#!/usr/bin/env python3
"""PreToolUse hook（Edit|Write）：改到系統 nginx 設定路徑、或寫入 ~/.claude/checks/ 才強制詢問。
repo 內的 migration、nginx 設定編輯不問——這類改動的把關在實際執行（bash_guard）與 push 閘門（bin/gate-evidence）。
~/.claude/checks/ 是 write_checks hook 的設定目錄，寫進去等於新增一個每次 Edit／Write 都會自動執行的指令。"""
import json
import os
import re
import sys

# 系統 nginx 路徑清單：編輯這些路徑才問，repo 內的 nginx 設定不問
SYSTEM_NGINX_PREFIXES = ("/etc/nginx/", "/etc/nginx.conf", "/etc/nginx-", "/usr/local/etc/nginx/",
                         "/opt/homebrew/etc/nginx/", "/private/etc/nginx/", "/System/Volumes/Data/private/etc/nginx/",
                         "/usr/local/nginx/", "/usr/local/openresty/", "/www/server/nginx/")


def ask(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    data = json.load(sys.stdin)  # 壞 payload 一路 raise，由 __main__ 轉 ask
    path = os.path.normpath(data["tool_input"]["file_path"])
    path = re.sub(r"^/+", "/", path).lower()  # normpath 保留開頭的 //
    prefixes = tuple(p.lower() for p in SYSTEM_NGINX_PREFIXES)

    if path.startswith(prefixes) or "sites-enabled" in path or "sites-available" in path:
        ask("全域規則：系統 nginx 設定的修改需 Mike 確認。")

    if under_checks_dir(data["tool_input"]["file_path"]):
        ask("寫入 checks 設定＝新增自動執行入口，需 Mike 確認")

    sys.exit(0)


def checks_roots():
    roots = [os.path.expanduser("~/.claude/checks")]
    if os.environ.get("WRITE_CHECKS_DIR"):
        roots.append(os.path.expanduser(os.environ["WRITE_CHECKS_DIR"]))
    return [os.path.abspath(root) for root in roots]


def existing_ancestors(path):
    while True:
        if os.path.exists(path):
            yield path
        parent = os.path.dirname(path)
        if parent == path:
            return
        path = parent


def same_location(path, root):
    try:
        return os.path.samefile(path, root)
    except OSError:
        return False


def textually_under(path, root):
    candidates = {os.path.normpath(path).casefold(), os.path.realpath(path).casefold()}
    bases = {os.path.normpath(root).casefold(), os.path.realpath(root).casefold()}
    return any(c == b or c.startswith(b + os.sep) for c in candidates for b in bases)


def under_checks_dir(raw_path):
    target = os.path.abspath(os.path.expanduser(raw_path))
    roots = checks_roots()
    if any(textually_under(target, root) for root in roots):
        return True
    resolved = os.path.realpath(target)
    if any(textually_under(resolved, root) for root in roots):
        return True
    existing_roots = [root for root in roots if os.path.exists(root)]
    return any(same_location(ancestor, root) for path in (target, resolved)
               for ancestor in existing_ancestors(path) for root in existing_roots)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # hook 崩潰等於放行，一律轉 ask
        ask(f"file_guard 無法判定（{type(e).__name__}），請人工確認。")
