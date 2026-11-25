# Wrapper: .\fabrica.ps1 <comando>   (equivale a python -m fabrica <comando>)
# Archivo ASCII a proposito: PowerShell 5.1 lee mal UTF-8 sin BOM.
Set-Location $PSScriptRoot
$exe = $null; $pre = @()
foreach ($cand in @(@("py", "-3"), @("python"))) {
    if (Get-Command $cand[0] -ErrorAction SilentlyContinue) {
        $extra = @(); if ($cand.Count -gt 1) { $extra = $cand[1..($cand.Count - 1)] }
        & $cand[0] @extra -c "import sys" 2>$null
        if ($LASTEXITCODE -eq 0) { $exe = $cand[0]; $pre = $extra; break }
    }
}
if (-not $exe) { Write-Error "Python no encontrado. Ejecuta .\install.ps1"; exit 1 }
& $exe @pre -m fabrica @args
exit $LASTEXITCODE
