#!/bin/bash
# test_diff_surface.sh — bin/diff-surface 的 seam 測試（只經 CLI：stdout + exit code）。
# 腳本路徑由 DIFF_SURFACE 決定（預設 ../diff-surface）。每案各自在 mktemp -d 下建一個 fixture git repo。
set -u
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

DIFF_SURFACE="${DIFF_SURFACE:-$(cd "$(dirname "$0")/.." && pwd)/diff-surface}"

PASS_COUNT=0
FAIL_COUNT=0
TMP="$(mktemp -d "${TMPDIR:-/tmp}/diff-surface-test.XXXXXX")"
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

CASE_N=0
new_repo() {
  CASE_N=$((CASE_N + 1))
  REPO="$TMP/repo$CASE_N"
  mkdir -p "$REPO"
  (
    cd "$REPO" && git init -q && git config user.email t@example.com && git config user.name t \
      && printf '# readme\n' > README.md && git add README.md && git commit -q -m init && git tag base
  ) >/dev/null 2>&1
}

put() { # put <path> <內容>：寫檔（含上層目錄）
  mkdir -p "$REPO/$(dirname "$1")"
  printf '%s\n' "$2" > "$REPO/$1"
}

commit_all() {
  (cd "$REPO" && git add -A && git commit -q -m change) >/dev/null 2>&1
}

run() { # run <args...>：OUT＝stdout，ERR 併入 OUT 不處理；RC＝exit
  OUT="$("$DIFF_SURFACE" --repo "$REPO" --base base "$@" 2>&1)"
  RC=$?
}

section() { # section <標題>：印出該標題到下一個 "## " 前的內容
  printf '%s\n' "$OUT" | awk -v t="## $1" '$0==t{on=1;next} /^## /{on=0} on'
}

echo "--- 改動面 ---"
new_repo; put svc/a.go 'package a'; commit_all; run
assert_eq "只改 .go → 後端" "後端" "$(section 改動面)"
new_repo; put web/a.vue '<template/>'; commit_all; run
assert_eq "只改 .vue → 前端" "前端" "$(section 改動面)"
new_repo; put svc/a.go 'package a'; put web/a.vue '<template/>'; commit_all; run
assert_eq "go＋vue → 前後端" "前後端" "$(section 改動面)"
new_repo; put docs/a.md 'hi'; commit_all; run
assert_eq "只改 .md → 無程式碼" "無程式碼" "$(section 改動面)"
assert_eq "exit 0" 0 "$RC"

echo "--- migration／db-reviewer／lane 下限 ---"
new_repo; put db/migrations/001_x.sql 'create table t(id int);'; commit_all; run
assert_contains "migration 命中" "$(section 命中類別)" "migration"
assert_contains "migration 列出檔案" "$(section 命中類別)" "db/migrations/001_x.sql"
assert_contains "reviewer 含 db-reviewer" "$(section reviewer)" "db-reviewer"
assert_contains "lane 下限 /feature" "$(section 'lane 下限')" "/feature（硬排除：migration）"
assert_contains "code-reviewer 一律列" "$(section reviewer)" "code-reviewer"
new_repo; put tools/q.sql 'select 1;'; commit_all; run
assert_contains "有 .sql 檔 → db-reviewer" "$(section reviewer)" "db-reviewer"
assert_eq "非 migration 的 .sql → lane 下限無" "無" "$(section 'lane 下限')"

echo "--- 金流 ---"
new_repo; put services/withdraw_fee.go 'package s'; commit_all; run
assert_contains "金流命中" "$(section 命中類別)" "金流"
assert_contains "金流列出檔案" "$(section 命中類別)" "services/withdraw_fee.go"
assert_contains "reviewer 含 security-reviewer" "$(section reviewer)" "security-reviewer"
assert_contains "lane 下限含金流" "$(section 'lane 下限')" "金流"

echo "--- 認證 ---"
new_repo; put svc/util.go 'package s
password := "x"'; commit_all; run
assert_contains "新增行含 password → 認證" "$(section 命中類別)" "認證"
assert_contains "認證報出檔案與行號" "$(section 命中類別)" "svc/util.go:2"
assert_contains "認證 → security-reviewer" "$(section reviewer)" "security-reviewer"
new_repo; put svc/jwt_helper.go 'package s'; commit_all; run
assert_contains "路徑含 jwt → 認證" "$(section 命中類別)" "svc/jwt_helper.go"
new_repo; put svc/util.go 'package s
func f() {}'; commit_all; run
assert_not_contains "無關鍵字不命中認證" "$(section 命中類別)" "認證"

