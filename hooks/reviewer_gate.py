#!/usr/bin/env python3
"""PreToolUse hook（matcher Agent|Task）：派 code-reviewer／security-reviewer／db-reviewer 前，
要求該 worktree 3 小時內跑過 `diff-surface --repo <worktree> --base <base> --record`，讓 reviewer 組合由 diff 決定。

放行條件（reviewer 類 subagent_type 才檢查，其他一律放行；subagent_type 轉小寫、取最後一個 `:` 之後再比對）：
  1. state 目錄（${DIFF_SURFACE_STATE:-~/.claude/state/diff-surface}）下有一筆有效紀錄：time 距今 ≤ 3 小時
     （未來至多 5 分鐘視為時鐘誤差），紀錄的 repo 路徑完整出現在 tool_input.prompt，
     且 `git -C <repo> rev-parse HEAD` 仍等於紀錄的 checkout_head（記錄當下的 HEAD；紀錄的 head 是被審的
     hash，可以是歷史 commit，不拿來比。checkout_head 為 null 則跳過此檢查；缺此欄的舊格式紀錄跳過並在
     stderr 記一行；git 失敗或逾時 2 秒視為符合並在 stderr 記一行）。
  2. 或 prompt 含字面「diff-surface: N/A（非 git）」（非 git 專案的出口，stderr 記一行）。
無符合紀錄就輸出 permissionDecision=deny；紀錄存在但 HEAD 已變時，reason 要求重跑 --record。

路徑比對：repo 前不得緊接 [A-Za-z0-9_.-/]，後不得緊接 [A-Za-z0-9_.-]，也不得接「/」加該類字元
（上層 repo 的紀錄不放行其下的路徑）；中文字、空白、標點緊貼路徑都算分隔。

無效紀錄（不是一般檔案：目錄、符號連結、FIFO；不可讀；超過 64KB；JSON 壞或過深；缺欄位；repo 不是絕對路徑
或是 /；time 解析失敗或無時區）略過並在 stderr 記一行，結果由其餘紀錄決定。

本 hook 刻意偏離 repo guard 慣例（bash_guard／file_guard 的例外與壞 payload 轉 ask）：這是流程輔助閘門，
對手模型是「大腦忘了跑 diff-surface」而非惡意繞過，所以 payload 缺 subagent_type 與任何未預期例外
一律 exit 0、stdout 空、stderr 印訊息，不卡派工。

紀錄的寫入端與欄位定義見 bin/diff-surface 檔頭（--record）。

payload 假設（欄位名未經 live 驗證，由大腦註冊後實測）：stdin 為 JSON，tool_input.subagent_type 與
tool_input.prompt 是字串；Agent 與 Task 兩種 tool_name 同樣處理。

已知限制：
  - SendMessage 續審既有 reviewer 不經 Agent 工具，不受本閘門約束。
  - 全 repo 總審（/mvp 畢業）沒有獨立出口：以空樹當 base（`git hash-object -t tree /dev/null`）跑
    diff-surface --record 即可產生紀錄。
  - 閘門只驗「有跑過 diff-surface 並寫明 worktree 路徑」，不驗 reviewer 組合是否照紀錄派。
  - 紀錄 checkout_head 與目前 HEAD 相同時，--record 之後才改的未 commit 內容不會使紀錄失效。
Exit：永遠 0。
"""
import datetime
import json
import os
import re
import stat
import subprocess
import sys
from typing import NamedTuple

REVIEWER_TYPES = {"code-reviewer", "security-reviewer", "db-reviewer"}
DEFAULT_STATE_DIR = os.path.join("~", ".claude", "state", "diff-surface")
MAX_AGE = datetime.timedelta(hours=3)
MAX_FUTURE_SKEW = datetime.timedelta(minutes=5)
MAX_RECORD_CHARS = 65536
GIT_TIMEOUT_SECONDS = 2
NOT_GIT_MARKER = "diff-surface: N/A（非 git）"
DENY_REASON = ("派 reviewer 前先對該 worktree 跑 `diff-surface --repo <worktree> --base <base> --record`，"
               "並在 reviewer prompt 單獨寫出 worktree 根路徑（realpath，路徑前後以空白或標點分隔），引用其下檔案不算")
