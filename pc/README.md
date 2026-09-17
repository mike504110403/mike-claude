# ~/.claude/pc — PC 延伸機（spec：~/.claude/plans/pc-offload.md v2）

| 檔 | 用途 |
| -- | ---- |
| `repos.txt` | 接收端 repo 清單（group repo mac_path），pc-push 與 bootstrap 共用的唯一 source |
| `post-receive.tmpl` | 接收端 hook 樣板，只認 `refs/heads/pc-test` |
| `bootstrap-wsl.sh` | WSL2 Ubuntu 內一次性環境建置（Docker Engine、Go、Node、Tailscale、14 bare repo） |
| `windows-prep.ps1` | Windows 端常駐前置（電源、.wslconfig、啟用 WSL 功能、sshd shell、開機排程） |

Mac 端工具在 `~/.claude/bin/`：`pc-reach`、`pc-push`、`pc-sync-stack`。

## 波 1 runbook（Mike 開好 BIOS SVM＋Tailscale unattended 後，全遠端）

```
# 0. 確認虛擬化已開（期望 True）
ssh ai-pc 'powershell -c "(Get-CimInstance Win32_Processor).VirtualizationFirmwareEnabled"'

# 1. 裝 Ubuntu（會下載；第一次進 Ubuntu 要建使用者 mike，用 --no-launch 跳過互動，之後手動建）
ssh ai-pc 'wsl --install -d Ubuntu --no-launch'
ssh ai-pc 'wsl -d Ubuntu -u root -- bash -c "useradd -m -s /bin/bash -G sudo mike && echo mike:mike | chpasswd && echo \"mike ALL=(ALL) NOPASSWD:ALL\" > /etc/sudoers.d/mike"'

# 2. 把三個檔送進 WSL（先落 Windows 再搬進 ext4，避免直接寫 /mnt/c 目錄）
scp ~/.claude/pc/{repos.txt,post-receive.tmpl,bootstrap-wsl.sh} ai-pc:
ssh ai-pc 'wsl -d Ubuntu -u mike -- bash -c "mkdir -p ~/ai-gateway && cp /mnt/c/Users/mike/{repos.txt,post-receive.tmpl,bootstrap-wsl.sh} ~/ai-gateway/ && chmod +x ~/ai-gateway/bootstrap-wsl.sh"'

# 3. 跑 bootstrap（tailscale up 會印登入網址，在 Mac 開一次）；跑完 wsl --shutdown 再跑第二次讓 systemd／docker 群組生效
ssh ai-pc 'wsl -d Ubuntu -u mike -- bash -lc "~/ai-gateway/bootstrap-wsl.sh"'
ssh ai-pc 'wsl --shutdown'
ssh ai-pc 'wsl -d Ubuntu -u mike -- bash -lc "~/ai-gateway/bootstrap-wsl.sh"'

# 4. Mac 端 ssh 別名（IP 取自 bootstrap 印出的「WSL 節點 IP」）
printf '\nHost ai-pc-wsl\n    HostName <WSL 節點 100.x IP>\n    User mike\n' >> ~/.ssh/config
pc-reach            # 期望 PC_READY

# 5. 直連驗證（期望 direct，不是 DERP）；不是就查路由器 UDP 41641
/Applications/Tailscale.app/Contents/MacOS/Tailscale ping ai-pc-wsl

# 6. 重開驗收：重開後不登入 Windows，60 秒內 ssh ai-pc-wsl 要回來
ssh ai-pc 'shutdown /r /t 5'
sleep 90; pc-reach
```

## 波 1 實跑筆記（2026-09-16 已完成，供重建時參考）

- 內建 `wsl --install` 在 ssh 非互動 session 下會失敗（要 Store）：改抓 GitHub `microsoft/WSL` release 的 `x64.msi` 靜默安裝，再 `wsl --install -d Ubuntu --no-launch` 即可（無 Store 依賴）。
- Windows 主機 → WSL 的 22 port 被 WSL 2.x Hyper-V 防火牆擋（加 `New-NetFirewallHyperVRule` 仍不通，未深究）。備援別名 `ai-pc-wsl-jump` 用 `ProxyCommand ssh ai-pc wsl -d Ubuntu -u mike -- nc 127.0.0.1 22` 管線繞過，握手 5-8 秒。
- Tailscale 登入：`tailscale up --timeout` 短逾時不一定印網址；用 `tailscale login --timeout 45s`，或背景跑後讀 `tailscale status --json | jq .AuthURL`。不開 Tailscale SSH（預設 ACL 為 check 模式，會要瀏覽器複驗），用 openssh-server 金鑰登入。
- WSL 節點 IP 100.66.189.18（ai-pc-wsl）；Windows 節點 100.120.195.79（ai-pc）。
- 重開驗收實測：`shutdown /r` 後 15 秒斷線、52 秒 Windows ssh 與 WSL pc-reach 同時回來，無人登入（AutoAdminLogon=0、無 explorer）仍全綠。
- **WSL 實例存活的兩個條件**（2026-09-17 實踩，缺一不可）：(1) `.wslconfig` 的 `vmIdleTimeout=-1`，否則 VM 閒置 60 秒關機；(2) 必須有一個常駐的 wsl.exe session（排程 `ai-gateway-wsl-boot` 跑 `-d Ubuntu -u root --exec /bin/sleep infinity`），否則**任何** wsl.exe 呼叫退出都會觸發 `systemctl poweroff`，docker／sshd／tailscaled 全被 SIGTERM 重生（10 分鐘 382 次，切斷了三次 16GB 的 MySQL 匯入）。用 `ai-pc-wsl-jump` 跳板時尤其明顯，因為它每次連線都是一個 wsl.exe session。
- Portainer CE 2.45 首次建管理員要日誌裡的 `setup_token`（`docker logs portainer | grep setup_token`），用 `X-Setup-Token` header 打 `/api/users/admin/init`；密碼在 `~/.ssh/ai-pc-portainer-password.txt`。
- ssh ai-pc 進的是 PowerShell：含 `|`、`<`、跳脫引號的指令一律寫檔 scp 過去執行（ps1 含中文要 UTF-8 BOM；WSL 內用 `wsl -d Ubuntu -u mike -- bash -l /mnt/c/Users/mike/<檔>.sh`）。

