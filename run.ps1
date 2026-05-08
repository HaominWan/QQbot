$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$log  = Join-Path $root "startup.log"
$napcat_dir   = Join-Path $root "NapCat.Shell.Windows.OneKey\NapCat.44498.Shell"
$napcat_quick = Join-Path $napcat_dir "napcat.quick.bat"

Set-Location $root
"==== Startup $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ====" | Set-Content -Encoding UTF8 $log
"Working directory: $root" | Add-Content -Encoding UTF8 $log

Write-Host "Starting QQbot from $root"

# Stop old bot process.
"Stopping old bot.py processes..." | Add-Content -Encoding UTF8 $log
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*bot.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Start-Sleep -Seconds 1

# Start NapCat if it is not already running.
# NapCat-injected QQ carries --enable-logging in its command line; plain QQ does not.
$napcat_running = Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq "QQ.exe" -and $_.CommandLine -like "*--enable-logging*" }
if ($napcat_running) {
    "NapCat (QQ.exe) already running, skipping start." | Add-Content -Encoding UTF8 $log
    Write-Host "NapCat already running."
} elseif (Test-Path $napcat_quick) {
    "Starting NapCat with quick login..." | Add-Content -Encoding UTF8 $log
    Write-Host "Starting NapCat..."
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/k", "`"$napcat_quick`"" `
        -WorkingDirectory $napcat_dir `
        -WindowStyle Normal
    Start-Sleep -Seconds 3
} else {
    "napcat.quick.bat not found at $napcat_quick" | Add-Content -Encoding UTF8 $log
    Write-Host "WARNING: napcat.quick.bat not found, NapCat not started."
}

# Start bot.py.
$python = Join-Path $root "Bot\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
    "Venv python not found, falling back to PATH python." | Add-Content -Encoding UTF8 $log
} else {
    "Found venv python: $python" | Add-Content -Encoding UTF8 $log
}

Write-Host "Starting QQ Bot websocket server..."
Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/k", "`"$python`" bot.py" `
    -WorkingDirectory (Join-Path $root "Bot") `
    -WindowStyle Normal

Write-Host "Waiting for QQ Bot websocket server on 127.0.0.1:8080..."
& (Join-Path $root "wait_port.ps1") -HostName "127.0.0.1" -Port 8080 -TimeoutSeconds 60
if ($LASTEXITCODE -ne 0) {
    "QQ Bot did not open port 8080 in time." | Add-Content -Encoding UTF8 $log
    Write-Host "QQ Bot did not open port 8080 in time. Check the QQ Bot console window."
    Read-Host "Press Enter to exit"
    exit 1
}

"QQ Bot websocket server is ready." | Add-Content -Encoding UTF8 $log
Write-Host "QQ Bot websocket server is ready."
Write-Host ""
Write-Host "NapCatQQ should connect to: ws://127.0.0.1:8080/onebot/v11/ws"
Write-Host ""
Read-Host "Press Enter to close this launcher window"