echo "--- nginx／全域配置 ---"
new_repo; put deploy/nginx/site.conf 'server {}'; commit_all; run
assert_contains "nginx 命中" "$(section 命中類別)" "nginx"
assert_contains "nginx → code-reviewer 加 nginx 檢查項" "$(section reviewer)" "code-reviewer 加 nginx 檢查項"
assert_eq "nginx 單獨不觸發 lane 下限" "無" "$(section 'lane 下限')"
new_repo; put settings.json '{}'; commit_all; run
assert_contains "settings.json → 全域配置" "$(section 命中類別)" "全域配置"
assert_contains "全域配置 → lane 下限" "$(section 'lane 下限')" "/feature（硬排除：全域配置）"
new_repo; put .github/workflows/ci.yml 'on: push'; put .env.local 'A=1'; commit_all; run
assert_contains "workflows 命中全域配置" "$(section 命中類別)" ".github/workflows/ci.yml"
assert_contains ".env.local 命中全域配置" "$(section 命中類別)" ".env.local"

echo "--- bruno-sync ---"
new_repo; mkdir -p "$REPO/bruno"; put bruno/README.md 'x'; commit_all
put api/handler/user.go 'package h'; commit_all
(cd "$REPO" && git tag base2 HEAD~1) >/dev/null 2>&1
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base base2 2>&1)"
assert_eq "有 bruno/ 且改 handler → 需要" "需要" "$(section bruno-sync)"
new_repo; mkdir -p "$REPO/bruno"; put bruno/README.md 'x'; commit_all
put svc/calc.go 'package c'; commit_all
(cd "$REPO" && git tag base2 HEAD~1) >/dev/null 2>&1
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base base2 2>&1)"
assert_eq "有 bruno/ 未命中 → 不需要" "不需要" "$(section bruno-sync)"
new_repo; put api/handler/user.go 'package h'; commit_all; run
assert_eq "無 bruno/ → 無 bruno/" "無 bruno/" "$(section bruno-sync)"

echo "--- stat ---"
new_repo; put svc/a.go 'package a'; commit_all; run
assert_contains "stat 含檔名" "$(section stat)" "svc/a.go"
assert_contains "stat 含摘要" "$(section stat)" "1 file changed"

echo "--- 新增註解行 ---"
new_repo
put svc/a.go 'package a
// go comment
func f() {}'
put tools/b.py 'import os
x = 1
# py comment'
put web/c.vue '<template>
<!-- vue comment -->
</template>'
put scripts/d.sh '#!/bin/bash
echo hi'
commit_all; run
C="$(section 新增註解行)"
assert_contains "註解總數 3" "$C" "共 3 行"
assert_contains "Go 註解行號" "$C" "svc/a.go:2 // go comment"
assert_contains "Python 註解行號" "$C" "tools/b.py:3 # py comment"
assert_contains "Vue 註解行號" "$C" "web/c.vue:2 <!-- vue comment -->"
assert_not_contains "shebang 不算" "$C" "scripts/d.sh"
new_repo
put svc/big.go "$(for i in $(seq 1 55); do echo "// c$i"; done)"
commit_all; run
C="$(section 新增註解行)"
assert_contains "超過 50 筆：總數" "$C" "共 55 行"
assert_contains "超過 50 筆：另有 5 筆" "$C" "另有 5 筆"
assert_not_contains "超過 50 筆：第 51 筆不印" "$C" "svc/big.go:51 "

echo "--- --json ---"
new_repo; put services/withdraw_fee.go 'package s
// c'; put docs/x.md 'x'; commit_all; run --json
printf '%s' "$OUT" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null
assert_eq "--json 可解析" 0 $?
KEYS="$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(" ".join(sorted(json.load(sys.stdin))))' 2>/dev/null)"
assert_eq "--json 欄位" "bruno_sync categories lane_floor new_comments reviewer_floor_note reviewers stat surface" "$KEYS"

echo "--- --include-worktree ---"
new_repo; put svc/a.go 'package a'; commit_all
put web/new.vue '<template/>'; printf 'package a\n// edit\n' > "$REPO/svc/a.go"
run
assert_eq "不帶旗標：未 commit 不計" "後端" "$(section 改動面)"
run --include-worktree
assert_eq "帶旗標：未 commit（含 untracked）計入" "前後端" "$(section 改動面)"
assert_contains "帶旗標：新增註解含 worktree 行" "$(section 新增註解行)" "svc/a.go:2 // edit"
assert_eq "帶旗標後 index 不被動到（untracked 仍 untracked）" "?? web/new.vue" "$(git -C "$REPO" status --short -uall | grep new.vue)"