STALE_HEAD_REASON = "HEAD 已變，請重跑 diff-surface --record"


class ReviewerRequest(NamedTuple):
    subagent_type: str
    prompt: str


def warn(message):
    print(f"reviewer_gate: {message}", file=sys.stderr)


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))


def state_dir():
    return os.path.expanduser(os.environ.get("DIFF_SURFACE_STATE") or DEFAULT_STATE_DIR)


def is_fresh(recorded_at, now):
    return -MAX_FUTURE_SKEW <= now - recorded_at <= MAX_AGE


def parse_record(data):
    if not isinstance(data, dict):
        raise ValueError("紀錄不是物件")
    repo = data.get("repo")
    if not isinstance(repo, str) or not os.path.isabs(repo) or repo == "/" or "\x00" in repo:
        raise ValueError("repo 不是有效的絕對路徑")
    if data.get("checkout_head") is not None and not isinstance(data["checkout_head"], str):
        raise ValueError("checkout_head 不是字串或 null")
    if not isinstance(data.get("time"), str):
        raise ValueError("缺 time 欄位")
    recorded_at = datetime.datetime.fromisoformat(data["time"])
    if recorded_at.tzinfo is None:
        raise ValueError("time 無時區")
    return data, recorded_at


def read_record(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, encoding="utf-8") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            raise ValueError("不是一般檔案")
        text = f.read(MAX_RECORD_CHARS + 1)
    if len(text) > MAX_RECORD_CHARS:
        raise ValueError("超過 64KB")
    return parse_record(json.loads(text))


def fresh_records(directory, now):
    try:
        names = sorted(os.listdir(directory))
    except FileNotFoundError:
        return []
    records = []
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            record, recorded_at = read_record(os.path.join(directory, name))
        except (OSError, ValueError, RecursionError) as e:
            warn(f"略過無效紀錄 {name}：{type(e).__name__}: {e}")
            continue
        if is_fresh(recorded_at, now):
            records.append(record)
    return records


def mentions_path(prompt, repo):
    return re.search(rf"(?<![A-Za-z0-9_.\-/]){re.escape(repo)}(?![A-Za-z0-9_.\-]|/[A-Za-z0-9_.\-])",
                     prompt) is not None


def head_matches(record):
    if "checkout_head" not in record:
        warn(f"紀錄缺 checkout_head 欄（舊格式），跳過 HEAD 檢查：{record['repo']}")
        return True
    recorded = record["checkout_head"]
    if recorded is None:
        return True
    try:
        proc = subprocess.run(["git", "-C", record["repo"], "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as e:
        warn(f"無法取得 {record['repo']} 的 HEAD（{type(e).__name__}），視為符合")
        return True
    if proc.returncode != 0:
        warn(f"git rev-parse HEAD 失敗於 {record['repo']}，視為符合：{proc.stderr.strip()}")
        return True
    return proc.stdout.strip() == recorded


def deny_reason(prompt, now):
    matched = [r for r in fresh_records(state_dir(), now) if mentions_path(prompt, r["repo"])]
    if not matched:
        return DENY_REASON
    return None if any(head_matches(r) for r in matched) else STALE_HEAD_REASON


def reviewer_request(payload):
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    subagent_type = tool_input.get("subagent_type") if isinstance(tool_input, dict) else None
    if not isinstance(subagent_type, str):
        warn("payload 缺 subagent_type（tool_input 不是 dict 或欄位缺失），放行")
        return None
    prompt = tool_input.get("prompt")
    return ReviewerRequest(subagent_type.strip().lower().rsplit(":", 1)[-1],
                           prompt if isinstance(prompt, str) else "")


def run():
    request = reviewer_request(json.load(sys.stdin))
    if request is None or request.subagent_type not in REVIEWER_TYPES:
        return
    prompt = request.prompt
    if NOT_GIT_MARKER in prompt:
        warn(f"prompt 含「{NOT_GIT_MARKER}」，放行")
        return
    reason = deny_reason(prompt, datetime.datetime.now(datetime.timezone.utc))
    if reason:
        deny(reason)


def main():
    try:
        run()
    except Exception as e:
        warn(f"未預期例外，放行：{type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
