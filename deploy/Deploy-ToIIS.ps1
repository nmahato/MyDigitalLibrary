<#
.SYNOPSIS
  Deploy PhotoLibrary Viewer as a local IIS site (FastAPI via HttpPlatformHandler).

.DESCRIPTION
  Idempotent. Run from an elevated PowerShell prompt:

      cd C:\Personal\projects\ImageViewer\deploy
      .\Deploy-ToIIS.ps1 -Port 8090 -PhotoLibrary D:\PhotoLibrary

  Re-run after pulling new code with -Build to rebuild the frontend and refresh deps.

.NOTES
  Prerequisites on the machine:
    * IIS with the "HttpPlatformHandler" module
      https://www.iis.net/downloads/microsoft/httpplatformhandler
    * Python 3.11+ on PATH (to create the backend venv), Node.js (to build the frontend)
    * ffmpeg / ffprobe on the machine PATH (or set FFMPEG_BINARY/FFPROBE_BINARY in web.config)
#>
[CmdletBinding()]
param(
  [string]$SiteName     = "PhotoLibrary",
  [string]$AppPoolName   = "PhotoLibrary",
  [int]   $Port          = 8099,
  [string]$PhotoLibrary  = "D:\PhotoLibrary",
  [string]$ProjectRoot   = (Split-Path -Parent $PSScriptRoot),
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
  param([string]$Path, [string]$Identity, [ValidateSet("RX","M")]$Level)
  if (-not (Test-Path $Path)) { return }
  $perm = if ($Level -eq "M") { "(OI)(CI)M" } else { "(OI)(CI)RX" }
  & icacls $Path /grant "${Identity}:$perm" /T /C /Q | Out-Null
  Write-Host "  granted $Level on $Path to $Identity"
}

Assert-Admin
Import-Module WebAdministration -ErrorAction Stop

$deployDir  = $PSScriptRoot
$backendDir = Join-Path $ProjectRoot "backend"
$frontDist  = Join-Path $ProjectRoot "frontend\dist"
$venvPy     = Join-Path $backendDir ".venv\Scripts\python.exe"
$logsDir    = Join-Path $deployDir "logs"
$dataDir    = Join-Path $deployDir "data"
$poolId     = "IIS AppPool\$AppPoolName"

Write-Host "== PhotoLibrary -> IIS ==" -ForegroundColor Cyan
Write-Host "project    : $ProjectRoot"
Write-Host "site/pool  : $SiteName / $AppPoolName   port $Port"
Write-Host "library    : $PhotoLibrary"

# --- 0. HttpPlatformHandler present? ---------------------------------------
$schema = Join-Path $env:WINDIR "System32\inetsrv\config\schema\httpplatform_schema.xml"
if (-not (Test-Path $schema)) {
  throw "HttpPlatformHandler is not installed. Get it from " +
        "https://www.iis.net/downloads/microsoft/httpplatformhandler then re-run."
}

# --- port free? (ignore a port already owned by our own site) -----------
$portOwner = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
if ($portOwner) {
  $ours = $false
  if (Test-Path "IIS:\Sites\$SiteName") {
    $b = (Get-WebBinding -Name $SiteName -ErrorAction SilentlyContinue).bindingInformation
    if ($b -and $b -match ":${Port}:") { $ours = $true }
  }
  if (-not $ours) {
    throw "Port $Port is already in use (PID $($portOwner.OwningProcess | Select-Object -First 1)). Pick another with -Port."
  }
}

New-Item -ItemType Directory -Force -Path $logsDir, $dataDir | Out-Null

# --- 1. backend venv + deps ----------------------------------------------
if (-not (Test-Path $venvPy)) {
  Write-Host "creating backend venv..."
  & py -3 -m venv (Join-Path $backendDir ".venv")
  if (-not $?) { & python -m venv (Join-Path $backendDir ".venv") }
}
if ($Build -or -not (Test-Path (Join-Path $backendDir ".venv\Lib\site-packages\fastapi"))) {
  Write-Host "installing backend requirements..."
  & $venvPy -m pip install --disable-pip-version-check -q --upgrade pip
  & $venvPy -m pip install --disable-pip-version-check -q -r (Join-Path $backendDir "requirements.txt")
}

# --- 2. frontend build --------------------------------------------------
if ($Build -or -not (Test-Path (Join-Path $frontDist "index.html"))) {
  Write-Host "building frontend..."
  Push-Location (Join-Path $ProjectRoot "frontend")
  try {
    if (Test-Path "package-lock.json") { & npm ci } else { & npm install }
    & npm run build
  } finally { Pop-Location }
}
if (-not (Test-Path (Join-Path $frontDist "index.html"))) {
  throw "frontend build missing at $frontDist"
}