new_repo; put svc/a.go 'package a'; commit_all
(cd "$REPO" && git branch trunk && git checkout -q -b feat) >/dev/null 2>&1
put svc/feat.go 'package a'; commit_all
(cd "$REPO" && git checkout -q trunk) >/dev/null 2>&1
put svc/main_only.go 'package a'; commit_all
(cd "$REPO" && git checkout -q feat) >/dev/null 2>&1
put web/wip.vue '<template/>'
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base trunk --include-worktree 2>&1)"
assert_not_contains "--include-worktree 用 merge-base：base 側 fork 後的提交不計入" "$OUT" "main_only.go"
assert_contains "--include-worktree 仍計入 feature 分支與未追蹤檔" "$OUT" "web/wip.vue"
new_repo; put web/only.vue '<template/>'
run --include-worktree
assert_eq "只有未追蹤新檔 → 計入" "前端" "$(section 改動面)"
assert_contains "只有未追蹤新檔 → stat 列出" "$(section stat)" "web/only.vue"
run
assert_eq "只有未追蹤新檔、不帶旗標 → 不計入" "無程式碼" "$(section 改動面)"

echo "--- --head ---"
new_repo; put svc/a.go 'package a'; commit_all; (cd "$REPO" && git tag mid) >/dev/null 2>&1
put web/a.vue '<template/>'; commit_all
run --head mid
assert_eq "--head 限定範圍" "後端" "$(section 改動面)"

hit_case() { # hit_case <desc> <path> <內容> <類別>
  new_repo; put "$2" "$3"; commit_all; run
  assert_line "$1" "$(section 命中類別)" "$4："
}
miss_case() {
  new_repo; put "$2" "$3"; commit_all; run
  assert_not_contains "$1" "$(section 命中類別)" "$4："
}
comment_case() { # comment_case <desc> <path> <內容>
  new_repo; put "$2" "$3"; commit_all; run
  assert_contains "$1" "$(section 新增註解行)" "共 1 行"
}

echo "--- 全域配置 8 形狀 ---"
for f in .env .env.x CLAUDE.md AGENTS.md Dockerfile docker-compose.prod.yml .gitlab-ci.yml .github/workflows/ci.yml; do
  hit_case "全域配置：$f" "$f" 'x' 全域配置
  assert_contains "全域配置 lane 下限：$f" "$(section 'lane 下限')" "全域配置"
done

echo "--- 認證路徑關鍵字 ---"
for kw in auth login logout session token jwt oauth password totp permission rbac credential guard acl; do
  hit_case "認證路徑：$kw" "svc/${kw}_x.go" 'package s' 認證
done
for f in .env .env.prod keys/server.pem keys/id.key svc/credentials.go; do
  hit_case "認證（憑證檔）：$f" "$f" 'x' 認證
done
assert_contains "憑證檔 → security-reviewer" "$(section reviewer)" "security-reviewer"

echo "--- 金流路徑關鍵字 ---"
for kw in pay payee withdraw deposit wallet recharge settle rebate bonus cash finance; do
  hit_case "金流路徑：$kw" "svc/${kw}_x.go" 'package s' 金流
done

echo "--- 內容關鍵字只掃非測試檔 ---"
for f in svc/util_test.go tests/fixture.go src/test/Foo.java web/a.spec.ts web/a.test.ts scripts/test_x.py; do
  miss_case "測試檔內容關鍵字不報：$f" "$f" 'password := "x"' 認證
done
hit_case "測試檔路徑關鍵字照舊：tests/auth_helper_test.go" "tests/auth_helper_test.go" 'package t' 認證
hit_case "名稱含 test 的非測試檔仍掃內容：svc/contest.go" "svc/contest.go" 'password := "x"' 認證

echo "--- 內容行號精確性 ---"
new_repo
put svc/a.go "$(printf 'password := "old"\nx2\nx3\nx4\nx5\nx6\nx7\nx8\nx9\nprivate_key := "gone"')"
commit_all; (cd "$REPO" && git tag base2) >/dev/null 2>&1
put svc/a.go "$(printf 'password := "old"\nx2\ny3\nx4\nx5\nx6\nx7\napi_key := "n"\nx9')"
commit_all
run --base base2
assert_line "只報新增行：第 2 個 hunk 的 svc/a.go:8（不含 base 既有第 1 行、不含刪除行）" "$(section 命中類別)" "  - svc/a.go:8"

echo "--- 註解反例 ---"
new_repo
put web/a.css '#id {
  color: red;
}'
put svc/b.go 'package b
#define X 1'
put docs/c.md '<!-- note -->'
commit_all; run
assert_contains "css #id、go # 行、md <!-- 都不計入" "$(section 新增註解行)" "共 0 行"

