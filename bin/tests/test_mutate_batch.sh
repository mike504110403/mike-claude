#!/bin/bash
# test_mutate_batch.sh — bin/mutate 的 --batch / --check 驗收測試（案 a-o，brief: mutate-batch v2）
# 純 bash + coreutils，各案獨立臨時目錄，不依賴 Go 或任何專案。
# PATH 陷阱防護：本檔一律用 bash "$MUTATE" 呼叫，禁止裸 `mutate`
# （grep -nE '^\s*mutate ' 本檔須無輸出）。
set -u

MUTATE="$(cd "$(dirname "$0")/.." && pwd)/mutate"

PASS_COUNT=0
FAIL_COUNT=0
TMP_DIRS=()

cleanup() {
  local d
  for d in "${TMP_DIRS[@]:-}"; do
    [ -n "$d" ] && [ -d "$d" ] && rm -rf "$d"
  done
}
trap cleanup EXIT

newtmp() {
  # 注意：不得用 D="$(newtmp)" 呼叫——command substitution 會讓整個函式在 subshell
  # 裡跑，TMP_DIRS+= 只改到 subshell 自己的副本，父層陣列永遠是空的、EXIT trap 清不到
  # 任何東西（每跑一次洩 20 個目錄，退件案例）。一律用：newtmp; D="$NEWTMP"
  NEWTMP="$(mktemp -d "${TMPDIR:-/tmp}/mutate-batch-test.XXXXXX")"
  TMP_DIRS+=("$NEWTMP")
}

ok() { PASS_COUNT=$((PASS_COUNT + 1)); echo "[PASS] $1"; }
bad() { FAIL_COUNT=$((FAIL_COUNT + 1)); echo "[FAIL] $1"; }

assert_eq() {
  local desc="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then ok "$desc"; else bad "${desc} (expected=${expected} actual=${actual})"; fi
}

assert_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if printf '%s' "$haystack" | grep -qF -- "$needle"; then ok "$desc"; else bad "$desc (找不到: $needle)"; fi
}

assert_not_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if printf '%s' "$haystack" | grep -qF -- "$needle"; then bad "$desc (不應含: $needle)"; else ok "$desc"; fi
}

assert_file_eq() {
  local desc="$1" f1="$2" f2="$3"
  if cmp -s "$f1" "$f2"; then ok "$desc"; else bad "$desc ($f1 與 $f2 逐位不一致)"; fi
}

assert_exists() {
  local desc="$1" f="$2"
  if [ -e "$f" ]; then ok "$desc"; else bad "$desc ($f 不存在)"; fi
}

assert_not_exists() {
  local desc="$1" f="$2"
  if [ -e "$f" ]; then bad "$desc ($f 不應存在)"; else ok "$desc"; fi
}

# 逐列斷言：從結果表抓出 id 那一列，比對指定欄位（1=id 2=applied 3=compile 4=test 5=expect 6=verdict 7=secs）
# 不靠總結計數（計數型斷言是恆真式，見退件案例）。
assert_row_field() {
  local desc="$1" table="$2" id="$3" field_idx="$4" expected="$5"
  local row actual
  row="$(printf '%s\n' "$table" | grep -E "^${id} \| ")"
  actual="$(printf '%s' "$row" | awk -F' \\| ' -v i="$field_idx" '{print $i}')"
  if [ "$expected" = "$actual" ]; then ok "$desc"; else bad "$desc (row=[$row] expected=$expected actual=$actual)"; fi
}

# ---------------------------------------------------------------------------
# 案 a：控制組紅 + 一條真變異紅 → 表兩行 PASS，exit 0，兩個目標檔逐位一致
# ---------------------------------------------------------------------------
case_a() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  cp "$D/f1.txt" "$D/f1.orig"
  cp "$D/f2.txt" "$D/f2.orig"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/FOO=bar/FOO=baz/
test: grep -q 'FOO=bar' f2.txt
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  assert_eq "a: exit 0" "0" "$rc"
  assert_contains "a: 總結 2 PASS" "$out" "2 PASS / 0 FAIL / 0 not-applied / 0 compile-red"
  assert_row_field "a: control 那一列 verdict 為 PASS（逐列）" "$out" "control" 6 "PASS"
  assert_row_field "a: M1 那一列 verdict 為 PASS（逐列）" "$out" "M1" 6 "PASS"
  assert_file_eq "a: f1.txt 還原一致" "$D/f1.txt" "$D/f1.orig"
  assert_file_eq "a: f2.txt 還原一致" "$D/f2.txt" "$D/f2.orig"
}

# ---------------------------------------------------------------------------
# 案 b：sed 沒匹配 → 該條 applied=no, verdict not-applied，exit 3，測試指令沒被執行
# ---------------------------------------------------------------------------
case_b() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  cp "$D/f2.txt" "$D/f2.orig"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/NOPE_NOT_PRESENT/xxx/
test: touch "$D/marker.txt"
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  assert_eq "b: exit 3" "3" "$rc"
  assert_contains "b: 表含 M1 | no" "$out" "M1 | no |"
  assert_contains "b: 表含 not-applied" "$out" "not-applied"
  assert_row_field "b: M1 那一列 verdict 為 not-applied（逐列）" "$out" "M1" 6 "not-applied"
  assert_not_exists "b: 測試指令沒被執行（marker 不存在）" "$D/marker.txt"
  assert_file_eq "b: f2.txt 逐位一致" "$D/f2.txt" "$D/f2.orig"
}

