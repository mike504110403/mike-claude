#!/bin/bash
# test_verify_run.sh — bin/verify-run 的 seam 測試（只經 CLI：stdout + exit code）。
# 腳本路徑由 VERIFY_RUN 決定（預設 ../verify-run）。fixture 全在 mktemp -d 底下。
set -u

VR="${VERIFY_RUN:-$(cd "$(dirname "$0")/.." && pwd)/verify-run}"

PASS_COUNT=0
FAIL_COUNT=0
TMP_ROOT="${TMPDIR:-/tmp}"
TMP="$(mktemp -d "${TMP_ROOT%/}/verify-run-test.XXXXXX")"
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
assert_line() {
  if printf '%s\n' "$2" | grep -qxF -- "$3"; then ok "$1"; else bad "$1 (沒有整行: $3)"; fi
}
assert_count() {
  local n
  n="$(printf '%s\n' "$2" | grep -cxF -- "$3")"
  if [ "$n" = "$4" ]; then ok "$1"; else bad "$1 (整行出現 $n 次，預期 $4：$3)"; fi
}
exists() { if [ -e "$1" ]; then echo yes; else echo no; fi; }

vr() { OUT="$("$VR" "$@" 2>&1)"; RC=$?; }

export VERIFY_RUN_CHECKS="$TMP/checks"

# ---------- fixture ----------
FX="$TMP/fx"
mkdir -p "$FX"
script() { cat > "$FX/$1"; }

