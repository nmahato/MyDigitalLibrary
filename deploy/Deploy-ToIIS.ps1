<#
.SYNOPSIS
  Deploy PhotoLibrary Viewer as a local IIS site (FastAPI via HttpPlatformHandler).

.DESCRIPTION
  Idempotent. Run from an elevated PowerShell prompt:

      cd C:\Personal\projects\ImageViewer\deploy
      .\Deploy-ToIIS.ps1 -Port 9090 -PhotoLibrary D:\PhotoLibrary

  Re-run after pulling new code with -Build to rebuild the frontend and refresh deps.

  Python / ffmpeg installed per-user (under %LOCALAPPDATA%, e.g. the Python
  install-manager or a winget ffmpeg) are NOT readable by the default
  ApplicationPoolIdentity. The script handles this by either:
    * running the pool as a real account  ->  pass -PoolUser / -PoolPassword
    * or granting the pool identity read/traverse into just those folders (default)

.NOTES
  Prerequisites:
    * IIS + the "HttpPlatformHandler" module
      https://www.iis.net/downloads/microsoft/httpplatformhandler
    * Python 3.11+ and Node.js on PATH (first deploy only, to build)
#>
[CmdletBinding()]
param(
  [string]$SiteName       = "PhotoLibrary",
  [string]$AppPoolName     = "PhotoLibrary",
  [int]   $Port            = 9090,
  [string]$PhotoLibrary    = "D:\PhotoLibrary",
  [string]$ProjectRoot     = (Split-Path -Parent $PSScriptRoot),
  [string]$PoolUser        = "",          # e.g. "MACHINE\me" — pool runs as this account
  [string]$PoolPassword    = "",          # omit to be prompted securely
  [switch]$DeepLibraryAcl,                # one-time recursive ACL over the whole library
  [switch]$Build
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  $p  = New-Object Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this script from an elevated (Administrator) PowerShell prompt."
  }
}

function Grant-Path {
  param(
    [string]$Path, [string]$Identity,
    [ValidateSet("RX","M")]$Level,
    [switch]$Recurse
  )
  if (-not (Test-Path $Path)) { return }
  $perm = if ($Level -eq "M") { "(OI)(CI)M" } else { "(OI)(CI)RX" }
  $extra = if ($Recurse) { @("/T") } else { @() }
  & icacls $Path /grant "${Identity}:$perm" @extra /C /Q | Out-Null
  Write-Host ("  {0,-2} {1} {2}" -f $Level, ($(if($Recurse){"(recursive)"}else{"         "})), $Path)
}

function Grant-Traverse {
  # "this folder only" RX (list + traverse, no inheritance) from $Target up to $StopAt.
  param([string]$Target, [string]$Identity, [string]$StopAt)
  $dir = Split-Path -Parent $Target
  while ($dir -and $dir.Length -ge $StopAt.Length -and $dir -like "$StopAt*") {
    & icacls $dir /grant "${Identity}:(RX)" /C /Q | Out-Null
    $dir = Split-Path -Parent $dir
  }
}

function Grant-BatchLogon {
  # Give a user account the "Log on as a batch job" right (SeBatchLogonRight).
  # IIS usually does this itself, but not always via a raw config edit.
  param([string]$Account)
  try {
    $sid = (New-Object Security.Principal.NTAccount($Account)).Translate(
      [Security.Principal.SecurityIdentifier]).Value
  } catch { Write-Warning "could not resolve $Account for batch-logon right"; return }
  $inf = Join-Path $env:TEMP "pl_secpol.inf"
  $sdb = Join-Path $env:TEMP "pl_secpol.sdb"
  secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
  $cur = (Select-String -Path $inf -Pattern '^SeBatchLogonRight\s*=\s*(.*)$').Matches.Groups[1].Value
  if ($cur -match [regex]::Escape($sid)) { return }
  $new = if ($cur) { "SeBatchLogonRight = $cur,*$sid" } else { "SeBatchLogonRight = *$sid" }
  $body = @"
[Unicode]
Unicode=yes
[Version]
signature="`$CHICAGO`$"
[Privilege Rights]
$new
"@
  Set-Content -Path $inf -Value $body -Encoding Unicode
  secedit /configure /db $sdb /cfg $inf /areas USER_RIGHTS | Out-Null
  Remove-Item $inf, $sdb -ErrorAction SilentlyContinue
  Write-Host "  granted 'Log on as a batch job' to $Account"
}

Assert-Admin
Import-Module WebAdministration -ErrorAction Stop

$deployDir  = $PSScriptRoot
$backendDir = Join-Path $ProjectRoot "backend"
$frontDist  = Join-Path $ProjectRoot "frontend\dist"
$venvDir    = Join-Path $backendDir ".venv"
$venvPy     = Join-Path $venvDir "Scripts\python.exe"
$logsDir    = Join-Path $deployDir "logs"
$dataDir    = Join-Path $deployDir "data"