# ---------------------------------------------------------------------------
# 案 c：變異落在測試沒守的行 → FAIL，exit 4，總結行含 1 FAIL
# ---------------------------------------------------------------------------
case_c() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\nUNCOVERED=1\n' >"$D/f2.txt"
  cp "$D/f2.txt" "$D/f2.orig"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/UNCOVERED=1/UNCOVERED=2/
test: grep -q 'FOO=bar' f2.txt
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  assert_eq "c: exit 4" "4" "$rc"
  assert_contains "c: 總結含 1 FAIL" "$out" "1 FAIL"
  assert_row_field "c: M1 那一列 verdict 為 FAIL（逐列，不靠總結計數）" "$out" "M1" 6 "FAIL"
  assert_file_eq "c: f2.txt 逐位一致" "$D/f2.txt" "$D/f2.orig"
}

# ---------------------------------------------------------------------------
# 案 d：控制組綠 → exit 5，第二條沒跑；控制組 sed 沒匹配 → 同樣 exit 5
# ---------------------------------------------------------------------------
case_d() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\nNOISE=1\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/NOISE=1/NOISE=2/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/FOO=bar/FOO=baz/
test: touch "$D/marker.txt"
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  assert_eq "d: 控制組綠 exit 5" "5" "$rc"
  assert_not_exists "d: 第二條沒跑（marker 不存在）" "$D/marker.txt"

  local D2; newtmp; D2="$NEWTMP"
  printf 'LIMIT=5\n' >"$D2/f1.txt"
  printf 'FOO=bar\n' >"$D2/f2.txt"
  cat >"$D2/list.mutations" <<EOF
cwd: $D2

id: control
file: f1.txt
sed: s/NOPE_NOT_PRESENT/xxx/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/FOO=bar/FOO=baz/
test: touch "$D2/marker.txt"
expect: red
EOF
  local rc2
  bash "$MUTATE" --batch "$D2/list.mutations" --out "$D2/out" >/dev/null 2>&1
  rc2=$?
  assert_eq "d: 控制組 not-applied exit 5" "5" "$rc2"
  assert_not_exists "d: not-applied 控制組時第二條也沒跑" "$D2/marker.txt"
}

# ---------------------------------------------------------------------------
# 案 e：--check 模式
# ---------------------------------------------------------------------------
case_e() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  cp "$D/f1.txt" "$D/f1.orig"
  cp "$D/f2.txt" "$D/f2.orig"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: touch "$D/marker.txt"
expect: red

id: M1
file: f2.txt
sed: s/FOO=bar/FOO=baz/
test: touch "$D/marker.txt"
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --check --out "$D/out" 2>&1)"
  rc=$?
  assert_eq "e: --check exit 0" "0" "$rc"
  assert_not_exists "e: --check 不跑測試（marker 不存在）" "$D/marker.txt"
  assert_not_contains "e: --check 表不含 verdict 欄" "$out" "verdict"
  assert_contains "e: --check 表頭只有 id | applied" "$out" "id | applied"
  assert_file_eq "e: --check f1.txt 逐位一致" "$D/f1.txt" "$D/f1.orig"
  assert_file_eq "e: --check f2.txt 逐位一致" "$D/f2.txt" "$D/f2.orig"

  local D2; newtmp; D2="$NEWTMP"
  printf 'LIMIT=5\n' >"$D2/f1.txt"
  printf 'FOO=bar\n' >"$D2/f2.txt"
  cat >"$D2/list.mutations" <<EOF
cwd: $D2

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: true
expect: red

id: M1
file: f2.txt
sed: s/NOPE_NOT_PRESENT/xxx/
test: true
expect: red
EOF
  local rc2
  bash "$MUTATE" --batch "$D2/list.mutations" --check --out "$D2/out" >/dev/null 2>&1
  rc2=$?
  assert_eq "e: --check sed 沒匹配 exit 3" "3" "$rc2"

  # --check 也強制第一條是 control
  local D3; newtmp; D3="$NEWTMP"
  printf 'LIMIT=5\n' >"$D3/f1.txt"
  cp "$D3/f1.txt" "$D3/f1.orig"
  cat >"$D3/list.mutations" <<EOF
cwd: $D3

id: notcontrol
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: true
expect: red
EOF
  bash "$MUTATE" --batch "$D3/list.mutations" --check --out "$D3/out" >/dev/null 2>&1
  assert_eq "e: --check 第一條非 control exit 2" "2" "$?"
  assert_file_eq "e: --check 第一條非 control 時未動檔" "$D3/f1.txt" "$D3/f1.orig"
}

# ---------------------------------------------------------------------------
# 案 f：patch: 條目可套用且 PASS；壞的 patch → not-applied 且無 .rej/.orig 殘留
# ---------------------------------------------------------------------------
case_f() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'VALUE=10\n' >"$D/f3.txt"
  cp "$D/f3.txt" "$D/f3.orig"
  cat >"$D/m.patch" <<'EOF'