echo "--- 註解標記各一格 ---"
comment_case "Go /* 註解" svc/a.go '/* c */'
comment_case "SQL -- 註解" tools/a.sql '-- c'
comment_case "HTML <!-- 註解" web/a.html '<!-- c -->'
comment_case "Ruby # 註解" svc/a.rb '# c'
comment_case "YAML # 註解" conf/a.yml '# c'
comment_case "TOML # 註解" conf/a.toml '# c'

echo "--- 其他規則各一格 ---"
new_repo; put svc/calc.go 'package c'; commit_all; run
assert_eq "全無命中 → lane 下限無" "無" "$(section 'lane 下限')"
assert_eq "全無命中 → 命中類別無" "無" "$(section 命中類別)"
assert_contains "reviewer 段印下限說明" "$(section reviewer)" "下限：大腦可依觸發表加派；不偵測：不可逆操作、/mvp 專案"
run --json
assert_eq "JSON 帶 reviewer_floor_note" "下限：大腦可依觸發表加派；不偵測：不可逆操作、/mvp 專案" \
  "$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["reviewer_floor_note"])')"
new_repo; put svc/schema_def.go 'package s'; commit_all; run
assert_contains "路徑含 schema → db-reviewer" "$(section reviewer)" "db-reviewer"
assert_eq "路徑含 schema 不設 lane 下限" "無" "$(section 'lane 下限')"

echo "--- 非 .sql 的 migration ---"
for f in db/migrate/001_x.rb alembic/versions/x.py; do
  hit_case "migration：$f" "$f" 'x = 1' migration
  assert_contains "db-reviewer：$f" "$(section reviewer)" "db-reviewer"
  assert_contains "lane 下限 /feature：$f" "$(section 'lane 下限')" "/feature（硬排除：migration）"
done

echo "--- 中文檔名、rename、刪除 ---"
new_repo; put 'services/提現_withdraw.go' 'package s'; put '服務/登入.go' 'package s
password := "x"'; commit_all; run
assert_contains "中文檔名不被引號化（命中類別）" "$(section 命中類別)" "services/提現_withdraw.go"
assert_contains "中文檔名不被引號化（stat）" "$(section stat)" "服務/登入.go"
assert_contains "中文檔名內容行號" "$(section 命中類別)" "服務/登入.go:2"
new_repo
put db/migrations/001_x.sql 'select 1;'; put lib/a.go 'package a'; put services/pay.go 'package s'
commit_all; (cd "$REPO" && git tag base2) >/dev/null 2>&1
(cd "$REPO" && git mv db/migrations/001_x.sql docs_x.md && git mv lib/a.go services/withdraw_fee.go \
  && git mv services/pay.go lib/b.go) >/dev/null 2>&1
commit_all; run --base base2
assert_contains "rename：舊路徑納入判定（migration）" "$(section 命中類別)" "db/migrations/001_x.sql"
assert_contains "rename：新路徑納入判定（金流）" "$(section 命中類別)" "services/withdraw_fee.go"
assert_contains "rename：舊路徑納入判定（金流）" "$(section 命中類別)" "services/pay.go"
new_repo; put db/migrations/002_y.sql 'select 1;'; commit_all; (cd "$REPO" && git tag base2) >/dev/null 2>&1
(cd "$REPO" && git rm -q db/migrations/002_y.sql) >/dev/null 2>&1; commit_all; run --base base2
assert_contains "刪除 migration 也算命中" "$(section 命中類別)" "db/migrations/002_y.sql"
assert_contains "刪除 migration → db-reviewer" "$(section reviewer)" "db-reviewer"

echo "--- 使用者 git config 不得影響 diff 解析（diff.noprefix／mnemonicPrefix）---"
for cfg in diff.noprefix diff.mnemonicPrefix; do
  for mode in default worktree; do
    new_repo; (cd "$REPO" && git config "$cfg" true) >/dev/null 2>&1
    put svc/util.go 'package s
password := "x"
// note'
    flag=""
    if [ "$mode" = worktree ]; then flag="--include-worktree"; else commit_all; fi
    run $flag
    assert_contains "${cfg}／${mode}：內容行號仍報出" "$(section 命中類別)" "svc/util.go:2"
    assert_contains "${cfg}／${mode}：註解仍報出" "$(section 新增註解行)" "svc/util.go:3 // note"
  done
done