## 副本搬遷（Mac docker volume → PC 容器，波 2／3 實跑筆記）

- 方法：Mac 起臨時容器掛原 volume → `mysqldump`／`pg_dump` → `gzip -1` → `ssh ai-pc-wsl 'gunzip | docker exec -i <db容器> mysql/psql …'`，不落檔。彩票 MySQL 16GB 約 57 分（直連），gold-price PG 三庫（goldprice／academy／finance）約 2 分。
- MySQL：先 `down.sh`（留 infra）、只起 mysql 容器；`--init-command` 設 `sql_mode=NO_ENGINE_SUBSTITUTION; FOREIGN_KEY_CHECKS=0`；灌完 `SET GLOBAL sql_mode` 等價設定再 `up.sh`（去牙會重跑）。
- PG（gold-price）：**timescaledb 版本必須與 Mac 相同**——`latest-pg16` 在 PC 拉到的是新版（2.30.1 vs Mac 2.24.0），還原後 hypertable／連續聚合全失效、api 報 `invalid materialized hypertable ID`。做法：`docker pull timescale/timescaledb@sha256:<Mac 的 RepoDigest>` 再 tag 成 `latest-pg16`；先 `CREATE EXTENSION timescaledb`、`SELECT timescaledb_pre_restore()`，灌完 `timescaledb_post_restore()`。臨時容器要帶 `PGDATA=/var/lib/postgresql/data/pgdata`（compose 這樣設，少了會 initdb）。
- 一次性腳本樣板：`~/.claude/tmp_dbmove.sh`（MySQL）、`~/.claude/tmp_gpmove.sh`（PG），波 4 回收群照 PG 版改（無 timescale，volume `gold-recycle-pg`）。
- 灌入期間 WSL 不可重啟（見上節常駐 session）。

## PC 三群同時常駐的埠對照（D7，2026-09-17 起）

| 群 | 服務 | Mac 埠 | PC 埠 | 由誰決定 |
| -- | ---- | ------ | ----- | -------- |
| 彩票 | platform API／health／Vue 後台 | 8080／8081／8082 | 同 | 不變（MySQL 3310、Redis 6679、Mongo 27019、RabbitMQ 5672） |
| 貴金屬 | 主 API／market-ws | 8080／8081 | **8180／8181** | `GP_API_PORT`／`GP_WS_PORT`（stack compose 插值＋up／status／frontend.sh） |
| 貴金屬 | academy-api／edge／SSR／OSS／PG／Redis／前台／後台 | 8090／8088／33000／4568／5432／6379／8000／3000 | 同 | 不變 |
| 回收群 | PG／Redis | 5432／6379 | **5433／6380** | `RC_PG_PORT`／`RC_REDIS_PORT`（`localstack/docker-compose.ports.yml` override＋`pc.rewrites` 改 config-local.yaml） |
| 回收群 | backend／admin／client／OSS | 18080／3100／8100／4569 | 同 | 不變 |

env 來源＝各群宣告檔 `pc.env`，/local-stack PC 模式前置到指令；`pc.rewrites` 由 pc-sync-stack 在 PC 端套用。三群全開實測：16 個容器、WSL 記憶體用 3GB。
另：gold-price `down.sh` 的 compose down 會刪 `gold-price-network`，舊的 oss-emulator 容器綁舊網路 ID 會 `docker start` 失敗，up.sh 已改成失敗即砍掉重建（資料在 bind mount）。

## 波 2-4 每群固定流程

```
for r in <該群 repo 路徑...>; do pc-push "$r"; done
pc-sync-stack <group>
ssh ai-pc-wsl 'cd ~/ai-gateway/<group> && localstack/up.sh'      # 第一次一定會踩 Mac 專屬路徑，逐條修
```
之後改由 /local-stack PC 模式自動執行（宣告檔 `pc` 區塊）。
