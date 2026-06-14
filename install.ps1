<#
.SYNOPSIS
OpenGeneral installer for Windows.

.DESCRIPTION
Run in an Administrator PowerShell:

  irm https://raw.githubusercontent.com/opengeneral/opengeneral/main/install.ps1 | iex

Downloads the prebuilt windows-x86_64 binaries (opengeneral.exe plus
opengeneral-svc.exe, the SCM service host) to %ProgramFiles%\OpenGeneral — a system
location the daemon's low-privilege virtual service account can execute — verifies
their checksums, and adds the dir to the system PATH. Installing a system service
needs Administrator, so the whole script does; -WithService also registers it.

Parameters: -WithService, -Uninstall, -Version vX.Y.Z.
Env overrides: INSTALL_DIR, OPENGENERAL_REPO, OPENGENERAL_VERSION.
#>
[CmdletBinding()]
param(
  [switch]$WithService,
  [switch]$Uninstall,
  [string]$Version = $(if ($env:OPENGENERAL_VERSION) { $env:OPENGENERAL_VERSION } else { 'latest' })
)

$ErrorActionPreference = 'Stop'
$Repo = if ($env:OPENGENERAL_REPO) { $env:OPENGENERAL_REPO } else { 'opengeneral/opengeneral' }
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $env:ProgramFiles 'OpenGeneral' }
$target = 'windows-x86_64'
$asset = "opengeneral-$target.exe"
# The SCM service host ships alongside the main binary; both install together.
$svcAsset = "opengeneral-svc-$target.exe"

function Test-IsAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

if (-not (Test-IsAdmin)) {
  Write-Error "OpenGeneral installs into Program Files and registers a system service, which need Administrator. Re-run this in an Administrator PowerShell."
  exit 1
}

function Remove-FromMachinePath {
  param([string]$Dir)
  $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
  if ($machinePath) {
    $newPath = (($machinePath -split ';') | Where-Object { $_ -and $_ -ne $Dir }) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'Machine')
  }
}

if ($Uninstall) {
  $bin = Join-Path $InstallDir 'opengeneral.exe'
  $svcBin = Join-Path $InstallDir 'opengeneral-svc.exe'
  if (Test-Path $bin) {
    & $bin daemon uninstall
    if ($LASTEXITCODE -ne 0) { Write-Host "Note: 'daemon uninstall' reported an issue; continuing." }
    Remove-Item -Force $bin
    if (Test-Path $svcBin) { Remove-Item -Force $svcBin }
    Remove-FromMachinePath -Dir $InstallDir
    Write-Host "Removed $bin"
  }
  else {
    Write-Host "No opengeneral binary at $bin — nothing to remove."
  }
  Write-Host "The daemon's config and secrets were left intact."
  exit 0
}

$base = if ($Version -eq 'latest') {
  "https://github.com/$Repo/releases/latest/download"
}
else {
  "https://github.com/$Repo/releases/download/$Version"
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("opengeneral-install-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
  Write-Host "Downloading opengeneral ($Version) ..."
  Invoke-WebRequest -Uri "$base/SHA256SUMS" -OutFile (Join-Path $tmp 'SHA256SUMS')
  $sums = Get-Content (Join-Path $tmp 'SHA256SUMS')

  function Install-VerifiedAsset {
    param([string]$AssetName, [string]$DestName)
    $download = Join-Path $tmp $AssetName
    Invoke-WebRequest -Uri "$base/$AssetName" -OutFile $download
    $line = $sums | Where-Object { ($_ -split '\s+')[1] -eq $AssetName } | Select-Object -First 1
    if (-not $line) { Write-Error "Checksum for $AssetName not found in SHA256SUMS"; exit 1 }
    $expected = (($line -split '\s+')[0]).ToLower()
    $actual = (Get-FileHash $download -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $expected) {
      Write-Error "Checksum mismatch for $AssetName (expected $expected, got $actual)"
      exit 1
    }
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
    Copy-Item -Force $download (Join-Path $InstallDir $DestName)
  }

  Install-VerifiedAsset $asset 'opengeneral.exe'
  Install-VerifiedAsset $svcAsset 'opengeneral-svc.exe'
  $dest = Join-Path $InstallDir 'opengeneral.exe'
  Write-Host "Installed opengeneral to $dest"
}
finally {
  Remove-Item -Recurse -Force -LiteralPath $tmp -ErrorAction SilentlyContinue
}

$machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
$entries = @()
if ($machinePath) { $entries = $machinePath -split ';' }
if ($entries -notcontains $InstallDir) {
  $newPath = if ([string]::IsNullOrEmpty($machinePath)) { $InstallDir } else { "$machinePath;$InstallDir" }
  [Environment]::SetEnvironmentVariable('Path', $newPath, 'Machine')
  Write-Host "Added $InstallDir to the system PATH (restart your shell to pick it up)."
}

if ($WithService) {
  Write-Host ""
  Write-Host "Registering the daemon service ..."
  & $dest daemon install
  if ($LASTEXITCODE -ne 0) { Write-Host "daemon install failed (exit $LASTEXITCODE)."; exit $LASTEXITCODE }
  Write-Host "Daemon service registered. Start it with: opengeneral daemon start"
}
else {
  Write-Host ""
  Write-Host "Next steps:"
  Write-Host "  opengeneral daemon install"
  Write-Host "  opengeneral daemon start"
  Write-Host "  opengeneral action-planes add default --endpoint http://127.0.0.1:4767/mcp"
  Write-Host "  opengeneral keys add <name> --type anthropic"
}
