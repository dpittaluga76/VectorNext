# Contract checks with Docker/HTTP/model-file metadata stubs. No services or models are touched.
$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$testRoot = Join-Path $repository ('data/t27/launcher-' + [guid]::NewGuid().ToString('N'))
$mockModels = Join-Path $testRoot 'models'
$mockSizes = @{}
$calls = [System.Collections.Generic.List[object]]::new()
$previousProfile = $env:VECTORNEXT_GENERATOR_PROFILE

foreach ($file in @('deployment/VectorNext.ps1', 'model_worker/generator_profiles.json',
    'experiments/t02/models.26b.lock.json', 'experiments/t27/models.12b.lock.json', 'processor/models.lock.json')) {
    $destination = Join-Path $testRoot $file
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath (Join-Path $repository $file) -Destination $destination
}
foreach ($file in @('experiments/t02/models.26b.lock.json', 'experiments/t27/models.12b.lock.json')) {
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
            vectornext = @{image = 'vectornext-app:t27'; ports = @(@{published = '8088'})}
            processor = @{image = 'vectornext-app-processor:t27'; volumes = @(@{target = '/models'; source = $mockModels})}
            llm = @{image = 'vectornext-app-llm:t27'}
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
    if ($mockSizes.ContainsKey($key)) { return @{Length = $mockSizes[$key]} }
    return Microsoft.PowerShell.Management\Get-Item -LiteralPath $LiteralPath
}
function Assert-Contract { param([bool]$Condition, [string]$Message); if (-not $Condition) { throw $Message } }
function Run-Action {
    param([string]$Action, [string]$Profile = '')
    $calls.Clear()
    & (Join-Path $testRoot 'deployment/VectorNext.ps1') -Action $Action -ModelProfile $Profile -NoBrowser
    Assert-Contract ($LASTEXITCODE -eq 0) ('Launcher failed: ' + $Action)
}
try {
    $env:VECTORNEXT_GENERATOR_PROFILE = $null
    Run-Action 'Start' '12b'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'build' -or $_ -contains 'run' }).Count -eq 0) 'Start built/downloaded models'
    $up = @($calls | Where-Object { $_ -contains 'up' })
    Assert-Contract ($up.Count -eq 1 -and $up[0] -contains '--no-build' -and $up[0] -contains 'never') 'Start lost offline flags'
    $saved = Join-Path $testRoot 'data/launcher/model-profile.txt'
    Assert-Contract ((Get-Content -LiteralPath $saved -Raw).Trim() -eq '12b') 'Profile was not saved'

    $env:VECTORNEXT_GENERATOR_PROFILE = $null
    Run-Action 'Start'
    Assert-Contract ($env:VECTORNEXT_GENERATOR_PROFILE -eq '12b') 'Routine Start forgot the saved model'
    Assert-Contract (@($calls | Where-Object { $_ -contains (Join-Path $testRoot 'compose.app.models.yaml') }).Count -gt 0) 'Saved profile omitted the app override'

    Run-Action 'Setup' '12b'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'model-download' -and $_ -contains (Join-Path $testRoot 'compose.models.12b.yaml') }).Count -eq 2) 'Setup used the wrong download lock'
    Run-Action 'Rebuild'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'build' }).Count -eq 1) 'Rebuild did not explicitly build'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'model-download' }).Count -eq 0) 'Rebuild downloaded model weights'

    Run-Action 'Stop'
    $stop = @($calls | Where-Object { $_ -contains 'stop' })
    Assert-Contract ($stop.Count -eq 1 -and $stop[0] -contains 'vectornext' -and $stop[0] -contains 'processor' -and $stop[0] -contains 'llm') 'Stop has the wrong scope'
    Assert-Contract (@($calls | Where-Object { $_ -contains 'down' -or $_ -contains '--volumes' -or $_ -contains 'prune' }).Count -eq 0) 'Stop removed storage'
    Assert-Contract ((Get-Content -LiteralPath $saved -Raw).Trim() -eq '12b') 'Stop changed model selection'

    Run-Action 'Start' '26b-offload22'
    Assert-Contract ((Get-Content -LiteralPath $saved -Raw).Trim() -eq '26b-offload22') 'Explicit rollback did not persist'
    Write-Output 'PASS: six launcher contracts; all Docker, HTTP and model metadata calls were stubbed.'
} finally {
    $env:VECTORNEXT_GENERATOR_PROFILE = $previousProfile
}
