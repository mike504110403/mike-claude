#!/bin/bash
# test_push_plan.sh — bin/push-plan 的 seam 測試（只經 CLI：stdout + exit code）。
# 腳本路徑由 PUSH_PLAN 決定（預設 ../push-plan）。fixture：本機 bare repo 當 remote，A＝主 checkout，B＝另一個 session。
set -u

PUSH_PLAN="${PUSH_PLAN:-$(cd "$(dirname "$0")/.." && pwd)/push-plan}"

PASS_COUNT=0
FAIL_COUNT=0
TMP="$(mktemp -d "${TMPDIR:-/tmp}/push-plan-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

ok() { PASS_COUNT=$((PASS_COUNT + 1)); echo "[PASS] $1"; }
bad() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "[FAIL] $1"; }

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then ok "$desc"; else bad "$desc (expected=$expected actual=$actual)"; fi
}
assert_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if printf '%s\n' "$haystack" | grep -qF -- "$needle"; then ok "$desc"; else bad "$desc (找不到: $needle)"; fi
}
assert_not_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if printf '%s\n' "$haystack" | grep -qF -- "$needle"; then bad "$desc (不該出現: $needle)"; else ok "$desc"; fi
}
exists() {
  local path="$1"
  if [ -e "$path" ]; then echo yes; else echo no; fi
}

export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.com GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.com

commit() {
  local repo="$1" message="$2"
  printf '%s\n' "$message" >> "$repo/file"
  git -C "$repo" add file
  git -C "$repo" commit -q -m "$message"
}

new_fixture() {
  local name="$1"
  local root="$TMP/$name"
  REMOTE="$root/remote.git"
  A="$root/A"
  B="$root/B"
  mkdir -p "$root"
  export PUSH_PLAN_STATE="$root/state"
  git init -q --bare -b dev "$REMOTE"
  git clone -q "$REMOTE" "$A" 2>/dev/null
  git -C "$A" checkout -q -b dev
  commit "$A" base
  git -C "$A" push -q origin dev
  git clone -q "$REMOTE" "$B" 2>/dev/null
  git -C "$B" checkout -q dev
}

snapshot_file() { echo "$PUSH_PLAN_STATE/$(basename "$A")-dev.json"; }

physical_path() {
  local dir="$1"
  (cd "$dir" && pwd -P)
}

set_snapshot_field() {
  local file="$1" key="$2" value="$3"
  python3 -c 'import json,sys; f,k,v=sys.argv[1:]; d=json.load(open(f)); d[k]=v; json.dump(d,open(f,"w"))' "$file" "$key" "$value"
}

drop_snapshot_field() {
  local file="$1" key="$2"
  python3 -c 'import json,sys; f,k=sys.argv[1:]; d=json.load(open(f)); del d[k]; json.dump(d,open(f,"w"))' "$file" "$key"
}

# ---------- 1. snapshot 列出 2 顆、寫快照、建議指令 ----------
new_fixture c1
commit "$A" one
commit "$A" two
OUT="$("$PUSH_PLAN" snapshot --repo "$A" --no-fetch 2>&1)"
assert_eq "1 snapshot exit 0" 0 $?
HEAD_A="$(git -C "$A" rev-parse dev)"
assert_contains "1 列出 one" "$OUT" "one"
assert_contains "1 列出 two" "$OUT" "two"
assert_eq "1 快照檔存在" yes "$(exists "$(snapshot_file)")"
LAST="$(printf '%s\n' "$OUT" | tail -n 1)"
assert_contains "1 建議指令含 local_head:dev" "$LAST" "$HEAD_A:dev"
assert_contains "1 建議指令 -C 主 checkout 實體路徑" "$LAST" "-C $(physical_path "$A") "
assert_contains "1 建議指令含 push origin" "$LAST" "push origin"

# ---------- 2. 快照後 A 的 dev 再多一顆 ----------
new_fixture c2
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
commit "$A" three
NEW_HASH="$(git -C "$A" rev-parse dev)"
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "2 本地新增 check exit 1" 1 $?
assert_contains "2 輸出標新增本地那顆" "$OUT" "新增 $NEW_HASH three"

# ---------- 3. 快照後 B 推新 commit、A fetch ----------
new_fixture c3
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
commit "$B" other-session
git -C "$B" push -q origin dev
git -C "$A" fetch -q origin dev
B_HASH="$(git -C "$B" rev-parse HEAD)"
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "3 remote 前進 check exit 1" 1 $?
assert_contains "3 輸出標 remote 新增 B 那顆" "$OUT" "remote 新增 $B_HASH other-session"

# ---------- 3b. B 推新 commit、A 不手動 fetch，check 自己 fetch ----------
new_fixture c3b
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
commit "$B" other-session
git -C "$B" push -q origin dev
B_HASH="$(git -C "$B" rev-parse HEAD)"
OUT="$("$PUSH_PLAN" check --repo "$A" 2>&1)"
assert_eq "3b 不帶 --no-fetch check exit 1" 1 $?
assert_contains "3b 輸出標 remote 新增 B 那顆" "$OUT" "remote 新增 $B_HASH other-session"