# --- 3. render web.config ---------------------------------------------
$tpl = Get-Content (Join-Path $deployDir "web.config.template") -Raw
$tpl = $tpl -replace 'processPath="[^"]*"', ('processPath="' + $venvPy + '"')
$tpl = $tpl -replace 'arguments="[^"]*"',   ('arguments="'  + (Join-Path $backendDir "run.py") + '"')
$tpl = $tpl -replace 'stdoutLogFile="[^"]*"', ('stdoutLogFile="' + (Join-Path $logsDir "stdout") + '"')
$tpl = $tpl -replace '(name="PYTHONPATH" value=")[^"]*(")',      ('${1}' + $backendDir + '${2}')
$tpl = $tpl -replace '(name="PHOTO_LIBRARY" value=")[^"]*(")',   ('${1}' + $PhotoLibrary + '${2}')
$tpl = $tpl -replace '(name="IMAGEVIEWER_DATA" value=")[^"]*(")',('${1}' + $dataDir + '${2}')

# Bake in ffmpeg/ffprobe absolute paths — the IIS pool identity won't have the
# deploying user's PATH (e.g. a winget install under %LOCALAPPDATA%).
$ff = @{}
foreach ($bin in "ffmpeg","ffprobe") {
  $cmd = Get-Command $bin -ErrorAction SilentlyContinue
  if ($cmd) { $ff[$bin] = $cmd.Source }
}
if ($ff.Count -eq 2) {
  $inject = "        <environmentVariable name=`"FFMPEG_BINARY`" value=`"$($ff['ffmpeg'])`" />`r`n" +
            "        <environmentVariable name=`"FFPROBE_BINARY`" value=`"$($ff['ffprobe'])`" />`r`n      </environmentVariables>"
  $tpl = $tpl -replace '\s*</environmentVariables>', ("`r`n" + $inject)
  Write-Host "  ffmpeg  : $($ff['ffmpeg'])"
} else {
  Write-Warning "ffmpeg/ffprobe not found on PATH - video thumbnails & metadata will be skipped. " +
                "Install them or edit FFMPEG_BINARY/FFPROBE_BINARY in web.config."
}

Set-Content -Path (Join-Path $deployDir "web.config") -Value $tpl -Encoding UTF8
Write-Host "web.config written"

# --- 4. app pool -----------------------------------------------------
if (-not (Test-Path "IIS:\AppPools\$AppPoolName")) {
  New-WebAppPool -Name $AppPoolName | Out-Null
}
Set-ItemProperty "IIS:\AppPools\$AppPoolName" managedRuntimeVersion ""          # No Managed Code
Set-ItemProperty "IIS:\AppPools\$AppPoolName" startMode "AlwaysRunning"
Set-ItemProperty "IIS:\AppPools\$AppPoolName" processModel.idleTimeout "00:00:00"
Set-ItemProperty "IIS:\AppPools\$AppPoolName" processModel.loadUserProfile $true
Set-ItemProperty "IIS:\AppPools\$AppPoolName" recycling.periodicRestart.time "00:00:00"
Set-ItemProperty "IIS:\AppPools\$AppPoolName" recycling.disallowRotationOnConfigChange $true

# --- 5. site --------------------------------------------------------
if (Test-Path "IIS:\Sites\$SiteName") {
  Set-ItemProperty "IIS:\Sites\$SiteName" physicalPath $deployDir
  Set-ItemProperty "IIS:\Sites\$SiteName" applicationPool $AppPoolName
  Get-WebBinding -Name $SiteName | Remove-WebBinding
  New-WebBinding -Name $SiteName -Protocol http -Port $Port -IPAddress "*"
} else {
  New-Website -Name $SiteName -PhysicalPath $deployDir -ApplicationPool $AppPoolName `
              -Port $Port -IPAddress "*" | Out-Null
}

# --- 6. filesystem permissions for the pool identity -----------------
Write-Host "setting permissions..."
Grant-Path -Path $backendDir  -Identity $poolId -Level RX
Grant-Path -Path $frontDist   -Identity $poolId -Level RX
Grant-Path -Path $logsDir     -Identity $poolId -Level M
Grant-Path -Path $dataDir     -Identity $poolId -Level M
Grant-Path -Path $deployDir   -Identity $poolId -Level RX
Grant-Path -Path $PhotoLibrary -Identity $poolId -Level M   # app imports / converts / deletes

# --- 7. (re)start ---------------------------------------------------
Restart-WebAppPool -Name $AppPoolName
Start-Website -Name $SiteName -ErrorAction SilentlyContinue

Start-Sleep -Seconds 3
try {
  $r = Invoke-RestMethod "http://localhost:$Port/api/health" -TimeoutSec 15
  Write-Host ""
  Write-Host "OK  ->  http://localhost:$Port/   (health: $($r | ConvertTo-Json -Compress))" -ForegroundColor Green
} catch {
  Write-Warning "Site created but /api/health did not answer yet. Check $logsDir\stdout*.log"
}
