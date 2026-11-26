#!/bin/bash
# test_brief_lint.sh — bin/brief-lint 的 seam 測試（只經 CLI：stdout + exit code）。
# 腳本路徑由 BRIEF_LINT 決定（預設 ../brief-lint），讓 dogfood 能指向副本。
# 純 bash + coreutils + git + python3，各案共用一個 mktemp -d 的 fixture git repo。
set -u
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

BRIEF_LINT="${BRIEF_LINT:-$(cd "$(dirname "$0")/.." && pwd)/brief-lint}"

PASS_COUNT=0
FAIL_COUNT=0
TMP="$(mktemp -d "${TMPDIR:-/tmp}/brief-lint-test.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

ok() { PASS_COUNT=$((PASS_COUNT + 1)); echo "[PASS] $1"; }
bad() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "[FAIL] $1"; }

assert_eq() {
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected=$2 actual=$3)"; fi
}
assert_contains() {
  if printf '%s\n' "$2" | grep -qF -- "$3"; then ok "$1"; else bad "$1 (找不到: $3)"; fi
}
assert_not_contains() {
  if printf '%s\n' "$2" | grep -qF -- "$3"; then bad "$1 (不該出現: $3)"; else ok "$1"; fi
}
assert_line() { # 整行比對（grep -qxF）：cmds 段的 DENIED／UNLISTED／NOT_RUN／RUN 行用
  if printf '%s\n' "$2" | grep -qxF -- "$3"; then ok "$1"; else bad "$1 (沒有整行: $3)"; fi
}
assert_count() { # desc haystack needle expected_count
  local n
  n="$(printf '%s\n' "$2" | grep -cF -- "$3")"
  if [ "$n" = "$4" ]; then ok "$1"; else bad "$1 (出現 $n 次，預期 $4：$3)"; fi
}
exists() { if [ -e "$1" ]; then echo yes; else echo no; fi; }

# ---------- fixture repo ----------
REPO="$TMP/repo"
mkdir -p "$REPO/src" "$REPO/tests"
printf 'package foo\n\nfunc NewFoo() int {\n\treturn 1\n}\n' > "$REPO/src/foo.go"
printf 'package foo\n\nfunc TestFoo() {\n\t_ = NewFoo()\n}\n' > "$REPO/src/foo_test.go"
printf 'package foo\n\nfunc useBar() {\n\t_ = NewFoo()\n}\n' > "$REPO/src/bar.go"
printf 'package tests\n\nfunc helper() {\n\t_ = NewFoo()\n}\n' > "$REPO/tests/helper.go"
printf '# readme\nhello fixture\n' > "$REPO/README.md"
printf 'tracked\n' > "$REPO/f"
(
  cd "$REPO" && git init -q && git config user.email t@example.com && git config user.name t \
    && git add src tests README.md f && git commit -q -m init
) >/dev/null 2>&1

# 白名單內、可產生各種結果的 fixture 測試腳本（untracked，不影響 git grep 計數）
mkdir -p "$REPO/bin/tests" "$REPO/scripts" "$REPO/sub"
printf 'touch "$1"\n' > "$REPO/tests/test_touch.sh"
printf 'echo hello\n' > "$REPO/tests/test_ok.sh"
printf 'echo "$@"\n' > "$REPO/tests/test_echo.sh"
printf 'exit 1\n' > "$REPO/tests/test_fail.sh"
printf "echo '--- SKIP: TestX'\n" > "$REPO/tests/test_skip.sh"
printf 'sleep 5\n' > "$REPO/tests/test_sleep.sh"
printf 'touch x_ran\n' > "$REPO/bin/tests/test_x.sh"
printf 'touch deploy_marker\n' > "$REPO/scripts/deploy.sh"
printf 'x\n' > "$REPO/sub/f"
printf 'foo\n' > "$REPO/b.txt"

OUT=""
RC=0
lint() { # brief-file args...
  local b="$1"; shift
  OUT="$(python3 "$BRIEF_LINT" "$b" "$@" 2>&1)"
  RC=$?
}
mkbrief() { # name  (stdin = content)
  cat > "$TMP/$1.md"
}

# ---------- refs ----------
mkbrief refs <<'EOF'
# t
引用 src/foo.go:3 與重複的 src/foo.go:3，還有範圍 src/foo.go:1-4，
缺檔 nofile/x.go:1，越界 src/foo.go:99。
## 驗收標準
無
EOF
lint "$TMP/refs.md" --repo "$REPO"
assert_contains "refs: [refs] 標頭" "$OUT" "[refs]"
assert_contains "refs: OK 含該行內容" "$OUT" "OK src/foo.go:3 | func NewFoo() int {"
assert_contains "refs: 範圍型只印起始行" "$OUT" "OK src/foo.go:1-4 | package foo"
assert_contains "refs: MISSING_FILE" "$OUT" "MISSING_FILE nofile/x.go:1"
assert_contains "refs: LINE_OUT_OF_RANGE 帶行數" "$OUT" "LINE_OUT_OF_RANGE src/foo.go:99 (file has 5 lines)"
assert_count "refs: 同 ref 重複只報一次" "$OUT" "OK src/foo.go:3 |" 1
assert_contains "refs: summary problems=2" "$OUT" "summary: problems=2"
assert_eq "refs: 有 problem exit 1" 1 "$RC"

mkbrief refs_abs <<EOF
# t
絕對路徑 $REPO/README.md:2 與 URL https://example.com/a.md:3 不當檔案。
## 驗收標準
EOF
lint "$TMP/refs_abs.md" --repo "$REPO"
assert_contains "refs: 絕對路徑照用" "$OUT" "OK $REPO/README.md:2 | hello fixture"
assert_not_contains "refs: URL 不被當成檔案引用" "$OUT" "example.com"
assert_eq "refs: 全 OK exit 0" 0 "$RC"

# ---------- cmds ----------
mkbrief cmds_plain <<'EOF'
# t
## 驗收標準
- `bash tests/test_touch.sh ran_marker`
- `bash tests/test_ok.sh`
- `notacommand_xyz --foo`
EOF
lint "$TMP/cmds_plain.md" --repo "$REPO"
assert_line "cmds: 無 --run 印 NOT_RUN" "$OUT" "NOT_RUN bash tests/test_touch.sh ran_marker"
assert_not_contains "cmds: 非指令的 inline code 忽略" "$OUT" "notacommand_xyz"
assert_eq "cmds: 無 --run 真的沒執行" "no" "$(exists "$REPO/ran_marker")"
assert_eq "cmds: NOT_RUN 不算 problem exit 0" 0 "$RC"

mkbrief cmds_deny <<'EOF'
# t
## 驗收標準
- `rm marker`
- `git checkout -- f`
- `true && rm marker2`
- `git -C . push origin x`
- `bash migrate.sh`
- `bash tests/test_echo.sh hi`
EOF
: > "$REPO/marker"; : > "$REPO/marker2"; printf 'dirty\n' > "$REPO/f"
lint "$TMP/cmds_deny.md" --repo "$REPO" --run
assert_line "cmds: rm DENIED" "$OUT" "DENIED rm marker"
assert_line "cmds: git checkout DENIED" "$OUT" "DENIED git checkout -- f"
assert_line "cmds: 複合命令內的 rm DENIED" "$OUT" "DENIED true && rm marker2"
assert_line "cmds: git push DENIED" "$OUT" "DENIED git -C . push origin x"
assert_line "cmds: migrate DENIED" "$OUT" "DENIED bash migrate.sh"
assert_eq "cmds: DENIED 的 rm 真的沒跑 (marker 仍在)" "yes" "$(exists "$REPO/marker")"
assert_eq "cmds: 複合 rm 沒跑 (marker2 仍在)" "yes" "$(exists "$REPO/marker2")"
assert_eq "cmds: git checkout 沒跑 (f 仍是髒的)" "dirty" "$(cat "$REPO/f")"
assert_eq "cmds: f 仍是未 commit 的修改" " M f" "$(git -C "$REPO" status --porcelain f)"
assert_line "cmds: 同批非 deny 指令照跑" "$OUT" "RUN exit=0 bash tests/test_echo.sh hi"
assert_eq "cmds: DENIED 不算 problem exit 0" 0 "$RC"
printf 'tracked\n' > "$REPO/f"

mkbrief cmds_run <<'EOF'
# t
## 驗收標準
- `bash tests/test_ok.sh`
- `bash tests/test_fail.sh`
- `bash tests/test_skip.sh`
- `grep -rn zzznotthere src`
- `grep -rn NewFoo src`
- `FOO=1 bash tests/test_ok.sh`
- `bash tests/test_touch.sh ran_inside`
EOF
lint "$TMP/cmds_run.md" --repo "$REPO" --run
assert_line "cmds: 通過的指令 exit=0" "$OUT" "RUN exit=0 bash tests/test_ok.sh"
assert_contains "cmds: 輸出末行縮排" "$OUT" "  hello"
assert_line "cmds: exit 1 的腳本標 FAIL" "$OUT" "RUN exit=1 FAIL bash tests/test_fail.sh"
assert_contains "cmds: SKIP 旗標" "$OUT" "SKIP bash tests/test_skip.sh"
assert_contains "cmds: grep 零命中 ZERO_MATCH" "$OUT" "ZERO_MATCH grep -rn zzznotthere src"
assert_not_contains "cmds: 有命中的 grep 不標 ZERO_MATCH" "$OUT" "ZERO_MATCH grep -rn NewFoo"
assert_line "cmds: VAR=val 前綴照跑" "$OUT" "RUN exit=0 FOO=1 bash tests/test_ok.sh"
assert_eq "cmds: 在 --repo 下執行" "yes" "$(exists "$REPO/ran_inside")"
assert_contains "cmds: problems=3 (FAIL, SKIP, ZERO_MATCH)" "$OUT" "summary: problems=3"
assert_eq "cmds: 有 problem exit 1" 1 "$RC"