script both.sh <<'SH'
echo out-line-1
echo err-line-2 >&2
SH
script fail_a.sh <<'SH'
echo "[FAIL] a"
echo "== done =="
exit 1
SH
script fail_aa.sh <<'SH'
echo "[FAIL] a"
echo "[FAIL] a"
echo "== done =="
exit 1
SH
script fail_ab.sh <<'SH'
echo "[FAIL] a"
echo "[FAIL] b"
echo "== done =="
exit 1
SH
script silent_fail.sh <<'SH'
echo boom
exit 3
SH
script crash.sh <<'SH'
echo "[FAIL] a"
nosuchcmd_xyz
exit 1
SH
script suffix_item.sh <<'SH'
echo "[FAIL] x [build failed]"
echo "== done =="
exit 1
SH
script go_fail.sh <<'SH'
echo "=== RUN   TestX"
echo "=== RUN   TestX/sub"
echo "--- FAIL: TestX (0.00s)"
echo "    --- FAIL: TestX/sub (0.00s)"
echo "=== RUN   TestY"
echo "--- SKIP: TestY (0.00s)"
printf 'FAIL\tpkg/a\t0.012s\n'
echo "FAIL"
exit 1
SH
script go_fail_z.sh <<'SH'
echo "=== RUN   TestX"
echo "=== RUN   TestX/sub"
echo "=== RUN   TestZ"
echo "--- FAIL: TestX (0.00s)"
echo "    --- FAIL: TestX/sub (0.00s)"
echo "--- FAIL: TestZ (0.00s)"
printf 'FAIL\tpkg/a\t0.012s\n'
exit 1
SH
script go_ok.sh <<'SH'
echo "=== RUN   TestA"
echo "--- PASS: TestA (0.00s)"
printf 'ok  \tpkg/a\t0.010s\n'
SH
script go_build_fail.sh <<'SH'
echo "=== RUN   TestOther"
echo "--- PASS: TestOther (0.00s)"
printf 'FAIL\tpkg/b [build failed]\n'
exit 1
SH
script go_noverbose.sh <<'SH'
echo "--- FAIL: TestX (0.00s)"
printf 'FAIL\tpkg/a\t0.012s\n'
exit 1
SH
script go_json.sh <<'SH'
echo '{"Action":"run","Package":"pkg/a","Test":"TestX"}'
echo '{"Action":"skip","Package":"pkg/a","Test":"TestY"}'
echo '{"Action":"fail","Package":"pkg/a","Test":"TestX"}'
exit 1
SH
script go_noresult.sh <<'SH'
echo "=== RUN   TestA"
echo "--- FAIL: TestA (0.00s)"
echo "=== RUN   TestNewFatal"
printf 'FAIL\tpkg/a\t0.100s\n'
exit 1
SH
script go_nosummary.sh <<'SH'
echo "=== RUN   TestA"
echo "--- FAIL: TestA (0.00s)"
exit 1
SH
script killed.sh <<'SH'
echo "[FAIL] a"
echo "== done =="
kill -9 $$
SH
script go_remnant.sh <<'SH'
echo "=== RUN   TestA"
echo "--- PASS: TestA (0.00s)"
echo "PASS"
printf 'ok  \tex/a\t0.100s\n'
echo "=== RUN   TestKnown"
echo "--- FAIL: TestKnown (0.00s)"
exit 1
SH
script go_cover_last.sh <<'SH'
echo "=== RUN   TestX"
echo "--- FAIL: TestX (0.00s)"
echo "FAIL"
printf 'FAIL\tpkg/a\t0.012s\n'
printf '\tpkg/c\t\tcoverage: 0.0%% of statements\n'
echo "FAIL"
exit 1
SH
script go_testmain.sh <<'SH'
echo "=== RUN   TestConfig"
echo "--- PASS: TestConfig (0.00s)"
echo "PASS"
printf 'ok  \tex/a\t0.100s\n'
echo "2026/11/26 15:25:08 setup"
printf 'FAIL\tex/b\t0.773s\n'
exit 1
SH
script go_samename.sh <<'SH'
echo "=== RUN   TestConfig"
echo "--- PASS: TestConfig (0.00s)"
echo "PASS"
printf 'ok  \tex/a\t0.100s\n'
echo "=== RUN   TestConfig"
printf 'FAIL\tex/b\t0.200s\n'
exit 1
SH
script go_mixed.sh <<'SH'
echo "=== RUN   TestA"
echo "--- PASS: TestA (0.00s)"
echo "PASS"
printf 'ok  \tex/a\t0.100s\n'
printf 'ok  \tex/b\t0.100s\n'
SH
script go_exempt.sh <<'SH'
printf '?   \tex/c\t[no test files]\n'
echo "testing: warning: no tests to run"
echo "PASS"
printf 'ok  \tex/d\t0.500s [no tests to run]\n'
echo "=== RUN   TestA"
echo "--- PASS: TestA (0.00s)"
echo "PASS"
printf 'ok  \tex/a\t0.100s\n'
SH
script go_bench.sh <<'SH'
echo "=== RUN   BenchmarkB"
echo "=== RUN   TestA"
echo "--- FAIL: TestA (0.00s)"
printf 'FAIL\tex/a\t0.100s\n'
exit 1
SH
script tsc_located.sh <<'SH'
echo "src/a.ts(1,2): error TS2322: bad"
exit 2
SH
script tsc_fail.sh <<'SH'
echo "src/a.ts(1,2): error TS2322: bad"
echo "src/b.ts(3,4): error TS2345: worse"
echo "src/c.ts(5,6): error TS2000: see x.ts(1,2): error TS9999"
echo "note: see y.ts(1,2): error TS8888"
echo "error TS6053: File 'z.ts' not found."
echo "== done =="
exit 2
SH
script py_fail.sh <<'SH'
echo "FAIL: test_one (mod.Case)"
echo "ERROR: test_two (mod.Case)"
echo "[FAIL] ignored-by-custom-pattern"
echo "== done =="
exit 1
SH
script env_fail.sh <<'SH'
printf '[FAIL] %s\n' "$X"
exit 1
SH
script cwd_fail.sh <<'SH'
printf '[FAIL] %s\n' "$(pwd -P)"
exit 1
SH

REPO="$TMP/.foo"
mkdir -p "$REPO/pkg/foo" "$REPO/sub"
printf 'package foo\n' > "$REPO/pkg/foo/foo.go"
printf 'package foo\n\nimport "os"\n\nconst addrEnv = "BAZ_TEST_ADDR"\n\nvar a = os.Getenv("FOO_TEST_DSN")\nvar b = os.Getenv("FOO_DEBUG")\nvar c = os.Getenv("BAR_TEST_URL")\nvar d = os.Getenv(addrEnv)\n' > "$REPO/pkg/foo/foo_test.go"
printf 'x\n' > "$REPO/sub/f"
(
  cd "$REPO" && git init -q && git config user.email t@example.com && git config user.name t \
    && git add . && git commit -q -m init
) >/dev/null 2>&1
BASE="$(git -C "$REPO" rev-parse HEAD)"
printf 'package foo\n\nfunc F() {}\n' > "$REPO/pkg/foo/foo.go"
git -C "$REPO" commit -q -am change >/dev/null 2>&1
WT="$TMP/linked"
git -C "$REPO" worktree add -q -b wt/x "$WT" >/dev/null 2>&1

cfg() { cat > "$TMP/cfg_$1.json"; }
DONE='"done_pattern":"^== done =="'