--- f3.txt
+++ f3.txt
@@ -1 +1 @@
-VALUE=10
+VALUE=20
EOF
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M-patch
file: f3.txt
patch: m.patch
test: grep -q 'VALUE=10' f3.txt
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  assert_eq "f: exit 0" "0" "$rc"
  assert_contains "f: 總結 2 PASS" "$out" "2 PASS / 0 FAIL / 0 not-applied / 0 compile-red"
  assert_file_eq "f: f3.txt 逐位一致" "$D/f3.txt" "$D/f3.orig"

  # 壞的 patch（脈絡對不上）→ not-applied，且無 .rej/.orig 殘留
  local D2; newtmp; D2="$NEWTMP"
  printf 'LIMIT=5\n' >"$D2/f1.txt"
  printf 'VALUE=10\n' >"$D2/f4.txt"
  cp "$D2/f4.txt" "$D2/f4.orig"
  cat >"$D2/bad.patch" <<'EOF'
--- f4.txt
+++ f4.txt
@@ -1 +1 @@
-VALUE=NOPE_CONTEXT_MISMATCH
+VALUE=20
EOF
  cat >"$D2/list.mutations" <<EOF
cwd: $D2

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M-badpatch
file: f4.txt
patch: bad.patch
test: true
expect: red
EOF
  local out2 rc2
  out2="$(bash "$MUTATE" --batch "$D2/list.mutations" --out "$D2/out" 2>&1)"
  rc2=$?
  assert_eq "f: 壞 patch exit 3" "3" "$rc2"
  assert_contains "f: 壞 patch not-applied" "$out2" "not-applied"
  assert_row_field "f: M-badpatch 那一列 verdict 為 not-applied（逐列）" "$out2" "M-badpatch" 6 "not-applied"
  assert_file_eq "f: 壞 patch 後 f4.txt 逐位一致" "$D2/f4.txt" "$D2/f4.orig"
  assert_not_exists "f: 無 .rej 殘留" "$D2/f4.txt.rej"
  assert_not_exists "f: 無 .orig 殘留" "$D2/f4.txt.orig"
}

# ---------------------------------------------------------------------------
# 案 g：expect: green 的 equivalent mutant → 測試綠 PASS；同條若測試紅 → FAIL
# ---------------------------------------------------------------------------
case_g() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'A=1\nB=2\n' >"$D/f4.txt"
  printf 'A=1\nB=2\n' >"$D/f5.txt"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M-equiv-pass
file: f4.txt
sed: s/B=2/B=99/
test: grep -q 'A=1' f4.txt
expect: green

id: M-equiv-fail
file: f5.txt
sed: s/A=1/A=99/
test: grep -q 'A=1' f5.txt
expect: green
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  assert_contains "g: 總結含 1 FAIL" "$out" "1 FAIL"
  assert_contains "g: 總結含 2 PASS" "$out" "2 PASS"
  # 逐列斷言（不靠總結計數——計數型斷言是恆真式：忽略 expect 直接照 test 紅/綠判，
  # 綠變異照樣算 FAIL、紅變異照樣算 PASS，計數不變，抓不到 expect 被忽略的迴歸）
  assert_row_field "g: M-equiv-pass 那一列 verdict 為 PASS（測試綠、expect green）" "$out" "M-equiv-pass" 6 "PASS"
  assert_row_field "g: M-equiv-fail 那一列 verdict 為 FAIL（測試紅、expect green）" "$out" "M-equiv-fail" 6 "FAIL"
}

# ---------------------------------------------------------------------------
# 案 h：有 compile: 且失敗 → compile=red, verdict compile-red，exit 6，test 欄為 -
# ---------------------------------------------------------------------------
case_h() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M-compile
file: f2.txt
sed: s/FOO=bar/FOO=baz/
compile: false
test: touch "$D/marker.txt"
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  assert_eq "h: exit 6" "6" "$rc"
  assert_contains "h: 表含 M-compile | yes | red | -" "$out" "M-compile | yes | red | -"
  assert_contains "h: 表含 compile-red" "$out" "compile-red"
  assert_row_field "h: M-compile 那一列 verdict 為 compile-red（逐列）" "$out" "M-compile" 6 "compile-red"
  assert_not_exists "h: test 沒跑（marker 不存在）" "$D/marker.txt"
}

# ---------------------------------------------------------------------------
# 案 i：中斷還原 — 背景跑 + kill -INT $MPID，無 fallback
# ---------------------------------------------------------------------------
case_i() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  cp "$D/f2.txt" "$D/f2.orig"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/FOO=bar/FOO=baz/
test: touch "$D/ran.marker"; sleep 10.246813
expect: red
EOF
  bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" >"$D/out.log" 2>&1 &
  local MPID=$!
  local waited=0
  while [ ! -f "$D/ran.marker" ] && [ "$waited" -lt 100 ]; do
    sleep 0.05
    waited=$((waited + 1))
  done
  assert_exists "i: 測試指令已開始跑（ran.marker 出現）" "$D/ran.marker"
  # 計時起點放在 kill -INT 之前（不含前面的輪詢等待），量的是「中斷到退出」
  local t_start; t_start="$(date +%s)"
  kill -INT "$MPID" 2>/dev/null
  wait "$MPID"
  local rc=$?
  local t_end elapsed; t_end="$(date +%s)"; elapsed=$((t_end - t_start))
  if [ "$rc" != "0" ]; then ok "i: 中斷後 exit 非 0"; else bad "i: 中斷後 exit 非 0 (實際 0)"; fi
  assert_file_eq "i: f2.txt 中斷後逐位一致" "$D/f2.txt" "$D/f2.orig"
  # 中斷必須「提早」發生：沒被真正中斷的話 test 指令會跑滿 sleep 10.246813 才自然結束
  if [ "$elapsed" -lt 5 ]; then ok "i: 中斷夠快（未跑滿 sleep 10.246813，耗時 ${elapsed}s）"; else bad "i: 中斷夠快（耗時 ${elapsed}s，疑似沒被真正中斷、跑到自然結束）"; fi
  # 孫行程（sleep）不得變孤兒殘留——用獨特秒數字串避免撞到別的 sleep
  sleep 0.3
  if pgrep -f 'sleep 10\.246813' >/dev/null 2>&1; then
    bad "i: 中斷後孫行程（sleep）沒有殘留 (仍有 sleep 10.246813 存活)"
  else
    ok "i: 中斷後孫行程（sleep）沒有殘留"
  fi
}

