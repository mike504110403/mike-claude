# 建立排程工作「WezTerm-Admin」：登入時以最高權限開 WezTerm，裡面跑的 CC 不再跳 UAC。
# 系統權限動作改由 bash_guard 的 SYSTEM_ADMIN 規則在 CC 內 ask（手機 Remote Control 可按）。
# 需在管理員 PowerShell 執行（建立最高權限工作），會跳一次 UAC。
# 縮小影響面（security review M8）：
#   - 提權 WezTerm 讀 C:\ProgramData\wezterm-admin\wezterm.lua（僅 Administrators/SYSTEM 可寫），不讀使用者可寫的 ~/.wezterm.lua
#   - shell 用 -NoProfile，不載入使用者可寫的 $PROFILE
#   - 工作的安全描述元只給 Administrators/SYSTEM：非提權程式不能 schtasks /run 它（只在登入時自動開）
# 殘餘風險：claude 執行檔與 ~/.claude 仍在使用者可寫目錄，見 README。
# 移除：Unregister-ScheduledTask -TaskName WezTerm-Admin -Confirm:$false
param([string]$UserConfig = "$env:USERPROFILE\.wezterm.lua")
$ErrorActionPreference = 'Stop'
$exe = 'C:\Program Files\WezTerm\wezterm-gui.exe'
if (-not (Test-Path $exe)) { throw "wezterm-gui.exe not found: $exe" }

# 1. 管理員專用設定：複製使用者設定，覆寫 default_prog 為完整路徑 + -NoProfile，ACL 只留 Administrators/SYSTEM 可寫
$dir = 'C:\ProgramData\wezterm-admin'
$cfg = Join-Path $dir 'wezterm.lua'
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$lua = Get-Content -Raw -Encoding UTF8 $UserConfig
$override = "config.default_prog = { 'C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe', '-NoLogo', '-NoProfile' }`n"
$idx = $lua.LastIndexOf('return config')
if ($idx -lt 0) { throw "'return config' not found in $UserConfig" }
$lua = $lua.Substring(0, $idx) + $override + $lua.Substring($idx)
[System.IO.File]::WriteAllText($cfg, $lua, (New-Object System.Text.UTF8Encoding $false))
icacls $dir /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-545:(OI)(CI)RX' | Out-Null

# 2. 排程工作
$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute $exe -Argument "--config-file `"$cfg`"" -WorkingDirectory $env:USERPROFILE
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -Priority 4 -MultipleInstances Parallel
Register-ScheduledTask -TaskName 'WezTerm-Admin' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null

# 3. 工作的安全描述元只給 Administrators/SYSTEM（非提權行程不能 /run、不能改 action）
$svc = New-Object -ComObject Schedule.Service
$svc.Connect()
$task = $svc.GetFolder('\').GetTask('WezTerm-Admin')
# 0x10 = TASK_DONT_ADD_PRINCIPAL_ACE：不讓排程器自動補回執行者（使用者）的 ACE
$task.SetSecurityDescriptor('D:P(A;;FA;;;BA)(A;;FA;;;SY)', 0x10)
$sd = $svc.GetFolder('\').GetTask('WezTerm-Admin').GetSecurityDescriptor(4)
if ($sd -notmatch '^D:PA?I?\(A;;FA;;;BA\)\(A;;FA;;;SY\)$') { throw "task SD not applied: $sd" }

Get-ScheduledTask -TaskName 'WezTerm-Admin' | Select-Object TaskName, State, @{n = 'RunLevel'; e = { $_.Principal.RunLevel } }
"task SD: $sd"
icacls $dir