$useSpecificUser = [bool]$PoolUser
$poolId = if ($useSpecificUser) { $PoolUser } else { "IIS AppPool\$AppPoolName" }

Write-Host "== PhotoLibrary -> IIS ==" -ForegroundColor Cyan
Write-Host "project    : $ProjectRoot"
Write-Host "site/pool  : $SiteName / $AppPoolName   port $Port"
Write-Host "identity   : $poolId"
Write-Host "library    : $PhotoLibrary"

# --- 0. prerequisites --------------------------------------------------
$schema = Join-Path $env:WINDIR "System32\inetsrv\config\schema\httpplatform_schema.xml"
if (-not (Test-Path $schema)) {
  throw "HttpPlatformHandler is not installed. https://www.iis.net/downloads/microsoft/httpplatformhandler"
}
if ($useSpecificUser -and -not $PoolPassword) {
  $sec = Read-Host "Windows password for $PoolUser" -AsSecureString
  $PoolPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
  if (-not $PoolPassword) { throw "no password entered" }
}

# --- port free? (ok if the port already belongs to our own site) ------
$portOwner = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($portOwner) {
  $ours = $false
  if (Test-Path "IIS:\Sites\$SiteName") {
    $b = (Get-WebBinding -Name $SiteName -ErrorAction SilentlyContinue).bindingInformation
    if ($b -and $b -match ":${Port}:") { $ours = $true }
  }
  if (-not $ours) {
    throw "Port $Port is in use (PID $($portOwner.OwningProcess | Select-Object -First 1)). Use -Port."
  }
}

New-Item -ItemType Directory -Force -Path $logsDir, $dataDir | Out-Null

# --- 1. backend venv + deps ------------------------------------------
if (-not (Test-Path $venvPy)) {
  Write-Host "creating backend venv..."
  & py -3 -m venv $venvDir
  if (-not (Test-Path $venvPy)) { & python -m venv $venvDir }
}
if ($Build -or -not (Test-Path (Join-Path $venvDir "Lib\site-packages\fastapi"))) {
  Write-Host "installing backend requirements..."
  & $venvPy -m pip install --disable-pip-version-check -q --upgrade pip
  & $venvPy -m pip install --disable-pip-version-check -q -r (Join-Path $backendDir "requirements.txt")
}

# --- 2. frontend build ----------------------------------------------
if ($Build -or -not (Test-Path (Join-Path $frontDist "index.html"))) {
  Write-Host "building frontend..."
  Push-Location (Join-Path $ProjectRoot "frontend")
  try {
    if (Test-Path "package-lock.json") { & npm ci } else { & npm install }
    & npm run build
  } finally { Pop-Location }
}
if (-not (Test-Path (Join-Path $frontDist "index.html"))) { throw "frontend build missing at $frontDist" }

# --- 3. locate the base Python + ffmpeg the venv/app actually need ----
$basePython = $null
$pyvenvCfg = Join-Path $venvDir "pyvenv.cfg"
if (Test-Path $pyvenvCfg) {
  $m = Select-String -Path $pyvenvCfg -Pattern '^\s*home\s*=\s*(.+)$'
  if ($m) { $basePython = $m.Matches.Groups[1].Value.Trim() }
}
$ff = @{}
foreach ($bin in "ffmpeg","ffprobe") {
  $cmd = Get-Command $bin -ErrorAction SilentlyContinue
  if ($cmd) { $ff[$bin] = $cmd.Source }
}

# --- 4. render web.config ------------------------------------------
$tpl = Get-Content (Join-Path $deployDir "web.config.template") -Raw
$tpl = $tpl -replace 'processPath="[^"]*"', ('processPath="' + $venvPy + '"')
$tpl = $tpl -replace 'arguments="[^"]*"',   ('arguments="'  + (Join-Path $backendDir "run.py") + '"')
$tpl = $tpl -replace 'stdoutLogFile="[^"]*"', ('stdoutLogFile="' + (Join-Path $logsDir "stdout") + '"')
$tpl = $tpl -replace '(name="PYTHONPATH" value=")[^"]*(")',      ('${1}' + $backendDir + '${2}')
$tpl = $tpl -replace '(name="PHOTO_LIBRARY" value=")[^"]*(")',   ('${1}' + $PhotoLibrary + '${2}')
$tpl = $tpl -replace '(name="IMAGEVIEWER_DATA" value=")[^"]*(")',('${1}' + $dataDir + '${2}')
if ($ff.Count -eq 2) {
  $inject = "        <environmentVariable name=`"FFMPEG_BINARY`" value=`"$($ff['ffmpeg'])`" />`r`n" +
            "        <environmentVariable name=`"FFPROBE_BINARY`" value=`"$($ff['ffprobe'])`" />`r`n      </environmentVariables>"
  $tpl = $tpl -replace '\s*</environmentVariables>', ("`r`n" + $inject)
  Write-Host "  ffmpeg  : $($ff['ffmpeg'])"
} else {
  Write-Warning "ffmpeg/ffprobe not on PATH - video thumbnails & metadata will be limited."
}
Set-Content -Path (Join-Path $deployDir "web.config") -Value $tpl -Encoding UTF8
Write-Host "web.config written"

