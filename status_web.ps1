$process = Get-Process -Name "waitress-serve" -ErrorAction SilentlyContinue
$isListening = Test-NetConnection 127.0.0.1 -Port 8888 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($isListening) {
    if ($process) {
        Write-Host "Website đang chạy. PID: $($process.Id -join ', ')"
    } else {
        Write-Host "Cổng 8888 đang mở nhưng không tìm thấy tiến trình waitress-serve."
    }
} else {
    Write-Host "Website đang tắt."
}
