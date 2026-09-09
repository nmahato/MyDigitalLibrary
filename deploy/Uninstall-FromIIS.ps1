<#
.SYNOPSIS
  Remove the PhotoLibrary IIS site + app pool created by Deploy-ToIIS.ps1 and
  strip the NTFS grants it added. Leaves the photo library contents, the code,
  and deploy\data (the DB / thumbnails) alone.

  Run elevated:  .\Uninstall-FromIIS.ps1
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

# The app-pool virtual account SID is deterministic and must be captured BEFORE
# the pool is deleted (afterwards the name no longer resolves and edits that
# reference it by name silently no-op).
function Get-AppPoolSid([string]$name) {
  $bytes = [Security.Cryptography.SHA1]::Create().ComputeHash(
    [Text.Encoding]::Unicode.GetBytes($name.ToLowerInvariant()))
  $chunks = for ($i = 0; $i -lt 5; $i++) { [BitConverter]::ToUInt32($bytes, $i * 4) }
  "S-1-5-82-" + ($chunks -join "-")
}
$poolSid  = Get-AppPoolSid $AppPoolName
$poolName = "IIS APPPOOL\$AppPoolName"

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

# --- paths Deploy-ToIIS.ps1 may have granted into ---
$usersRoot = Join-Path $env:SystemDrive "Users"
$paths = [System.Collections.Generic.List[string]]::new()
@(
  $PhotoLibrary,
  (Join-Path $ProjectRoot "backend"),
  (Join-Path $ProjectRoot "frontend\dist"),
  $PSScriptRoot,
  (Join-Path $PSScriptRoot "logs"),
  (Join-Path $PSScriptRoot "data")
) | ForEach-Object { $paths.Add($_) }

$leaves = @()
$pyCfg = Join-Path $ProjectRoot "backend\.venv\pyvenv.cfg"
if (Test-Path $pyCfg) {
  $m = Select-String -Path $pyCfg -Pattern '^\s*home\s*=\s*(.+)$'
  if ($m) { $leaves += $m.Matches.Groups[1].Value.Trim() }
}
$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ff) { $leaves += (Split-Path -Parent $ff.Source) }
foreach ($leaf in $leaves) {
  $d = $leaf
  while ($d -and $d.Length -ge $usersRoot.Length -and $d -like "$usersRoot*") {
    $paths.Add($d); $d = Split-Path -Parent $d
  }
}

# --- remove the ACEs via the ACL API (works for now-unresolvable SIDs) ---
foreach ($p in ($paths | Select-Object -Unique)) {
  if (-not (Test-Path $p)) { continue }
  $acl = Get-Acl -LiteralPath $p
  $n = 0
  foreach ($ace in @($acl.Access)) {
    if ($ace.IsInherited) { continue }
    $v = $ace.IdentityReference.Value
    if ($v -eq $poolName -or $v -eq $poolSid) { [void]$acl.RemoveAccessRule($ace); $n++ }
  }
  if ($n) {
    Set-Acl -LiteralPath $p -AclObject $acl
    Write-Host "  removed $poolName from $p"
  }
}

Write-Host "Done. deploy\data (database + thumbnails) and deploy\web.config were left in place."
Write-Host "Delete those by hand for a full wipe."
