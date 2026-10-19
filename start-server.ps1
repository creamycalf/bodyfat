$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$existing = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    $health = Invoke-RestMethod 'http://127.0.0.1:8787/api/health' -TimeoutSec 3
    if ($health.service -ne 'zhiheng-api') { throw 'Port 8787 is occupied by another service.' }
    Write-Host 'Zhiheng server is already listening on http://127.0.0.1:8787'
    Start-Process 'http://127.0.0.1:8787'
    exit 0
}

Write-Host 'Starting Zhiheng server with the host Python runtime...'
Write-Host 'Keep this window open. Press Ctrl+C to stop the server.'
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
$configPath = Join-Path $projectRoot 'config.json'
if (Test-Path -LiteralPath $configPath) {
    try {
        $localConfig = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
        $keyEnvName = if ($localConfig.ai.api_key_env) { [string]$localConfig.ai.api_key_env } else { 'ZHIHENG_AI_API_KEY' }
        if (-not [Environment]::GetEnvironmentVariable($keyEnvName, 'Process')) {
            $userKey = [Environment]::GetEnvironmentVariable($keyEnvName, 'User')
            if ($userKey) { [Environment]::SetEnvironmentVariable($keyEnvName, $userKey, 'Process') }
        }
        if ($localConfig.ai.api_key) {
            Write-Warning 'API Key is stored directly in config.json. Prefer the environment variable named by ai.api_key_env, then remove ai.api_key.'
        }
    } catch {
        throw "config.json is not valid JSON: $($_.Exception.Message)"
    }
}
& $pythonPath server.py
