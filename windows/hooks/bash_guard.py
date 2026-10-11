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


DELETE_ALIASES = r"(?:remove-item|ri|rm|del|erase|rd|rmdir)"
# 指令名前可為行首、分隔符、空白或引號（powershell -Command "Remove-Item ..."、cmd /c "rd ..."）
PS_DELETE_CMD = re.compile(r"(?:^|[;&|({\"'`]\s*|\s)" + DELETE_ALIASES + r"(?=\s)", re.IGNORECASE)


def windows_recursive_delete(cmd):
    """PowerShell 參數可縮寫且不分大小寫（-r / -rec / -Recurse、-fo / -Force）；cmd 用 /s /q（可連寫 /s/q）。
    回傳 "deny"（遞迴＋強制）、"ask"（只遞迴）或 None。"""
    verdict = None
    for m in PS_DELETE_CMD.finditer(cmd):
        seg = re.split(r"[;|&\n]", cmd[m.end():], maxsplit=1)[0]
        ps_flags = [f.lower() for f in re.findall(r"(?:^|\s)-([A-Za-z]+)", seg)]
        cmd_flags = [c.lower() for grp in re.findall(r"(?:^|\s)((?:/[A-Za-z])+)(?=[\s\"']|$)", seg) for c in grp[1::2]]
        recurse = "s" in cmd_flags or any("recurse".startswith(f) for f in ps_flags)
        force = "q" in cmd_flags or any(len(f) >= 2 and "force".startswith(f) for f in ps_flags)
        if recurse and force:
            return "deny"
        if recurse:
            verdict = "ask"
    # 管線批次刪除（gci -Recurse | Remove-Item、| ForEach-Object { Remove-Item ... }），等同 find -delete
    # 刪除指令只在「指令位置」才算：緊接 | 或 {，或經 xargs / ForEach-Object / % 轉呼
    if re.search(r"\s-r\w*\b[^;\n]*[|{]\s*(?:(?:xargs(?:\s+-\S+)*|foreach-object|foreach|%)\s*\{?\s*)?"
                 + DELETE_ALIASES + r"(?=\s|$|\})", cmd, re.IGNORECASE):
        verdict = verdict or "ask"
    return verdict


# (?![.\w])：HKU.cache 這類檔名不算
HIVE = r"(HKLM|HKEY_LOCAL_MACHINE|HKCR|HKEY_CLASSES_ROOT|HKU|HKEY_USERS)(?![.\w])"
SYSTEM_ADMIN = re.compile("|".join([
    r"\bwinget(\.exe)?\s+(--?\S+\s+)*(install|add|uninstall|remove|rm|upgrade|update|import|repair|configure)\b",
    r"\bmsiexec\b",
    r"\bchoco(\.exe)?\s+(install|uninstall|upgrade)\b",
    r"\bSet-ExecutionPolicy\b(?![^;|&\n]*-Scope\s+Process\b)",
    r"\breg(\.exe)?\s+(add|delete|copy|restore|load|unload)\s+[\"']?" + HIVE,
    r"\breg(\.exe)?\s+import\b",
    r"\bregedit(\.exe)?\b",
    r"\bsc(\.exe)?\s+(config|create|delete|start|stop|pause|continue|failure|sdset|privs)\b",
    r"\b(Set|New|Remove|Start|Stop|Restart|Suspend)-Service\b",
    r"(?<![-\w])(spsv|sasv)\s",
    r"\bnet(\.exe)?\s+(stop|start|pause|continue)\b",
    r"\bnet(\.exe)?\s+(user|localgroup)\b[^;|&\n]*\s[/-]+(add|delete)\b",
    r"\bschtasks(\.exe)?\s+[/-]+(create|delete|change)\b",
    r"\b(Register|Unregister|Set)-ScheduledTask\b",
    r"\b(bcdedit|dism|netsh|takeown|icacls)(\.exe)?\b",
    r"\b(Set|Add|Remove)-MpPreference\b",
    r"\b(Enable|Disable)-WindowsOptionalFeature\b",
    r"\b(Add|Remove)-WindowsCapability\b",
    r"\b(shutdown(\.exe)?\s|Restart-Computer\b|Stop-Computer\b)",
    # machine 級環境變數（系統 PATH）
    r"\bsetx(\.exe)?\b[^;|&\n]*\s[/-]+M\b",
    r"SetEnvironmentVariable\b[^\n]*\bMachine\b",
    # 直接跑安裝檔（winget 沒有的套件）
    r"\.msi\b",
    r"\bStart-Process\b[^;|&\n]*\.exe\b",
    r"\.exe\b[^;|&\n]*\s[/-]{1,2}(quiet|qn|passive|VERYSILENT|SILENT|S)(?![\w/])",
    # 防火牆、本機帳號（cmd 版 netsh／net user 在上面）
    r"\b(New|Set|Remove|Enable|Disable|Rename|Copy)-NetFirewall\w+\b",
    r"\b(New|Set|Remove|Enable|Disable|Rename)-LocalUser\b",
    r"\b(Add|Remove)-LocalGroupMember\b",
    # 全機信任憑證
    r"\bcertutil(\.exe)?\b[^;|&\n]*[/-]+(addstore|delstore|importpfx)\b",
    r"\bImport-(Pfx)?Certificate\b[^\n]*LocalMachine",
]), re.IGNORECASE)