mkbrief cmds_ok <<'EOF'
# t
## 驗收標準
- `bash tests/test_ok.sh`
- `grep -rn NewFoo src`
EOF
lint "$TMP/cmds_ok.md" --repo "$REPO" --run
assert_contains "cmds: 全通過 problems=0" "$OUT" "summary: problems=0"
assert_eq "cmds: 全通過 exit 0" 0 "$RC"

mkbrief cmds_nosect <<'EOF'
# t
## 範圍
- `bash tests/test_touch.sh outside_scope`
## 驗收標準
- `bash tests/test_fail.sh`
## 紀律
- `bash tests/test_touch.sh outside_after`
EOF
lint "$TMP/cmds_nosect.md" --repo "$REPO" --run
assert_count "cmds: 只跑驗收標準節（exit 1 腳本只算一次）" "$OUT" "RUN exit=1 FAIL bash tests/test_fail.sh" 1
assert_eq "cmds: 範圍節的 inline code 沒被執行" "no" "$(exists "$REPO/outside_scope")"
assert_eq "cmds: 驗收標準之後的節沒被執行" "no" "$(exists "$REPO/outside_after")"

mkbrief cmds_timeout <<'EOF'
# t
## 驗收標準
- `bash tests/test_sleep.sh`
EOF
START=$SECONDS
lint "$TMP/cmds_timeout.md" --repo "$REPO" --run --timeout 1
ELAPSED=$((SECONDS - START))
assert_contains "cmds: 逾時標 TIMEOUT" "$OUT" "TIMEOUT bash tests/test_sleep.sh"
assert_eq "cmds: 逾時算 problem exit 1" 1 "$RC"
if [ "$ELAPSED" -lt 5 ]; then ok "cmds: 逾時有真的提早終止 (${ELAPSED}s)"; else bad "cmds: 逾時沒提早終止 (${ELAPSED}s)"; fi

# ---------- refs: host:port 與範圍越界 ----------
mkbrief refs_host <<'EOF'
# t
連 example.com:8080、api.example.org:443、127.0.0.1:3306、localhost:5432、
user@db.internal:22、dial(db.internal:5432)、https://example.com/a.md:3 都不是檔案。
範圍型迄超過檔尾 src/foo.go:3-99，括號內的真引用 (README.md:2) 仍要檢查。
## 驗收標準
EOF
lint "$TMP/refs_host.md" --repo "$REPO"
assert_not_contains "refs: host:port／IP／user@host／呼叫括號不報 MISSING_FILE" "$OUT" "MISSING_FILE"
assert_contains "refs: 範圍型迄超過檔尾 LINE_OUT_OF_RANGE" "$OUT" "LINE_OUT_OF_RANGE src/foo.go:3-99 (file has 5 lines)"
assert_contains "refs: 括號內真引用仍檢查" "$OUT" "OK README.md:2 | hello fixture"
assert_contains "refs: host 排除後 problems=1" "$OUT" "summary: problems=1"

# ---------- cmds: 佔位符 ----------
printf 'x\n' > "$REPO/wt"
mkbrief cmds_placeholder <<'EOF'
# t
## 驗收標準
- `cat <wt> > marker_ph`
- `python3 bin/brief-lint <brief> --repo <worktree> --run`
- `bash tests/test_echo.sh real`
EOF
lint "$TMP/cmds_placeholder.md" --repo "$REPO"
assert_line "cmds: 佔位符印 PLACEHOLDER (無 --run)" "$OUT" "PLACEHOLDER cat <wt> > marker_ph"
assert_line "cmds: 佔位符第二條 (無 --run)" "$OUT" "PLACEHOLDER python3 bin/brief-lint <brief> --repo <worktree> --run"
assert_line "cmds: 無佔位符的仍 NOT_RUN" "$OUT" "NOT_RUN bash tests/test_echo.sh real"
lint "$TMP/cmds_placeholder.md" --repo "$REPO" --run
assert_line "cmds: 佔位符印 PLACEHOLDER (--run)" "$OUT" "PLACEHOLDER cat <wt> > marker_ph"
assert_eq "cmds: 佔位符真的沒執行 (marker_ph 不存在)" "no" "$(exists "$REPO/marker_ph")"
assert_not_contains "cmds: 佔位符不產生假 FAIL" "$OUT" "FAIL"
assert_line "cmds: 非佔位符照跑" "$OUT" "RUN exit=0 bash tests/test_echo.sh real"
assert_contains "cmds: PLACEHOLDER 不算 problem" "$OUT" "summary: problems=0"
assert_eq "cmds: PLACEHOLDER exit 0" 0 "$RC"

# ---------- cmds: ZERO_MATCH 判準 ----------
printf 'hello\n' > "$REPO/a.txt"
mkbrief cmds_grep <<'EOF'
# t
## 驗收標準
- `grep nomatch a.txt | head -n 5`
- `grep -q hello a.txt`
- `grep -q nomatch a.txt`
- `grep -c nomatch a.txt | head -n 5`
- `grep -c hello a.txt`
- `grep -l hello a.txt`
- `grep hello a.txt`
EOF
lint "$TMP/cmds_grep.md" --repo "$REPO" --run
assert_line "grep: exit 0 但 stdout 空 → 只有 ZERO_MATCH (無 FAIL)" "$OUT" "RUN exit=0 ZERO_MATCH grep nomatch a.txt | head -n 5"
assert_line "grep: -q 命中無旗標" "$OUT" "RUN exit=0 grep -q hello a.txt"
assert_line "grep: -q 未命中 exit 1 只有 FAIL" "$OUT" "RUN exit=1 FAIL grep -q nomatch a.txt"
assert_line "grep: -c 全 0 → ZERO_MATCH" "$OUT" "RUN exit=0 ZERO_MATCH grep -c nomatch a.txt | head -n 5"
assert_line "grep: -c 有計數無旗標" "$OUT" "RUN exit=0 grep -c hello a.txt"
assert_line "grep: -l 命中無旗標" "$OUT" "RUN exit=0 grep -l hello a.txt"
assert_line "grep: 一般命中無旗標" "$OUT" "RUN exit=0 grep hello a.txt"
assert_contains "grep: problems=3" "$OUT" "summary: problems=3"

# ---------- cmds: deny 擴充 ----------
FAKEBIN="$TMP/fakebin"; export SHIM_MARK="$TMP/shimmarks"
mkdir -p "$FAKEBIN" "$SHIM_MARK"
for n in sudo kill pkill killall systemctl launchctl redis-cli nginx alembic flyway goose npx find xargs npm pnpm yarn make go pytest flutter dart cargo rg; do
  printf '#!/bin/sh\ntouch "$SHIM_MARK/$(basename "$0")"\n' > "$FAKEBIN/$n"
  chmod +x "$FAKEBIN/$n"
done
DENY_CMDS=(
  'sudo true' 'kill -0 999999' 'pkill nosuchproc' 'killall nosuchproc' 'systemctl status x'
  'launchctl list' 'redis-cli ping' 'nginx -t' 'alembic upgrade head' 'flyway info'
  'goose status' 'npx foo' 'find . -delete' 'xargs echo'
  'npm run deploy-prod' 'pnpm run push-images' 'yarn run release' 'make deploy'
  "bash -c 'touch bash_c_marker'" "sh -c 'touch sh_c_marker'" 'true && eval touch eval_marker'
  'git -C . checkout -- f' 'git diff --output=out_marker' 'rg x --pre cat .'
)
{ echo '# t'; echo '## 驗收標準'; for c in "${DENY_CMDS[@]}"; do echo "- \`$c\`"; done; echo '- `bash tests/test_echo.sh ok`'; } > "$TMP/cmds_deny2.md"
printf 'dirty2\n' > "$REPO/f"
PATH="$FAKEBIN:$PATH" lint "$TMP/cmds_deny2.md" --repo "$REPO" --run
for c in "${DENY_CMDS[@]}"; do
  assert_line "deny: DENIED $c" "$OUT" "DENIED $c"
done
assert_eq "deny: shim 一個都沒被執行" "0" "$(ls -A "$SHIM_MARK" | wc -l | tr -d ' ')"
assert_eq "deny: bash -c 沒跑" "no" "$(exists "$REPO/bash_c_marker")"
assert_eq "deny: sh -c 沒跑" "no" "$(exists "$REPO/sh_c_marker")"
assert_eq "deny: eval 沒跑" "no" "$(exists "$REPO/eval_marker")"
assert_eq "deny: git diff --output 沒寫檔" "no" "$(exists "$REPO/out_marker")"
assert_eq "deny: git -C . checkout -- f 沒跑 (f 仍是修改後內容)" "dirty2" "$(cat "$REPO/f")"
assert_eq "deny: f 仍是未 commit 的修改" " M f" "$(git -C "$REPO" status --porcelain f)"
assert_line "deny: 同批非 deny 照跑" "$OUT" "RUN exit=0 bash tests/test_echo.sh ok"
assert_eq "deny: 全 DENIED 不算 problem" 0 "$RC"
printf 'tracked\n' > "$REPO/f"

