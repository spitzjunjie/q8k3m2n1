Get-WmiObject Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
    Write-Host "PID: $($_.ProcessId)"
    Write-Host "CPU: $($_.UserModeTime / 10000000)"
    Write-Host "Cmd: $($_.CommandLine)"
    Write-Host "---"
}
