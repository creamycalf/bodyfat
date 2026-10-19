param(
    [ValidateSet('Status', 'Install', 'Remove')]
    [string]$Action = 'Status'
)

$ErrorActionPreference = 'Stop'
$taskName = 'Zhiheng Local Health Server'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverScript = Join-Path $projectRoot 'start-supervised.ps1'

function Stop-ZhihengListener {
    $connection = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $connection) { return }
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8787/api/health' -TimeoutSec 3
    } catch {
        throw 'Port 8787 is in use, but the listener could not be verified as Zhiheng. It was not stopped.'
    }
    if ($health.service -ne 'zhiheng-api') {
        throw 'Port 8787 belongs to another service. It was not stopped.'
    }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($connection.OwningProcess)"
    if (-not $process -or $process.CommandLine -notmatch '(^|\s|["''])server\.py(["'']|\s|$)') {
        throw 'The listener answered as Zhiheng but its process command could not be verified. It was not stopped.'
    }
    Stop-Process -Id $connection.OwningProcess -Force
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not (Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue)) { return }
        Start-Sleep -Milliseconds 250
    }
    throw 'Zhiheng listener did not stop within five seconds.'
}

if ($Action -eq 'Status') {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Host 'Zhiheng startup task is not installed.'
        exit 1
    }
    $info = Get-ScheduledTaskInfo -TaskName $taskName
    Write-Output "TaskName=$($task.TaskName)"
    Write-Output "State=$($task.State)"
    $lastRunText = if ($info.LastRunTime) { $info.LastRunTime.ToString('o') } else { 'N/A' }
    $nextRunText = if ($info.NextRunTime) { $info.NextRunTime.ToString('o') } else { 'N/A' }
    Write-Output "LastRunTime=$lastRunText"
    Write-Output ("LastTaskResult={0} (0x{1:X8})" -f $info.LastTaskResult, [uint32]$info.LastTaskResult)
    Write-Output "NextRunTime=$nextRunText"
    try {
        $health = Invoke-RestMethod 'http://127.0.0.1:8787/api/health' -TimeoutSec 3
        Write-Output "Health=$($health.ok) Service=$($health.service)"
    } catch {
        Write-Output "Health=False Error=$($_.Exception.Message)"
    }
    exit 0
}

if ($Action -eq 'Remove') {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Stop-ZhihengListener
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host 'Zhiheng startup task was removed.'
    } else {
        Write-Host 'Zhiheng startup task is not installed.'
    }
    exit 0
}

if (-not (Test-Path -LiteralPath $serverScript)) {
    throw "Missing startup script: $serverScript"
}
$pwshPath = Join-Path $PSHOME 'pwsh.exe'
if (-not (Test-Path -LiteralPath $pwshPath)) {
    $pwshPath = (Get-Command powershell.exe -ErrorAction Stop).Source
}
$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$arguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $serverScript + '"'
$taskAction = New-ScheduledTaskAction -Execute $pwshPath -Argument $arguments -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId
$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $trigger -Principal $principal -Settings $settings -Description 'Runs the local-only Zhiheng health server after sign-in.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Host 'Zhiheng startup task was installed and started.'
