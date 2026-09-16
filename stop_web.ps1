$ErrorActionPreference = "Stop"
$processes = Get-Process -Name waitress -ErrorAction SilentlyContinue
if ($processes) { $processes | Stop-Process -Force; Write-Host "Đã tắt website." } else { Write-Host "Website không đang chạy." }
