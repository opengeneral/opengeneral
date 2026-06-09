<#
.SYNOPSIS
Remove the installed opengeneral.exe and unregister its daemon service.

.DESCRIPTION
Leaves user config (%USERPROFILE%\.opengeneral) and Windows Credential Manager
secrets intact — those are the user's data, not install artifacts. Unregistering
the service needs an elevated (Administrator) prompt.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'elevation.ps1')
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\OpenGeneral' }
$target = Join-Path $InstallDir 'opengeneral.exe'

if (Test-Path $target) {
  # Unregister the service before deleting the binary it points at. This needs
  # Administrator rights, so Invoke-ServiceCommand triggers a UAC prompt when the
  # session isn't elevated. If it still fails, keep the binary — it is the only
  # tool that can cleanly remove the service, and deleting it would strand the
  # registration.
  $rc = Invoke-ServiceCommand -Binary $target -Action @('daemon', 'uninstall')
  if ($rc -ne 0) {
    Write-Host ""
    Write-Host "Error: 'daemon uninstall' failed (exit $rc), so the binary was left in place."
    Write-Host "The service may still reference it. Resolve the issue, then re-run this script."
    exit 1
  }
  Remove-Item -Force $target
  Write-Host "Removed $target"

  # Drop our entry from the per-user PATH (leave everything else).
  $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
  if ($userPath) {
    $newPath = (($userPath -split ';') | Where-Object { $_ -and $_ -ne $InstallDir }) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
  }
}
else {
  Write-Host "No opengeneral binary at $target — nothing to remove."
}

Write-Host ""
Write-Host "Left intact:"
Write-Host "  - config at $env:USERPROFILE\.opengeneral"
Write-Host "  - API key secrets in Windows Credential Manager"
Write-Host "Remove config with:  Remove-Item -Recurse -Force `"$env:USERPROFILE\.opengeneral`""