echo "--- 全域配置補強 ---"
for f in Dockerfile.ci deploy/app.dockerfile docker-compose.yaml deploy/compose.yml compose.override.yaml \
  config/config-prod.yml config/app.prod.toml config/prod.json conf/config/app-prod.yaml; do
  hit_case "全域配置：$f" "$f" 'x' 全域配置
done
for f in src/config/app.yml svc/prod.yml config/config-prod.go docs/compose.md; do
  miss_case "非全域配置：$f" "$f" 'x' 全域配置
done
hit_case "認證路徑：middleware/admin_guard.go" "middleware/admin_guard.go" 'package m' 認證
hit_case "認證路徑：middleware/acl.go" "middleware/acl.go" 'package m' 認證

echo "--- DB schema 類 ---"
hit_case "DB schema：.sql" tools/q.sql 'select 1;' "DB schema"
hit_case "DB schema：路徑含 schema" svc/schema_def.go 'package s' "DB schema"
assert_contains "DB schema 列出觸發檔案" "$(section 命中類別)" "svc/schema_def.go"
assert_eq "DB schema 不計入 lane 下限" "無" "$(section 'lane 下限')"
new_repo; put docs/schema.md '# schema'; put docs/schema.txt 'schema'; commit_all; run
assert_not_contains "docs/schema.md／.txt 不派 db-reviewer" "$(section reviewer)" "db-reviewer"
assert_not_contains "docs/schema.md／.txt 不算 DB schema" "$(section 命中類別)" "DB schema："

echo "--- rename 不重報舊內容 ---"
for mode in default worktree; do
  new_repo; put svc/old.go 'package a
// keep this comment'
  commit_all; (cd "$REPO" && git tag base2) >/dev/null 2>&1
  (cd "$REPO" && git mv svc/old.go svc/new.go) >/dev/null 2>&1
  flag=""
  if [ "$mode" = worktree ]; then flag="--include-worktree"; else commit_all; fi
  run --base base2 $flag
  assert_contains "git mv 後不重報註解（${mode}）" "$(section 新增註解行)" "共 0 行"
  assert_contains "git mv 後新路徑仍列入 stat（${mode}）" "$(section stat)" "svc/new.go"
done

echo "--- 內容關鍵字 secret／前後端副檔名／bruno 關鍵字／註解補格 ---"
hit_case "內容關鍵字 secret" svc/util.go 'secret = "x"' 認證
hit_case "內容關鍵字 private_key" svc/util.go 'private_key = "x"' 認證
hit_case "內容關鍵字 api_key" svc/util.go 'API_KEY = "x"' 認證
for ext in .vue .ts .tsx .js .jsx .css .scss .less .html .dart .swift; do
  new_repo; put "x/a$ext" 'x'; commit_all; run
  assert_eq "前端副檔名 $ext" "前端" "$(section 改動面)"
done
for ext in .go .py .java .kt .rs .sql .rb .php .sh; do
  new_repo; put "x/a$ext" 'x'; commit_all; run
  assert_eq "後端副檔名 $ext" "後端" "$(section 改動面)"
done
for kw in router route controller dto endpoint; do
  new_repo; mkdir -p "$REPO/bruno"; put bruno/README.md 'x'; commit_all
  put "svc/${kw}_x.go" 'package s'; commit_all
  (cd "$REPO" && git tag base2 HEAD~1) >/dev/null 2>&1
  OUT="$("$DIFF_SURFACE" --repo "$REPO" --base base2 2>&1)"
  assert_eq "bruno 關鍵字：$kw → 需要" "需要" "$(section bruno-sync)"
done
comment_case "Shell # 註解" scripts/a.sh '# c'
comment_case "YAML(.yaml) # 註解" conf/a.yaml '# c'

echo "--- diff.relative／--repo 指向子目錄 ---"
for mode in default worktree; do
  new_repo; put sub/keep.txt 'x'; commit_all; (cd "$REPO" && git tag base2 && git config diff.relative true) >/dev/null 2>&1
  put svc/a.go 'package a'
  flag=""
  if [ "$mode" = worktree ]; then flag="--include-worktree"; else commit_all; fi
  OUT="$("$DIFF_SURFACE" --repo "$REPO/sub" --base base2 $flag 2>&1)"
  assert_eq "子目錄 --repo 仍看到子目錄外改動：改動面（${mode}）" "後端" "$(section 改動面)"
  assert_contains "子目錄 --repo 仍看到子目錄外改動：stat（${mode}）" "$(section stat)" "svc/a.go"
done

echo "--- gitattributes -diff 的檔案仍掃內容 ---"
new_repo; put .gitattributes '*.cfg -diff'; put svc/app.cfg 'password=1'; commit_all; run
assert_contains "-diff 屬性的檔案：新增 password 仍報認證" "$(section 命中類別)" "svc/app.cfg:1"

