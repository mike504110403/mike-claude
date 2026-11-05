#!/usr/bin/env python3
"""PreToolUse hook（Edit|Write）：只有改到系統 nginx 設定路徑才強制詢問。
repo 內的 migration、nginx 設定編輯不問——這類改動的把關在實際執行（bash_guard）與 push 閘門（bin/gate-evidence）。"""
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

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # hook 崩潰等於放行，一律轉 ask
        ask(f"file_guard 無法判定（{type(e).__name__}），請人工確認。")
