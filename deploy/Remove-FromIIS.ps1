<#
.SYNOPSIS
  Remove the PhotoLibrary IIS site + app pool created by Deploy-ToIIS.ps1.
  Does NOT touch the photo library, the code, or deploy\data (the DB / thumbnails).
#>
[CmdletBinding()]
param(
  [string]$SiteName    = "PhotoLibrary",
  [string]$AppPoolName = "PhotoLibrary"
)
$ErrorActionPreference = "Stop"
Import-Module WebAdministration

if (Test-Path "IIS:\Sites\$SiteName") {
  Remove-Website -Name $SiteName
  Write-Host "removed site $SiteName"
}
if (Test-Path "IIS:\AppPools\$AppPoolName") {
  Remove-WebAppPool -Name $AppPoolName
  Write-Host "removed app pool $AppPoolName"
}
Write-Host "Done. deploy\data (database + thumbnails) was left in place."