# ---------- cmds: 白名單 (UNLISTED) ----------
mkbrief cmds_allow <<'EOF'
# t
## 驗收標準
- `touch m1`
- `cd sub && touch m2`
- `cd sub && grep x f`
- `grep foo b.txt | wc -l`
- `id`
- `sed`
- `bash scripts/deploy.sh`
- `bash bin/tests/test_x.sh`
- `grep foo b.txt > out.txt`
- `grep foo b.txt & touch bg_marker`
- `grep foo $(touch sub_marker)`
- `grep foo b.txt 2>&1`
- `grep foo b.txt 2>/dev/null`
- `grep -E 'foo|bar' b.txt`
- `grep foo b.txt && cd sub`
EOF
lint "$TMP/cmds_allow.md" --repo "$REPO" --run
assert_line "allow: touch 是 UNLISTED" "$OUT" "UNLISTED touch m1"
assert_eq "allow: touch m1 真的沒跑" "no" "$(exists "$REPO/m1")"
assert_line "allow: cd && touch 是 UNLISTED" "$OUT" "UNLISTED cd sub && touch m2"
assert_eq "allow: cd sub && touch m2 沒跑 (sub)" "no" "$(exists "$REPO/sub/m2")"
assert_eq "allow: cd sub && touch m2 沒跑 (repo)" "no" "$(exists "$REPO/m2")"
assert_line "allow: cd && grep 會執行" "$OUT" "RUN exit=0 cd sub && grep x f"
assert_line "allow: pipeline grep | wc 會執行" "$OUT" "RUN exit=0 grep foo b.txt | wc -l"
assert_line "allow: id 單字片段 UNLISTED" "$OUT" "UNLISTED id"
assert_line "allow: sed 單字片段 UNLISTED" "$OUT" "UNLISTED sed"
assert_line "allow: bash scripts/deploy.sh UNLISTED" "$OUT" "UNLISTED bash scripts/deploy.sh"
assert_eq "allow: deploy.sh 沒跑" "no" "$(exists "$REPO/deploy_marker")"
assert_line "allow: bash bin/tests/test_x.sh 會執行" "$OUT" "RUN exit=0 bash bin/tests/test_x.sh"
assert_eq "allow: test_x.sh 真的跑了" "yes" "$(exists "$REPO/x_ran")"
assert_line "allow: 寫檔重導向 UNLISTED" "$OUT" "UNLISTED grep foo b.txt > out.txt"
assert_eq "allow: out.txt 沒產生" "no" "$(exists "$REPO/out.txt")"
assert_line "allow: 背景執行 UNLISTED" "$OUT" "UNLISTED grep foo b.txt & touch bg_marker"
assert_eq "allow: bg_marker 沒產生" "no" "$(exists "$REPO/bg_marker")"
assert_line "allow: 指令替換 UNLISTED" "$OUT" "UNLISTED grep foo \$(touch sub_marker)"
assert_eq "allow: sub_marker 沒產生" "no" "$(exists "$REPO/sub_marker")"
assert_line "allow: 2>&1 允許" "$OUT" "RUN exit=0 grep foo b.txt 2>&1"
assert_line "allow: 2>/dev/null 允許" "$OUT" "RUN exit=0 grep foo b.txt 2>/dev/null"
assert_line "allow: 引號內的 | 不切段" "$OUT" "RUN exit=0 grep -E 'foo|bar' b.txt"
assert_line "allow: 非開頭的 cd 段不允許" "$OUT" "UNLISTED grep foo b.txt && cd sub"
assert_contains "allow: 九條 UNLISTED 中七條指令形狀計 problem（id、sed 單 token 不計）" "$OUT" "summary: problems=7"
assert_eq "allow: exit 1" 1 "$RC"

lint "$TMP/cmds_allow.md" --repo "$REPO"
assert_line "allow: 無 --run 白名單外仍 UNLISTED" "$OUT" "UNLISTED touch m1"
assert_line "allow: 無 --run 白名單內 NOT_RUN" "$OUT" "NOT_RUN cd sub && grep x f"
assert_line "allow: 無 --run pipeline NOT_RUN" "$OUT" "NOT_RUN grep foo b.txt | wc -l"

ALLOWED_CMDS=(
  'go test ./...' 'go vet ./...' 'go build ./...' 'pnpm test' 'npm run typecheck' 'yarn run lint'
  'pnpm exec vue-tsc --noEmit' 'npm exec vitest run' 'python3 -m unittest discover' 'python3 -m pytest -q'
  'python3 -m py_compile x.py' 'pytest -q' 'flutter test' 'flutter analyze' 'dart test' 'dart analyze'
  'cargo test' 'cargo check' 'cargo build' 'make test' 'rg foo' 'git -C . log -1' 'git diff --stat'
  'git status --short' 'git show --stat HEAD' 'git ls-files' 'git rev-parse HEAD' 'git grep -n foo'
  'bash tests/test_a.sh' 'bash tests/x/test_b.sh' 'python3 bin/brief-lint x.md'
  'wc -l b.txt' 'head b.txt' 'tail b.txt' 'cat b.txt' 'ls' 'test -f b.txt' 'test -d sub'
  'FOO=1 grep foo b.txt'
  'FOO_TEST_DSN=x pytest -q' 'make test && git -C . log -1' 'make test | grep -C 2 x' 'grep -o foo b.txt' 'rg -o foo' 'ls -O'
)
NOT_ALLOWED_CMDS=(
  'go run main.go' 'npm install' 'pnpm run dev' 'make all' 'test -z x' 'git branch' 'git fetch'
  'touch x' 'cp a b' 'chmod 444 a' 'sleep 1' 'echo hi' 'bash scripts/run.sh' 'python3 x.py'
  'cat b.txt | tee out.txt' 'ls; touch x'
)
{ echo '# t'; echo '## 驗收標準'
  for c in "${ALLOWED_CMDS[@]}" "${NOT_ALLOWED_CMDS[@]}"; do echo "- \`$c\`"; done; } > "$TMP/cmds_allow2.md"
PATH="$FAKEBIN:$PATH" lint "$TMP/cmds_allow2.md" --repo "$REPO"
for c in "${ALLOWED_CMDS[@]}"; do
  assert_line "allow: 白名單內 NOT_RUN $c" "$OUT" "NOT_RUN $c"
done
for c in "${NOT_ALLOWED_CMDS[@]}"; do
  assert_line "allow: 白名單外 UNLISTED $c" "$OUT" "UNLISTED $c"
done

# ---------- cmds: 環境變數前綴 deny ----------
export SHIM_MARK="$TMP/shimmarks2"; mkdir -p "$SHIM_MARK"
printf 'touch "%s/bashenv_ran"\n' "$TMP" > "$TMP/bashenv.sh"
ENV_DENY_CMDS=(
  'GIT_SSH_COMMAND=x git log -1' "BASH_ENV=$TMP/bashenv.sh bash tests/test_ok.sh" 'ENV=x grep foo b.txt'
  'LD_PRELOAD=x grep foo b.txt' 'DYLD_INSERT_LIBRARIES=x grep foo b.txt' 'PYTHONSTARTUP=x python3 -m pytest'
  'PYTHONHOME=x pytest -q' 'PYTHONINSPECT=1 pytest -q' 'MY_CONFIG_PATH=x grep foo b.txt'
  'GOFLAGS=-x go test ./...' 'MAKEFLAGS=x make test' 'CARGO_HOME=x cargo test' 'RUSTC_WRAPPER=x cargo check'
  'RUSTFLAGS=x cargo build' 'PAGER=x git log' 'GIT_PAGER=x git log' 'EDITOR=x git log' 'NODE_OPTIONS=x npm test'
  'npm_config_prefix=x npm test' 'PATH=/tmp:$PATH grep foo b.txt' 'SHELL=x grep foo b.txt'
  'PROMPT_COMMAND=x grep foo b.txt' 'PS4=x grep foo b.txt' 'true && GIT_DIR=x git log' 'FOO=1 BASH_ENV=x grep foo b.txt'
  'NPM_CONFIG_PREFIX=x npm test' 'PYTEST_ADDOPTS=x pytest -q' 'MAKEFILES=x make test' 'Pager=x git log'
  "cd sub && FOO='a;b' BASH_ENV=x bash tests/t.sh"
)
{ echo '# t'; echo '## 驗收標準'; for c in "${ENV_DENY_CMDS[@]}"; do echo "- \`$c\`"; done
  echo '- `XXX_TEST_DSN=postgres://x go test ./...`'; echo '- `FOO=1 grep foo b.txt`'; } > "$TMP/cmds_envdeny.md"
PATH="$FAKEBIN:$PATH" lint "$TMP/cmds_envdeny.md" --repo "$REPO" --run
for c in "${ENV_DENY_CMDS[@]}"; do
  assert_line "env: DENIED $c" "$OUT" "DENIED $c"
done
assert_eq "env: BASH_ENV 沒被載入 (bashenv_ran 不存在)" "no" "$(exists "$TMP/bashenv_ran")"
assert_eq "env: 被 DENIED 的 shim 都沒跑，只有放行的 go test 跑了" "go" "$(ls -A "$SHIM_MARK" | tr '\n' ' ' | sed 's/ *$//')"
assert_line "env: 其他變數名放行 (XXX_TEST_DSN) 且照跑" "$OUT" "RUN exit=0 XXX_TEST_DSN=postgres://x go test ./..."
assert_line "env: FOO=1 放行" "$OUT" "RUN exit=0 FOO=1 grep foo b.txt"

# ---------- cmds: 危險旗標 deny ----------
export SHIM_MARK="$TMP/shimmarks3"; mkdir -p "$SHIM_MARK"
FLAG_DENY_CMDS=(
  'go vet -vettool=/tmp/x ./...' 'go test -exec /tmp/x ./...' 'go build -toolexec /tmp/x ./...'
  'git grep -O less foo' 'git grep -Oless foo' 'git grep --open-files-in-pager=less foo'
  'make -f evil.mk test' 'make --file=evil.mk test' 'make --makefile=evil.mk test' 'make -C sub test'
  'make --directory=sub test' 'make test CC=evil' 'make test X=1'
  'pytest -p evilplugin' 'python3 -m pytest -p evilplugin' 'cargo test --config build.rustc-wrapper=x'
  "rg --pre-glob '*.x' foo"
  'go test --exec /tmp/x ./...' 'git grep -nO less foo' 'git -C . grep -O less foo'
  'go test -c ./...' 'go build -o out ./...' 'go test -o x ./...' 'go test -coverprofile=c.out ./...'
  'go build --o out ./...' 'go test --coverprofile=c.out ./...' 'go test --c ./...'
  'go test -cpuprofile=c ./...' 'go test -memprofile=m ./...' 'go test -blockprofile=b ./...'
  'go test -mutexprofile=m ./...' 'pnpm exec vitest run --outputFile=x' 'pnpm exec vitest run --output-file x'
  'pytest --junitxml=x.xml' 'pytest --basetemp=x' 'pytest -o cache_dir=x'
  'pnpm exec eslint --fix src' 'npm run lint -- --fix' 'pnpm exec vitest run -u' 'pnpm test -- --update'
  'pnpm exec vitest run --updateSnapshot'
)
{ echo '# t'; echo '## 驗收標準'; for c in "${FLAG_DENY_CMDS[@]}"; do echo "- \`$c\`"; done; } > "$TMP/cmds_flagdeny.md"
PATH="$FAKEBIN:$PATH" lint "$TMP/cmds_flagdeny.md" --repo "$REPO" --run
for c in "${FLAG_DENY_CMDS[@]}"; do
  assert_line "flag: DENIED $c" "$OUT" "DENIED $c"
