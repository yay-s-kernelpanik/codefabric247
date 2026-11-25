# Fabrica247 v3 · instalador guiado Windows PowerShell 5.1+
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $py = "py"; $prefix = @("-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python"; $prefix = @() }
else { throw "Instalá Python 3.9+ y volvé a ejecutar install.ps1." }
& $py @prefix -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Fabrica247 requiere Python 3.9 o superior." }
& $py @prefix -m fabrica setup --edition windows
if ($LASTEXITCODE -ne 0) { throw "La instalación no se completó." }