# ---------------------------------------------------------------------------
# 案 i2：中斷還原第二案（測試指令內自送 SIGINT 給父行程 $PPID，不取代案 i，兩者併存）
# ---------------------------------------------------------------------------
case_i2() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  cp "$D/f2.txt" "$D/f2.orig"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/FOO=bar/FOO=baz/
test: kill -INT \$PPID; sleep 0.3; exit 1
expect: red
EOF
  bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" >"$D/out.log" 2>&1
  local rc=$?
  assert_file_eq "i2: f2.txt 中斷後逐位一致（測試指令自送 SIGINT）" "$D/f2.txt" "$D/f2.orig"
  if [ "$rc" != "0" ]; then ok "i2: 中斷後 exit 非 0"; else bad "i2: 中斷後 exit 非 0 (實際 0)"; fi
}

# ---------------------------------------------------------------------------
# 案 i3：測試指令自己擋掉 SIGTERM（trap '' TERM）＋無窮迴圈 → SIGTERM 殺不動時
# 要能升級 SIGKILL，孫行程才不會變成永遠殺不掉的孤兒
# ---------------------------------------------------------------------------
case_i3() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  cp "$D/f2.txt" "$D/f2.orig"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/FOO=bar/FOO=baz/
test: touch "$D/i3.marker"; trap '' TERM; while true; do sleep 0.837462; done
expect: red
EOF
  bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" >"$D/out.log" 2>&1 &
  local MPID=$!
  local waited=0
  while [ ! -f "$D/i3.marker" ] && [ "$waited" -lt 100 ]; do
    sleep 0.05
    waited=$((waited + 1))
  done
  assert_exists "i3: 測試指令已開始跑（i3.marker 出現）" "$D/i3.marker"
  kill -INT "$MPID" 2>/dev/null
  # 這條 test 指令是殺不死的無窮迴圈：若 mutate 的中斷處理失效（例如 dogfood 的
  # M-interrupt-trap 把 SIGINT 吞掉），裸 `wait` 會永遠不回來、整套測試連同 dogfood
  # 一起掛死。所以等待有上限：30 秒，最壞情況是 SIGTERM 寬限 5 秒＋SIGKILL 再等 5 秒＝10 秒，
  # 健康路徑實測約 5.3 秒；上限只是防掛死的保險，不會拖慢正常路徑。逾時判紅並強殺。
  waited=0
  while kill -0 "$MPID" 2>/dev/null && [ "$waited" -lt 300 ]; do
    sleep 0.1
    waited=$((waited + 1))
  done
  if kill -0 "$MPID" 2>/dev/null; then
    bad "i3: 中斷後 30 秒內未退出（中斷處理失效），強殺"
    kill -9 "$MPID" 2>/dev/null
    wait "$MPID" 2>/dev/null
    # 強殺出來的 exit code 不是量到的結論，不對它做「exit 非 0」斷言
  else
    wait "$MPID"
    local rc=$?
    if [ "$rc" != "0" ]; then ok "i3: 中斷後 exit 非 0"; else bad "i3: 中斷後 exit 非 0 (實際 0)"; fi
  fi
  assert_file_eq "i3: f2.txt 中斷後逐位一致" "$D/f2.txt" "$D/f2.orig"
  # 只比對本案自己起的行程：命令列含本案唯一的 "$D/i3.marker" 路徑，不用全機共用的
  # 固定字串（第四輪 review：全機 pgrep 會被別次執行／dogfood 留下的孤兒染成假紅）。
  # SIGKILL 後 reaping 需要一點時間，輪詢最多 3 秒而非固定 sleep。
  local reaped=0
  waited=0
  while [ "$waited" -lt 30 ]; do
    if ! pgrep -f "$D/i3.marker" >/dev/null 2>&1; then reaped=1; break; fi
    sleep 0.1
    waited=$((waited + 1))
  done
  if [ "$reaped" = "1" ]; then
    ok "i3: SIGTERM 被擋掉時 SIGKILL 升級後整個測試指令 process group 真的死了"
  else
    bad "i3: SIGTERM 被擋掉時 SIGKILL 升級後整個測試指令 process group 真的死了（本案的 busy-loop 仍存活）"
  fi
  # 無論紅綠都收屍：這條 test 指令設計上殺不掉，防線失效時不能把孤兒留在機器上
  # 污染之後每一次執行（dogfood 的 M-no-sigkill 每跑必觸發此路徑）。
  pkill -9 -f "$D/i3.marker" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# 案 j：格式錯誤 → exit 2，且沒有任何檔被改
