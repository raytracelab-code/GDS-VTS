[CmdletBinding()]
param([string]$Python38, [switch]$SkipTests)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $root
# Windows PowerShell wraps native stderr as ErrorRecords even for successful
# tools (PyInstaller logs INFO there). Check native exit codes explicitly.
$ErrorActionPreference='Continue'
$python=Join-Path $root '.venv-win7\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    if (-not $Python38) { throw 'Pass -Python38 with the full path to an installed CPython 3.8.10 AMD64 python.exe.' }
    & $Python38 -c 'import sys; assert sys.version_info[:3]==(3,8,10) and sys.maxsize>2**32'
    if ($LASTEXITCODE) { throw 'CPython 3.8.10 AMD64 is required.' }
    & $Python38 -m venv .venv-win7
    if ($LASTEXITCODE) { throw 'venv creation failed' }
    & $python -m pip install pip==24.3.1 setuptools==69.5.1 wheel==0.45.1
    if ($LASTEXITCODE) { throw 'Build bootstrap installation failed' }
    & $python -m pip install -r requirements-win7-test.txt
    if ($LASTEXITCODE) { throw 'Dependency installation failed' }
}
& $python -c 'import sys; assert sys.version_info[:3]==(3,8,10) and sys.maxsize>2**32'
if ($LASTEXITCODE) { throw 'Wrong compatibility interpreter' }
& $python -m pip check
if ($LASTEXITCODE) { throw 'Dependency consistency check failed' }
& $python tools\windows\check_environment.py
if ($LASTEXITCODE) { throw 'Legacy release inputs do not match requirements-win7.txt' }
& $python -m compileall -q app main.py tools
if ($LASTEXITCODE) { throw 'Python 3.8 compilation failed' }
if (-not $SkipTests) {
    $oldPlatform=$env:QT_QPA_PLATFORM
    try { $env:QT_QPA_PLATFORM='offscreen'; & $python -m pytest -q --tb=short; if ($LASTEXITCODE) { throw 'Regression tests failed' } }
    finally { $env:QT_QPA_PLATFORM=$oldPlatform }
}
& $python -m PyInstaller --noconfirm --clean --workpath build\win7-pyinstaller gds_vts_win7.spec
if ($LASTEXITCODE) { throw 'PyInstaller failed' }
$ErrorActionPreference='Stop'
$dist=Join-Path $root 'dist\GDS VTS'
foreach ($relative in @('GDS VTS.exe','PySide2\QtWebEngineProcess.exe','app\resources\templates\vdr_executive_brilliance_template.xlsx','app\resources\map\index.html')) {
    if (-not (Test-Path -LiteralPath (Join-Path $dist $relative))) { throw "Missing packaged resource: $relative" }
}
Copy-Item -LiteralPath scripts\Check-WindowsPrerequisites.ps1 -Destination $dist
Copy-Item -LiteralPath docs\windows-compatibility.md -Destination (Join-Path $dist 'Windows compatibility.md')
$files=Get-ChildItem -LiteralPath $dist -Recurse -File
if ($files | Where-Object {$_.FullName.Length -gt 240}) { throw 'Build paths exceed the legacy path budget; use a shorter checkout path.' }
$manifest=$files | ForEach-Object { [pscustomobject]@{Path=$_.FullName.Substring($dist.Length+1);Bytes=$_.Length;SHA256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash} }
$manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $dist 'SHA256SUMS.json') -Encoding UTF8
Get-FileHash -LiteralPath (Join-Path $dist 'GDS VTS.exe') -Algorithm SHA256
Write-Host "Distribute the entire folder: $dist"
