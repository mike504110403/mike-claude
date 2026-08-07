#!/usr/bin/env bash
# 一鍵安裝 mike-claude 工作流到 ~/.claude（+ ~/.tmux.conf）。
# 支援 macOS 與 Linux/WSL；Windows 使用者請在 WSL 內執行本腳本。
#
#   curl -fsSL https://raw.githubusercontent.com/mike504110403/mike-claude/main/install.sh | bash
#
# 客製環境變數（見 README.md）：
#   INSTALL_NAME      落地後 CLAUDE.md 內「Mike」全部替換成這個名字
#   MIKE_CLAUDE_FULL  設為 1 時安裝完整版 settings.json（含 Mike 個人化三鍵）
#   MIKE_CLAUDE_REPO  指定安裝來源（git URL 或本地路徑）；顯式設定時一律走 git clone
set -euo pipefail

DEFAULT_REPO="https://github.com/mike504110403/mike-claude.git"
CLAUDE_HOME="$HOME/.claude"

declare -a TMP_FILES=()
declare -a BACKED_UP=()
CLEANUP_DIR=""

cleanup() {
  local f
  if [ ${#TMP_FILES[@]} -gt 0 ]; then
    for f in "${TMP_FILES[@]}"; do
      [ -n "$f" ] && [ -f "$f" ] && rm -f "$f"
    done
  fi
  if [ -n "$CLEANUP_DIR" ] && [ -d "$CLEANUP_DIR" ]; then
    rm -rf "$CLEANUP_DIR"
  fi
}
trap cleanup EXIT

log() { printf '%s\n' "$*" >&2; }
err() { printf 'ERROR: %s\n' "$*" >&2; }

# ── 1. 依賴檢查 ──────────────────────────────────────────
check_deps() {
  local need=(git tmux python3 jq bc) missing=() cmd
  for cmd in "${need[@]}"; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done
  [ ${#missing[@]} -eq 0 ] && return 0

  log "缺少依賴：${missing[*]}"
  if [ "$(uname -s)" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then
      log "偵測到 Homebrew，安裝缺少的依賴…"
      brew install "${missing[@]}"
    else
      err "需要 Homebrew 才能自動補齊依賴（本腳本不會幫你安裝 Homebrew 本身）"
      log "請先手動安裝：https://brew.sh"
      log "安裝完成後重新執行本腳本。"
      exit 1
    fi
  else
    err "缺少依賴，請手動安裝後重跑（本腳本不會執行 sudo）："
    log "  sudo apt install ${missing[*]}"
    exit 1
  fi
}

# ── 2. 來源解析：顯式 MIKE_CLAUDE_REPO > 自我偵測 > 預設 GitHub URL ──
resolve_repo_src() {
  local explicit_repo="${MIKE_CLAUDE_REPO:-}"

  if [ -n "$explicit_repo" ]; then
    local tmp_clone
    tmp_clone="$(mktemp -d)"
    CLEANUP_DIR="$tmp_clone"
    log "MIKE_CLAUDE_REPO 已顯式設定，clone 來源：$explicit_repo"
    git clone --quiet "$explicit_repo" "$tmp_clone" \
      || { err "git clone 失敗，來源：$explicit_repo"; exit 1; }
    printf '%s' "$tmp_clone"
    return 0
  fi

  local script_source="${BASH_SOURCE[0]:-}" script_dir=""
  if [ -n "$script_source" ] && [ -f "$script_source" ]; then
    script_dir="$(cd "$(dirname "$script_source")" && pwd)"
  fi
  if [ -n "$script_dir" ] && [ -f "$script_dir/.gitignore" ] && [ -d "$script_dir/skills" ]; then
    log "未設定 MIKE_CLAUDE_REPO，偵測到腳本位於 repo checkout 內，直接以此為來源：$script_dir"
    printf '%s' "$script_dir"
    return 0
  fi

  local tmp_clone
  tmp_clone="$(mktemp -d)"
  CLEANUP_DIR="$tmp_clone"
  log "未設定 MIKE_CLAUDE_REPO 且非 repo checkout 內執行，clone 預設來源：$DEFAULT_REPO"
  git clone --quiet "$DEFAULT_REPO" "$tmp_clone" \
    || { err "git clone 失敗，來源：$DEFAULT_REPO"; exit 1; }
  printf '%s' "$tmp_clone"
}

# ── 備份工具：同名檔/目錄先搬去 .bak-<timestamp>，timestamp 撞號時加序號 ──
backup_path() {
  local target="$1" ts candidate n=1
  ts="$(date +%Y%m%d%H%M%S)"
  candidate="${target}.bak-${ts}"
  while [ -e "$candidate" ]; do
    candidate="${target}.bak-${ts}-${n}"
    n=$((n + 1))
  done
  printf '%s' "$candidate"
}

backup_if_exists() {
  local target="$1" bak
  if [ -e "$target" ]; then
    bak="$(backup_path "$target")"
    mv "$target" "$bak"
    log "備份：$target -> $bak"
    BACKED_UP+=("$bak")
  fi
}

# ── settings.json 過濾：外部輸入信任邊界，落地前用 python3 stdlib 刪三鍵 ──
filter_settings_in_place() {
  local target="$1"
  if [ "${MIKE_CLAUDE_FULL:-}" = "1" ]; then
    return 0
  fi
  local tmp
  tmp="$(mktemp)"
  TMP_FILES+=("$tmp")
  python3 - "$target" "$tmp" <<'PYEOF'
import json
import sys

src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f:
    data = json.load(f)

data.pop("model", None)
data.pop("skipDangerousModePermissionPrompt", None)
if isinstance(data.get("permissions"), dict):
    data["permissions"].pop("defaultMode", None)

with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF
  mv "$tmp" "$target"
}

# ── 名字客製：INSTALL_NAME 有值就把落地後 CLAUDE.md 的「Mike」全部換掉 ──
apply_install_name() {
  local claude_md="$1"
  [ -n "${INSTALL_NAME:-}" ] || return 0
  python3 - "$claude_md" "$INSTALL_NAME" <<'PYEOF'
import sys

path, name = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    content = f.read()
content = content.replace("Mike", name)
with open(path, "w", encoding="utf-8") as f:
    f.write(content)
PYEOF
}

# ── 3. 安裝 ~/.claude ────────────────────────────────────
install_claude_home() {
  local repo_src="$1"

  if [ ! -d "$CLAUDE_HOME" ]; then
    log "全新安裝：git clone 到 ${CLAUDE_HOME}（日後更新 = cd ~/.claude && git pull）"
    git clone --quiet "$repo_src" "$CLAUDE_HOME"
  else
    log "偵測到既有 ${CLAUDE_HOME}，僅複製白名單資產，其他既有檔案不動"

    local f
    for f in CLAUDE.md statusline.sh; do
      backup_if_exists "$CLAUDE_HOME/$f"
      cp "$repo_src/$f" "$CLAUDE_HOME/$f"
    done

    backup_if_exists "$CLAUDE_HOME/settings.json"
    cp "$repo_src/settings.json" "$CLAUDE_HOME/settings.json"

    local d
    for d in skills agents hooks bin; do
      backup_if_exists "$CLAUDE_HOME/$d"
      cp -R "$repo_src/$d" "$CLAUDE_HOME/$d"
    done
  fi

  filter_settings_in_place "$CLAUDE_HOME/settings.json"
  apply_install_name "$CLAUDE_HOME/CLAUDE.md"
  chmod +x "$CLAUDE_HOME/bin/phase" "$CLAUDE_HOME/statusline.sh"
}

# ── 4. tmux 設定 ─────────────────────────────────────────
install_tmux_conf() {
  local repo_src="$1" target="$HOME/.tmux.conf"
  backup_if_exists "$target"
  cp "$repo_src/tmux.conf" "$target"
  if [ -n "${TMUX:-}" ]; then
    log "偵測到目前在 tmux 內，套用新設定…"
    tmux source-file "$target" || log "警告：tmux source-file 失敗，請手動 :source-file ~/.tmux.conf"
  fi
}

# ── main ─────────────────────────────────────────────────
main() {
  check_deps

  local repo_src
  repo_src="$(resolve_repo_src)"

  install_claude_home "$repo_src"
  install_tmux_conf "$repo_src"

  log ""
  log "=== 安裝完成 ==="
  log "已安裝：~/.claude（CLAUDE.md、settings.json、statusline.sh、skills/、agents/、hooks/、bin/）、~/.tmux.conf"
  if [ ${#BACKED_UP[@]} -gt 0 ]; then
    log "備份了以下既有檔案/目錄（皆保留，未刪除）："
    local b
    for b in "${BACKED_UP[@]}"; do
      log "  - $b"
    done
  else
    log "沒有既有同名檔案需要備份。"
  fi
  log ""
  log "後續手動步驟："
  if [ -z "${INSTALL_NAME:-}" ]; then
    log "  - CLAUDE.md 裡的「Mike」尚未替換，之後可重跑並設 INSTALL_NAME=你的名字，或手動編輯 ~/.claude/CLAUDE.md"
  else
    log "  - CLAUDE.md 裡的「Mike」已替換為「${INSTALL_NAME}」"
  fi
  log "  - 若需要完整版 settings.json（含 permissions.defaultMode / model 等個人化設定），設 MIKE_CLAUDE_FULL=1 重跑本腳本"
  log "  - Claude Code 內執行 /config 可開啟手機推播通知"
  log "  - Windows 使用者：Claude Code 與本工作流需在 WSL 內執行，不是 Windows 原生終端機"
}

main "$@"