# ---------------------------------------------------------------------------
case_j() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  cp "$D/f1.txt" "$D/f1.orig"

  cat >"$D/j1.mutations" <<EOF
cwd: $D

file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
expect: red
EOF
  bash "$MUTATE" --batch "$D/j1.mutations" --out "$D/out1" >/dev/null 2>&1
  assert_eq "j1: 缺 id exit 2" "2" "$?"
  assert_file_eq "j1: 未動檔" "$D/f1.txt" "$D/f1.orig"

  cat >"$D/j2.mutations" <<EOF
cwd: $D

id: control
sed: s/LIMIT=5/LIMIT=999/
expect: red
EOF
  bash "$MUTATE" --batch "$D/j2.mutations" --out "$D/out2" >/dev/null 2>&1
  assert_eq "j2: 缺 file exit 2" "2" "$?"
  assert_file_eq "j2: 未動檔" "$D/f1.txt" "$D/f1.orig"

  cat >"$D/j3.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
patch: nonexist.patch
expect: red
EOF
  bash "$MUTATE" --batch "$D/j3.mutations" --out "$D/out3" >/dev/null 2>&1
  assert_eq "j3: sed+patch 並給 exit 2" "2" "$?"
  assert_file_eq "j3: 未動檔" "$D/f1.txt" "$D/f1.orig"

  cat >"$D/j4.mutations" <<EOF
cwd: $D

id: notcontrol
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
expect: red
EOF
  bash "$MUTATE" --batch "$D/j4.mutations" --out "$D/out4" >/dev/null 2>&1
  assert_eq "j4: 第一條非 control exit 2" "2" "$?"
  assert_file_eq "j4: 未動檔" "$D/f1.txt" "$D/f1.orig"

  cat >"$D/j5.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
expect: red
EOF
  bash "$MUTATE" --batch "$D/j5.mutations" --out "$D/out5" >/dev/null 2>&1
  assert_eq "j5: 沒有任何 test exit 2" "2" "$?"
  assert_file_eq "j5: 未動檔" "$D/f1.txt" "$D/f1.orig"

  # j6：漏一個空行，兩條變異的欄位擠成一個區塊（重複 key）→ exit 2，不得靜默吞掉一條。
  # 刻意讓「倖存值」是 control 自己的欄位（bogus 條寫在前面被蓋掉）——這樣重複 key 防線
  # 被拿掉時，解析結果會退化成「只剩一條合法的 control」而悄悄跑成 exit 0，不會被其他
  # 檢查（如「第一條必須是 control」）意外撞出同樣的 exit 2，才是真正的差異化測試。
  cat >"$D/j6.mutations" <<EOF
cwd: $D

id: bogus-lost-entry
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: touch "$D/j6-bogus.marker"
expect: red
id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red
EOF
  bash "$MUTATE" --batch "$D/j6.mutations" --out "$D/out6" >/dev/null 2>&1
  assert_eq "j6: 漏空行合併區塊（重複 key）exit 2" "2" "$?"
  assert_file_eq "j6: 未動 f1.txt" "$D/f1.txt" "$D/f1.orig"
  assert_not_exists "j6: bogus 條的 test 沒被跑到（本來就該連解析都過不了）" "$D/j6-bogus.marker"

  # j7：未知 key（拼錯，如 expcet）→ exit 2
  cat >"$D/j7.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expcet: red
EOF
  bash "$MUTATE" --batch "$D/j7.mutations" --out "$D/out7" >/dev/null 2>&1
  assert_eq "j7: 未知 key（拼錯）exit 2" "2" "$?"
  assert_file_eq "j7: 未動檔" "$D/f1.txt" "$D/f1.orig"

  # j7b：全域預設區塊（第一個無 id 的區塊）含拼錯 key（cwdd 而非 cwd）→ exit 2；
  # j7 只驗了「條目區塊」的未知 key 防線，全域區塊是另一段獨立檢查，沒有案覆蓋過。
  cat >"$D/j7b.mutations" <<EOF
cwd: $D
cwdd: bogus

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: touch "$D/j7b-control.marker"
expect: red