# ---------- 1. generic 通過 + log 完整 ----------
cfg pass <<EOF
{"commands":[{"name":"ok","cmd":"bash $FX/both.sh","kind":"generic"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_pass.json" --out "$TMP/out1"
assert_eq "pass: exit 0" 0 "$RC"
assert_line "pass: RESULT PASS" "$OUT" "RESULT PASS"
assert_eq "pass: log 存在" yes "$(exists "$TMP/out1/ok.log")"
LOGTXT="$(cat "$TMP/out1/ok.log" 2>/dev/null)"
assert_contains "pass: log 含 stdout" "$LOGTXT" "out-line-1"
assert_contains "pass: log 含 stderr" "$LOGTXT" "err-line-2"
assert_contains "pass: 結果表含 log 路徑" "$OUT" "$TMP/out1/ok.log"
assert_contains "pass: 結果表欄位" "$OUT" "ok | 0 | NEW 0 | KNOWN 0 | UNPARSED 0 | SKIP 0 | "

# ---------- 2. known_fail 吸收／新增失敗 ----------
cfg known <<EOF
{"commands":[{"name":"g","cmd":"bash $FX/fail_a.sh","kind":"generic",$DONE,"known_fail":["^a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_known.json" --out "$TMP/out2"
assert_eq "known: 全吸收 exit 0" 0 "$RC"
assert_line "known: RESULT PASS" "$OUT" "RESULT PASS"
assert_line "known: KNOWN_FAIL 行" "$OUT" "KNOWN_FAIL g a"
assert_contains "known: 表 KNOWN 1" "$OUT" "g | 1 | NEW 0 | KNOWN 1 | UNPARSED 0 | SKIP 0 | "

cfg newfail <<EOF
{"commands":[{"name":"g","cmd":"bash $FX/fail_ab.sh","kind":"generic",$DONE,"known_fail":["^a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_newfail.json" --out "$TMP/out2b"
assert_eq "newfail: exit 1" 1 "$RC"
assert_line "newfail: NEW_FAIL b" "$OUT" "NEW_FAIL g b"
assert_not_contains "newfail: a 不是 NEW_FAIL" "$OUT" "NEW_FAIL g a"
assert_line "newfail: RESULT FAIL" "$OUT" "RESULT FAIL"

# ---------- 2b. known_fail count ----------
cfg count1 <<EOF
{"commands":[{"name":"g","cmd":"bash $FX/fail_aa.sh","kind":"generic",$DONE,"known_fail":[{"re":"^a\$","count":1}]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_count1.json" --out "$TMP/out2c"
assert_eq "count: 超出次數 exit 1" 1 "$RC"
assert_count "count: 恰 1 個 NEW_FAIL" "$OUT" "NEW_FAIL g a" 1
assert_count "count: 恰 1 個 KNOWN_FAIL" "$OUT" "KNOWN_FAIL g a" 1
assert_contains "count: 表 NEW 1 KNOWN 1" "$OUT" "g | 1 | NEW 1 | KNOWN 1 | UNPARSED 0 | SKIP 0 | "

cfg count2 <<EOF
{"commands":[{"name":"g","cmd":"bash $FX/fail_aa.sh","kind":"generic",$DONE,"known_fail":[{"re":"^a\$","count":2}]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_count2.json" --out "$TMP/out2d"
assert_eq "count: 次數剛好吸收 exit 0" 0 "$RC"

cfg countstr <<EOF
{"commands":[{"name":"g","cmd":"bash $FX/fail_aa.sh","kind":"generic",$DONE,"known_fail":["^a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_countstr.json" --out "$TMP/out2e"
assert_eq "count: 字串不限次數 exit 0" 0 "$RC"

cfg countbad <<EOF
{"commands":[{"name":"g","cmd":"true","kind":"generic","known_fail":[{"re":"^a\$","count":"x"}]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_countbad.json" --out "$TMP/out2f"
assert_eq "count: count 型別錯 → 2" 2 "$RC"

# ---------- 2c. 可吸收性是欄位、不是名稱後綴 ----------
cfg suffix <<EOF
{"commands":[{"name":"s","cmd":"bash $FX/suffix_item.sh","kind":"generic",$DONE,"known_fail":["^x"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_suffix.json" --out "$TMP/out2g"
assert_eq "absorbable: generic 項目名恰好以 [build failed] 結尾仍可吸收" 0 "$RC"

# ---------- 3. exit≠0 無可抽取項 ----------
cfg unparsed <<EOF
{"commands":[{"name":"u","cmd":"bash $FX/silent_fail.sh","kind":"generic","known_fail":[".*"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_unparsed.json" --out "$TMP/out3"
assert_eq "unparsed: exit 1" 1 "$RC"
assert_contains "unparsed: UNPARSED_FAIL no_items" "$OUT" "UNPARSED_FAIL u no_items exit=3"
assert_contains "unparsed: 表 UNPARSED 1" "$OUT" "u | 3 | NEW 0 | KNOWN 0 | UNPARSED 1 | SKIP 0 | "
assert_line "unparsed: RESULT FAIL" "$OUT" "RESULT FAIL"

# ---------- 3b. generic fail_pattern ----------
cfg pat <<EOF
{"commands":[{"name":"py","cmd":"bash $FX/py_fail.sh","kind":"generic",$DONE,"fail_pattern":"^(?:FAIL|ERROR): (.*)","known_fail":["^test_one"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_pat.json" --out "$TMP/out3b"
assert_eq "pattern: exit 1" 1 "$RC"
assert_line "pattern: KNOWN test_one" "$OUT" "KNOWN_FAIL py test_one (mod.Case)"
assert_line "pattern: NEW test_two" "$OUT" "NEW_FAIL py test_two (mod.Case)"
assert_not_contains "pattern: 預設 [FAIL] 不再抽" "$OUT" "ignored-by-custom-pattern"

cfg patbad <<EOF
{"commands":[{"name":"py","cmd":"true","kind":"generic","fail_pattern":"^FAIL .*"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_patbad.json" --out "$TMP/out3c"
assert_eq "pattern: 無 capture group → 2" 2 "$RC"

# ---------- 3c. 管線不能遮蔽失敗 ----------
cfg pipe <<EOF
{"commands":[{"name":"p","cmd":"bash $FX/fail_a.sh | cat","kind":"generic"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_pipe.json" --out "$TMP/out3d"
assert_eq "pipefail: 管線前段失敗 → exit 1" 1 "$RC"
assert_line "pipefail: NEW_FAIL a" "$OUT" "NEW_FAIL p a"

# ---------- 3d. 吸收需要完成標記 ----------
cfg nodone <<EOF
{"commands":[{"name":"c","cmd":"bash $FX/crash.sh","kind":"generic","known_fail":["^a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_nodone.json" --out "$TMP/out3e"
assert_eq "done: 有吸收但未設 done_pattern → exit 1" 1 "$RC"
assert_line "done: UNPARSED_FAIL incomplete" "$OUT" "UNPARSED_FAIL c incomplete"

cfg donemiss <<EOF
{"commands":[{"name":"c","cmd":"bash $FX/crash.sh","kind":"generic",$DONE,"known_fail":["^a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_donemiss.json" --out "$TMP/out3f"
assert_eq "done: 設了 done_pattern 但 log 無標記 → exit 1" 1 "$RC"
assert_line "done: UNPARSED_FAIL incomplete（done_pattern 版）" "$OUT" "UNPARSED_FAIL c incomplete"
assert_contains "done: 表 UNPARSED 1" "$OUT" "NEW 0 | KNOWN 1 | UNPARSED 1 | SKIP 0 | "

cfg donebad <<EOF
{"commands":[{"name":"c","cmd":"true","kind":"generic","done_pattern":"("}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_donebad.json" --out "$TMP/out3g"
assert_eq "done: done_pattern regex 壞 → 2" 2 "$RC"

# ---------- 4. go kind ----------
cfg gokind <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_fail.sh","kind":"go","known_fail":["^TestX\$","^TestX/sub\$","^pkg/a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gokind.json" --out "$TMP/out4"
assert_eq "go: 吸收後 exit 0" 0 "$RC"
assert_line "go: SKIP 行" "$OUT" "SKIP go TestY"
assert_line "go: KNOWN_FAIL TestX" "$OUT" "KNOWN_FAIL go TestX"
assert_line "go: KNOWN_FAIL 子測試" "$OUT" "KNOWN_FAIL go TestX/sub"
assert_line "go: KNOWN_FAIL pkg/a" "$OUT" "KNOWN_FAIL go pkg/a"
assert_contains "go: 表 SKIP 1" "$OUT" "NEW 0 | KNOWN 3 | UNPARSED 0 | SKIP 1 | "
assert_not_contains "go: 有 RUN 輸出不報 NO_VERBOSE" "$OUT" "NO_VERBOSE"

cfg gonew <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_fail_z.sh","kind":"go","known_fail":["^TestX\$","^TestX/sub\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gonew.json" --out "$TMP/out4b"
assert_eq "go: 未吸收的 TestZ／pkg exit 1" 1 "$RC"
assert_line "go: NEW_FAIL TestZ" "$OUT" "NEW_FAIL go TestZ"
assert_line "go: 套件區塊有未吸收失敗 → [package failed]" "$OUT" "NEW_FAIL go pkg/a [package failed]"

cfg gook <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_ok.sh","kind":"go"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gook.json" --out "$TMP/out4c"
assert_eq "go: 全綠 exit 0" 0 "$RC"

cfg gobuild <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_build_fail.sh","kind":"go","known_fail":[".*"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gobuild.json" --out "$TMP/out4d"
assert_eq "go: build failed 永不吸收 exit 1" 1 "$RC"
assert_line "go: NEW_FAIL 保留 build failed 後綴" "$OUT" "NEW_FAIL go pkg/b [build failed]"

cfg gonov <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_noverbose.sh -v","kind":"go","known_fail":["^TestX\$","^pkg/a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gonov.json" --out "$TMP/out4e"
assert_eq "go: 命令字串有 -v 但輸出無 RUN → exit 1" 1 "$RC"
assert_line "go: NO_VERBOSE 行" "$OUT" "NO_VERBOSE go"
assert_contains "go: 表 UNPARSED 計 NO_VERBOSE" "$OUT" "KNOWN 2 | UNPARSED 1 | SKIP 0 | "

cfg gonov0 <<EOF
{"commands":[{"name":"go","cmd":"echo hi","kind":"go"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gonov0.json" --out "$TMP/out4f"
assert_eq "go: 無 RUN 輸出即使 exit 0 也判失敗" 1 "$RC"

cfg gojson <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_json.sh -json","kind":"go","known_fail":[".*"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gojson.json" --out "$TMP/out4g"
assert_eq "go: -json 形狀輸出 → exit 1" 1 "$RC"
assert_line "go: -json 形狀 NO_VERBOSE" "$OUT" "NO_VERBOSE go"
assert_line "go: 無結尾行的殘段（無 RUN）→ [no package result]" "$OUT" "NEW_FAIL go - [no package result]"

cfg gonores <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_noresult.sh","kind":"go","known_fail":[".*"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gonores.json" --out "$TMP/out4h"
assert_eq "go: RUN 無結果行（即使 known_fail 全吸收）→ exit 1" 1 "$RC"
assert_line "go: NEW_FAIL TestNewFatal [no result]" "$OUT" "NEW_FAIL go TestNewFatal [no result]"
assert_line "go: 有結果行的 TestA 仍被吸收" "$OUT" "KNOWN_FAIL go TestA"

cfg gonosum <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_nosummary.sh","kind":"go","known_fail":["^TestA\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gonosum.json" --out "$TMP/out4i"
assert_eq "go: 有吸收但無套件總結行 → exit 1" 1 "$RC"
assert_line "go: UNPARSED_FAIL incomplete" "$OUT" "UNPARSED_FAIL go incomplete"

cfg gotestmain <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_testmain.sh","kind":"go","known_fail":["^ex/b\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gotestmain.json" --out "$TMP/out4j"
assert_eq "go: TestMain 失敗整包沒跑（known_fail 含該 pkg）→ exit 1" 1 "$RC"
assert_line "go: 無失敗測試的套件失敗 → [package failed]" "$OUT" "NEW_FAIL go ex/b [package failed]"

cfg gosame <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_samename.sh","kind":"go"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gosame.json" --out "$TMP/out4k"
assert_eq "go: 兩套件同名測試、b 無結果 → exit 1" 1 "$RC"
assert_line "go: 配對只在套件區塊內" "$OUT" "NEW_FAIL go TestConfig [no result]"

cfg gomixed <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_mixed.sh","kind":"go"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gomixed.json" --out "$TMP/out4l"
assert_eq "go: 混合 -v／非 -v 區塊 → exit 1" 1 "$RC"
assert_line "go: 混合區塊 NO_VERBOSE" "$OUT" "NO_VERBOSE go"

cfg goexempt <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_exempt.sh","kind":"go"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_goexempt.json" --out "$TMP/out4m"
assert_eq "go: no test files／no tests to run 區塊免 RUN → exit 0" 0 "$RC"
assert_not_contains "go: 免 RUN 區塊不報 NO_VERBOSE" "$OUT" "NO_VERBOSE"

cfg gobench <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_bench.sh","kind":"go","known_fail":["^TestA\$","^ex/a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gobench.json" --out "$TMP/out4n"
assert_eq "go: Benchmark 的 RUN 不做 [no result] 配對 → exit 0" 0 "$RC"
assert_not_contains "go: Benchmark 無 [no result]" "$OUT" "BenchmarkB"

cfg goremnant <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_remnant.sh","kind":"go","known_fail":["^TestKnown\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_goremnant.json" --out "$TMP/out4o"
assert_eq "go: ok 區塊後只剩已知失敗的殘段 → exit 1" 1 "$RC"
assert_line "go: 殘段 NEW_FAIL [no package result]" "$OUT" "NEW_FAIL go TestKnown [no package result]"
assert_line "go: 殘段內的已知失敗仍可吸收" "$OUT" "KNOWN_FAIL go TestKnown"

# ---------- 4b. 被殺／SIGPIPE 的指令不吸收 ----------
cfg killed <<EOF
{"commands":[{"name":"k","cmd":"bash $FX/killed.sh; exit \$?","kind":"generic",$DONE,"known_fail":["^a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_killed.json" --out "$TMP/out4p"
assert_eq "killed: 子 shell 被 kill -9（exit 137）→ exit 1" 1 "$RC"
assert_line "killed: UNPARSED_FAIL killed" "$OUT" "UNPARSED_FAIL k killed exit=137"
assert_line "killed: 項目不吸收" "$OUT" "NEW_FAIL k a"

cfg killed2 <<EOF
{"commands":[{"name":"k","cmd":"echo '[FAIL] a'; echo '== done =='; kill -9 \$\$","kind":"generic",$DONE,"known_fail":["^a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_killed2.json" --out "$TMP/out4q"
assert_eq "killed: 指令 shell 本身被 kill -9（returncode<0）→ exit 1" 1 "$RC"
assert_line "killed: returncode<0 也印 killed" "$OUT" "UNPARSED_FAIL k killed exit=-9"

cfg sigpipe <<EOF
{"commands":[{"name":"p","cmd":"yes '[FAIL] a' | head -n 2","kind":"generic","done_pattern":"^.FAIL","known_fail":["^a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_sigpipe.json" --out "$TMP/out4r"
assert_eq "killed: 管線 SIGPIPE（exit 141）→ exit 1" 1 "$RC"
assert_line "killed: SIGPIPE 印 killed" "$OUT" "UNPARSED_FAIL p killed exit=141"

cfg gotimeout <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_fail.sh; exit 124","kind":"go","known_fail":["^TestX\$","^TestX/sub\$","^pkg/a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gotimeout.json" --out "$TMP/out4s"
assert_eq "go: 完整已知失敗區塊後 exit 124（外部 timeout）→ exit 1" 1 "$RC"
assert_line "go: exit 124 判 killed" "$OUT" "UNPARSED_FAIL go killed exit=124"

cfg gocover <<EOF
{"commands":[{"name":"go","cmd":"bash $FX/go_cover_last.sh","kind":"go","known_fail":["^TestX\$","^pkg/a\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_gocover.json" --out "$TMP/out4t"
assert_eq "go: -cover 無測試檔套件排最後 → 不算殘段 exit 0" 0 "$RC"
assert_not_contains "go: -cover 區塊不報 no package result" "$OUT" "no package result"

# ---------- 5. vue-tsc kind ----------
cfg tsc <<EOF
{"commands":[{"name":"tsc","cmd":"bash $FX/tsc_fail.sh","kind":"vue-tsc",$DONE,"known_fail":["^src/a.ts:error TS2322\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_tsc.json" --out "$TMP/out5"
assert_eq "tsc: exit 1" 1 "$RC"
assert_line "tsc: NEW_FAIL b" "$OUT" "NEW_FAIL tsc src/b.ts:error TS2345"
assert_line "tsc: NEW_FAIL c（訊息內含誘餌）" "$OUT" "NEW_FAIL tsc src/c.ts:error TS2000"
assert_line "tsc: KNOWN_FAIL a" "$OUT" "KNOWN_FAIL tsc src/a.ts:error TS2322"
assert_not_contains "tsc: a 不是 NEW_FAIL" "$OUT" "NEW_FAIL tsc src/a.ts"
assert_not_contains "tsc: 訊息中段誘餌不抽" "$OUT" "TS9999"
assert_line "tsc: 無位置的 error TS 行 unlocated" "$OUT" "NEW_FAIL tsc error TS6053: File 'z.ts' not found. [unlocated]"
assert_line "tsc: 非行首位置格式的 error TS 行 unlocated" "$OUT" "NEW_FAIL tsc note: see y.ts(1,2): error TS8888 [unlocated]"

cfg tsclocated <<EOF
{"commands":[{"name":"tsc","cmd":"bash $FX/tsc_located.sh","kind":"vue-tsc","known_fail":["^src/a.ts:error TS2322\$"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_tsclocated.json" --out "$TMP/out5c"
assert_eq "tsc: 有吸收且未設 done_pattern → 不要求完成標記 exit 0" 0 "$RC"

cfg tscall <<EOF
{"commands":[{"name":"tsc","cmd":"bash $FX/tsc_fail.sh","kind":"vue-tsc",$DONE,"known_fail":[".*"]}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_tscall.json" --out "$TMP/out5b"
assert_eq "tsc: known_fail .* 也吸收不了 unlocated → exit 1" 1 "$RC"
assert_line "tsc: unlocated 仍是 NEW_FAIL" "$OUT" "NEW_FAIL tsc error TS6053: File 'z.ts' not found. [unlocated]"
assert_contains "tsc: 位置齊全者都吸收" "$OUT" "KNOWN 3 | UNPARSED 0 | SKIP 0 | "

# ---------- 6. --base MISSING_ENV ----------
cfg envmiss <<EOF
{"commands":[{"name":"ok","cmd":"true","kind":"generic"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_envmiss.json" --out "$TMP/out6" --base "$BASE"
assert_line "env: 缺 DSN" "$OUT" "MISSING_ENV FOO_TEST_DSN pkg/foo"
assert_line "env: 缺 URL" "$OUT" "MISSING_ENV BAR_TEST_URL pkg/foo"
assert_line "env: const 寫法的 ADDR" "$OUT" "MISSING_ENV BAZ_TEST_ADDR pkg/foo"
assert_not_contains "env: 非 _DSN/_URL/_ADDR 不報" "$OUT" "FOO_DEBUG"
assert_eq "env: MISSING_ENV 不擋" 0 "$RC"

vr --repo "$REPO/sub" --config "$TMP/cfg_envmiss.json" --out "$TMP/out6d" --base "$BASE"
assert_line "env: --repo 指向子目錄仍掃得到" "$OUT" "MISSING_ENV FOO_TEST_DSN pkg/foo"

cfg envgiven <<EOF
{"commands":[
 {"name":"first","cmd":"true","kind":"generic"},
 {"name":"second","cmd":"true","kind":"generic","env":{"FOO_TEST_DSN":"x","BAZ_TEST_ADDR":"y"}}
]}
EOF
BAR_TEST_URL=set vr --repo "$REPO" --config "$TMP/cfg_envgiven.json" --out "$TMP/out6b" --base "$BASE"
assert_not_contains "env: 任一指令的設定檔 env 都算已提供" "$OUT" "MISSING_ENV FOO_TEST_DSN"
assert_not_contains "env: const 寫法設定檔給了不報" "$OUT" "MISSING_ENV BAZ_TEST_ADDR"
assert_not_contains "env: 當前環境有不報" "$OUT" "MISSING_ENV BAR_TEST_URL"

vr --repo "$REPO" --config "$TMP/cfg_envmiss.json" --out "$TMP/out6c"
assert_not_contains "env: 沒給 --base 不檢查" "$OUT" "MISSING_ENV"

# ---------- 7. 設定檔解析 ----------
mkdir -p "$VERIFY_RUN_CHECKS/foo"
cp "$TMP/cfg_pass.json" "$VERIFY_RUN_CHECKS/foo/verify.json"
vr --repo "$REPO" --out "$TMP/out7a"
assert_eq "key: 主 checkout .foo 去開頭點 → foo 找到設定" 0 "$RC"
vr --repo "$WT" --out "$TMP/out7b"
assert_eq "key: linked worktree 解析成主 checkout 名" 0 "$RC"
assert_line "key: worktree RESULT PASS" "$OUT" "RESULT PASS"
VERIFY_RUN_CHECKS="$TMP/nochecks" vr --repo "$REPO" --out "$TMP/out7c"
assert_eq "config: 設定檔不存在 → 2" 2 "$RC"
vr --repo "$REPO" --key other --out "$TMP/out7d"
assert_eq "key: --key 覆寫（other 無設定）→ 2" 2 "$RC"
printf '{not json' > "$TMP/cfg_broken.json"
vr --repo "$REPO" --config "$TMP/cfg_broken.json" --out "$TMP/out7e"
assert_eq "config: JSON 壞 → 2" 2 "$RC"
cfg badkind <<EOF
{"commands":[{"name":"x","cmd":"true","kind":"nope"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_badkind.json" --out "$TMP/out7f"
assert_eq "config: kind 不合法 → 2" 2 "$RC"
printf '{"commands":[]}' > "$TMP/cfg_empty.json"
vr --repo "$REPO" --config "$TMP/cfg_empty.json" --out "$TMP/out7g"
assert_eq "config: commands 為空 → 2" 2 "$RC"
for bad_name in "a b" "../x" "-x" ""; do
  printf '{"commands":[{"name":"%s","cmd":"true"}]}' "$bad_name" > "$TMP/cfg_badname.json"
  vr --repo "$REPO" --config "$TMP/cfg_badname.json" --out "$TMP/out7h"
  assert_eq "config: 指令名「${bad_name}」不合法 → 2" 2 "$RC"
done
printf '{"commands":[{"name":"unit.v2-x_1","cmd":"true"}]}' > "$TMP/cfg_goodname.json"
vr --repo "$REPO" --config "$TMP/cfg_goodname.json" --out "$TMP/out7i"
assert_eq "config: 指令名 unit.v2-x_1 合法" 0 "$RC"

# ---------- 7b. 預設 --out ----------
vr --repo "$REPO" --config "$TMP/cfg_pass.json"
LOGPATH="$(printf '%s\n' "$OUT" | sed -n 's/.* | \([^ ]*ok\.log\)$/\1/p')"
assert_contains "out: 預設 mkdtemp 目錄名含 key" "$LOGPATH" "/verify-run-foo-"
assert_eq "out: 預設目錄內有 log" yes "$(exists "$LOGPATH")"
LOGDIR="$(dirname "$LOGPATH")"
case "$LOGDIR" in
  "${TMP_ROOT%/}"/verify-run-* | "$TMP"/*) rm -rf "$LOGDIR" ;;
  *) bad "out: 預設輸出目錄不在 TMPDIR 底下，不刪除：$LOGDIR" ;;
esac

# ---------- 8. --only、cwd、env ----------
cfg two <<EOF
{"commands":[
 {"name":"a","cmd":"true","kind":"generic"},
 {"name":"b","cmd":"bash $FX/fail_a.sh","kind":"generic"}
]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_two.json" --out "$TMP/out8" --only a
assert_eq "only: 只跑 a → exit 0" 0 "$RC"
assert_eq "only: b 沒有 log" no "$(exists "$TMP/out8/b.log")"
assert_contains "only: 表有 a" "$OUT" "a | 0 | "
assert_not_contains "only: 表無 b" "$OUT" "b | 1 | "
vr --repo "$REPO" --config "$TMP/cfg_two.json" --out "$TMP/out8b" --only nope
assert_eq "only: 未知名稱 → 2" 2 "$RC"
vr --repo "$REPO" --config "$TMP/cfg_two.json" --out "$TMP/out8e" --only ""
assert_eq "only: 空字串篩完為空 → 2" 2 "$RC"
vr --repo "$REPO" --config "$TMP/cfg_two.json" --out "$TMP/out8f" --only ","
assert_eq "only: 只有逗號篩完為空 → 2" 2 "$RC"

cfg envrun <<EOF
{"commands":[{"name":"e","cmd":"bash $FX/env_fail.sh","kind":"generic","env":{"X":"value-from-config"}}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_envrun.json" --out "$TMP/out8c"
assert_line "env: 設定檔 env 傳進指令" "$OUT" "NEW_FAIL e value-from-config"

cfg cwdrun <<EOF
{"commands":[{"name":"c","cmd":"bash $FX/cwd_fail.sh","cwd":"sub","kind":"generic"}]}
EOF
vr --repo "$REPO" --config "$TMP/cfg_cwdrun.json" --out "$TMP/out8d"
EXPECT_CWD="$(cd "$REPO/sub" && pwd -P)"
assert_line "cwd: 相對 repo 根" "$OUT" "NEW_FAIL c $EXPECT_CWD"

# ---------- --help ----------
vr --help
assert_eq "help: exit 0" 0 "$RC"
assert_contains "help: 有用法" "$OUT" "--repo"
assert_contains "help: 有 exit code 說明" "$OUT" "Exit codes"
assert_contains "help: 說明 --base 只掃已 commit 範圍" "$OUT" "committed range"

echo
echo "TOTAL: $((PASS_COUNT + FAIL_COUNT))  PASS: $PASS_COUNT  FAIL: $FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