# ---------- 4. 未變動 → check exit 0 ----------
new_fixture c4
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
"$PUSH_PLAN" check --repo "$A" --no-fetch >/dev/null 2>&1
assert_eq "4 未變動 check exit 0" 0 $?

# ---------- 5. 無待推 commit → exit 3 且不寫快照 ----------
new_fixture c5
OUT="$("$PUSH_PLAN" snapshot --repo "$A" --no-fetch 2>&1)"
assert_eq "5 無待推 exit 3" 3 $?
assert_contains "5 印無待推 commit" "$OUT" "無待推 commit"
assert_eq "5 不產生快照檔" no "$(exists "$(snapshot_file)")"

# ---------- 6. linked worktree 內呼叫，檔名用主 checkout basename ----------
new_fixture c6
commit "$A" one
WT="$TMP/c6/linked-wt"
git -C "$A" worktree add -q -b side "$WT" >/dev/null 2>&1
OUT="$("$PUSH_PLAN" snapshot --repo "$WT" --no-fetch 2>&1)"
assert_eq "6 worktree snapshot exit 0" 0 $?
assert_contains "6 建議指令用主 checkout 實體路徑" "$(printf '%s\n' "$OUT" | tail -n 1)" "-C $(physical_path "$A") "
assert_eq "6 快照檔名用主 checkout basename" yes "$(exists "$(snapshot_file)")"
assert_eq "6 沒有 worktree basename 的快照" no "$(exists "$PUSH_PLAN_STATE/linked-wt-dev.json")"
"$PUSH_PLAN" check --repo "$A" --no-fetch >/dev/null 2>&1
assert_eq "6 從主 checkout check 讀得到同一檔 exit 0" 0 $?

# ---------- 7. 無快照 → check exit 2 ----------
new_fixture c7
commit "$A" one
"$PUSH_PLAN" check --repo "$A" --no-fetch >/dev/null 2>&1
assert_eq "7 無快照 check exit 2" 2 $?

# ---------- 8. snapshot 後 remote 不見 → check 不帶 --no-fetch exit 2 ----------
new_fixture c8
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
mv "$REMOTE" "$REMOTE.moved"
"$PUSH_PLAN" check --repo "$A" >/dev/null 2>&1
assert_eq "8 fetch 失敗 check exit 2" 2 $?

# ---------- 9. snapshot 後 A reset --hard HEAD~1 → 消失 ----------
new_fixture c9
commit "$A" one
commit "$A" two
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
GONE_HASH="$(git -C "$A" rev-parse HEAD)"
git -C "$A" reset -q --hard HEAD~1
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "9 commit 消失 check exit 1" 1 $?
assert_contains "9 輸出含 消失 <hash> <subject>" "$OUT" "消失 $GONE_HASH two"

# ---------- 10. --repo 非 git 目錄 → exit 2 ----------
mkdir -p "$TMP/not-git"
"$PUSH_PLAN" snapshot --repo "$TMP/not-git" --no-fetch >/dev/null 2>&1
assert_eq "10 非 git 目錄 snapshot exit 2" 2 $?
"$PUSH_PLAN" check --repo "$TMP/not-git" --no-fetch >/dev/null 2>&1
assert_eq "10 非 git 目錄 check exit 2" 2 $?

# ---------- 11. 快照 repo 欄位與主 checkout 不一致 → exit 2 ----------
new_fixture c11
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
set_snapshot_field "$(snapshot_file)" repo /elsewhere/A
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "11 repo 欄位不一致 check exit 2" 2 $?
assert_contains "11 輸出含快照的 repo" "$OUT" "/elsewhere/A"
assert_contains "11 輸出含現在的主 checkout" "$OUT" "$(physical_path "$A")"

# ---------- 12. 同名 tag dev 不影響待推清單 ----------
new_fixture c12
commit "$A" one
git -C "$A" tag dev origin/dev
OUT="$("$PUSH_PLAN" snapshot --repo "$A" --no-fetch 2>&1)"
assert_eq "12 同名 tag snapshot exit 0" 0 $?
assert_contains "12 仍列出待推 commit" "$OUT" "one"

# ---------- 13. snapshot 不帶 --no-fetch 自己 fetch ----------
new_fixture c13
commit "$A" one
commit "$B" other-session
git -C "$B" push -q origin dev
B_HASH="$(git -C "$B" rev-parse HEAD)"
OUT="$("$PUSH_PLAN" snapshot --repo "$A" 2>&1)"
assert_eq "13 snapshot 不帶 --no-fetch exit 0" 0 $?
assert_contains "13 列出待推 commit" "$OUT" "one"
assert_contains "13 快照的 remote_head 是 fetch 後的 B 那顆" "$(cat "$(snapshot_file)")" "$B_HASH"