id: M1
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: touch "$D/j7b-m1.marker"
expect: red
EOF
  bash "$MUTATE" --batch "$D/j7b.mutations" --out "$D/out7b" >/dev/null 2>&1
  assert_eq "j7b: 全域區塊未知 key（拼錯 cwdd）exit 2" "2" "$?"
  assert_file_eq "j7b: 未動檔" "$D/f1.txt" "$D/f1.orig"
  assert_not_exists "j7b: control 沒跑（marker 不存在）" "$D/j7b-control.marker"
  assert_not_exists "j7b: 後續條目 M1 沒跑（marker 不存在）" "$D/j7b-m1.marker"

  # j8：id 含 / 或 ../ → exit 2，且未動檔。刻意放在「第二條」（control 之外）：
  # 放第一條的話，格式檢查被拿掉時仍會被「第一條必須是 control」意外撞出同樣的 exit 2，
  # 測不出這條防線真的有沒有在用（id="sub/dir" 這種非法 id 本來就不可能等於 "control"）。
  cat >"$D/j8a.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: sub/dir
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: true
expect: red
EOF
  bash "$MUTATE" --batch "$D/j8a.mutations" --out "$D/out8a" >/dev/null 2>&1
  assert_eq "j8: id 含 / exit 2" "2" "$?"
  assert_file_eq "j8: id 含 / 時未動檔" "$D/f1.txt" "$D/f1.orig"

  cat >"$D/j8b.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: ../escape
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: true
expect: red
EOF
  bash "$MUTATE" --batch "$D/j8b.mutations" --out "$D/out8b" >/dev/null 2>&1
  assert_eq "j8: id 含 ../ exit 2" "2" "$?"
  assert_file_eq "j8: id 含 ../ 時未動檔" "$D/f1.txt" "$D/f1.orig"
  assert_not_exists "j8: id 含 ../ 沒有寫檔逃出 --out（\$D/escape.log 不存在）" "$D/escape.log"
}

# ---------------------------------------------------------------------------
# 案 k：單條模式回歸（既有行為一字不變）
# ---------------------------------------------------------------------------
case_k() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f.txt"
  local out rc
  out="$(cd "$D" && bash "$MUTATE" --file f.txt --sed 's/LIMIT=5/LIMIT=9/' --test "grep -q 'LIMIT=5' f.txt" 2>&1)"
  rc=$?
  assert_eq "k1: exit 0" "0" "$rc"
  assert_contains "k1: 輸出含 [結論] 紅" "$out" "[結論] 紅"

  printf 'LIMIT=5\n' >"$D/f2.txt"
  local out2 rc2
  out2="$(cd "$D" && bash "$MUTATE" --file f2.txt --sed 's/NOPE_NOT_PRESENT/xxx/' --test "true" 2>&1)"
  rc2=$?
  assert_eq "k2: sed 不匹配 exit 3" "3" "$rc2"
  assert_contains "k2: stderr 含 diff 為空" "$out2" "diff 為空"
  assert_contains "k2: stderr 含 判 FAIL" "$out2" "判 FAIL"

  printf 'FOO=bar\n' >"$D/f3.txt"
  local out3 rc3
  out3="$(cd "$D" && bash "$MUTATE" --file f3.txt --sed 's/FOO=bar/FOO=bar2/' --test "true" 2>&1)"
  rc3=$?
  assert_eq "k3: 變異存活(綠) exit 4" "4" "$rc3"
  assert_contains "k3: stdout 含 [結論] 綠 ✗ — 變異存活" "$out3" "[結論] 綠 ✗ — 變異存活"
}

# ---------------------------------------------------------------------------
# 案 l：cwd 優先序 — --cwd 覆寫清單檔 cwd:
# ---------------------------------------------------------------------------
case_l() {
  local D; newtmp; D="$NEWTMP"
  local A="$D/A" B="$D/B"
  mkdir -p "$A" "$B"
  printf 'LIMIT=5\n' >"$A/f1.txt"
  printf 'LIMIT=5\n' >"$B/f1.txt"
  cp "$A/f1.txt" "$A/f1.orig"
  cp "$B/f1.txt" "$B/f1.orig"
  cat >"$D/list.mutations" <<EOF
cwd: $A

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: touch marker.txt && grep -q 'LIMIT=5' f1.txt
expect: red
EOF
  bash "$MUTATE" --batch "$D/list.mutations" --out "$D/outA" >/dev/null 2>&1
  assert_exists "l: 未帶 --cwd 時改 A（A/marker.txt 存在）" "$A/marker.txt"
  assert_not_exists "l: 未帶 --cwd 時不動 B（B/marker.txt 不存在）" "$B/marker.txt"
  assert_file_eq "l: A/f1.txt 還原一致" "$A/f1.txt" "$A/f1.orig"

  bash "$MUTATE" --batch "$D/list.mutations" --cwd "$B" --out "$D/outB" >/dev/null 2>&1
  assert_exists "l: 帶 --cwd B 時改 B（B/marker.txt 存在）" "$B/marker.txt"
  assert_file_eq "l: B/f1.txt 還原一致" "$B/f1.txt" "$B/f1.orig"
}

# ---------------------------------------------------------------------------
# 案 m：還原失敗中止 — chmod 444 讓 cp 還原 permission denied
# ---------------------------------------------------------------------------
case_m() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  printf 'BAZ=1\n' >"$D/f3.txt"
  chmod 444 "$D/f2.txt"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/FOO=bar/FOO=baz/
test: true
expect: red

id: M2
file: f3.txt
sed: s/BAZ=1/BAZ=2/
test: touch "$D/marker.txt"
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  chmod 644 "$D/f2.txt" 2>/dev/null || true
  assert_eq "m: 還原失敗 exit 1" "1" "$rc"
  assert_not_exists "m: 第三條沒跑（marker 不存在）" "$D/marker.txt"

  local bkpath
  bkpath="$(printf '%s' "$out" | grep -oE '備份留在 [^；]*' | sed 's/^備份留在 //' | tail -1)"
  if [ -n "$bkpath" ]; then
    ok "m: 輸出含備份檔路徑"
    assert_exists "m: 備份檔確實存在（未被誤刪）" "$bkpath"
    rm -f "$bkpath" 2>/dev/null || true
  else
    bad "m: 輸出含備份檔路徑 (找不到「備份留在 」字串)"
  fi
}