done
assert_eq "flag: shim 仍沒被執行" "0" "$(ls -A "$SHIM_MARK" | wc -l | tr -d ' ')"

# ---------- cmds: bash／python 路徑 ----------
mkdir -p "$TMP/abs/tests" "$TMP/x/tests"
printf 'touch "%s/abs_ran"\n' "$TMP" > "$TMP/abs/tests/a.sh"
printf 'touch "%s/up_ran"\n' "$TMP" > "$TMP/x/tests/a.sh"
printf 'touch latest_ran\n' > "$REPO/scripts/latest_deploy.sh"
printf 'touch tx_ran\n' > "$REPO/tests/test_x.sh"
printf 'touch run_ran\n' > "$REPO/bin/tests/run.sh"
printf 'touch smoke_ran\n' > "$REPO/scripts/test_smoke.sh"
BASH_UNLISTED=(
  'bash scripts/latest_deploy.sh' 'bash ../x/tests/a.sh' "bash $TMP/abs/tests/a.sh" 'bash ~/tests/a.sh'
  'bash tests/test_$X.sh' 'bash -x tests/test_x.sh' 'bash tests/test_x.sh/../../scripts/latest_deploy.sh'
  'python3 evil/bin/brief-lint x.md' 'python3 bin/brief-lint-evil x.md' 'python3 x/brief-lint x.md'
)
BASH_OK=( 'bash tests/test_x.sh' 'bash bin/tests/run.sh' 'bash scripts/test_smoke.sh' )
{ echo '# t'; echo '## 驗收標準'; for c in "${BASH_UNLISTED[@]}" "${BASH_OK[@]}"; do echo "- \`$c\`"; done; } > "$TMP/cmds_bashpath.md"
lint "$TMP/cmds_bashpath.md" --repo "$REPO" --run
for c in "${BASH_UNLISTED[@]}"; do
  assert_line "bashpath: UNLISTED $c" "$OUT" "UNLISTED $c"
done
for c in "${BASH_OK[@]}"; do
  assert_line "bashpath: 照常執行 $c" "$OUT" "RUN exit=0 $c"
done
assert_eq "bashpath: latest_deploy.sh 沒跑" "no" "$(exists "$REPO/latest_ran")"
assert_eq "bashpath: ../x/tests/a.sh 沒跑" "no" "$(exists "$TMP/up_ran")"
assert_eq "bashpath: 絕對路徑腳本沒跑" "no" "$(exists "$TMP/abs_ran")"
assert_eq "bashpath: tests/test_x.sh 跑了" "yes" "$(exists "$REPO/tx_ran")"
assert_eq "bashpath: bin/tests/run.sh 跑了" "yes" "$(exists "$REPO/run_ran")"
assert_eq "bashpath: scripts/test_smoke.sh 跑了" "yes" "$(exists "$REPO/smoke_ran")"
mkbrief cmds_pybl <<'EOF'
# t
## 驗收標準
- `python3 bin/brief-lint x.md`
- `python3 ~/.claude/bin/brief-lint x.md`
- `python3 /Users/mike/.claude/bin/brief-lint x.md`
EOF
lint "$TMP/cmds_pybl.md" --repo "$REPO"
assert_line "pybl: bin/brief-lint 白名單內" "$OUT" "NOT_RUN python3 bin/brief-lint x.md"
assert_line "pybl: ~/.claude/bin/brief-lint 白名單內" "$OUT" "NOT_RUN python3 ~/.claude/bin/brief-lint x.md"
assert_line "pybl: 絕對路徑 brief-lint 白名單內" "$OUT" "NOT_RUN python3 /Users/mike/.claude/bin/brief-lint x.md"

# ---------- cmds: ZERO_MATCH 判定範圍 ----------
mkbrief cmds_zscope <<'EOF'
# t
## 驗收標準
- `git -C . grep nomatch`
- `cd sub && grep nomatch f`
- `FOO=1 grep nomatch f`
- `grep foo b.txt | wc -l`
EOF
lint "$TMP/cmds_zscope.md" --repo "$REPO" --run
assert_contains "zscope: git -C . grep 帶 ZERO_MATCH" "$OUT" "ZERO_MATCH git -C . grep nomatch"
assert_contains "zscope: cd 段後的 grep 帶 ZERO_MATCH" "$OUT" "ZERO_MATCH cd sub && grep nomatch f"
assert_contains "zscope: 環境變數前綴後的 grep 帶 ZERO_MATCH" "$OUT" "ZERO_MATCH FOO=1 grep nomatch f"
assert_line "zscope: grep | wc -l 管線維持不判 ZERO_MATCH" "$OUT" "RUN exit=0 grep foo b.txt | wc -l"

# ---------- cmds: 引號感知的 ZERO_MATCH ----------
mkbrief cmds_zquote <<'EOF'
# t
## 驗收標準
- `grep 'zz;yy' b.txt | head -n 5`
- `grep -n "a && b" b.txt | head -n 5`
- `grep -E 'fo|zz' -q b.txt`
EOF
lint "$TMP/cmds_zquote.md" --repo "$REPO" --run
assert_line "zquote: 引號內 ; 不切段，仍判 ZERO_MATCH" "$OUT" "RUN exit=0 ZERO_MATCH grep 'zz;yy' b.txt | head -n 5"
assert_line "zquote: 引號內 && 不切段，仍判 ZERO_MATCH" "$OUT" 'RUN exit=0 ZERO_MATCH grep -n "a && b" b.txt | head -n 5'
assert_line "zquote: 引號內 | 不切段，-q 命中不誤報" "$OUT" "RUN exit=0 grep -E 'fo|zz' -q b.txt"

# ---------- cmds: 拆段器邊角 ----------
{ echo '# t'; echo '## 驗收標準'
  printf '%s\n' '- `grep foo b.txt &> out_a.txt`' '- `grep foo b.txt >| out_b.txt`' '- `grep foo b.txt >&out_c.txt`' \
    '- `grep "$(touch dq_marker)" b.txt`' "- \`grep 'foo b.txt\`"
  printf '%s\n' "- \`$(printf 'grep foo b.txt >\tout_d.txt')\`" "- \`$(printf 'grep\tfoo\tb.txt\t>\tout_e.txt')\`"
} > "$TMP/cmds_splitter.md"
lint "$TMP/cmds_splitter.md" --repo "$REPO" --run
assert_line "splitter: &> 檔 UNLISTED" "$OUT" 'UNLISTED grep foo b.txt &> out_a.txt'
assert_line "splitter: >| 檔 UNLISTED" "$OUT" 'UNLISTED grep foo b.txt >| out_b.txt'
assert_line "splitter: >&檔 UNLISTED" "$OUT" 'UNLISTED grep foo b.txt >&out_c.txt'
assert_line "splitter: 雙引號內 \$( UNLISTED" "$OUT" 'UNLISTED grep "$(touch dq_marker)" b.txt'
assert_line "splitter: 引號未閉合 UNLISTED" "$OUT" "UNLISTED grep 'foo b.txt"
assert_line "splitter: > 後 tab 再接檔 UNLISTED" "$OUT" "$(printf 'UNLISTED grep foo b.txt >\tout_d.txt')"
assert_line "splitter: 全 tab 分隔 UNLISTED" "$OUT" "$(printf 'UNLISTED grep\tfoo\tb.txt\t>\tout_e.txt')"
for f in out_a.txt out_b.txt out_c.txt dq_marker out_d.txt out_e.txt; do
  assert_eq "splitter: $f 沒產生" "no" "$(exists "$REPO/$f")"
done

mkbrief cmds_stdin <<'EOF'
# t
## 驗收標準
- `cat`
EOF
# stdin 由一條還開著 4 秒的 pipe 提供：若指令繼承了 stdin，cat 會卡到 --timeout
OUT="$(sleep 4 | python3 "$BRIEF_LINT" "$TMP/cmds_stdin.md" --repo "$REPO" --run --timeout 2 2>&1)"; RC=$?
assert_line "stdin: 無參數 cat 不繼承 stdin、立即結束" "$OUT" "RUN exit=0 cat"
assert_not_contains "stdin: 不逾時" "$OUT" "TIMEOUT"

# ---------- callers ----------
mkbrief callers <<'EOF'
# t
## 範圍
- 改 `NewFoo(` 與 `pkg.NewFoo(` 的簽名；`zzzMissing(` 無人呼叫
## 驗收標準
- `echo NoCallerHere(` （不實跑：只驗範圍節外不枚舉）
## 其他
- `OtherFunc(` 不在範圍節
EOF
lint "$TMP/callers.md" --repo "$REPO"
assert_contains "callers: [callers] 標頭" "$OUT" "[callers]"
assert_contains "callers: total/tests 計數" "$OUT" "NewFoo total=4 tests=2"
assert_contains "callers: 列出命中行" "$OUT" "src/foo_test.go:4"
assert_contains "callers: pkg.Name 取最後一段搜尋" "$OUT" "pkg.NewFoo total=4 tests=2"
assert_contains "callers: 無命中 total=0" "$OUT" "zzzMissing total=0 tests=0"
assert_not_contains "callers: 範圍節外不枚舉 (驗收標準)" "$OUT" "NoCallerHere total="
assert_not_contains "callers: 範圍節外不枚舉 (其他)" "$OUT" "OtherFunc total="
assert_eq "callers: 純資訊不算 problem exit 0" 0 "$RC"

