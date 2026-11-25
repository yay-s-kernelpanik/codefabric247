# Registra el worker al iniciar sesión del usuario actual; no requiere admin.
param([string]$Config = (Join-Path $env:APPDATA "Fabrica247\worker.json"))
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path $Config)) { throw "No existe $Config. Ejecutá worker join primero." }
if (Get-Command py -ErrorAction SilentlyContinue) { $exe = (Get-Command py).Source; $arguments = "-3 -m fabrica worker run --config `"$Config`"" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $exe = (Get-Command python).Source; $arguments = "-m fabrica worker run --config `"$Config`"" }
else { throw "Python no encontrado." }
$action = New-ScheduledTaskAction -Execute $exe -Argument $arguments -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -RestartCount 50 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
Register-ScheduledTask -TaskName "Fabrica247-Worker" -Action $action -Trigger $trigger -Settings $settings -Description "Fabrica247 volunteer worker" -Force | Out-Null
Start-ScheduledTask -TaskName "Fabrica247-Worker"
Write-Host "Worker programado. Detener: Stop-ScheduledTask -TaskName Fabrica247-Worker"
