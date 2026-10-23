$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot ".venv\Scripts\waitress-serve.exe"
$stdoutLog = Join-Path $PSScriptRoot "waitress.stdout.log"
$stderrLog = Join-Path $PSScriptRoot "waitress.stderr.log"
if (-not (Test-Path $python)) { throw "Missing .venv or waitress-serve.exe." }
if (Test-NetConnection 127.0.0.1 -Port 8888 -InformationLevel Quiet -WarningAction SilentlyContinue) {
    Write-Host "Website is already listening on port 8888."
    exit 0
}

$process = Start-Process -FilePath $python -ArgumentList "--listen=0.0.0.0:8888 run:app" -WorkingDirectory $PSScriptRoot -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -PassThru
for ($attempt = 0; $attempt -lt 15; $attempt++) {
    Start-Sleep -Seconds 1
    $process.Refresh()
    if ($process.HasExited) { break }
    if (Test-NetConnection 127.0.0.1 -Port 8888 -InformationLevel Quiet -WarningAction SilentlyContinue) {
        Write-Host "Website started at http://10.96.31.30:8888/"
        exit 0
    }
}

Write-Host "Waitress failed to start or did not listen on port 8888."
if (Test-Path $stderrLog) { Get-Content $stderrLog -Tail 40 }
if (Test-Path $stdoutLog) { Get-Content $stdoutLog -Tail 20 }
throw "Website startup failed. Check waitress.stderr.log."
