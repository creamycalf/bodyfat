param(
    [string]$Jdk = 'F:\aiworkspace\codexworkspace\moviedl\.tool-downloads\jdk17\jdk-17.0.20.1+1',
    [string]$Gradle = 'F:\aiworkspace\codexworkspace\moviedl\.tool-downloads\gradle\gradle-9.5.0\bin\gradle.bat',
    [switch]$Offline,
    [switch]$EmbedModel,
    [switch]$NoEmbedModel,
    [string]$BaseUrl = ''
)
$ErrorActionPreference = 'Stop'
if ($EmbedModel -and $NoEmbedModel) { throw 'Choose either -EmbedModel or -NoEmbedModel.' }
$includeModel = -not $NoEmbedModel
$standaloneRoot = $PSScriptRoot
$projectRoot = Split-Path -Parent (Split-Path -Parent $standaloneRoot)
$env:JAVA_HOME = $Jdk
$env:GRADLE_USER_HOME = Join-Path $projectRoot 'android\.gradle-standalone'
$pythonPath = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$embeddedAsset = Join-Path $standaloneRoot 'app\src\main\assets\engine\default_model.json'
$prepareArgs = @((Join-Path $standaloneRoot 'prepare.py'))
if ($includeModel) { $prepareArgs += '--embed-model' }
if ($BaseUrl) { $prepareArgs += @('--base-url',$BaseUrl) }
try {
    & $pythonPath @prepareArgs
    if ($LASTEXITCODE -ne 0) { throw 'Asset preparation failed; no keyless fallback was built.' }
    $buildArgs = @('-p',$standaloneRoot,'assembleRelease','--no-daemon')
    if ($Offline) { $buildArgs += '--offline' }
    & $Gradle @buildArgs
    if ($LASTEXITCODE -ne 0) { throw 'APK build failed.' }
    $releaseDir = Join-Path $projectRoot 'release\android-0.4.43'
    New-Item -ItemType Directory -Force $releaseDir | Out-Null
    $apkName = if ($includeModel) { 'Zhiheng-0.4.43-embedded-model-test.apk' } else { 'Zhiheng-0.4.43-standalone-test.apk' }
    $apkPath = Join-Path $releaseDir $apkName
    Copy-Item -LiteralPath (Join-Path $standaloneRoot 'app\build\outputs\apk\release\app-release.apk') -Destination $apkPath -Force
    $hash = (Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -LiteralPath (Join-Path $releaseDir "$apkName.sha256") -Value "$hash  $apkName" -Encoding utf8
    Write-Host "Built $apkPath"
} finally {
    if ($includeModel -and (Test-Path -LiteralPath $embeddedAsset)) {
        Remove-Item -LiteralPath $embeddedAsset -Force
    }
}