# ---------- exit codes ----------
lint "$TMP/nonexistent.md" --repo "$REPO"
assert_eq "exit: brief 不存在 → 2" 2 "$RC"
lint "$TMP/cmds_ok.md" --repo "$TMP/not-a-dir"
assert_eq "exit: --repo 不是目錄 → 2" 2 "$RC"
OUT="$(python3 "$BRIEF_LINT" 2>&1)"; RC=$?
assert_eq "exit: 無參數 → 2" 2 "$RC"
lint "$TMP/cmds_ok.md" --repo "$REPO" --timeout notanumber
assert_eq "exit: 參數錯 → 2" 2 "$RC"
lint "$TMP/cmds_ok.md" --repo "$REPO"
assert_eq "exit: 無 problem → 0" 0 "$RC"
lint "$TMP/refs.md" --repo "$REPO"
assert_eq "exit: 有 problem → 1" 1 "$RC"

echo
# ---------- cmds: $'...' ANSI-C 引號一律 UNLISTED ----------
{ echo '# t'; echo '## 驗收標準'; printf '%s\n' "- \`grep \$'\\'' b.txt ; touch ansi_new ; grep y \\'\`"; } > "$TMP/cmds_ansi.md"
lint "$TMP/cmds_ansi.md" --repo "$REPO" --run
assert_contains "ansi: \$' 指令 UNLISTED" "$OUT" "UNLISTED grep \$'"
assert_eq "ansi: 沒有執行" "no" "$(exists "$REPO/ansi_new")"

# ---------- refs: 錨點原文比對 ----------
mkbrief snip_ok <<'EOF'
# t
相符 `src/foo.go:3「func NewFoo()」` 與無反引號 src/foo.go:4「return 1」。
EOF
lint "$TMP/snip_ok.md" --repo "$REPO"
assert_contains "snippet: 相符印 OK 行" "$OUT" "OK src/foo.go:3 | func NewFoo() int {"
assert_not_contains "snippet: 相符不報 SNIPPET_MISMATCH" "$OUT" "SNIPPET_MISMATCH"
assert_contains "snippet: 相符 problems=0" "$OUT" "summary: problems=0"
assert_eq "snippet: 相符 exit 0" 0 "$RC"

mkbrief snip_bad <<'EOF'
# t
不符 `src/foo.go:3「func Other」`。
EOF
lint "$TMP/snip_bad.md" --repo "$REPO"
assert_line "snippet: 不符印 SNIPPET_MISMATCH 與實際行" "$OUT" "SNIPPET_MISMATCH src/foo.go:3 「func Other」 | 實際：func NewFoo() int {"
assert_not_contains "snippet: 不符不印 OK 行" "$OUT" "OK src/foo.go:3"
assert_contains "snippet: 不符 problems=1" "$OUT" "summary: problems=1"
assert_eq "snippet: 不符 exit 1" 1 "$RC"

mkbrief snip_range <<'EOF'
# t
區間第二行相符 src/foo.go:3-4「return 1」，區間內都不符 src/foo.go:3-4「nothere」。
EOF
lint "$TMP/snip_range.md" --repo "$REPO"
assert_contains "snippet: 區間第二行相符 OK" "$OUT" "OK src/foo.go:3-4 | func NewFoo() int {"
assert_line "snippet: 區間都不符 MISMATCH" "$OUT" "SNIPPET_MISMATCH src/foo.go:3-4 「nothere」 | 實際：func NewFoo() int {"
assert_contains "snippet: 區間 problems=1" "$OUT" "summary: problems=1"

mkbrief snip_space <<'EOF'
# t
片段空白 src/foo.go:4「  return 1  」，行首有 tab 的行 src/foo.go:4「return 1」。
EOF
lint "$TMP/snip_space.md" --repo "$REPO"
assert_not_contains "snippet: 前後空白差異不影響" "$OUT" "SNIPPET_MISMATCH"
assert_contains "snippet: 空白差異 problems=0" "$OUT" "summary: problems=0"

mkbrief snip_nofile <<'EOF'
# t
缺檔 nofile/x.go:1「abc」 與越界 src/foo.go:99「abc」。
EOF
lint "$TMP/snip_nofile.md" --repo "$REPO"
assert_contains "snippet: 缺檔仍 MISSING_FILE" "$OUT" "MISSING_FILE nofile/x.go:1"
assert_contains "snippet: 越界仍 LINE_OUT_OF_RANGE" "$OUT" "LINE_OUT_OF_RANGE src/foo.go:99"
assert_not_contains "snippet: 缺檔／越界不比片段" "$OUT" "SNIPPET_MISMATCH"

# ---------- cmds: UNLISTED 判紅 ----------
mkbrief unl_red <<'EOF'
# t
## 驗收標準
- `touch m1`
EOF
lint "$TMP/unl_red.md" --repo "$REPO"
assert_line "unlisted: 狀態字樣不變" "$OUT" "UNLISTED touch m1"
assert_contains "unlisted: problems=1" "$OUT" "summary: problems=1"
assert_eq "unlisted: exit 1" 1 "$RC"
lint "$TMP/unl_red.md" --repo "$REPO" --run
assert_contains "unlisted: --run 同樣 problems=1" "$OUT" "summary: problems=1"
assert_eq "unlisted: --run 沒執行" "no" "$(exists "$REPO/m1")"

mkbrief unl_ack <<'EOF'
# t
## 驗收標準
- `touch m1` （不實跑：有副作用）
- `touch m2`
EOF
lint "$TMP/unl_ack.md" --repo "$REPO"
assert_line "unlisted: 行尾不實跑 → UNLISTED_ACK" "$OUT" "UNLISTED_ACK touch m1"
assert_line "unlisted: 沒標記的同批仍 UNLISTED" "$OUT" "UNLISTED touch m2"
assert_contains "unlisted: ACK 不計、另一條計 problems=1" "$OUT" "summary: problems=1"

mkbrief unl_ack_only <<'EOF'
# t
## 驗收標準
- `touch m1` （不實跑：有副作用）
EOF
lint "$TMP/unl_ack_only.md" --repo "$REPO"
assert_contains "unlisted: 只有 ACK problems=0" "$OUT" "summary: problems=0"
assert_eq "unlisted: 只有 ACK exit 0" 0 "$RC"

mkbrief unl_denied_ph <<'EOF'
# t
## 驗收標準
- `rm marker`
- `cat <wt> > marker_ph`
EOF
lint "$TMP/unl_denied_ph.md" --repo "$REPO"
assert_line "unlisted: DENIED 照印" "$OUT" "DENIED rm marker"
assert_line "unlisted: PLACEHOLDER 照印" "$OUT" "PLACEHOLDER cat <wt> > marker_ph"
assert_contains "unlisted: DENIED／PLACEHOLDER 不計 problems=0" "$OUT" "summary: problems=0"
assert_eq "unlisted: DENIED／PLACEHOLDER exit 0" 0 "$RC"

# ---------- scope: 範圍新檔被 .gitignore 擋 ----------
IGN="$TMP/repo_ign"
mkdir -p "$IGN/src"
printf 'checks/\n*.secret\n' > "$IGN/.gitignore"
printf 'x\n' > "$IGN/src/keep.go"
(cd "$IGN" && git init -q && git config user.email t@example.com && git config user.name t \
  && git add .gitignore src && git commit -q -m init) >/dev/null 2>&1

mkbrief scope_ign <<'EOF'
# t
## 範圍
- 新增 `checks/x/verify.json` 與 `src/new_file.go`，另有 `a/b.secret`、`NewFoo(` 與 `bin/tool --flag`
## 驗收標準
- `checks/y/other.json` 只是驗收節的 inline code
EOF
lint "$TMP/scope_ign.md" --repo "$IGN"
assert_line "scope: ignore 目錄下的新檔 IGNORED_PATH" "$OUT" "IGNORED_PATH checks/x/verify.json"
assert_line "scope: ignore 萬用字元 IGNORED_PATH" "$OUT" "IGNORED_PATH a/b.secret"
assert_not_contains "scope: 未被 ignore 的新檔不報" "$OUT" "IGNORED_PATH src/new_file.go"
assert_not_contains "scope: 驗收節的路徑不檢查" "$OUT" "IGNORED_PATH checks/y/other.json"
assert_not_contains "scope: 非路徑項目不檢查" "$OUT" "IGNORED_PATH NewFoo("
assert_count "scope: 只報兩條" "$OUT" "IGNORED_PATH" 2
assert_contains "scope: problems=2" "$OUT" "summary: problems=2"
assert_eq "scope: exit 1" 1 "$RC"

mkbrief scope_clean <<'EOF'
# t
## 範圍
- 只動 `src/new_file.go` 與 `src/keep.go:1`
EOF
lint "$TMP/scope_clean.md" --repo "$IGN"
assert_not_contains "scope: 乾淨範圍不報" "$OUT" "IGNORED_PATH"
assert_contains "scope: 乾淨 problems=0" "$OUT" "summary: problems=0"
assert_eq "scope: 乾淨 exit 0" 0 "$RC"

mkbrief scope_lineno <<'EOF'
# t
## 範圍
- `checks/z.json:3`
EOF
lint "$TMP/scope_lineno.md" --repo "$IGN"
assert_line "scope: 帶行號的路徑也檢查" "$OUT" "IGNORED_PATH checks/z.json"

# ---------- M2/M3: 錨點變體 ----------
mkbrief snip_tick <<'EOF'
# t
反引號後接片段 `src/foo.go:3`「func NewFoo」，夾空白 `src/foo.go:4` 「return 1」。
EOF
lint "$TMP/snip_tick.md" --repo "$REPO"
assert_contains "snippet: `p:n`「x」 相符 OK" "$OUT" "OK src/foo.go:3 | func NewFoo() int {"
assert_contains "snippet: `p:n` 「x」 夾空白相符 OK" "$OUT" "OK src/foo.go:4 | "
assert_not_contains "snippet: 反引號變體相符不報" "$OUT" "SNIPPET_MISMATCH"

