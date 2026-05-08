param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8080,
    [int]$TimeoutSeconds = 60
)

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

while ((Get-Date) -lt $deadline) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync($HostName, $Port)
        if ($task.Wait(1000) -and $client.Connected) {
            exit 0
        }
    } catch {
    } finally {
        $client.Dispose()
    }

    Start-Sleep -Seconds 1
}

exit 1
