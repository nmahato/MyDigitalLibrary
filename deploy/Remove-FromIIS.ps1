<#
.SYNOPSIS
  Remove the PhotoLibrary IIS site + app pool created by Deploy-ToIIS.ps1, and
  strip the NTFS grants it added. Does NOT touch the photo library contents, the
  code, or deploy\data (the DB / thumbnails).

  Run elevated:  .\Remove-FromIIS.ps1
#>
[CmdletBinding()]
param(
  [string]$SiteName     = "PhotoLibrary",
  [string]$AppPoolName   = "PhotoLibrary",
  [string]$PhotoLibrary  = "D:\PhotoLibrary",
  [string]$ProjectRoot   = (Split-Path -Parent $PSScriptRoot)
)
$ErrorActionPreference = "Continue"
Import-Module WebAdministration

if (Test-Path "IIS:\Sites\$SiteName") {
  Stop-Website -Name $SiteName -ErrorAction SilentlyContinue
  Remove-Website -Name $SiteName
  Write-Host "removed site $SiteName"
}
if (Test-Path "IIS:\AppPools\$AppPoolName") {
  try { Stop-WebAppPool -Name $AppPoolName -ErrorAction SilentlyContinue } catch {}
  Remove-WebAppPool -Name $AppPoolName
  Write-Host "removed app pool $AppPoolName"
}

# kill any HttpPlatformHandler child still running our run.py (leave debugpy alone)
Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'python.exe' -and $_.CommandLine -match '\brun\.py\b' -and $_.CommandLine -notmatch 'debugpy'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

# strip the ACEs Deploy-ToIIS.ps1 granted to the (now gone) virtual pool account
$id = "IIS AppPool\$AppPoolName"
$paths = @(
  $PhotoLibrary,
  (Join-Path $ProjectRoot "backend"),
  (Join-Path $ProjectRoot "frontend\dist"),
  $PSScriptRoot,
  (Join-Path $PSScriptRoot "logs"),
  (Join-Path $PSScriptRoot "data"),
  "$env:SystemDrive\Users",
  "$env:USERPROFILE",
  "$env:LOCALAPPDATA",
  (Split-Path -Parent (Split-Path -Parent $env:LOCALAPPDATA))  # C:\Users\<me>\AppData
)
# plus the per-user Python + ffmpeg dirs the script may have granted into
$pyCfg = Join-Path $ProjectRoot "backend\.venv\pyvenv.cfg"
if (Test-Path $pyCfg) {
  $m = Select-String -Path $pyCfg -Pattern '^\s*home\s*=\s*(.+)$'
  if ($m) { $paths += $m.Matches.Groups[1].Value.Trim() }
}
$ff = (Get-Command ffmpeg -ErrorAction SilentlyContinue)
if ($ff) { $paths += (Split-Path -Parent $ff.Source) }

foreach ($p in ($paths | Select-Object -Unique)) {
  if ((Test-Path $p) -and (((icacls $p) -join "`n") -match [regex]::Escape($id))) {
    icacls $p /remove:g "$id" /C /Q | Out-Null
    Write-Host "  removed $id from $p"
  }
}

Write-Host "Done. deploy\data (database + thumbnails) and deploy\web.config were left in place."
Write-Host "Delete those by hand if you want a full wipe."
