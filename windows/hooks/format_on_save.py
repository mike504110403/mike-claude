#!/usr/bin/env python3
"""PostToolUse hook（Edit|Write）：存檔自動 format。.go 跑 gofmt，前端檔案跑專案內 prettier。"""
import json
import os
import shutil
import subprocess
import sys

PRETTIER_EXTS = {".js", ".jsx", ".ts", ".tsx", ".json", ".css", ".scss", ".html", ".md", ".yaml", ".yml"}


def main():
    try:
        data = json.load(sys.stdin)
        path = (data.get("tool_input") or {}).get("file_path") or ""
        if not path or not os.path.isfile(path):
            return
        ext = os.path.splitext(path)[1].lower()

        # 用 shutil.which 的完整路徑：Windows 上 prettier/npx 是 .cmd shim，裸名稱 subprocess 叫不起來
        gofmt, prettier, npx = shutil.which("gofmt"), shutil.which("prettier"), shutil.which("npx")
        if ext == ".go" and gofmt:
            subprocess.run([gofmt, "-w", path], capture_output=True, timeout=30)
        elif ext in PRETTIER_EXTS:
            if prettier:
                subprocess.run([prettier, "--write", path], capture_output=True, timeout=60)
            elif npx:
                # 只用專案內已安裝的 prettier（--no-install），專案沒裝就靜默跳過
                subprocess.run(
                    [npx, "--no-install", "prettier", "--write", path],
                    capture_output=True, timeout=60,
                    cwd=os.path.dirname(path) or ".",
                )
    except Exception:
        pass


if __name__ == "__main__":
    main()