# ---------------------------------------------------------------------------
# 案 n：--out 產物 — 逐條 log 含 diff／測試輸出，summary.txt 與 stdout 逐行相同（忽略 secs）
# ---------------------------------------------------------------------------
case_n() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf 'FOO=bar\n' >"$D/f2.txt"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: echo CONTROL_TEST_OUTPUT_XYZ; grep -q 'LIMIT=5' f1.txt
expect: red

id: M1
file: f2.txt
sed: s/FOO=bar/FOO=baz/
test: echo M1_TEST_OUTPUT_XYZ; grep -q 'FOO=bar' f2.txt
expect: red
EOF
  local out
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/o" 2>&1)"

  assert_exists "n: control.log 存在" "$D/o/control.log"
  assert_exists "n: M1.log 存在" "$D/o/M1.log"
  if grep -qE '^[+-][^+-]' "$D/o/control.log"; then ok "n: control.log 含變異 diff 行"; else bad "n: control.log 含變異 diff 行"; fi
  if grep -qE '^[+-][^+-]' "$D/o/M1.log"; then ok "n: M1.log 含變異 diff 行"; else bad "n: M1.log 含變異 diff 行"; fi
  assert_contains "n: control.log 含測試輸出字串" "$(cat "$D/o/control.log")" "CONTROL_TEST_OUTPUT_XYZ"
  assert_contains "n: M1.log 含測試輸出字串" "$(cat "$D/o/M1.log")" "M1_TEST_OUTPUT_XYZ"
  assert_exists "n: summary.txt 存在" "$D/o/summary.txt"

  local stdout_nosecs summary_nosecs
  stdout_nosecs="$(printf '%s\n' "$out" | sed -E 's/ \| [0-9]+$//')"
  summary_nosecs="$(sed -E 's/ \| [0-9]+$//' "$D/o/summary.txt")"
  assert_eq "n: summary.txt 與 stdout 逐行相同（忽略 secs）" "$stdout_nosecs" "$summary_nosecs"
}

# ---------------------------------------------------------------------------
# 案 o：全註解變異 → 印警告字串，且該條因測試綠而 FAIL
# ---------------------------------------------------------------------------
case_o() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  printf '# NOTE: LIMIT default\nFOO=bar\n' >"$D/f2.txt"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red

id: M-comment
file: f2.txt
sed: s/# NOTE: LIMIT default/# NOTE: LIMIT changed/
test: grep -q 'FOO=bar' f2.txt
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  assert_contains "o: 含全註解警告字串" "$out" "所有變動行看起來都是註解"
  assert_contains "o: 總結含 1 FAIL" "$out" "1 FAIL"
  assert_row_field "o: M-comment 那一列 verdict 為 FAIL（逐列，不靠總結計數）" "$out" "M-comment" 6 "FAIL"
  assert_eq "o: exit 4" "4" "$rc"
}

# ---------------------------------------------------------------------------
# 案 procsub：test: 含 <(...) 這種 bash 專屬語法要能正常判紅綠
# （改走 bash -c 之前，走 /bin/sh 的話這裡會直接語法錯，不是判斷紅綠的問題）
# ---------------------------------------------------------------------------
case_procsub() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: diff <(grep LIMIT= f1.txt) <(printf 'LIMIT=5\n')
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --out "$D/out" 2>&1)"
  rc=$?
  assert_eq "procsub: <(...) 可正常判紅（exit 0）" "0" "$rc"
  assert_row_field "procsub: control 那一列 verdict 為 PASS" "$out" "control" 6 "PASS"
  # 語法錯的訊息在測試指令自己的 stderr 裡，只會出現在逐條 log（--out/<id>.log），
  # 不會出現在結果表（$out）——早先誤查 $out，走 /bin/sh 語法錯照樣「巧合」判紅過。
  # 先斷 log 檔真的存在，否則下面用 cat ... 2>/dev/null 讀不到檔案時會是空字串，
  # assert_not_contains 對空字串恆過，測不出「檔案根本沒生出來」這種更糟的情況。
  assert_exists "procsub: control.log 存在（下面那條斷言的前提）" "$D/out/control.log"
  assert_not_contains "procsub: log 裡沒有 shell 語法錯（沒有巧合走到 /bin/sh 才紅）" "$(cat "$D/out/control.log" 2>/dev/null)" "syntax error"
}

# ---------------------------------------------------------------------------
# 案 default-out：不傳 --out 時，全批模式仍落在 <清單目錄>/mutate-out/
# ---------------------------------------------------------------------------
case_default_out() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  cat >"$D/list.mutations" <<EOF
cwd: $D

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red
EOF
  bash "$MUTATE" --batch "$D/list.mutations" >/dev/null 2>&1
  assert_exists "default-out: 全批模式預設 <清單目錄>/mutate-out/summary.txt 存在" "$D/mutate-out/summary.txt"

  # --check 沒給 --out 時是唯一例外：不落地，清單旁不該有 mutate-out/
  local D2; newtmp; D2="$NEWTMP"
  printf 'LIMIT=5\n' >"$D2/f1.txt"
  cat >"$D2/list.mutations" <<EOF
cwd: $D2

