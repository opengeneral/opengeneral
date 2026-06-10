<#
.SYNOPSIS
Install the opengeneral.exe binary onto the user's PATH.

.DESCRIPTION
Works both from a release download (the binary ships next to this script) and
from a source checkout (builds dist\opengeneral.exe if needed). Copies the binary
to %LOCALAPPDATA%\Programs\OpenGeneral by default (override with INSTALL_DIR env
var) and adds that directory to the per-user PATH. Pass -WithService to also
register the daemon — that step needs an elevated (Administrator) prompt because
Windows services are registered system-wide.
#>
[CmdletBinding()]
param(
  [switch]$WithService
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'elevation.ps1')
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\OpenGeneral' }

# Locate the binary to install:
#   1. one shipped alongside this script (release download/archive)
#   2. the repo build output, building it if this is a source checkout
$sibling = Get-ChildItem -Path $PSScriptRoot -Filter 'opengeneral*.exe' -File -ErrorAction SilentlyContinue | Select-Object -First 1
if ($sibling) {
  $BinSource = $sibling.FullName
}
else {
  $RepoRoot = Split-Path -Parent $PSScriptRoot
  $BinSource = Join-Path $RepoRoot 'dist\opengeneral.exe'
  if (-not (Test-Path $BinSource)) {
    $buildScript = Join-Path $PSScriptRoot 'build.ps1'
    if (Test-Path $buildScript) {
      Write-Host "No binary found — building from source."
      & $buildScript
    }
    else {
      Write-Error "No opengeneral.exe found next to this script or at $BinSource"
      exit 1
    }
  }
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$target = Join-Path $InstallDir 'opengeneral.exe'
Copy-Item -Force $BinSource $target
Write-Host "Installed opengeneral to $target"

# Add to the per-user PATH (no admin needed) if it isn't already there.
$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$entries = @()
if ($userPath) { $entries = $userPath -split ';' }
if ($entries -notcontains $InstallDir) {
  $newPath = if ([string]::IsNullOrEmpty($userPath)) { $InstallDir } else { "$userPath;$InstallDir" }
  [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
  Write-Host "Added $InstallDir to your user PATH (restart your shell to pick it up)."
}

if ($WithService) {
  Write-Host ""
  Write-Host "Registering the daemon service ..."
  $rc = Invoke-ServiceCommand -Binary $target -Action @('daemon', 'install')
  if ($rc -ne 0) {
    Write-Host "daemon install failed (exit $rc)."
    exit $rc
  }
  Write-Host "Daemon service registered. Start it with: opengeneral daemon start"
}
else {
  Write-Host ""
  Write-Host "Next steps:"
  Write-Host "  opengeneral keys add <name> --type anthropic"
  Write-Host "  opengeneral action-planes add default --endpoint http://127.0.0.1:4767/mcp"
  Write-Host "  # register the background service (prompts for elevation automatically):"
  Write-Host "  .\packaging\install.ps1 -WithService"
  Write-Host "  opengeneral daemon start"
}
