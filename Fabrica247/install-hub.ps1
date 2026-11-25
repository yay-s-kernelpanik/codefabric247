# Fabrica247 Hub: instalación para el administrador. No requiere admin ni agente local.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py"; $prefix = @("-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python"; $prefix = @() }
else { throw "Instalá Python 3.9+ y volvé a ejecutar este script." }
& $py @prefix -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Fabrica247 requiere Python 3.9 o superior." }
Write-Host "Inicializando Fabrica247 Hub (sin agente local)..." -ForegroundColor Cyan
& $py @prefix -m fabrica hub init
if ($LASTEXITCODE -ne 0) { throw "No se pudo inicializar el Hub." }
Write-Host "`nPara iniciar: $py -m fabrica hub serve" -ForegroundColor Green
Write-Host "Para acceso por VPN/red privada: $py -m fabrica hub serve --host 0.0.0.0 --port 8765"
Write-Host "No publiques el puerto directamente en Internet; usá una VPN privada o HTTPS."
