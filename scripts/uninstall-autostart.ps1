# ==================================================================
#  Removes the logon shortcut created by install-autostart.ps1.
#  Running servers are left alone; use the launcher to stop them:
#      pythonw scripts\launcher.pyw stop
# ==================================================================
[CmdletBinding()]
param(
    [string]$Name = "Social Auto Upload"
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup "$Name.lnk"

if (Test-Path $lnkPath) {
    Remove-Item $lnkPath -Force
    Write-Host "Removed: $lnkPath"
} else {
    Write-Host "Nothing to remove - $lnkPath does not exist."
}

$pathsFile = Join-Path $scriptDir 'paths.json'
if (Test-Path $pathsFile) {
    Remove-Item $pathsFile -Force
    Write-Host "Removed: $pathsFile"
}

Write-Host "Autostart disabled. Servers that are already running stay up."
