# ==================================================================
#  Registers social-auto-upload to start at user logon.
#
#  What it does:
#    1. Detects node.exe and the project venv python, and records both
#       absolute paths in scripts\paths.json so the launcher works even
#       when node is not on PATH at logon.
#    2. Creates a shortcut in the current user's Startup folder that runs
#       scripts\launcher.pyw with pythonw.exe -> no console window at all.
#    3. Optionally starts the servers immediately. The launcher skips any
#       port that is already serving, so nothing gets started twice.
#
#  Usage (or just double-click install-autostart.bat):
#    install-autostart.bat                      install + start now
#    install-autostart.bat -NoStart             install only
#    install-autostart.bat -Name "My App"       custom shortcut name
# ==================================================================
[CmdletBinding()]
param(
    [switch]$NoStart,
    [string]$Name = "Social Auto Upload"
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root      = Split-Path -Parent $scriptDir

$launcher  = Join-Path $scriptDir 'launcher.pyw'
$pythonw   = Join-Path $root '.venv\Scripts\pythonw.exe'
$python    = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $launcher)) {
    throw "launcher.pyw not found in $scriptDir"
}
if (-not (Test-Path $pythonw)) {
    # Fall back to a system pythonw next to whichever python is on PATH.
    $py = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($py) {
        $candidate = Join-Path (Split-Path -Parent $py.Source) 'pythonw.exe'
        if (Test-Path $candidate) { $pythonw = $candidate; $python = $py.Source }
    }
    if (-not (Test-Path $pythonw)) {
        throw "pythonw.exe not found. Create the venv first: python -m venv .venv"
    }
}

# ---------- 1. locate node ----------
$nodeExe = $null
$cmd = Get-Command node.exe -ErrorAction SilentlyContinue
if ($cmd) { $nodeExe = $cmd.Source }

if (-not $nodeExe) {
    foreach ($c in @(
        "$env:ProgramFiles\nodejs\node.exe",
        "$env:LOCALAPPDATA\Programs\nodejs\node.exe"
    )) {
        if (Test-Path $c) { $nodeExe = $c; break }
    }
}

if (-not $nodeExe) {
    Write-Warning "node.exe not found - the frontend cannot start until Node.js is installed."
}

# ---------- 2. record absolute paths ----------
$paths = [ordered]@{
    python = $python
    pythonw = $pythonw
    node   = if ($nodeExe) { $nodeExe } else { '' }
}
$pathsFile = Join-Path $scriptDir 'paths.json'
# Write without a BOM so the launcher can parse it with json.loads.
[System.IO.File]::WriteAllText($pathsFile, ($paths | ConvertTo-Json), (New-Object System.Text.UTF8Encoding($false)))

Write-Host "  python  : $python"
Write-Host "  node    : $(if ($nodeExe) { $nodeExe } else { '<missing>' })"
Write-Host "  recorded: $pathsFile"

# ---------- 3. shortcut in the Startup folder ----------
$startup = [Environment]::GetFolderPath('Startup')
$lnkPath = Join-Path $startup "$Name.lnk"

$wsh = New-Object -ComObject WScript.Shell
$sc  = $wsh.CreateShortcut($lnkPath)
$sc.TargetPath       = $pythonw
$sc.Arguments        = '"' + $launcher + '"'
$sc.WorkingDirectory = $root
$sc.WindowStyle      = 7
$sc.Description      = 'Starts the social-auto-upload backend (:5409) and frontend (:5173) at logon'
$sc.Save()

Write-Host "  shortcut: $lnkPath"

# ---------- 4. start now ----------
if (-not $NoStart) {
    Start-Process -FilePath $pythonw -ArgumentList ('"' + $launcher + '"') -WorkingDirectory $root
    Write-Host "  started : launch request sent"
}

Write-Host ""
Write-Host "Done. Both servers start automatically on the next sign-in."
Write-Host "  logs    : $root\logs\backend.log, $root\logs\frontend.log"
Write-Host "  status  : pythonw scripts\launcher.pyw status"
Write-Host "  remove  : scripts\uninstall-autostart.bat"