mkbrief snip_tick_bad <<'EOF'
# t
反引號後不符 `src/foo.go:3`「func Other」，夾空白不符 `src/foo.go:4` 「nothere」。
EOF
lint "$TMP/snip_tick_bad.md" --repo "$REPO"
assert_line "snippet: `p:n`「x」 不符 MISMATCH" "$OUT" "SNIPPET_MISMATCH src/foo.go:3 「func Other」 | 實際：func NewFoo() int {"
assert_line "snippet: `p:n` 「x」 夾空白不符 MISMATCH" "$OUT" "SNIPPET_MISMATCH src/foo.go:4 「nothere」 | 實際：return 1"
assert_contains "snippet: 反引號變體 problems=2" "$OUT" "summary: problems=2"

mkbrief snip_otherline <<'EOF'
# t
片段在檔內他行 src/foo.go:3「return 1」。
EOF
lint "$TMP/snip_otherline.md" --repo "$REPO"
assert_line "snippet: 片段在他行不在引用行 → MISMATCH" "$OUT" "SNIPPET_MISMATCH src/foo.go:3 「return 1」 | 實際：func NewFoo() int {"
assert_contains "snippet: 他行 problems=1" "$OUT" "summary: problems=1"

mkbrief snip_afterplain <<'EOF'
# t
先無片段 src/foo.go:3 後有片段 src/foo.go:3「nothere」。
EOF
lint "$TMP/snip_afterplain.md" --repo "$REPO"
assert_contains "snippet: 同 p:n 先無片段 OK" "$OUT" "OK src/foo.go:3 | func NewFoo() int {"
assert_line "snippet: 同 p:n 後有片段仍比對" "$OUT" "SNIPPET_MISMATCH src/foo.go:3 「nothere」 | 實際：func NewFoo() int {"

# ---------- UNLISTED: 指令形狀與節範圍 ----------
mkbrief unl_single <<'EOF'
# t
## 驗收標準
- `id`
- `sed`
- `FOO=1 id`
EOF
lint "$TMP/unl_single.md" --repo "$REPO"
assert_line "unlisted: 單 token 仍印 UNLISTED" "$OUT" "UNLISTED id"
assert_line "unlisted: 前置變數後單 token 仍印" "$OUT" "UNLISTED FOO=1 id"
assert_contains "unlisted: 單 token 不計 problems=0" "$OUT" "summary: problems=0"
assert_eq "unlisted: 單 token exit 0" 0 "$RC"

mkbrief unl_othersec <<'EOF'
# t
## 範圍
- 提到 `touch m9`
## 其他
- 提到 `touch m8`
## 驗收標準
- `grep foo b.txt`
EOF
lint "$TMP/unl_othersec.md" --repo "$REPO"
assert_not_contains "unlisted: 其他節不掃描" "$OUT" "UNLISTED"
assert_contains "unlisted: 其他節 problems=0" "$OUT" "summary: problems=0"

mkbrief unl_ack_var <<'EOF'
# t
## 驗收標準
- `touch m1` （不實跑：全形加句號）。
- `touch m2` （不實跑：行尾空白）   
- `touch m3` (不實跑:半形括號)
- `touch m4` (不實跑：半形括號加句點).
- `touch m5` （不實跑：後面還有字） 後面還有字
EOF
lint "$TMP/unl_ack_var.md" --repo "$REPO"
assert_line "ack: 全形後接句號" "$OUT" "UNLISTED_ACK touch m1"
assert_line "ack: 行尾空白" "$OUT" "UNLISTED_ACK touch m2"
assert_line "ack: 半形括號與冒號" "$OUT" "UNLISTED_ACK touch m3"
assert_line "ack: 半形括號加句點" "$OUT" "UNLISTED_ACK touch m4"
assert_line "ack: 不在行尾不認" "$OUT" "UNLISTED touch m5"
assert_contains "ack: 只有一條計 problems=1" "$OUT" "summary: problems=1"

# ---------- 白名單: repo 內唯讀／測試入口 ----------
mkdir -p "$REPO/hooks" "$REPO/codex"
for t in tool brief-lint diff-surface gate-evidence push-plan verify-run pdf2md phase usage-diag trust-dir cmux-pet-notify.sh lint-rules; do
  printf 'echo toolhelp "$@"\n' > "$REPO/bin/$t"; chmod +x "$REPO/bin/$t"
done
printf 'echo mutate_ran\n' > "$REPO/bin/mutate"; chmod +x "$REPO/bin/mutate"
printf 'print("hookok")\n' > "$REPO/hooks/test_a.py"
printf 'print("validok")\n' > "$REPO/codex/validate.py"
mkbrief allow_new <<'EOF'
# t
## 驗收標準
- `bin/brief-lint --help`
- `bin/brief-lint --other`
- `bin/brief-lint --help --x`
- `bin/mutate --help`
- `python3 hooks/test_a.py`
- `python3 hooks/test_a.py -v`
- `python3 hooks/test_a.py --evil`
- `python3 ../hooks/test_a.py`
- `python3 hooks/other.py`
- `python3 codex/validate.py`
- `python3 codex/validate.py extra`
- `python3 codex/validate.py --fix`
EOF
lint "$TMP/allow_new.md" --repo "$REPO" --run
assert_line "allow: 列舉的 bin/<名> --help 執行" "$OUT" "RUN exit=0 bin/brief-lint --help"
assert_line "allow: 列舉的 bin/<名> 其他旗標 UNLISTED" "$OUT" "UNLISTED bin/brief-lint --other"
assert_line "allow: 列舉的 bin/<名> --help 後帶額外旗標 UNLISTED" "$OUT" "UNLISTED bin/brief-lint --help --x"
assert_line "allow: bin/mutate --help 仍 DENIED" "$OUT" "DENIED bin/mutate --help"
assert_line "allow: hooks/test_*.py 執行" "$OUT" "RUN exit=0 python3 hooks/test_a.py"
assert_line "allow: hooks/test_*.py -v 執行" "$OUT" "RUN exit=0 python3 hooks/test_a.py -v"
assert_line "allow: hooks/test_*.py 其他旗標 UNLISTED" "$OUT" "UNLISTED python3 hooks/test_a.py --evil"
assert_line "allow: hooks 路徑含 .. UNLISTED" "$OUT" "UNLISTED python3 ../hooks/test_a.py"
assert_line "allow: hooks 非 test_ 前綴 UNLISTED" "$OUT" "UNLISTED python3 hooks/other.py"
assert_line "allow: codex/validate.py 執行" "$OUT" "RUN exit=0 python3 codex/validate.py"
assert_line "allow: codex/validate.py 帶引數 UNLISTED" "$OUT" "UNLISTED python3 codex/validate.py extra"
assert_line "allow: codex/validate.py --fix 仍 DENIED" "$OUT" "DENIED python3 codex/validate.py --fix"
assert_contains "allow: 新白名單 problems=6（六條 UNLISTED 指令形狀）" "$OUT" "summary: problems=6"

mkbrief allow_bin_enum <<'EOF'
# t
## 驗收標準
- `bin/diff-surface --help`
- `bin/gate-evidence --help`
- `bin/push-plan --help`
- `bin/verify-run --help`
- `bin/pdf2md --help`
- `bin/phase --help`
- `bin/usage-diag --help`
- `bin/trust-dir --help`
- `bin/tool --help`
- `bin/cmux-pet-notify.sh --help`
- `bin/lint-rules --help`
EOF
lint "$TMP/allow_bin_enum.md" --repo "$REPO"
for t in diff-surface gate-evidence push-plan verify-run pdf2md phase usage-diag trust-dir; do
  assert_line "allow: 列舉 bin/$t --help" "$OUT" "NOT_RUN bin/$t --help"
done
assert_line "allow: 未列舉 bin/tool --help UNLISTED" "$OUT" "UNLISTED bin/tool --help"
assert_line "allow: bin/cmux-pet-notify.sh --help UNLISTED" "$OUT" "UNLISTED bin/cmux-pet-notify.sh --help"
assert_line "allow: bin/lint-rules --help UNLISTED" "$OUT" "UNLISTED bin/lint-rules --help"
assert_contains "allow: 未列舉三條計 problems=3" "$OUT" "summary: problems=3"

mkbrief allow_unittest <<'EOF'
# t
## 驗收標準
- `python3 -m unittest discover -s codex/tests`
EOF
lint "$TMP/allow_unittest.md" --repo "$REPO"
assert_line "allow: unittest discover -s <目錄> 在白名單內（NOT_RUN）" "$OUT" "NOT_RUN python3 -m unittest discover -s codex/tests"

# ---------- 驗收標準: 候選範圍與 problem 計法 ----------
mkbrief cand_pos <<'EOF'
# t
## 驗收標準
- `grep foo b.txt` exit 0，用 `mktemp -d` 的真 git repo，再看 `touch m_second`
句中提到 `touch m_prose` 不是列點。
  - `touch m_indented`
  3. 縮排子項描述 `touch m_sub`
  - `bash tests/test_ok.sh` 縮排列點照常判定