# --- 5. app pool --------------------------------------------------
if (-not (Test-Path "IIS:\AppPools\$AppPoolName")) { New-WebAppPool -Name $AppPoolName | Out-Null }
$ap = "IIS:\AppPools\$AppPoolName"
Set-ItemProperty $ap managedRuntimeVersion ""
Set-ItemProperty $ap startMode "AlwaysRunning"
Set-ItemProperty $ap processModel.idleTimeout "00:00:00"
Set-ItemProperty $ap processModel.loadUserProfile $true
Set-ItemProperty $ap recycling.periodicRestart.time "00:00:00"
Set-ItemProperty $ap recycling.disallowRotationOnConfigChange $true
Set-ItemProperty $ap failure.rapidFailProtection $false
if ($useSpecificUser) {
  Set-ItemProperty $ap processModel.identityType "SpecificUser"
  Set-ItemProperty $ap processModel.userName $PoolUser
  Set-ItemProperty $ap processModel.password $PoolPassword
  Grant-BatchLogon $PoolUser
} else {
  Set-ItemProperty $ap processModel.identityType "ApplicationPoolIdentity"
}

# --- 6. site -----------------------------------------------------
if (Test-Path "IIS:\Sites\$SiteName") {
  Set-ItemProperty "IIS:\Sites\$SiteName" physicalPath $deployDir
  Set-ItemProperty "IIS:\Sites\$SiteName" applicationPool $AppPoolName
  Get-WebBinding -Name $SiteName | Remove-WebBinding
  New-WebBinding -Name $SiteName -Protocol http -Port $Port -IPAddress "*"
} else {
  New-Website -Name $SiteName -PhysicalPath $deployDir -ApplicationPool $AppPoolName `
              -Port $Port -IPAddress "*" | Out-Null
}

# --- 7. filesystem permissions ---------------------------------
Write-Host "permissions for $poolId :"
Grant-Path -Path $backendDir   -Identity $poolId -Level RX
Grant-Path -Path $frontDist    -Identity $poolId -Level RX
Grant-Path -Path $deployDir    -Identity $poolId -Level RX
Grant-Path -Path $logsDir      -Identity $poolId -Level M
Grant-Path -Path $dataDir      -Identity $poolId -Level M
# Library: inheritance flags cover files created from now on; -DeepLibraryAcl
# forces the (slow) recursive pass over everything already there.
Grant-Path -Path $PhotoLibrary -Identity $poolId -Level M -Recurse:$DeepLibraryAcl

if (-not $useSpecificUser) {
  # Reach the per-user Python / ffmpeg that live under a profile.
  $usersRoot = Join-Path $env:SystemDrive "Users"
  foreach ($p in @($basePython, ($ff.Values | ForEach-Object { Split-Path -Parent $_ }))) {
    if ($p -and (Test-Path $p) -and $p -like "$usersRoot\*") {
      Write-Host "  granting read into per-user path: $p"
      Grant-Path -Path $p -Identity $poolId -Level RX -Recurse
      Grant-Traverse -Target $p -Identity $poolId -StopAt $usersRoot
    }
  }
}

# --- 8. (re)start ----------------------------------------------
Stop-WebSite  -Name $SiteName -ErrorAction SilentlyContinue
Start-WebAppPool -Name $AppPoolName -ErrorAction SilentlyContinue   # clears "disabled" state
Restart-WebAppPool -Name $AppPoolName
Start-WebSite -Name $SiteName -ErrorAction SilentlyContinue

$ok = $false
foreach ($try in 1..8) {
  Start-Sleep -Seconds 2
  try {
    $r = Invoke-RestMethod "http://localhost:$Port/api/health" -TimeoutSec 10
    if ($r.ok) { $ok = $true; break }
  } catch { }
}
Write-Host ""
if ($ok) {
  Write-Host "OK  ->  http://localhost:$Port/" -ForegroundColor Green
} else {
  Write-Warning "Pool started but /api/health is not answering. Last stdout log:"
  Get-ChildItem "$logsDir\stdout*.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime | Select-Object -Last 1 |
    ForEach-Object { Get-Content $_.FullName -Tail 30 }
}
