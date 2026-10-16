# Contract checks with Docker/HTTP/model-file metadata stubs. No services or models are touched.
$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$testRoot = Join-Path $repository ('data/t37/launcher-' + [guid]::NewGuid().ToString('N'))
$mockModels = Join-Path $testRoot 'models'
$mockSizes = @{}
$calls = [System.Collections.Generic.List[object]]::new()
$checkedModels = [System.Collections.Generic.List[string]]::new()
$previousProfile = $env:VECTORNEXT_DEFAULT_ANSWER_MODE

foreach ($file in @('deployment/VectorNext.ps1', 'model_worker/generator_profiles.json',
    'model_assets/setup.lock.json', 'processor/models.lock.json')) {
    $destination = Join-Path $testRoot $file
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath (Join-Path $repository $file) -Destination $destination
}
foreach ($file in @('model_assets/setup.lock.json')) {
    $lock = Get-Content -LiteralPath (Join-Path $repository $file) -Raw | ConvertFrom-Json
    foreach ($model in $lock.models.PSObject.Properties.Value) {
        foreach ($artifact in $model.files) {
            $key = [IO.Path]::GetFullPath((Join-Path (Join-Path $mockModels $model.directory) $artifact.path))
            $mockSizes[$key] = $artifact.size
        }
    }
}
$pdf = Get-Content -LiteralPath (Join-Path $repository 'processor/models.lock.json') -Raw | ConvertFrom-Json
foreach ($artifact in $pdf.files) {
    $mockSizes[[IO.Path]::GetFullPath((Join-Path $mockModels $artifact.path))] = $artifact.bytes
}

function docker {
    $calls.Add(@($args))
    $global:LASTEXITCODE = 0
    if ($args[0] -eq 'info') { return 'linux' }
    if ($args -contains 'config') {
        return (@{services = @{
            vectornext = @{image = 'vectornext-app:t28-12b'; ports = @(@{published = '8088'})}
            processor = @{image = 'vectornext-app-processor:t28-12b'; volumes = @(@{target = '/models'; source = $mockModels})}
            llm = @{image = 'vectornext-app-llm:t28-12b'}
        }} | ConvertTo-Json -Depth 8)
    }
}
function Invoke-RestMethod { param($Uri, $TimeoutSec); return @{live = $true} }
function Test-Path {
    param([string]$LiteralPath, [string]$Path, [string]$PathType)
    if ($LiteralPath -and $mockSizes.ContainsKey([IO.Path]::GetFullPath($LiteralPath))) { return $true }
    return Microsoft.PowerShell.Management\Test-Path @PSBoundParameters
}
function Get-Item {
    param([string]$LiteralPath)
    $key = [IO.Path]::GetFullPath($LiteralPath)
    if ($mockSizes.ContainsKey($key)) { $checkedModels.Add($key); return @{Length = $mockSizes[$key]} }
    return Microsoft.PowerShell.Management\Get-Item -LiteralPath $LiteralPath
}
function Assert-Contract { param([bool]$Condition, [string]$Message); if (-not $Condition) { throw $Message } }
function Run-Action {
    param([string]$Action, [string]$Profile = '')
    $calls.Clear()
    & (Join-Path $testRoot 'deployment/VectorNext.ps1') -Action $Action -AnswerMode $Profile -NoBrowser
    Assert-Contract ($LASTEXITCODE -eq 0) ('Launcher failed: ' + $Action)
}
try {
    $env:VECTORNEXT_DEFAULT_ANSWER_MODE = $null
    $legacy = Join-Path $testRoot 'data/launcher/model-profile.txt'
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $legacy) | Out-Null
    Set-Content -LiteralPath $legacy -Value '26b-offload22'
    Run-Action 'Start'
    Assert-Contract ($env:VECTORNEXT_DEFAULT_ANSWER_MODE -eq 'hybrid') 'Legacy selection did not migrate to Hybrid'
    Assert-Contract (@($checkedModels | Where-Object { $_ -like '*generator-12b*' }).Count -gt 0) 'Start did not check Gemma'
    Assert-Contract (@($checkedModels | Where-Object { $_ -like '*nuextract*' }).Count -gt 0) 'Start did not check NuExtract'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'build' -or (($_ -contains 'run') -and ($_ -notcontains 'check-generator')) }).Count -eq 0) 'Start built/downloaded models'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'check-generator' -and $_ -contains 'never' }).Count -eq 1) 'Start skipped offline unfinished-ingestion guard'
    Assert-Contract (@($calls | Where-Object { $_ -contains '--no-build' -and $_ -contains 'never' }).Count -eq 1) 'Start did not enforce offline image reuse'
    Run-Action 'Setup'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'model-download' }).Count -eq 2) 'Setup must build and run the combined verified model setup'
    Run-Action 'Start' 'gemma'
    Assert-Contract ($env:VECTORNEXT_DEFAULT_ANSWER_MODE -eq 'gemma') 'Explicit Gemma selection lost'
    Run-Action 'Start'
    Assert-Contract ($env:VECTORNEXT_DEFAULT_ANSWER_MODE -eq 'gemma') 'New mode was not persisted'
    Run-Action 'Start' 'nuextract'
    Assert-Contract ($env:VECTORNEXT_DEFAULT_ANSWER_MODE -eq 'nuextract') 'Explicit NuExtract selection lost'
    Run-Action 'Stop'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'stop' -and $_ -contains 'vectornext' -and $_ -contains 'processor' -and $_ -contains 'llm' }).Count -eq 1) 'Stop must target only normal services'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'down' -or $_ -contains '-v' }).Count -eq 0) 'Stop deleted state'
    Write-Host 'T37 launcher contracts passed.' -ForegroundColor Green
} finally {
    $env:VECTORNEXT_DEFAULT_ANSWER_MODE = $previousProfile
}