* `touch m_star`
1. `touch m4`
```
touch m5
$ bash tests/test_echo.sh
```
EOF
lint "$TMP/cand_pos.md" --repo "$REPO"
assert_line "cand: 列點第一個 inline code 照常判定" "$OUT" "NOT_RUN grep foo b.txt"
assert_line "cand: 同列點第二個 inline code 照常印（不計）" "$OUT" "UNLISTED mktemp -d"
assert_line "cand: 同列點第三個 inline code 照常印（不計）" "$OUT" "UNLISTED touch m_second"
assert_line "cand: 非列點句中 inline code 照常印（不計）" "$OUT" "UNLISTED touch m_prose"
assert_line "cand: 縮排列點 UNLISTED 照印但不計" "$OUT" "UNLISTED touch m_indented"
assert_line "cand: 縮排 N. 子項 UNLISTED 照印但不計" "$OUT" "UNLISTED touch m_sub"
assert_line "cand: 縮排列點的 NOT_RUN 不變" "$OUT" "NOT_RUN bash tests/test_ok.sh"
assert_line "cand: * 列點計" "$OUT" "UNLISTED touch m_star"
assert_line "cand: N. 列點計" "$OUT" "UNLISTED touch m4"
assert_not_contains "cand: 圍欄內的行不是候選" "$OUT" "m5"
assert_not_contains "cand: 圍欄內 \$ 行不是候選" "$OUT" "test_echo.sh"
assert_contains "cand: 只有頂層列點第一個 inline code 計 problems=2" "$OUT" "summary: problems=2"

mkbrief cand_denied_any <<'EOF'
# t
## 驗收標準
說明文字 `rm marker` 與 `bash tests/test_ok.sh`，還有 `grep foo b.txt`。
EOF
lint "$TMP/cand_denied_any.md" --repo "$REPO"
assert_line "cand: 非列點句中也判 DENIED" "$OUT" "DENIED rm marker"
assert_line "cand: 非列點句中也判 NOT_RUN" "$OUT" "NOT_RUN bash tests/test_ok.sh"
assert_line "cand: 非列點句中第三個也判 NOT_RUN" "$OUT" "NOT_RUN grep foo b.txt"
assert_contains "cand: 非列點無 problem" "$OUT" "summary: problems=0"

mkbrief fence_heading <<'EOF'
# t
## 其他
```
## 驗收標準
- `touch m_fenced`
```
## 驗收標準
- `grep foo b.txt`
EOF
lint "$TMP/fence_heading.md" --repo "$REPO"
assert_not_contains "fence: 圍欄內的 ## 驗收標準 不算標題" "$OUT" "m_fenced"
assert_line "fence: 真標題後的指令照常判定" "$OUT" "NOT_RUN grep foo b.txt"
assert_contains "fence: problems=0" "$OUT" "summary: problems=0"

# ---------- is_command: ./ 開頭 ----------
printf 'echo local\n' > "$REPO/local_tool"; chmod +x "$REPO/local_tool"
printf 'echo noexec\n' > "$REPO/not_exec"; chmod -x "$REPO/not_exec"
mkbrief dotslash <<'EOF'
# t
## 驗收標準
- `./local_tool arg`
- `./missing_tool arg`
- `./not_exec arg`
- `./api/backend/ ./api/front/ -run 'Rebate|Cascade'`
EOF
lint "$TMP/dotslash.md" --repo "$REPO"
assert_line "dotslash: repo 內存在且可執行才是指令（UNLISTED）" "$OUT" "UNLISTED ./local_tool arg"
assert_not_contains "dotslash: 不存在的 ./x 不是指令" "$OUT" "missing_tool"
assert_not_contains "dotslash: 存在但不可執行的 ./x 不是指令" "$OUT" "not_exec"
assert_not_contains "dotslash: ./ 開頭的路徑片段不是指令" "$OUT" "api/backend"
assert_contains "dotslash: 只有一條計 problems=1" "$OUT" "summary: problems=1"

# ---------- 白名單: 唯讀檢查類 ----------
mkdir -p "$REPO/node_modules/.bin" "$TMP/fakebin"
for t in vue-tsc eslint prettier vite; do
  printf 'echo %s "$@"\n' "$t" > "$REPO/node_modules/.bin/$t"; chmod +x "$REPO/node_modules/.bin/$t"
done
for t in gofmt graft swag; do
  printf 'echo %s "$@"\n' "$t" > "$TMP/fakebin/$t"; chmod +x "$TMP/fakebin/$t"
done
mkbrief allow_ro <<'EOF'
# t
## 驗收標準
- `./node_modules/.bin/vue-tsc --noEmit`
- `./node_modules/.bin/vue-tsc --noEmit --skipLibCheck 2>&1`
- `./node_modules/.bin/vue-tsc --noEmit --skipLibCheck -p tsconfig.app.json`
- `./node_modules/.bin/eslint src/a.ts src/views/b.vue`
- `./node_modules/.bin/prettier --check src/a.ts src/b.ts`
- `gofmt -l ./services .`
- `graft blast --base b39ee9f3 --no-refresh`
- `graft blast --no-refresh`
EOF
PATH="$TMP/fakebin:$PATH" lint "$TMP/allow_ro.md" --repo "$REPO"
assert_line "ro: vue-tsc --noEmit" "$OUT" "NOT_RUN ./node_modules/.bin/vue-tsc --noEmit"
assert_line "ro: vue-tsc --noEmit --skipLibCheck 2>&1" "$OUT" "NOT_RUN ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck 2>&1"
assert_line "ro: vue-tsc -p 專案檔" "$OUT" "NOT_RUN ./node_modules/.bin/vue-tsc --noEmit --skipLibCheck -p tsconfig.app.json"
assert_line "ro: eslint 檔案" "$OUT" "NOT_RUN ./node_modules/.bin/eslint src/a.ts src/views/b.vue"
assert_line "ro: prettier --check" "$OUT" "NOT_RUN ./node_modules/.bin/prettier --check src/a.ts src/b.ts"
assert_line "ro: gofmt -l" "$OUT" "NOT_RUN gofmt -l ./services ."
assert_line "ro: graft blast --no-refresh（帶 --base）" "$OUT" "NOT_RUN graft blast --base b39ee9f3 --no-refresh"
assert_line "ro: graft blast --no-refresh" "$OUT" "NOT_RUN graft blast --no-refresh"
assert_contains "ro: 全部在白名單 problems=0" "$OUT" "summary: problems=0"

mkbrief allow_ro_bad <<'EOF'
# t
## 驗收標準
- `./node_modules/.bin/vue-tsc --noEmit --build`
- `./node_modules/.bin/vue-tsc --noEmit > out.txt`
- `./node_modules/.bin/eslint --fix src/a.ts`
- `./node_modules/.bin/eslint --fix-dry-run src/a.ts`
- `./node_modules/.bin/eslint --output-file o.txt src/a.ts`
- `./node_modules/.bin/prettier --write src/a.ts`
- `./node_modules/.bin/prettier --check --write src/a.ts`
- `./node_modules/.bin/vite build`
- `gofmt -w x.go`
- `gofmt -l x.go > o.txt`
- `graft blast --base dev`
- `graft blast --no-refresh --out o.json`
- `swag init`
EOF
PATH="$TMP/fakebin:$PATH" lint "$TMP/allow_ro_bad.md" --repo "$REPO"
assert_line "ro-bad: vue-tsc 其他旗標 UNLISTED" "$OUT" "UNLISTED ./node_modules/.bin/vue-tsc --noEmit --build"
assert_line "ro-bad: vue-tsc 重導向寫檔 UNLISTED" "$OUT" "UNLISTED ./node_modules/.bin/vue-tsc --noEmit > out.txt"
assert_line "ro-bad: eslint --fix DENIED" "$OUT" "DENIED ./node_modules/.bin/eslint --fix src/a.ts"
assert_line "ro-bad: eslint --fix-dry-run DENIED" "$OUT" "DENIED ./node_modules/.bin/eslint --fix-dry-run src/a.ts"
assert_line "ro-bad: eslint --output-file DENIED" "$OUT" "DENIED ./node_modules/.bin/eslint --output-file o.txt src/a.ts"
assert_line "ro-bad: prettier --write UNLISTED" "$OUT" "UNLISTED ./node_modules/.bin/prettier --write src/a.ts"
assert_line "ro-bad: prettier --check --write UNLISTED" "$OUT" "UNLISTED ./node_modules/.bin/prettier --check --write src/a.ts"
assert_line "ro-bad: vite build UNLISTED" "$OUT" "UNLISTED ./node_modules/.bin/vite build"
assert_line "ro-bad: gofmt -w UNLISTED" "$OUT" "UNLISTED gofmt -w x.go"
assert_line "ro-bad: gofmt 重導向 UNLISTED" "$OUT" "UNLISTED gofmt -l x.go > o.txt"
assert_line "ro-bad: graft blast 無 --no-refresh UNLISTED" "$OUT" "UNLISTED graft blast --base dev"
assert_line "ro-bad: graft blast 其他旗標 UNLISTED" "$OUT" "UNLISTED graft blast --no-refresh --out o.json"
assert_line "ro-bad: swag init UNLISTED" "$OUT" "UNLISTED swag init"
assert_contains "ro-bad: 十條 UNLISTED 指令形狀計 problems（三條 DENIED 不計）" "$OUT" "summary: problems=10"

# ---------- ACK: 白名單指令、括號理由 ----------
mkbrief ack_allowed <<'EOF'
# t
## 驗收標準
- `bash tests/test_touch.sh ran_ack` （不實跑：會寫檔）
- `bash tests/test_touch.sh ran_noack`
- `touch m1 （不實跑：寫在 code 內）`
- `touch m2` （不實跑：理由含 (括號) 與 （全形括號））
EOF
lint "$TMP/ack_allowed.md" --repo "$REPO" --run
assert_line "ack: 白名單指令加 ACK → NOT_RUN_ACK" "$OUT" "NOT_RUN_ACK bash tests/test_touch.sh ran_ack"
assert_eq "ack: NOT_RUN_ACK 在 --run 下也不執行" "no" "$(exists "$REPO/ran_ack")"
assert_line "ack: 沒 ACK 的白名單指令照跑" "$OUT" "RUN exit=0 bash tests/test_touch.sh ran_noack"
assert_eq "ack: 沒 ACK 的真的跑了" "yes" "$(exists "$REPO/ran_noack")"
assert_line "ack: ACK 寫在 code 內先剝除再判定" "$OUT" "UNLISTED_ACK touch m1"
assert_line "ack: 理由含括號仍認" "$OUT" "UNLISTED_ACK touch m2"
assert_contains "ack: 全部 ACK 不計 problems=0" "$OUT" "summary: problems=0"
rm -f "$REPO/ran_noack"

