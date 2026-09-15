#!/bin/bash
# run_dogfood.sh — mutate-batch 自己的 dogfood 變異證明入口。
#
# 唯一正確跑法：`bash bin/tests/run_dogfood.sh`（從任何 cwd 皆可，路徑靠 $0 自解析）。
# 絕不要直接對 worktree 執行 `bash bin/mutate --batch bin/tests/mutate-batch.mutations`
# ——那份清單的全域 cwd: 刻意指到一個不存在的路徑（見清單檔內註解），沒帶 --cwd 覆寫
# 直接跑會在解析期就以「目標檔不存在」exit 2，防的正是誤觸真檔案這件事；
# 就算哪天清單被改掉這個保險失效，也不該對「活的」bin/mutate-batch.py 做變異
# ——跟 brief 要求的「被變異的只有副本」相反。
# 本腳本負責：mktemp -d → cp -R bin 到副本 → 對副本跑 --check 與 --batch
# （皆帶 --cwd 指向副本）→ 用「跑前/跑後 shasum 自比對」驗證 worktree 的
# bin/mutate-batch.py 沒被動過（不拿 git HEAD 當基準——本地有未 commit 改動時
# 拿 HEAD 比一定誤紅）→ 三項全過才清理副本，否則保留現場供人工檢查。
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"   # .../bin
MUTATE="$SCRIPT_DIR/mutate"
LIST="$SCRIPT_DIR/tests/mutate-batch.mutations"
# 兩個都驗：批次邏輯全在 mutate-batch.py，但 mutate 本身也是「活的」執行檔
# （單條模式、--batch 分流都在裡面），沒理由只驗其中一個。
LIVE_FILES=("$SCRIPT_DIR/mutate" "$SCRIPT_DIR/mutate-batch.py")

TMP="$(mktemp -d "${TMPDIR:-/tmp}/mutate-dogfood.XXXXXX")"

# trap 只處理「跑到一半被中斷」的清理（Ctrl-C／被 kill）；正常收尾的清理與否
# 由跑完後的三項結果決定（見腳本尾端），不能兩邊都想刪、想留就打架。
_interrupted_cleanup() {
  echo "!! 收到中止信號，清掉副本 $TMP" >&2
  rm -rf "$TMP"
  exit 130
}
trap _interrupted_cleanup INT TERM

cp -R "$SCRIPT_DIR" "$TMP/bin"
BEFORE_SHA="$(shasum -a 256 "${LIVE_FILES[@]}")"

echo "TMP=$TMP"
echo "===== --check ====="
bash "$MUTATE" --batch "$LIST" --check --cwd "$TMP" --out "$TMP/check-out"
CHECK_RC=$?

echo
echo "===== --batch ====="
bash "$MUTATE" --batch "$LIST" --cwd "$TMP" --out "$TMP/batch-out"
BATCH_RC=$?

echo
echo "===== 驗主體未被動過（跑前/跑後 shasum 自比對，不用 git HEAD） ====="
AFTER_SHA="$(shasum -a 256 "${LIVE_FILES[@]}")"
if [ "$BEFORE_SHA" = "$AFTER_SHA" ]; then
  echo "一致：bin/mutate 與 bin/mutate-batch.py 跑前跑後 shasum 都相同（未被動過）"
  CMP_RC=0
else
  echo "!! 不一致：跑前後 shasum 有差異，dogfood 動到活的檔案" >&2
  echo "--- 跑前 ---" >&2; printf '%s\n' "$BEFORE_SHA" >&2
  echo "--- 跑後 ---" >&2; printf '%s\n' "$AFTER_SHA" >&2
  CMP_RC=1
fi

trap - INT TERM
echo
if [ "$CHECK_RC" = "0" ] && [ "$BATCH_RC" = "0" ] && [ "$CMP_RC" = "0" ]; then
  rm -rf "$TMP"
  echo "===== dogfood 全過（副本已清理） ====="
  exit 0
else
  echo "===== dogfood 有問題：check_rc=$CHECK_RC batch_rc=$BATCH_RC cmp_rc=$CMP_RC =====" >&2
  echo "保留現場：$TMP" >&2
  exit 1
fi