echo "--- 搬進非測試路徑的檔案仍掃內容 ---"
new_repo; put tests/fx.go 'package a
secret := "real"'; commit_all; (cd "$REPO" && git tag base2) >/dev/null 2>&1
(cd "$REPO" && mkdir -p svc && git mv tests/fx.go svc/fx.go) >/dev/null 2>&1; commit_all; run --base base2
assert_contains "tests/ 搬到 svc/：secret 行報認證" "$(section 命中類別)" "svc/fx.go:2"

echo "--- diff.interHunkContext 不得影響行號 ---"
new_repo; put svc/a.go "$(printf 'x1\nx2\nx3\nx4\nx5\nx6\nx7\nx8')"; commit_all
(cd "$REPO" && git tag base2 && git config diff.interHunkContext 5) >/dev/null 2>&1
put svc/a.go "$(printf 'x1\ny2\nx3\nx4\napi_key := "n"\nx6\nx7\nx8')"; commit_all; run --base base2
assert_line "interHunkContext 5：hunk 合併時行號仍正確" "$(section 命中類別)" "  - svc/a.go:5"

echo "--- 全域配置名稱大小寫 ---"
hit_case "全域配置：agents.md（小寫）" agents.md 'x' 全域配置
hit_case "全域配置：DOCKERFILE.prod（大寫）" DOCKERFILE.prod 'x' 全域配置

echo "--- 錯誤處理 ---"
new_repo
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base no-such-ref 2>&1)"; RC=$?
assert_eq "不存在的 base → exit 2" 2 "$RC"
assert_contains "不存在的 base → 訊息指出 ref" "$OUT" "ref 不存在：no-such-ref"
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base base --head HEAD --include-worktree 2>&1)"; RC=$?
assert_eq "--include-worktree 與 --head 互斥 → exit 2" 2 "$RC"
OUT="$("$DIFF_SURFACE" --repo "$TMP/not-a-repo" --base base 2>&1)"; RC=$?
assert_eq "非 git 目錄 → exit 2" 2 "$RC"
"$DIFF_SURFACE" --help >/dev/null 2>&1
assert_eq "--help exit 0" 0 $?
assert_contains "--help 印用法" "$("$DIFF_SURFACE" --help 2>&1)" "--include-worktree"

echo "--- 單一 source：替身 gate-evidence ---"
ALT="$TMP/alt/bin"
mkdir -p "$ALT"
cp "$DIFF_SURFACE" "$ALT/diff-surface"
printf 'def sensitive_classes(path):\n    return {"nginx"} if path == "foo/plain.go" else set()\n' > "$ALT/gate-evidence"
new_repo; put foo/plain.go 'package foo'; put db/migrations/001_x.sql 'select 1;'; commit_all
OUT="$("$ALT/diff-surface" --repo "$REPO" --base base 2>&1)"
assert_line "替身判 nginx → 輸出命中 nginx" "$(section 命中類別)" "nginx："
assert_not_contains "替身不判 migration → 輸出不命中 migration（沒有自寫判定）" "$(section 命中類別)" "migration："
grep -qE 'MIGRATION_DIRS|sites-available' "$DIFF_SURFACE"
assert_eq "diff-surface 未自寫 migration／nginx 判定" 1 $?

echo "--- --record ---"
json_field() { # json_field <檔> <python 運算式，變數 d>
  python3 -I -c 'import json,sys; d=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' "$1" "$2"
}
fresh_state() { # 每案一個全新 state 目錄，不需刪除
  STATE="$TMP/state-$CASE_N"
  export DIFF_SURFACE_STATE="$STATE"
}
rec_file() { # rec_file <toplevel 路徑>：該 worktree 的紀錄檔（realpath 的 sha1 前 12 碼）
  printf '%s/%s.json' "$STATE" "$(printf '%s' "$(cd "$1" && pwd -P)" | shasum | cut -c1-12)"
}
file_exists() { [ -f "$1" ] && echo 1 || echo 0; }
path_exists() { [ -e "$1" ] && echo 1 || echo 0; }

