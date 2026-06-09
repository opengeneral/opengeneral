<#
.SYNOPSIS
Install the locally-built opengeneral.exe onto the user's PATH.

.DESCRIPTION
Builds the binary first if dist\opengeneral.exe is missing. Copies it to
%LOCALAPPDATA%\Programs\OpenGeneral by default (override with INSTALL_DIR env var)
and adds that directory to the per-user PATH. Pass -WithService to also register
the daemon — that step needs an elevated (Administrator) prompt because Windows
services are registered system-wide.
#>
[CmdletBinding()]
param(
  [switch]$WithService
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'elevation.ps1')
$RepoRoot = Split-Path -Parent $PSScriptRoot
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\OpenGeneral' }
$BinSource = Join-Path $RepoRoot 'dist\opengeneral.exe'

if (-not (Test-Path $BinSource)) {
  Write-Host "No binary at $BinSource — building it first."
  & (Join-Path $PSScriptRoot 'build.ps1')
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
