$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Python runtime not found.' }
try { $health = Invoke-RestMethod 'http://127.0.0.1:8787/api/health' -TimeoutSec 3 } catch {
    Start-Process -FilePath (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File','start-supervised.ps1') -WorkingDirectory $projectRoot -WindowStyle Hidden
    Start-Sleep -Seconds 4
    $health = Invoke-RestMethod 'http://127.0.0.1:8787/api/health' -TimeoutSec 5
}
if ($health.service -ne 'zhiheng-api') { throw 'Unexpected service on port 8787.' }
$addresses = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)' })
$chosen = $addresses | Where-Object { $_.InterfaceAlias -match 'WLAN|Wi-Fi' } | Select-Object -First 1
if (-not $chosen) { $chosen = $addresses | Select-Object -First 1 }
if (-not $chosen) { throw 'No LAN address found. Connect the computer to Wi-Fi first.' }
$existing = Get-NetTCPConnection -LocalPort 8788 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$($existing[0].OwningProcess)"
    if ($processInfo.CommandLine -notmatch 'mobile_gateway.py' -or $existing[0].LocalAddress -ne $chosen.IPAddress) { throw 'Port 8788 is occupied or the Wi-Fi address has changed. Restart the verified mobile_gateway.py process before reconnecting.' }
}
if (-not $existing) {
    $privateDir = Join-Path $projectRoot '.mobile-private'
    New-Item -ItemType Directory -Force -Path $privateDir | Out-Null
    Start-Process -FilePath $pythonPath -ArgumentList @('mobile_gateway.py','--host',$chosen.IPAddress) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $privateDir 'gateway.log') -RedirectStandardError (Join-Path $privateDir 'gateway-error.log')
    Start-Sleep -Seconds 2
}
$pairingFile = Join-Path $projectRoot '.mobile-private\pairing-url.txt'
if (-not (Test-Path -LiteralPath $pairingFile)) { throw 'Gateway failed to start; inspect .mobile-private/gateway-error.log.' }
Get-Content -LiteralPath $pairingFile
Write-Host 'Copy the URL above into the Android app. Keep the computer powered on and on the same Wi-Fi.'
Write-Host 'If Windows asks for firewall access, allow only your trusted private network.'
