<#
.SYNOPSIS
OpenGeneral installer for Windows.

.DESCRIPTION
Run via:

  irm https://raw.githubusercontent.com/opengeneral/opengeneral/main/install.ps1 | iex

Downloads the prebuilt windows-x86_64 binaries from the latest GitHub Release
(opengeneral.exe plus opengeneral-svc.exe, the SCM service host), verifies their
checksums, and installs them to %LOCALAPPDATA%\Programs\OpenGeneral on the per-user
PATH. Registering the daemon (-WithService) needs Administrator rights; the script
triggers a UAC prompt for just that step.

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
$InstallDir = if ($env:INSTALL_DIR) { $env:INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA 'Programs\OpenGeneral' }
$target = 'windows-x86_64'
$asset = "opengeneral-$target.exe"
# The SCM service host ships alongside the main binary; both install together.
$svcAsset = "opengeneral-svc-$target.exe"

function Test-IsAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

function Invoke-ServiceCommand {
  # Run `<Binary> <Action...>`, elevating via UAC when the session is not admin.
  param(
    [Parameter(Mandatory)][string]$Binary,
    [Parameter(Mandatory)][string[]]$Action
  )
  if (Test-IsAdmin) {
    & $Binary @Action
    return $LASTEXITCODE
  }
  Write-Host "This step needs Administrator rights — Windows will prompt for elevation."
  $outFile = [System.IO.Path]::GetTempFileName()
  try {
    $inner = '"{0}" {1} > "{2}" 2>&1' -f $Binary, ($Action -join ' '), $outFile
    $cmdArgs = '/c "{0}"' -f $inner
    $proc = Start-Process -FilePath $env:ComSpec -ArgumentList $cmdArgs -Verb RunAs -Wait -PassThru
    Get-Content -LiteralPath $outFile -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
    if ($null -ne $proc.ExitCode) { return $proc.ExitCode }
    return 1
  }
  catch {
    Write-Host "Elevation was cancelled or failed: $($_.Exception.Message)"
    return 1
  }
  finally {
    Remove-Item -LiteralPath $outFile -ErrorAction SilentlyContinue
  }
}

function Remove-FromUserPath {
  param([string]$Dir)
  $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
  if ($userPath) {
    $newPath = (($userPath -split ';') | Where-Object { $_ -and $_ -ne $Dir }) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
  }
}

if ($Uninstall) {
  $bin = Join-Path $InstallDir 'opengeneral.exe'
  $svcBin = Join-Path $InstallDir 'opengeneral-svc.exe'
  if (Test-Path $bin) {
    $rc = Invoke-ServiceCommand -Binary $bin -Action @('daemon', 'uninstall')
    if ($rc -ne 0) {
      Write-Host "Error: 'daemon uninstall' failed (exit $rc); binary left in place."
      exit 1
    }
    Remove-Item -Force $bin
    if (Test-Path $svcBin) { Remove-Item -Force $svcBin }
    Remove-FromUserPath -Dir $InstallDir
    Write-Host "Removed $bin"
  }
  else {
    Write-Host "No opengeneral binary at $bin — nothing to remove."
  }
  Write-Host "Config at $env:USERPROFILE\.opengeneral and Credential Manager secrets were left intact."
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
  $rc = Invoke-ServiceCommand -Binary $dest -Action @('daemon', 'install')
  if ($rc -ne 0) { Write-Host "daemon install failed (exit $rc)."; exit $rc }
  Write-Host "Daemon service registered. Start it with: opengeneral daemon start"
}
else {
  Write-Host ""
  Write-Host "Next steps:"
  Write-Host "  opengeneral keys add <name> --type anthropic"
  Write-Host "  opengeneral action-planes add default --endpoint http://127.0.0.1:4767/mcp"
  Write-Host "  opengeneral daemon install   # prompts for Administrator elevation"
  Write-Host "  opengeneral daemon start"
}
