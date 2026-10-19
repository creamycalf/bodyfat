$ErrorActionPreference = 'Stop'
$configPath = Join-Path $PSScriptRoot 'config.json'
$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
$key = [string]$config.ai.api_key
if (-not $key) { throw 'No direct ai.api_key to migrate.' }
$name = 'ZHIHENG_AI_API_KEY'
$existing = [Environment]::GetEnvironmentVariable($name, 'User')
if ($existing -and $existing -ne $key) { throw 'A different user environment key already exists; nothing changed.' }
[Environment]::SetEnvironmentVariable($name, $key, 'User')
if ([Environment]::GetEnvironmentVariable($name, 'User') -ne $key) { throw 'Environment key verification failed; config retained.' }
$config.ai | Add-Member -NotePropertyName api_key_env -NotePropertyValue $name -Force
$config.ai.PSObject.Properties.Remove('api_key')
$config.ai.PSObject.Properties.Remove('apiKey')
$temporary = $configPath + '.tmp'
[IO.File]::WriteAllText($temporary, ($config | ConvertTo-Json -Depth 20), (New-Object Text.UTF8Encoding($false)))
Move-Item -LiteralPath $temporary -Destination $configPath -Force
Write-Output 'Key migrated to user environment; plaintext key removed from config.json.'
