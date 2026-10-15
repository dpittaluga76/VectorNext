[CmdletBinding()]
param(
    [ValidateSet('Menu', 'Setup', 'Start', 'Rebuild', 'Stop', 'Status')]
    [string]$Action = 'Menu',
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$appCompose = Join-Path $projectRoot 'compose.app.yaml'
$appArguments = @('compose', '--project-name', 'vectornext', '--project-directory', $projectRoot, '-f', $appCompose)

function Invoke-Docker {
    param([string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Docker could not finish this step (exit $LASTEXITCODE). Review the message above." }
}
function Check-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install Docker Desktop with WSL 2 and Linux containers, then run Setup again.' }
    $engine = & docker info --format '{{.OSType}}' 2>$null
    if ($LASTEXITCODE -ne 0 -or $engine -ne 'linux') { throw 'Start Docker Desktop using Linux containers, wait until it is ready, and try again.' }
    Invoke-Docker @('compose', 'version')
}
function Check-Installed {
    $configuration = Get-AppConfiguration
    foreach ($service in @('vectornext', 'processor', 'llm')) {
        $image = $configuration.services.$service.image
        & docker image inspect $image --format '{{.Id}}' 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Required image $image is missing. Choose Setup first, or Rebuild after a repository update." }
    }
    $modelRoot = ($configuration.services.processor.volumes | Where-Object { $_.target -eq '/models' }).source
    $manifest = Get-Content -LiteralPath (Join-Path $projectRoot 'experiments/t02/models.26b.lock.json') -Raw | ConvertFrom-Json
    foreach ($model in $manifest.models.PSObject.Properties.Value) {
        foreach ($file in $model.files) {
            $path = Join-Path (Join-Path $modelRoot $model.directory) $file.path
            if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -ne $file.size) { throw "Missing or incomplete model file: $path. Choose Setup to repair it." }
        }
    }
    $pdfManifest = Get-Content -LiteralPath (Join-Path $projectRoot 'processor/models.lock.json') -Raw | ConvertFrom-Json
    foreach ($file in $pdfManifest.files) {
        $path = Join-Path $modelRoot $file.path
        if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -ne $file.bytes) { throw "Missing or incomplete PDF model: $path. Choose Setup to repair it." }
    }
}
function Get-AppConfiguration {
    $raw = & docker @appArguments config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve Compose configuration. Check the repository .env file.' }
    return ($raw | ConvertFrom-Json)
}
function Start-Workspace {
    Check-Installed
    Write-Host 'Starting the installed application. No images or models will be downloaded.' -ForegroundColor Cyan
    Invoke-Docker ($appArguments + @('up', '-d', '--no-build', '--pull', 'never', 'vectornext', 'processor', 'llm'))
    $port = (Get-AppConfiguration).services.vectornext.ports[0].published
    $address = "http://localhost:$port"
    Write-Host 'Waiting for document storage and the browser interface. Model loading continues in the app.'
    $available = $false
    for ($attempt = 0; $attempt -lt 45; $attempt++) {
        try { $health = Invoke-RestMethod "$address/healthz" -TimeoutSec 2; if ($health.live) { $available = $true; break } } catch { }
        Start-Sleep -Seconds 2
    }
    if (-not $available) { throw 'The interface did not start. Choose Status and inspect Docker Desktop logs for the vectornext service.' }
    Write-Host "Ready to browse: $address" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $address }
}
try {
    if ($Action -eq 'Menu') {
        Write-Host "`nVectorNext - local document workspace`n" -ForegroundColor Cyan
        Write-Host '1. Start (everyday use)'
        Write-Host '2. Setup (first use / repair models; internet required)'
        Write-Host '3. Rebuild (after a repository update; internet may be required)'
        Write-Host '4. Stop (keeps documents, models and caches)'
        Write-Host '5. Status'
        $choice = Read-Host 'Choose 1-5, or Enter to start'
        $Action = switch ($choice) { '2' { 'Setup' }; '3' { 'Rebuild' }; '4' { 'Stop' }; '5' { 'Status' }; '' { 'Start' }; '1' { 'Start' }; default { throw 'Choose a number from 1 to 5.' } }
    }
    Check-Docker
    switch ($Action) {
        'Setup' {
            $configuredModels = ((Get-AppConfiguration).services.processor.volumes | Where-Object { $_.target -eq '/models' }).source
            if ([IO.Path]::GetFullPath($configuredModels) -ne [IO.Path]::GetFullPath((Join-Path $projectRoot 'models'))) { throw 'Setup uses this repository models folder. Remove the custom VECTORNEXT_MODELS_DIR setting for Setup, or prepare that directory with the documented developer commands.' }
            Write-Host 'Step 1 of 4: Checking GPU access inside Docker.' -ForegroundColor Cyan
            Invoke-Docker @('compose', '--project-directory', $projectRoot, '-f', (Join-Path $projectRoot 'compose.models.yaml'), 'run', '--rm', '--no-deps', 'gpu-check')
            Write-Host 'Step 2 of 4: Preparing the download tools and verifying local Gemma / embedding / reranking files. Existing valid files are reused.' -ForegroundColor Cyan
            $modelsArguments = @('compose', '--project-directory', $projectRoot, '-f', (Join-Path $projectRoot 'compose.models.yaml'), '-f', (Join-Path $projectRoot 'compose.models.26b.yaml'))
            Invoke-Docker ($modelsArguments + @('build', 'model-download'))
            Invoke-Docker ($modelsArguments + @('run', '--rm', '--no-deps', 'model-download'))
            Write-Host 'Step 3 of 4: Preparing and verifying PDF / OCR assets.' -ForegroundColor Cyan
            $pdfArguments = @('compose', '--project-directory', $projectRoot, '-f', (Join-Path $projectRoot 'compose.processor.yaml'))
            Invoke-Docker ($pdfArguments + @('build', 'processor'))
            Invoke-Docker ($pdfArguments + @('run', '--rm', '--no-deps', 'pdf-setup'))
            Write-Host 'Step 4 of 4: Building the three application services, including browser assets.' -ForegroundColor Cyan
            Invoke-Docker ($appArguments + @('build'))
            Start-Workspace
        }
        'Start' { Start-Workspace }
        'Rebuild' { Write-Host 'Rebuilding application images. Stored documents and models are preserved.'; Invoke-Docker ($appArguments + @('build')); Start-Workspace }
        'Stop' { Invoke-Docker ($appArguments + @('stop', 'vectornext', 'processor', 'llm')); Write-Host 'VectorNext stopped. Documents, models and caches are preserved.' }
        'Status' { Invoke-Docker ($appArguments + @('ps', '-a')); Write-Host 'For details, open Docker Desktop and select the vectornext project.' }
    }
} catch {
    Write-Host "`n$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
