#!/usr/bin/env python3
"""PreToolUse hook（Bash）：硬擋危險命令、git push 強制詢問、nginx/migration 強制詢問。"""
import json
import re
import sys


def respond(decision, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = (data.get("tool_input") or {}).get("command") or ""

    # 硬擋：rm 帶有 r+f 組合旗標（rm -rf / -fr / -r -f ...）
    if re.search(r"\brm\s+(-\w*r\w*\s+)*-\w*f", cmd) and re.search(r"\brm\s+(-\w*\s+)*-\w*r", cmd):
        respond("deny", "硬擋：rm -rf 被全域規則禁止。請改用精確路徑逐一刪除，或請 Mike 手動執行。")
    if re.search(r"\brm\s+-\w*(rf|fr)\w*\b", cmd):
        respond("deny", "硬擋：rm -rf 被全域規則禁止。請改用精確路徑逐一刪除，或請 Mike 手動執行。")

    # 硬擋：force push
    if re.search(r"\bgit\s+push\b", cmd) and re.search(r"(\s--force(-with-lease)?\b|\s-f\b)", cmd):
        respond("deny", "硬擋：force push 被全域規則禁止。")

    # 硬擋：git add . / -A / --all
    if re.search(r"\bgit\s+add\s+(\.(\s|$)|-A\b|--all\b)", cmd):
        respond("deny", "硬擋：git add . / -A 被禁止，請逐一指定要加入的檔案。")

    # 硬擋：強制刪分支 / 強制移除 worktree（/feature-flow：清理只用 -d / remove）
    if re.search(r"\bgit\s+branch\s+(-\w+\s+)*-D\b", cmd):
        respond("deny", "硬擋：git branch -D 被禁止——分支未完全合併就先查明差在哪些 commit，清理只用 -d（/feature-flow）。")
    if re.search(r"\bgit\s+worktree\s+remove\b", cmd) and re.search(r"(\s--force\b|\s-f\b)", cmd):
        respond("deny", "硬擋：git worktree remove --force 被禁止——先查明未 commit 改動是什麼再處置（/feature-flow）。")

    # 強制詢問：覆蓋工作區未 commit 改動（退件教訓：曾洗掉工人未 commit 的修正）
    if re.search(r"\bgit\s+checkout\s+--\s", cmd):
        respond("ask", "警示：git checkout -- 會覆蓋未 commit 改動（變異還原請改用 cp 備份）。確定要丟棄？")
    if re.search(r"\bgit\s+restore\b", cmd) and not re.search(r"--staged\b", cmd):
        respond("ask", "警示：git restore 會覆蓋未 commit 改動。確定要丟棄？")

    # 強制詢問：git push（Push 閘門）
    if re.search(r"\bgit\s+push\b", cmd):
        respond("ask", "Push 閘門：git push 需要 Mike 明確確認才能執行。")

    # 硬擋：git clean 帶清除旗標（會洗掉未 commit / untracked 改動，含工人未回報的修正）
    if re.search(r"\bgit\s+clean\b", cmd) and re.search(r"\s-\w*[fdxX]", cmd):
        respond("deny", "硬擋：git clean -f/-d/-x 會洗掉未 commit 與 untracked 改動。先 git status 查明，逐一處置。")

    # 硬擋：git stash 變更操作（stash 堆疊跨 worktree 共用；乾淨樹上 push 是 no-op、pop 會彈出別人的 stash——2026-08-12/08-19 三起）
    if re.search(r"\bgit\s+(-C\s+\S+\s+)?stash\b", cmd) and not re.search(r"\bstash\s+(list|show)\b", cmd):
        respond("deny", "硬擋：git stash 變更操作被禁止（堆疊跨 worktree 共用，pop 會彈出別人的 WIP）。暫存改動用 cp 備份；取舊版用 git show <ref>:<path>；baseline 比對用 git diff <ref>。")

    # 硬擋：裸 npx（無 node_modules 時靜默抓 registry 新版產出假結果——/vue-dev 禁令）
    if re.search(r"(^|[;&|]\s*)npx\s", cmd):
        respond("deny", "硬擋：裸 npx 被禁止——沒裝依賴時會靜默抓 registry 新版產出假結果。改用 pnpm exec <tool> 或 ./node_modules/.bin/<tool>（先確認依賴已依 lock 檔安裝）。")

    # 強制詢問：git reset --hard（丟棄工作區與 index）
    if re.search(r"\bgit\s+reset\s+(-\w+\s+)*--hard\b", cmd):
        respond("ask", "警示：git reset --hard 會丟棄未 commit 改動。確定？")

    # 強制詢問：遞迴刪除（rm -r 不帶 -f 也要問）與 find -delete
    if re.search(r"\brm\s+(-\w*\s+)*-\w*r", cmd):
        respond("ask", "警示：遞迴刪除。目標路徑確認過了嗎？")
    if re.search(r"\bfind\b.*\s-delete\b", cmd):
        respond("ask", "警示：find -delete 批次刪除。先跑一次不帶 -delete 確認清單。")

    # 強制詢問：名稱疑似含 commit/push/部署的 script（hook 看不進 script 內容）
    if re.search(r"\b(npm|pnpm|yarn)\s+run\s+(commit|push|deploy|release|publish)\b", cmd) or \
       re.search(r"\bmake\s+(deploy|release|publish|push)\b", cmd):
        respond("ask", "警示：此 script 名稱疑似含 commit/push/部署動作，hook 看不進內容。先讀 script 確認實際做什麼。")

    # 強制詢問：nginx / 執行 migration
    if re.search(r"\bnginx\b", cmd, re.IGNORECASE):
        respond("ask", "全域規則：nginx 相關操作需 Mike 確認。")
    if re.search(r"\b(migrate|alembic|flyway|goose)\b", cmd, re.IGNORECASE):
        respond("ask", "全域規則：DB migration 相關操作需 Mike 確認。")

    sys.exit(0)


if __name__ == "__main__":
    main()
