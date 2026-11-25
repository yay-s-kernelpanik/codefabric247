# Fabrica247 Worker: registro de una PC participante. No requiere administrador.
param(
  [Parameter(Mandatory=$true)][string]$Hub,
  [Parameter(Mandatory=$true)][string]$Invite,
  [string]$Name = $env:COMPUTERNAME,
  [string]$Project = "",
  [string]$Repo = "",
  [string]$Config = "",
  [switch]$AllowRemoteCode,
  [switch]$AllowShell,
  [switch]$AcceptRemoteControl
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Instalá Git antes de registrar un worker." }
if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py"; $prefix = @("-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python"; $prefix = @() }
else { throw "Instalá Python 3.9+ y volvé a ejecutar este script." }
& $py @prefix -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Fabrica247 requiere Python 3.9 o superior." }
$argsList = @("worker", "join", "--hub", $Hub, "--invite", $Invite, "--name", $Name)
if ($Project) { $argsList += @("--project", $Project) }
if ($Repo) { $argsList += @("--repo", $Repo) }
if ($Config) { $argsList += @("--config", $Config) }
if ($AllowRemoteCode) { $argsList += "--allow-remote-code" }
if ($AllowShell) { $argsList += "--allow-shell" }
if ($AcceptRemoteControl) { $argsList += "--accept-remote-control" }
& $py @prefix -m fabrica @argsList
if ($LASTEXITCODE -ne 0) { throw "No se pudo registrar esta PC." }
Write-Host "`nPC registrada. Editá worker.json, configurá projects y agent.providers." -ForegroundColor Green
Write-Host "Instalá OpenCode por separado si esta PC va a ejecutar un agente de código."
Write-Host "Después ejecutá: $py -m fabrica worker doctor ; $py -m fabrica worker run"
