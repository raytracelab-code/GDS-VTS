# Run before the executable: loader failures occur before Python can show a dialog.
[CmdletBinding()]
param([switch]$Launch)
$ErrorActionPreference='Stop'
$failures=New-Object System.Collections.Generic.List[string]
$os=Get-WmiObject Win32_OperatingSystem
$version=[version]$os.Version
if (-not [Environment]::Is64BitOperatingSystem) { $failures.Add('64-bit Windows is required.') }
if ($version -lt [version]'6.1' -or ($version.Major -eq 6 -and $version.Minor -eq 1 -and $os.ServicePackMajorVersion -lt 1)) {
    $failures.Add('Windows 7 SP1 or later is required.')
}
if (-not (Test-Path -LiteralPath "$env:windir\System32\ucrtbase.dll")) {
    $failures.Add('Install the Universal C Runtime update KB2999226 (or its replacement) and restart Windows.')
}
foreach ($dll in @('vcruntime140.dll','msvcp140.dll')) {
    if (-not (Test-Path -LiteralPath "$env:windir\System32\$dll")) {
        $failures.Add('Install Microsoft Visual C++ 2015-2019 Redistributable x64 (14.29, Windows 7 compatible).')
        break
    }
}
if ($version.Major -eq 6 -and $version.Minor -eq 1) {
    $updates=@(Get-HotFix | ForEach-Object {$_.HotFixID})
    # Superseding rollups may contain these fixes without listing individual KBs.
    foreach ($kb in @('KB4474419','KB4490628')) {
        if ($updates -notcontains $kb) { Write-Warning "$kb is not listed. Verify SHA-2/servicing support through an applicable superseding rollup before installation." }
    }
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class GdsLoaderProbe {
 [DllImport("kernel32.dll", CharSet=CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr h, string name);
 [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern IntPtr GetModuleHandle(string name);
 public static bool Available() { return GetProcAddress(GetModuleHandle("kernel32.dll"),"AddDllDirectory") != IntPtr.Zero; }
}
'@
    if (-not [GdsLoaderProbe]::Available()) { $failures.Add('Install Windows loader update KB2533623 / KB3063858 or a superseding rollup and restart.') }
}
if ($failures.Count) {
    $message="GDS VTS prerequisites are missing:`r`n"+($failures -join "`r`n")
    Write-Host $message
    if ($Launch) { Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show($message,'GDS VTS prerequisites') | Out-Null }
    exit 1
}
Write-Host 'Basic Windows prerequisites detected. This check does not certify OS runtime compatibility.'
if ($Launch) { Start-Process -FilePath (Join-Path $PSScriptRoot 'GDS VTS.exe') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden }
