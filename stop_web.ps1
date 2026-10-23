$ErrorActionPreference = "Stop"
$processes = Get-Process -Name "waitress-serve" -ErrorAction SilentlyContinue
if ($processes) {
    $processes | Stop-Process -Force
    Write-Host "Đã tắt website."
} else {
    Write-Host "Website không đang chạy."
}
