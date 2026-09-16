#!/bin/bash
# bootstrap-wsl.sh — 在 PC 的 WSL2 Ubuntu 內以使用者 mike 執行一次（需 sudo）。冪等，可重跑。
# 前置：Mac 先把 ~/.claude/pc/{repos.txt,post-receive.tmpl,bootstrap-wsl.sh} scp 到 ~/ai-gateway/。
# 對應 spec §3.1 與波 1；驗收：docker info 通、tailscale ip 有 100.x、14 個 bare repo 各有可執行 hook。
set -euo pipefail
GO_VER="${GO_VER:-1.26.1}"
GW="$HOME/ai-gateway"
REPOS="$GW/repos.txt"
TMPL="$GW/post-receive.tmpl"
[ -f "$REPOS" ] && [ -f "$TMPL" ] || { echo "缺 $REPOS 或 $TMPL，先從 Mac scp 過來" >&2; exit 2; }

echo "== 1/7 wsl.conf（systemd＋預設使用者）"
if ! grep -q 'systemd=true' /etc/wsl.conf 2>/dev/null; then
  printf '[boot]\nsystemd=true\n\n[user]\ndefault=%s\n' "$USER" | sudo tee /etc/wsl.conf >/dev/null
  echo "   已寫 /etc/wsl.conf，本輪結束後在 Windows 跑 wsl --shutdown 再進來一次"
fi

echo "== 2/7 apt 基礎"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates curl git rsync build-essential jq unzip openssh-client >/dev/null

echo "== 3/7 Docker Engine"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo usermod -aG docker "$USER"
sudo systemctl enable --now docker >/dev/null 2>&1 || echo "   systemd 尚未生效（第一次跑正常），wsl --shutdown 後重進再跑一次本腳本"

echo "== 4/7 Go $GO_VER"
if ! /usr/local/go/bin/go version 2>/dev/null | grep -q "go$GO_VER"; then
  curl -fsSL "https://go.dev/dl/go${GO_VER}.linux-amd64.tar.gz" -o /tmp/go.tgz
  sudo rm -r -f /usr/local/go
  sudo tar -C /usr/local -xzf /tmp/go.tgz
  rm -f /tmp/go.tgz
fi
grep -q '/usr/local/go/bin' ~/.profile || echo 'export PATH="$PATH:/usr/local/go/bin:$HOME/go/bin"' >> ~/.profile

echo "== 5/7 Node 20＋22（nvm）＋pnpm 10"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] || curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash >/dev/null
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"
nvm install 22.20.0 >/dev/null
nvm install 20.20.0 >/dev/null
nvm alias default 22.20.0 >/dev/null
nvm use default >/dev/null
npm i -g pnpm@10 >/dev/null

echo "== 6/7 Tailscale（獨立節點 ai-pc-wsl，開 Tailscale SSH）"
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh --hostname ai-pc-wsl || echo "   tailscale up 需要瀏覽器登入：照上面印出的網址在 Mac 開一次"
echo "   WSL 節點 IP：$(tailscale ip -4 2>/dev/null || echo 未取得)"

echo "== 7/7 ai-gateway 接收端（bare repo＋hook）"
n=0
while read -r group repo _path; do
  case "$group" in ''|'#'*) continue ;; esac
  bare="$GW/.bare/$group/$repo.git"
  work="$GW/$group/$repo"
  [ -d "$bare" ] || git init --bare -q "$bare"
  mkdir -p "$work"
  sed -e "s|__BARE__|$bare|g" -e "s|__WORK__|$work|g" "$TMPL" > "$bare/hooks/post-receive"
  chmod +x "$bare/hooks/post-receive"
  n=$((n+1))
done < "$REPOS"
echo "   建好 $n 個接收端於 $GW/.bare/"

echo
echo "完成。驗收："
echo "  docker info >/dev/null && echo DOCKER_OK   （新 shell 才吃 docker 群組）"
echo "  /usr/local/go/bin/go version"
echo "  tailscale status | head -3"
echo "  ls $GW/.bare/*/*.git/hooks/post-receive | wc -l   → 期望 $n"
