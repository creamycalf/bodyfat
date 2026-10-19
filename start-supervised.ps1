param(
    [ValidateRange(0, 100)]
    [int]$MaxRestarts = 10,
    [ValidateRange(1, 60)]
    [int]$RestartDelaySeconds = 2
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$existing = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    throw 'Port 8787 is already in use. Stop the existing process before starting supervised mode.'
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$commandPath = if ($pythonCommand) { $pythonCommand.Source } else { $null }
$candidates = @(
    (Join-Path $projectRoot '.venv\Scripts\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'hermes\hermes-agent\venv\Scripts\python.exe'),
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    $commandPath
) | Where-Object { $_ -and $_ -notlike '*\WindowsApps\*' } | Select-Object -Unique
$pythonPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $pythonPath) {
    throw 'Python 3 was not found. Install Python or add python.exe to PATH.'
}

$restartCount = 0
$supervisorLog = Join-Path $projectRoot '.logs\supervisor.log'
$null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $supervisorLog)
$configPath = Join-Path $projectRoot 'config.json'
if (Test-Path -LiteralPath $configPath) {
    $localConfig = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
    $keyEnvName = if ($localConfig.ai.api_key_env) { [string]$localConfig.ai.api_key_env } else { 'ZHIHENG_AI_API_KEY' }
    if (-not [Environment]::GetEnvironmentVariable($keyEnvName, 'Process')) {
        $userKey = [Environment]::GetEnvironmentVariable($keyEnvName, 'User')
        if ($userKey) { [Environment]::SetEnvironmentVariable($keyEnvName, $userKey, 'Process') }
    }
}
while ($true) {
    Add-Content -LiteralPath $supervisorLog -Value "$(Get-Date -Format o) starting server.py (attempt $($restartCount + 1))"
    & $pythonPath server.py
    $exitCode = $LASTEXITCODE
    Add-Content -LiteralPath $supervisorLog -Value "$(Get-Date -Format o) server.py exited with code $exitCode"
    if ($restartCount -ge $MaxRestarts) {
        throw "Zhiheng exited with code $exitCode and reached the restart limit ($MaxRestarts)."
    }
    $restartCount++
    Write-Warning "Zhiheng exited with code $exitCode. Restart $restartCount of $MaxRestarts in $RestartDelaySeconds seconds."
    Start-Sleep -Seconds $RestartDelaySeconds
}