mkbrief ack_last_only <<'EOF'
# t
## 驗收標準
- `touch a1` 與 `touch a2` （不實跑：只套最後一個）
- `touch b1` （不實跑：理由）（後面又有一段）
- `touch b2` （不實跑：理由含 (一層 (兩層) 巢狀) 結束）
- `touch b3` （不實跑：理由含 (一層) 與 （另一組）結束）
EOF
lint "$TMP/ack_last_only.md" --repo "$REPO"
assert_line "ack: 同行多個 code 只有最後一個吃 ACK（前者仍 UNLISTED）" "$OUT" "UNLISTED touch a1"
assert_line "ack: 同行最後一個 code 吃 ACK" "$OUT" "UNLISTED_ACK touch a2"
assert_line "ack: 後面還有另一組括號不吃" "$OUT" "UNLISTED touch b1"
assert_line "ack: 理由內超過一層巢狀不認" "$OUT" "UNLISTED touch b2"
assert_line "ack: 理由內一層巢狀（含並列兩組）仍認" "$OUT" "UNLISTED_ACK touch b3"
assert_contains "ack: a1、b1、b2 計 problems=3" "$OUT" "summary: problems=3"

# ---------- DENY_ENV／路徑引數不含 .. ----------
{ echo '# t'; echo '## 驗收標準'
  for v in PYTHONPATH PYTHONUSERBASE PYTHONSTARTUP PYTHONHOME NODE_OPTIONS NODE_PATH HOME XDG_CONFIG_HOME XDG_DATA_DIRS GOENV GOROOT GOTOOLCHAIN PYTHONWARNINGS; do echo "- \`$v=x grep foo b.txt\`"; done; } > "$TMP/deny_env2.md"
lint "$TMP/deny_env2.md" --repo "$REPO"
for v in PYTHONPATH PYTHONUSERBASE PYTHONSTARTUP PYTHONHOME NODE_OPTIONS NODE_PATH HOME XDG_CONFIG_HOME XDG_DATA_DIRS GOENV GOROOT GOTOOLCHAIN PYTHONWARNINGS; do
  assert_line "deny-env: $v 前綴賦值 DENIED" "$OUT" "DENIED $v=x grep foo b.txt"
done
mkbrief path_dotdot <<'EOF'
# t
## 驗收標準
- `gofmt -l ../x`
- `gofmt -l src/../../x`
- `./node_modules/.bin/eslint ../../etc`
- `./node_modules/.bin/prettier --check ../a.ts`
- `./node_modules/.bin/vue-tsc --noEmit -p /etc/tsconfig.json`
- `./node_modules/.bin/vue-tsc --noEmit -p sub/tsconfig.json`
- `gofmt -l src/a..b`
- `gofmt -l src/ok.go`
EOF
PATH="$TMP/fakebin:$PATH" lint "$TMP/path_dotdot.md" --repo "$REPO"
assert_line "dotdot: gofmt ../x 不放行" "$OUT" "UNLISTED gofmt -l ../x"
assert_line "dotdot: gofmt 中段 .. 不放行" "$OUT" "UNLISTED gofmt -l src/../../x"
assert_line "dotdot: eslint ../ 不放行" "$OUT" "UNLISTED ./node_modules/.bin/eslint ../../etc"
assert_line "dotdot: prettier ../ 不放行" "$OUT" "UNLISTED ./node_modules/.bin/prettier --check ../a.ts"
assert_line "abs: vue-tsc -p 絕對路徑不放行" "$OUT" "UNLISTED ./node_modules/.bin/vue-tsc --noEmit -p /etc/tsconfig.json"
assert_line "abs: vue-tsc -p 相對路徑放行" "$OUT" "NOT_RUN ./node_modules/.bin/vue-tsc --noEmit -p sub/tsconfig.json"
assert_line "dotdot: 含 .. 子字串一律不放行" "$OUT" "UNLISTED gofmt -l src/a..b"
assert_line "dotdot: 正常路徑照放行" "$OUT" "NOT_RUN gofmt -l src/ok.go"

# ---------- graft blast: --base 值限制 ----------
mkbrief graft_base <<'EOF'
# t
## 驗收標準
- `graft blast --base origin/dev^ --no-refresh`
- `graft blast --base HEAD~3 --no-refresh`
- `graft blast --base {HEAD,--export-viz=x} --no-refresh`
- `graft blast --base x${IFS}--export-viz --no-refresh`
- `graft blast --base --no-refresh .`
- `graft blast --base ~x --no-refresh`
EOF
PATH="$TMP/fakebin:$PATH" lint "$TMP/graft_base.md" --repo "$REPO"
assert_line "graft: --base 帶 ^ 放行" "$OUT" "NOT_RUN graft blast --base origin/dev^ --no-refresh"
assert_line "graft: --base 帶 ~（非首字）放行" "$OUT" "NOT_RUN graft blast --base HEAD~3 --no-refresh"
assert_line "graft: --base 大括號展開不放行" "$OUT" "UNLISTED graft blast --base {HEAD,--export-viz=x} --no-refresh"
assert_line "graft: --base \${IFS} 不放行" "$OUT" 'UNLISTED graft blast --base x${IFS}--export-viz --no-refresh'
assert_line "graft: --base 後直接接旗標不放行" "$OUT" "UNLISTED graft blast --base --no-refresh ."
assert_line "graft: --base ~ 開頭不放行" "$OUT" "UNLISTED graft blast --base ~x --no-refresh"
assert_contains "graft: 四條反例計 problems=4" "$OUT" "summary: problems=4"

# ---------- 錨點: 無反引號路徑與片段之間可夾空白 ----------
mkbrief snip_space_between <<'EOF'
# t
無反引號夾空白相符 src/foo.go:3 「func NewFoo」，不符 src/foo.go:4 「nothere」。
EOF
lint "$TMP/snip_space_between.md" --repo "$REPO"
assert_contains "snippet: p:n 「x」 夾空白相符 OK" "$OUT" "OK src/foo.go:3 | func NewFoo() int {"
assert_line "snippet: p:n 「x」 夾空白不符 MISMATCH" "$OUT" "SNIPPET_MISMATCH src/foo.go:4 「nothere」 | 實際：return 1"

# ---------- 未預期例外 → exit 2 ----------
if [ "$(id -u)" != "0" ]; then
  cp "$TMP/refs_abs.md" "$TMP/unreadable.md"; chmod 000 "$TMP/unreadable.md"
  lint "$TMP/unreadable.md" --repo "$REPO"
  assert_eq "exception: 讀不到 brief → exit 2（不與 problems 的 exit 1 混同）" 2 "$RC"
  assert_contains "exception: 印出訊息" "$OUT" "brief-lint:"
  chmod 600 "$TMP/unreadable.md"
fi

# ---------- scope: 路徑判定 ----------
IGN_ABS="$(cd "$IGN" && pwd -P)"
mkbrief scope_paths <<EOF
# t
## 範圍
- \`~/checks/home.json\`、\`/elsewhere/checks/out.json\`、\`$IGN_ABS/checks/in.json\`
- \`checks/*.json\`、\`src/*.go\`
EOF
lint "$TMP/scope_paths.md" --repo "$IGN_ABS"
assert_line "scope: repo 內絕對路徑轉相對再查" "$OUT" "IGNORED_PATH checks/in.json"
assert_not_contains "scope: ~ 開頭略過" "$OUT" "home.json"
assert_not_contains "scope: repo 外絕對路徑略過" "$OUT" "out.json"
assert_line "scope: glob 印 SCOPE_GLOB_SKIPPED（ignore 目錄）" "$OUT" "SCOPE_GLOB_SKIPPED checks/*.json"
assert_line "scope: glob 印 SCOPE_GLOB_SKIPPED（一般）" "$OUT" "SCOPE_GLOB_SKIPPED src/*.go"
assert_contains "scope: glob 不計、只有 in.json 計 problems=1" "$OUT" "summary: problems=1"

NOGIT="$TMP/nogit"
mkdir -p "$NOGIT"
mkbrief scope_nogit <<'EOF'
# t
## 範圍
- `src/a.go`
EOF
lint "$TMP/scope_nogit.md" --repo "$NOGIT"
assert_line "scope: 非 git 目錄印 SCOPE_UNCHECKED 帶 rc" "$OUT" "SCOPE_UNCHECKED src/a.go 128"
assert_contains "scope: 非 git 目錄 problems=0" "$OUT" "summary: problems=0"
assert_eq "scope: 非 git 目錄不 exit 2" 0 "$RC"

# ---------- --help ----------
HELP="$(python3 "$BRIEF_LINT" --help 2>&1)"; HRC=$?
assert_eq "help: exit 0" 0 "$HRC"
assert_contains "help: 說明 SNIPPET_MISMATCH" "$HELP" "SNIPPET_MISMATCH"
assert_contains "help: 說明 UNLISTED_ACK" "$HELP" "UNLISTED_ACK"
assert_contains "help: 說明 NOT_RUN_ACK" "$HELP" "NOT_RUN_ACK"
assert_contains "help: 寫明新增 bin 工具需同步 --help 清單" "$HELP" "同步"
assert_contains "help: 已知限制寫明依賴 shutil.which" "$HELP" "shutil.which"
assert_contains "help: 引用檔頭 docstring（單一 source）" "$HELP" "用法：brief-lint"
assert_contains "help: 說明 IGNORED_PATH" "$HELP" "IGNORED_PATH"
assert_contains "help: 說明 SCOPE_GLOB_SKIPPED" "$HELP" "SCOPE_GLOB_SKIPPED"
assert_contains "help: 說明 SCOPE_UNCHECKED" "$HELP" "SCOPE_UNCHECKED"
assert_contains "help: 寫明片段含「」」的已知限制" "$HELP" "已知限制"

echo "TOTAL: $((PASS_COUNT + FAIL_COUNT))  PASS: $PASS_COUNT  FAIL: $FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
