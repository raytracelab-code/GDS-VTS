<# Explicit build/import entry point. Default is a read-only resource preflight. #>
[CmdletBinding()]
param(
    [ValidateSet('preflight','build','package','inspect')][string]$Action = 'preflight',
    [string]$WorkRoot = (Join-Path $env:LOCALAPPDATA 'GDS VTS\map-build'),
    [string]$PlanetilerJar, [string]$Java = 'java',
    [string]$Osm, [string]$Gebco, [switch]$DownloadOsm,
    [ValidateSet(0,4)][int]$MinZoom = 4,
    [ValidateSet(13,14)][int]$MaxZoom = 13,
    [ValidateRange(6,9)][int]$BathymetryMaxZoom = 8,
    [ValidateRange(4,64)][int]$HeapGiB = 6,
    [string]$Basemap, [string]$Bathymetry, [string]$Overview,
    [string[]]$Detail, [string]$Provenance, [string]$Path,
    [string]$Store, [string]$Report, [switch]$Install
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Project virtual environment is missing.' }
$buildArgs = @((Join-Path $PSScriptRoot 'build_southeast_asia.py'),$Action,
    '--work-root',$WorkRoot,'--java',$Java,'--heap-gib',"$HeapGiB",
    '--minzoom',"$MinZoom",'--maxzoom',"$MaxZoom",'--bathymetry-maxzoom',"$BathymetryMaxZoom")
$values = @{'planetiler-jar'=$PlanetilerJar; 'osm'=$Osm; 'gebco'=$Gebco;
    'basemap'=$Basemap; 'bathymetry'=$Bathymetry; 'overview'=$Overview;
    'provenance'=$Provenance; 'path'=$Path; 'store'=$Store; 'report'=$Report}
foreach ($key in $values.Keys) { if ($values[$key]) { $buildArgs += @("--$key",$values[$key]) } }
foreach ($tilePath in $Detail) { $buildArgs += @('--detail',$tilePath) }
if ($DownloadOsm) { $buildArgs += '--download-osm' }
if ($Install) { $buildArgs += '--install' }
& $pythonPath @buildArgs
exit $LASTEXITCODE
