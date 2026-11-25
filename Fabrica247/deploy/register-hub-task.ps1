# Registra el Hub al iniciar sesión del usuario actual; no requiere admin.
param([string]$HostAddress = "127.0.0.1", [int]$Port = 8765)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (Get-Command py -ErrorAction SilentlyContinue) { $exe = (Get-Command py).Source; $arguments = "-3 -m fabrica hub serve --host $HostAddress --port $Port" }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $exe = (Get-Command python).Source; $arguments = "-m fabrica hub serve --host $HostAddress --port $Port" }
else { throw "Python no encontrado." }
$action = New-ScheduledTaskAction -Execute $exe -Argument $arguments -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -RestartCount 50 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
Register-ScheduledTask -TaskName "Fabrica247-Hub" -Action $action -Trigger $trigger -Settings $settings -Description "Fabrica247 dashboard and task coordinator" -Force | Out-Null
Start-ScheduledTask -TaskName "Fabrica247-Hub"
Write-Host "Hub programado. Detener: Stop-ScheduledTask -TaskName Fabrica247-Hub"