new_repo; fresh_state; put svc/pay.go 'package pay'; commit_all
run --record
REC="$(rec_file "$REPO")"
HEAD_HASH="$(git -C "$REPO" rev-parse HEAD)"
assert_eq "--record exit 0" 0 "$RC"
assert_line "--record 最後一行印 RECORDED 路徑" "$(printf '%s\n' "$OUT" | tail -n 1)" "RECORDED $REC"
assert_eq "--record 寫出以 toplevel 雜湊命名的檔" 1 "$(file_exists "$REC")"
assert_eq "record.repo 是 toplevel realpath" "$(cd "$REPO" && pwd -P)" "$(json_field "$REC" 'd["repo"]')"
assert_eq "record.base" "base" "$(json_field "$REC" 'd["base"]')"
assert_eq "record.head 是 HEAD 的 hash" "$HEAD_HASH" "$(json_field "$REC" 'd["head"]')"
assert_eq "record.checkout_head 是 HEAD 的 hash" "$HEAD_HASH" "$(json_field "$REC" 'd["checkout_head"]')"
assert_eq "record.worktree 預設 False" "False" "$(json_field "$REC" 'd["worktree"]')"
assert_eq "record.reviewers" "code-reviewer,security-reviewer" "$(json_field "$REC" '",".join(d["reviewers"])')"
assert_eq "record.lane_floor" "/feature（硬排除：金流）" "$(json_field "$REC" 'd["lane_floor"]')"
assert_eq "record.categories 是類別名清單" "金流" "$(json_field "$REC" '",".join(d["categories"])')"
assert_eq "record.time 是 +00:00 形 ISO8601" 1 \
  "$(json_field "$REC" 'int(d["time"].endswith("+00:00") and __import__("datetime").datetime.fromisoformat(d["time"]).utcoffset().total_seconds()==0)')"
assert_eq "record 欄位齊全" "base,categories,checkout_head,head,lane_floor,repo,reviewers,time,worktree" "$(json_field "$REC" '",".join(sorted(d))')"

echo "--- --record：--head、--include-worktree、覆寫 ---"
new_repo; fresh_state; put svc/a.go 'package a'; commit_all
REC="$(rec_file "$REPO")"
put svc/b.go 'package b'; commit_all
OLD_HEAD="$(git -C "$REPO" rev-parse HEAD~1)"
run --head HEAD~1 --record
assert_eq "--head 指定 → record.head 為該 ref 的 hash" "$OLD_HEAD" "$(json_field "$REC" 'd["head"]')"
assert_eq "--head 指定 → record.checkout_head 仍是目前 checkout 的 HEAD" "$(git -C "$REPO" rev-parse HEAD)" "$(json_field "$REC" 'd["checkout_head"]')"
run --include-worktree --record
assert_eq "--include-worktree → record.head 為 HEAD hash" "$(git -C "$REPO" rev-parse HEAD)" "$(json_field "$REC" 'd["head"]')"
assert_eq "--include-worktree → record.worktree True" "True" "$(json_field "$REC" 'd["worktree"]')"
assert_eq "同 worktree 只留一份（覆寫）" 1 "$(ls "$STATE" | wc -l | tr -d ' ')"
put svc/auth.go 'package a'; commit_all
run --record
assert_eq "覆寫後 record 反映最新結果" "認證" "$(json_field "$REC" '",".join(d["categories"])')"

echo "--- --record：不帶旗標不寫檔、--json 保持可解析 ---"
new_repo; fresh_state; put svc/a.go 'package a'; commit_all
run
assert_eq "不帶 --record 不建 state 目錄" 0 "$(path_exists "$STATE")"
assert_not_contains "不帶 --record 不印 RECORDED" "$OUT" "RECORDED"
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base base --json --record 2>/dev/null)"; RC=$?
assert_eq "--json --record：stdout 仍是合法 JSON" 0 "$(printf '%s' "$OUT" | python3 -I -c 'import json,sys; json.load(sys.stdin)' >/dev/null 2>&1; echo $?)"
assert_eq "--json --record 寫檔" 1 "$(file_exists "$(rec_file "$REPO")")"
ERR="$("$DIFF_SURFACE" --repo "$REPO" --base base --json --record 2>&1 >/dev/null)"
assert_contains "--json --record：RECORDED 印在 stderr" "$ERR" "RECORDED $(rec_file "$REPO")"

echo "--- --record：worktree 各自一份 ---"
new_repo; fresh_state; put svc/a.go 'package a'; commit_all
WT="$TMP/wt-of-repo$CASE_N"
(cd "$REPO" && git worktree add -q -b wt-x "$WT") >/dev/null 2>&1
run --record
OUT="$("$DIFF_SURFACE" --repo "$WT" --base base --record 2>&1)"; RC=$?
assert_eq "worktree 內跑 exit 0" 0 "$RC"
assert_eq "主 checkout 與 worktree 紀錄並存" 2 "$(ls "$STATE" | wc -l | tr -d ' ')"
assert_eq "worktree 紀錄 repo 是 worktree 路徑" "$(cd "$WT" && pwd -P)" "$(json_field "$(rec_file "$WT")" 'd["repo"]')"
assert_eq "主 checkout 紀錄 repo 是主 checkout 路徑" "$(cd "$REPO" && pwd -P)" "$(json_field "$(rec_file "$REPO")" 'd["repo"]')"

