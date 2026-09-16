$process = Get-Process -Name waitress -ErrorAction SilentlyContinue
if ($process) { Write-Host "Website đang chạy. PID: $($process.Id)" } else { Write-Host "Website đang tắt." }
Test-NetConnection 127.0.0.1 -Port 8888 -InformationLevel Quiet