HIVE_RE = re.compile(HIVE, re.IGNORECASE)
REG_WRITE = re.compile(r"(?<![-\w])((Set|New|Remove|Rename|Copy|Move|Clear)-Item(Property)?|sp|si|ni|rp|ri)\s", re.IGNORECASE)
# 寫入動作（重導、PowerShell 寫檔 cmdlet、cp/mv/tee/sed -i/rm、Python open）
WRITE_VERB = re.compile(r"(?<![\d&])>(?!&|\s*(/dev/null|\$null|nul)\b)|\b(Add|Set|Clear)-Content\b|\bOut-File\b|\b(Copy|Move|Remove|New|Rename)-Item\b|"
                        r"(?<![-\w])(cp|mv|tee|rm|ri|del|sc|ac)\s|\bsed\s+(-\w+\s+)*-i|\bopen\(|\bwrite", re.IGNORECASE)
SYSTEM_DIR = re.compile(r"(?:[A-Za-z]:|/[a-z])[\\/]+(Windows|Program Files( \(x86\))?|ProgramData)\b", re.IGNORECASE)
# 唯一防線本身：settings.json 與 hooks/
GUARD_FILES = re.compile(r"\.claude[\\/]+(settings(\.local)?\.json|hooks[\\/])", re.IGNORECASE)

# 前面不能是 - 或字母數字：排除 docker run --rm、git-rm 這類
POSIX_RM_CMD = re.compile(r"(?<![-\w])rm(\.exe)?(?=\s)")


def posix_rm(cmd):
    """GNU rm 旗標：-r / -R / --recursive（長旗標可縮寫成唯一前綴），-f / --force；短旗標可合寫、可放在路徑後。
    短旗標只認 GNU rm 字母集 [dfiIrRv]，含其他字母的（PowerShell 的 -Force、-Path）不算；只比前綴，-rf$x 照算。
    回傳 "deny"（遞迴＋強制）、"ask"（只遞迴）或 None。"""
    verdict = None
    for m in POSIX_RM_CMD.finditer(cmd):
        seg = re.split(r"[;|&\n]", cmd[m.end():], maxsplit=1)[0]
        recurse = force = False
        for tok in seg.split():
            if tok == "--":
                break
            if tok.startswith("--"):
                name = tok[2:].split("=", 1)[0].lower()
                recurse = recurse or (name and "recursive".startswith(name))
                force = force or (name and "force".startswith(name))
            elif (fm := re.match(r"-([A-Za-z]+)", tok)) and set(fm.group(1)) <= set("dfiIrRv"):
                recurse = recurse or "r" in fm.group(1).lower()
                force = force or "f" in fm.group(1)
        if recurse and force:
            return "deny"
        if recurse:
            verdict = "ask"
    return verdict


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cmd = (data.get("tool_input") or {}).get("command") or ""
    # bash 反斜線續行接回同一行（rm x \⏎ -rf）
    cmd = re.sub(r"\\\r?\n", " ", cmd)

    # 硬擋：rm 帶有遞迴＋強制旗標（-rf / -fR / -r -f / --recursive --force ...）
    rm_del = posix_rm(cmd)
    if rm_del == "deny":
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

    # Windows（PC 版）：PowerShell Remove-Item 系與 cmd rd/del 的遞迴＋強制刪除
    ps_del = windows_recursive_delete(cmd)
    if ps_del == "deny":
        respond("deny", "硬擋：遞迴＋強制刪除（Remove-Item -Recurse -Force / rd /s /q）被全域規則禁止。請改用精確路徑逐一刪除，或請 Mike 手動執行。")
    # （ps_del == "ask" 在後面所有 deny 之後才判，不能讓詢問蓋掉 stash/clean/npx 的硬擋）

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
    if rm_del == "ask":
        respond("ask", "警示：遞迴刪除。目標路徑確認過了嗎？")
    if re.search(r"\bfind\b.*\s-delete\b", cmd):
        respond("ask", "警示：find -delete 批次刪除。先跑一次不帶 -delete 確認清單。")
    if ps_del == "ask":
        respond("ask", "警示：遞迴刪除（Remove-Item -Recurse / rd /s）。目標路徑確認過了嗎？")

    # 強制詢問：名稱疑似含 commit/push/部署的 script（hook 看不進 script 內容）
    if re.search(r"\b(npm|pnpm|yarn)\s+run\s+(commit|push|deploy|release|publish)\b", cmd) or \
       re.search(r"\bmake\s+(deploy|release|publish|push)\b", cmd):
        respond("ask", "警示：此 script 名稱疑似含 commit/push/部署動作，hook 看不進內容。先讀 script 確認實際做什麼。")

    # 強制詢問：系統權限動作（PC 上 CC 以管理員執行，沒有 UAC 把關，改由這裡在 CC 內確認——手機 Remote Control 可按）
    if SYSTEM_ADMIN.search(cmd) or (HIVE_RE.search(cmd) and REG_WRITE.search(cmd)) or \
       (SYSTEM_DIR.search(cmd) and WRITE_VERB.search(cmd)):
        respond("ask", "系統權限動作（CC 以管理員執行、無 UAC 把關）：安裝／移除軟體、改 HKLM 登錄、服務、排程工作、開機或防護設定。確認要執行？")

    # 強制詢問：改 hook 本身或 settings.json（agent 被擋後改防線繞過）
    if GUARD_FILES.search(cmd) and WRITE_VERB.search(cmd):
        respond("ask", "警示：要改 ~/.claude 的 settings.json 或 hooks（全域防線本身）。確認？")

    # 強制詢問：nginx / 執行 migration
    if re.search(r"\bnginx\b", cmd, re.IGNORECASE):
        respond("ask", "全域規則：nginx 相關操作需 Mike 確認。")
    if re.search(r"\b(migrate|alembic|flyway|goose)\b", cmd, re.IGNORECASE):
        respond("ask", "全域規則：DB migration 相關操作需 Mike 確認。")

    sys.exit(0)


if __name__ == "__main__":
    main()