id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red
EOF
  bash "$MUTATE" --batch "$D2/list.mutations" --check >/dev/null 2>&1
  assert_not_exists "default-out: --check 沒給 --out 時清單旁沒有 mutate-out/" "$D2/mutate-out"
}

# ---------------------------------------------------------------------------
# 案 comment-syntax：清單檔含 # 開頭註解行仍可正常解析
# ---------------------------------------------------------------------------
case_comment_syntax() {
  local D; newtmp; D="$NEWTMP"
  printf 'LIMIT=5\n' >"$D/f1.txt"
  cat >"$D/list.mutations" <<EOF
# 這是註解行，勿直接對 worktree 執行（範例）
cwd: $D

# 這行也是註解，出現在區塊中間不該打斷解析
id: control
file: f1.txt
sed: s/LIMIT=5/LIMIT=999/
test: grep -q 'LIMIT=5' f1.txt
expect: red
EOF
  local out rc
  out="$(bash "$MUTATE" --batch "$D/list.mutations" --check --out "$D/out" 2>&1)"
  rc=$?
  assert_eq "comment-syntax: 含 # 註解行仍可解析、--check exit 0" "0" "$rc"
  assert_contains "comment-syntax: control applied=yes" "$out" "control | yes"
}

# ---------------------------------------------------------------------------
# 案 dogfood-list-guard：直接對 worktree 跑 dogfood 清單（沒帶 --cwd 覆寫）
# 必須在解析期就安全失敗，不得碰到活的 bin/mutate-batch.py
# ---------------------------------------------------------------------------
case_dogfood_list_guard() {
  local REPO_ROOT; REPO_ROOT="$(cd "$(dirname "$MUTATE")/.." && pwd)"
  local LIST="$REPO_ROOT/bin/tests/mutate-batch.mutations"
  local LIVE="$REPO_ROOT/bin/mutate-batch.py"
  local before_sha after_sha
  before_sha="$(shasum -a 256 "$LIVE" | awk '{print $1}')"
  bash "$MUTATE" --batch "$LIST" >/dev/null 2>&1
  local rc=$?
  after_sha="$(shasum -a 256 "$LIVE" | awk '{print $1}')"
  assert_eq "dogfood-list-guard: 直接對 worktree 跑（沒帶 --cwd）exit 2" "2" "$rc"
  assert_eq "dogfood-list-guard: bin/mutate-batch.py 跑前跑後 shasum 相同（沒被動過）" "$before_sha" "$after_sha"
}

echo "===== bin/mutate --batch/--check 驗收測試（a-o） ====="
case_a
case_b
case_c
case_d
case_e
case_f
case_g
case_h
case_i
case_i2
case_i3
case_j
case_k
case_l
case_m
case_n
case_o
case_procsub
case_default_out
case_comment_syntax
case_dogfood_list_guard

# 驗證 newtmp() 的洩漏修復：手動先清一次（EXIT trap 稍後會再呼叫一次，
# TMP_DIRS 到那時已經沒有存在的目錄了，是安全的 no-op），再逐一檢查本次自己建立
# 的每個目錄是否真的消失——不數共享 $TMPDIR 底下符合前綴的目錄總量：那個數字包含
# 其他行程（例如 run_dogfood.sh 一次跑 17 條、每條起一份套件；或大腦同時跑另一份
# 驗證）同時建立的同名前綴目錄，會被誤判成「洩漏」（reviewer 已用外部目錄重現過）。
CREATED_TMP_DIR_COUNT="${#TMP_DIRS[@]}"
# 反向檢查：TMP_DIRS 記帳本身要有效，否則下面「逐一檢查已消失」這條斷言在
# TMP_DIRS 空空如也時會恆真通過——這正是最早那個 subshell 記帳 bug 的樣子
# （newtmp 在 command substitution 裡跑，TMP_DIRS+= 只改到 subshell 自己的
# 副本，父層陣列永遠是空的），跑起來會實際洩漏一堆目錄卻顯示「無洩漏」。
# 門檻 20 ＝ 目前 newtmp 呼叫點數（25）的保守下限；刪併案例到 20 個以下時同步調低，
# 否則這條反向斷言會失去「記帳有效」的鑑別力。
if [ "$CREATED_TMP_DIR_COUNT" -ge 20 ]; then
  ok "cleanup: TMP_DIRS 記帳有效（記到 ${CREATED_TMP_DIR_COUNT} 個，>= 20）"
else
  bad "cleanup: TMP_DIRS 記帳有效（只記到 ${CREATED_TMP_DIR_COUNT} 個，太少，newtmp 記帳可能又被 subshell 吃掉）"
fi
cleanup
LEFTOVER_COUNT=0
for __d in "${TMP_DIRS[@]:-}"; do
  if [ -n "$__d" ] && [ -d "$__d" ]; then
    LEFTOVER_COUNT=$((LEFTOVER_COUNT + 1))
  fi
done
assert_eq "cleanup: 本次建立的 ${CREATED_TMP_DIR_COUNT} 個暫存目錄跑完後全部被清掉（逐一檢查，不數共享 TMPDIR）" "0" "$LEFTOVER_COUNT"

echo "===== 總結：$PASS_COUNT PASS / $FAIL_COUNT FAIL ====="
[ "$FAIL_COUNT" -eq 0 ]
