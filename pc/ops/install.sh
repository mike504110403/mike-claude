#!/bin/bash
# 在 PC（WSL）安裝／更新波 7 的 systemd unit（system 層、User=mike；user 層在 WSL 沒 linger 不穩）。冪等，重跑即更新。
set -euo pipefail
OPS="$HOME/ai-gateway/ops"; U=/etc/systemd/system
sudo -n tee $U/ai-gateway-health.service >/dev/null <<UNIT
[Unit]
Description=ai-gateway 三群健檢（寫 state/health.json）
After=docker.service
[Service]
Type=oneshot
User=$USER
Environment=HOME=$HOME
ExecStart=$OPS/healthcheck.sh
UNIT
sudo -n tee $U/ai-gateway-health.timer >/dev/null <<UNIT
[Unit]
Description=每 5 分鐘健檢
[Timer]
OnBootSec=3min
OnUnitActiveSec=5min
AccuracySec=30s
[Install]
WantedBy=timers.target
UNIT
sudo -n tee $U/ai-gateway-deploy.service >/dev/null <<UNIT
[Unit]
Description=ai-gateway push 即部署（state/deploy-pending 非空時跑）
After=docker.service
[Service]
Type=oneshot
User=$USER
Environment=HOME=$HOME
ExecStart=$OPS/deploy.sh
UNIT
sudo -n tee $U/ai-gateway-deploy.path >/dev/null <<UNIT
[Unit]
Description=監看 state/deploy-pending
[Path]
DirectoryNotEmpty=$HOME/ai-gateway/state/deploy-pending
[Install]
WantedBy=multi-user.target
UNIT
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now ai-gateway-health.timer ai-gateway-deploy.path
systemctl list-timers ai-gateway-health.timer --no-pager | head -3
systemctl status ai-gateway-deploy.path --no-pager | head -3