# ---------- 14. 快照缺必要欄位 → exit 2 ----------
new_fixture c14
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
drop_snapshot_field "$(snapshot_file)" commits
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "14 缺欄位 check exit 2" 2 $?
assert_contains "14 輸出指出缺 commits" "$OUT" "快照格式錯誤：缺 commits"

# ---------- 15. 快照 branch 欄位與指定分支不一致 → exit 2 ----------
new_fixture c15
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
set_snapshot_field "$(snapshot_file)" branch other
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "15 branch 欄位不一致 check exit 2" 2 $?
assert_contains "15 輸出指出 branch 不一致" "$OUT" "快照 branch 與指定分支不一致"

# ---------- 16. 快照不是合法 JSON → exit 2 並印例外型別 ----------
new_fixture c16
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
echo 'not json' > "$(snapshot_file)"
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "16 壞 JSON check exit 2" 2 $?
assert_contains "16 輸出含例外型別名稱" "$OUT" "JSONDecodeError"

# ---------- 17. A 的 commit 被別的 clone 推上 remote → 已上 remote ----------
new_fixture c17
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
ONE_HASH="$(git -C "$A" rev-parse HEAD)"
git -C "$B" pull -q --ff-only "$A" dev
git -C "$B" push -q origin dev
git -C "$A" fetch -q origin dev
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "17 已上 remote check exit 1" 1 $?
assert_contains "17 輸出標已上 remote" "$OUT" "已上 remote $ONE_HASH one"
assert_not_contains "17 不印消失" "$OUT" "消失"
assert_not_contains "17 不在 remote 新增重複列" "$OUT" "remote 新增 $ONE_HASH"

# ---------- 18. check --src 必須等於快照 local_head ----------
new_fixture c18
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
A_HEAD="$(git -C "$A" rev-parse HEAD)"
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch --src "$A_HEAD" 2>&1)"
assert_eq "18 src 等於快照 local_head → exit 0" 0 $?
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch --src dev 2>&1)"
assert_eq "18 src 給分支名、解析後相同 → exit 0" 0 $?
git -C "$A" branch side HEAD~1
SIDE_HASH="$(git -C "$A" rev-parse side)"
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch --src side 2>&1)"
assert_eq "18 src 與快照 local_head 不同 → exit 1" 1 $?
assert_contains "18 輸出快照 local_head" "$OUT" "$A_HEAD"
assert_contains "18 輸出本次 src" "$OUT" "$SIDE_HASH"
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch --src no-such-rev 2>&1)"
assert_eq "18 src 解析失敗 → exit 2" 2 $?

# ---------- 19. check --remote 必須等於快照 remote ----------
new_fixture c19
commit "$A" one
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch --remote origin 2>&1)"
assert_eq "19 remote 相同 → exit 0" 0 $?
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch --remote other 2>&1)"
assert_eq "19 remote 不同 → exit 1" 1 $?
assert_contains "19 輸出兩邊 remote" "$OUT" "快照=origin 本次=other"

# ---------- 20. check 一致時印快照的待推 commit 清單 ----------
new_fixture c20
commit "$A" first-pending
commit "$A" second-pending
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "20 一致 exit 0" 0 $?
assert_contains "20 印出第一顆待推 commit" "$OUT" "$(git -C "$A" log -1 --format='%h %s' HEAD~1)"
assert_contains "20 印出第二顆待推 commit" "$OUT" "$(git -C "$A" log -1 --format='%h %s' HEAD)"

# ---------- 21. 主旨含 \r、U+2028 時清單仍是一顆一行 ----------
new_fixture c21
printf 'x\n' >> "$A/file"
git -C "$A" add file
git -C "$A" commit -q -m $'evil\rforged one'
printf 'y\n' >> "$A/file"
git -C "$A" add file
git -C "$A" commit -q -m $'evil forged two'
"$PUSH_PLAN" snapshot --repo "$A" --no-fetch >/dev/null 2>&1
OUT="$("$PUSH_PLAN" check --repo "$A" --no-fetch 2>&1)"
assert_eq "21 一致 exit 0" 0 $?
assert_contains "21 \\r 留在同一行" "$OUT" "$(git -C "$A" log -1 --format=%h HEAD~1) evil"$'\r'"forged one"
assert_contains "21 U+2028 留在同一行" "$OUT" "$(git -C "$A" log -1 --format=%h HEAD) evil"$' '"forged two"

# ---------- --help ----------
OUT="$("$PUSH_PLAN" --help 2>&1)"
assert_eq "help exit 0" 0 $?
assert_contains "help 印出 snapshot 用法" "$OUT" "snapshot"
assert_contains "help 印出 check 用法" "$OUT" "check"

echo "PASS=$PASS_COUNT FAIL=$FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ] || exit 1
