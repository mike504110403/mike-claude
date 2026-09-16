# windows-prep.ps1 — PC Windows 端常駐前置（spec §3.4），不依賴 WSL／虛擬化，可在 BIOS 改之前跑。冪等。
# 用法（Mac）：scp ~/.claude/pc/windows-prep.ps1 ai-pc:windows-prep.ps1 && ssh ai-pc 'powershell -NoProfile -ExecutionPolicy Bypass -File windows-prep.ps1'
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

Write-Output "== 1/6 電源：永不睡眠、休眠關閉、螢幕 10 分"
powercfg /change standby-timeout-ac 0 | Out-Null
powercfg /change hibernate-timeout-ac 0 | Out-Null
powercfg /change monitor-timeout-ac 10 | Out-Null
powercfg /hibernate off | Out-Null
$sleepIdx = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String 'AC').Line.Trim()
Write-Output ("POWER_STANDBY_AC=" + $sleepIdx)
Write-Output ("HIBERNATE=" + (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Power' -Name HibernateEnabled -ErrorAction SilentlyContinue).HibernateEnabled)

Write-Output "== 2/6 .wslconfig（memory=20GB swap=4GB）"
Set-Content -Path "$env:USERPROFILE\.wslconfig" -Value "[wsl2]`nmemory=20GB`nswap=4GB`nlocalhostForwarding=true`n" -Encoding ASCII
Write-Output ("WSLCONFIG=" + ((Get-Content "$env:USERPROFILE\.wslconfig") -join ' | '))

Write-Output "== 3/6 啟用 WSL 與 VirtualMachinePlatform（重開後生效）"
$f1 = Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -All -NoRestart
$f2 = Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All -NoRestart
Write-Output ("FEATURES=WSL:" + (Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux).State + " VMP:" + (Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform).State + " restartNeeded:" + ($f1.RestartNeeded -or $f2.RestartNeeded))

Write-Output "== 4/6 sshd 預設 shell → PowerShell（免 cmd 引號地雷）"
New-ItemProperty -Path 'HKLM:\SOFTWARE\OpenSSH' -Name DefaultShell -Value 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -PropertyType String -Force | Out-Null
Write-Output ("SSHD_SHELL=" + (Get-ItemProperty 'HKLM:\SOFTWARE\OpenSSH').DefaultShell)

Write-Output "== 5/6 工作排程：開機拉起 WSL（不論登入）"
$act = New-ScheduledTaskAction -Execute 'C:\Windows\System32\wsl.exe' -Argument '-d Ubuntu --exec /bin/true'
$trg = New-ScheduledTaskTrigger -AtStartup
$pr  = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest
$set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName 'ai-gateway-wsl-boot' -Action $act -Trigger $trg -Principal $pr -Settings $set -Force | Out-Null
Write-Output ("TASK=" + (Get-ScheduledTask -TaskName 'ai-gateway-wsl-boot').State)

Write-Output "== 6/6 預先安裝 WSL 本體（無虛擬化時可能失敗，只回報）"
$w = (wsl --install --no-distribution 2>&1 | Out-String)
Write-Output ("WSL_INSTALL=" + (($w -replace "`0", "") -replace "\s+", " ").Trim())
Write-Output "PREP_DONE"
