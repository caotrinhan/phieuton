$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\waitress-serve.exe"
$stdoutLog = Join-Path $PSScriptRoot "waitress.stdout.log"
$stderrLog = Join-Path $PSScriptRoot "waitress.stderr.log"
if (-not (Test-Path $python)) { throw "Missing .venv or waitress-serve.exe." }
if (Get-Process -Name waitress -ErrorAction SilentlyContinue) { Write-Host "Website is already running."; exit 0 }
Start-Process -FilePath $python -ArgumentList "--listen=0.0.0.0:8888 run:app" -WorkingDirectory $PSScriptRoot -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
Write-Host "Website started at http://10.96.31.30:8888/"