echo "--- --record：空樹當 base（全 repo 總審）---"
new_repo; fresh_state; put svc/pay.go 'package pay'; commit_all
EMPTY_TREE="$(git -C "$REPO" hash-object -t tree /dev/null)"
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base "$EMPTY_TREE" --record 2>&1)"; RC=$?
assert_eq "空樹 base exit 0" 0 "$RC"
assert_contains "空樹 base：README 也在 stat" "$OUT" "README.md"
assert_contains "空樹 base：命中金流" "$(section 命中類別)" "svc/pay.go"
assert_eq "空樹 base 產生紀錄" 1 "$(file_exists "$(rec_file "$REPO")")"
assert_eq "空樹 base：record.base" "$EMPTY_TREE" "$(json_field "$(rec_file "$REPO")" 'd["base"]')"
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base "$EMPTY_TREE" --include-worktree 2>&1)"; RC=$?
assert_eq "空樹 base＋--include-worktree exit 0" 0 "$RC"
assert_contains "空樹 base＋--include-worktree：含 README" "$OUT" "README.md"

echo "--- --record：原子寫入、權限、unborn HEAD ---"
new_repo; fresh_state; put svc/a.go 'package a'; commit_all
mkdir -p "$STATE"
printf 'victim\n' > "$TMP/victim-$CASE_N"
ln -s "$TMP/victim-$CASE_N" "$(rec_file "$REPO")"
run --record
assert_eq "預置符號連結的紀錄檔：--record exit 0" 0 "$RC"
assert_eq "符號連結指向的檔案內容不變" "victim" "$(cat "$TMP/victim-$CASE_N")"
assert_eq "紀錄檔被換成一般檔（不再是符號連結）" 0 "$([ -L "$(rec_file "$REPO")" ] && echo 1 || echo 0)"
assert_eq "紀錄檔內容是合法紀錄" "base" "$(json_field "$(rec_file "$REPO")" 'd["base"]')"
assert_eq "state 目錄只留紀錄檔（無殘留暫存檔）" 1 "$(ls -A "$STATE" | wc -l | tr -d ' ')"
new_repo; fresh_state; put svc/a.go 'package a'; commit_all
run --record
assert_eq "新建 state 目錄權限 700" "0o700" "$(python3 -I -c 'import os,sys; print(oct(os.stat(sys.argv[1]).st_mode & 0o777))' "$STATE")"
assert_eq "紀錄檔權限 600" "0o600" "$(python3 -I -c 'import os,sys; print(oct(os.stat(sys.argv[1]).st_mode & 0o777))' "$(rec_file "$REPO")")"
fresh_state
REPO="$TMP/unborn$CASE_N"; mkdir -p "$REPO"
(cd "$REPO" && git init -q) >/dev/null 2>&1
put svc/a.go 'package a'
EMPTY_TREE="$(git -C "$REPO" hash-object -t tree /dev/null)"
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base "$EMPTY_TREE" --include-worktree --record 2>&1)"; RC=$?
assert_eq "unborn HEAD＋空樹 base＋--include-worktree＋--record → exit 0" 0 "$RC"
assert_eq "unborn HEAD → record.head 為 null" "None" "$(json_field "$(rec_file "$REPO")" 'd["head"]')"
assert_eq "unborn HEAD → record.checkout_head 為 null" "None" "$(json_field "$(rec_file "$REPO")" 'd["checkout_head"]')"

echo "--- --record：失敗不寫檔 ---"
new_repo; fresh_state
OUT="$("$DIFF_SURFACE" --repo "$REPO" --base no-such-ref --record 2>&1)"; RC=$?
assert_eq "base 不存在＋--record → exit 2" 2 "$RC"
assert_eq "失敗時不留 state" 0 "$(path_exists "$STATE")"
printf 'x' > "$TMP/state-is-file"
OUT="$(DIFF_SURFACE_STATE="$TMP/state-is-file" "$DIFF_SURFACE" --repo "$REPO" --base base --record 2>&1)"; RC=$?
assert_eq "state 路徑是檔案 → diff-surface exit 2" 2 "$RC"
unset DIFF_SURFACE_STATE

echo "TOTAL: $((PASS_COUNT + FAIL_COUNT))  PASS: $PASS_COUNT  FAIL: $FAIL_COUNT"
[ "$FAIL_COUNT" -eq 0 ]
