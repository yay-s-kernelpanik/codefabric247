# Registra Fabrica247 como tarea programada de Windows (arranca al iniciar sesion y se reinicia si falla).
# Uso (PowerShell): powershell -ExecutionPolicy Bypass -File .\deploy\register-task.ps1
$root = Split-Path -Parent $PSScriptRoot
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$root\start.ps1`"" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "Fabrica247" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Tarea 'Fabrica247' registrada. Inicio manual: Start-ScheduledTask -TaskName Fabrica247"
