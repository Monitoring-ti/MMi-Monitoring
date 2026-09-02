# Publica vitrina MMI al VPS (codigo + JSON + HTML)
param(
    [string]$Host = "root@2.25.197.231",
    [string]$RemoteDir = "/opt/mmi",
    [switch]$JsonOnly,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

if (-not $SkipBuild) {
    $env:MMI_DEPLOY_MODE = "vitrina"
    Write-Host ">> Generando vitrina..." -ForegroundColor Cyan
    & .venv\Scripts\python -m mmi.tools.vitrina
    if ($LASTEXITCODE -ne 0) { throw "vitrina fallo" }
}

$jsonFiles = @(
    "query-smoke.json",
    "golden-set-eval.json",
    "rag-validation.json",
    "load-test-report.json",
    "analysis-status.json",
    "ingestion-results.json"
)

Write-Host ">> Sync JSON -> $Host`:$RemoteDir/out/" -ForegroundColor Cyan
foreach ($f in $jsonFiles) {
    $local = Join-Path "out" $f
    if (Test-Path $local) {
        scp $local "${Host}:${RemoteDir}/out/"
    } else {
        Write-Host "   (omitido $f — no existe)" -ForegroundColor DarkYellow
    }
}

if ($JsonOnly) {
    Write-Host ">> Regenerando vitrina en remoto..." -ForegroundColor Cyan
    ssh $Host "cd $RemoteDir && export MMI_DEPLOY_MODE=vitrina && .venv/bin/python -m mmi.tools.vitrina && systemctl restart mmi-api"
    Write-Host "Listo (solo JSON)." -ForegroundColor Green
    exit 0
}

Write-Host ">> Sync logos -> $Host`:$RemoteDir/public/" -ForegroundColor Cyan
foreach ($logo in @("monitoring-logo-horizontal.svg", "monitoring-logo-circular.svg")) {
    $local = Join-Path "public" $logo
    if (Test-Path $local) { scp $local "${Host}:${RemoteDir}/public/" }
}

Write-Host ">> Sync HTML estatico -> $Host`:$RemoteDir/out/" -ForegroundColor Cyan
$htmlFiles = @(
    "index.html", "pruebas.html", "ejemplos.html", "search.html", "rag.html",
    "robots.txt", "vitrina-report.json"
)
foreach ($f in $htmlFiles) {
    $local = Join-Path "out" $f
    if (Test-Path $local) { scp $local "${Host}:${RemoteDir}/out/" }
}

Write-Host @"

>> Siguiente paso (codigo en VPS):
   git push origin feature/mmi-operational-web
   ssh $Host "cd $RemoteDir && git pull && .venv/bin/pip install -e . && export MMI_DEPLOY_MODE=vitrina && .venv/bin/python -m mmi.tools.vitrina && systemctl restart mmi-api"

>> Verificar:
   curl -s -u USUARIO:CLAVE https://mmi.monitoring.lat/
   curl -s -u USUARIO:CLAVE https://mmi.monitoring.lat/api/motor/health

"@ -ForegroundColor Green
