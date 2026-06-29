<#
Offline test of the root install.ps1 (Windows) against a fake GitHub release.

Stubs Invoke-WebRequest to serve a local fake-release dir, so no network/published
release is needed. Requires OPENGENERAL_BINARY (the built opengeneral.exe). Exits
non-zero on a failed assertion. Covers download + checksum-verify + install; the
service-coupled -Uninstall path is exercised by the service-lifecycle CI job.
#>
$ErrorActionPreference = 'Stop'

# $PSScriptRoot is tests/installer; the repo root is two levels up.
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$installPs1 = Join-Path $repoRoot 'install.ps1'

$srcBin = $env:OPENGENERAL_BINARY
if (-not $srcBin -or -not (Test-Path $srcBin)) {
  Write-Host "OPENGENERAL_BINARY not set or missing; skipping Windows installer test."
  exit 0
}

$sbx = Join-Path ([System.IO.Path]::GetTempPath()) ("ogtest-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $sbx | Out-Null
try {
  $rel = Join-Path $sbx 'release'
  New-Item -ItemType Directory -Force -Path $rel | Out-Null
  # Three assets ship on Windows: the main binary, the SCM service host, and the TUI.
  # The built opengeneral.exe stands in for all three here — this exercises the
  # installer's download/verify/install logic, not the binaries' runtime behavior.
  $asset = 'opengeneral-windows-x86_64.exe'
  $svcAsset = 'opengeneral-svc-windows-x86_64.exe'
  $tuiAsset = 'opengeneral-tui-windows-x86_64.exe'
  $sumLines = @()
  foreach ($a in @($asset, $svcAsset, $tuiAsset)) {
    Copy-Item $srcBin (Join-Path $rel $a)
    $hash = (Get-FileHash (Join-Path $rel $a) -Algorithm SHA256).Hash.ToLower()
    $sumLines += "$hash  $a"
  }
  $sumLines | Set-Content -Path (Join-Path $rel 'SHA256SUMS') -Encoding ascii

  # Function shadows the Invoke-WebRequest cmdlet; child scopes (& install.ps1) inherit it.
  function Invoke-WebRequest {
    param($Uri, $OutFile)
    Copy-Item (Join-Path $rel (Split-Path $Uri -Leaf)) $OutFile
  }

  $env:INSTALL_DIR = Join-Path $sbx 'bin'
  $dest = Join-Path $env:INSTALL_DIR 'opengeneral.exe'
  $svcDest = Join-Path $env:INSTALL_DIR 'opengeneral-svc.exe'
  $tuiDest = Join-Path $env:INSTALL_DIR 'opengeneral-tui.exe'

  # install
  & $installPs1
  if (-not (Test-Path $dest)) { throw "FAIL: binary not installed at $dest" }
  if (-not (Test-Path $svcDest)) { throw "FAIL: service host not installed at $svcDest" }
  if (-not (Test-Path $tuiDest)) { throw "FAIL: tui not installed at $tuiDest" }
  & $dest --help | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "FAIL: installed binary --help exited $LASTEXITCODE" }
  Write-Host "ok: install (all binaries) + --help"

  # a tampered checksum on either asset must be rejected and must not install
  @("deadbeef  $asset", $sumLines[1]) | Set-Content -Path (Join-Path $rel 'SHA256SUMS') -Encoding ascii
  Remove-Item $dest, $svcDest -Force -ErrorAction SilentlyContinue
  $failed = $false
  try { & $installPs1 } catch { $failed = $true }
  if (Test-Path $dest) { throw "FAIL: binary installed despite checksum mismatch" }
  if (-not $failed) { throw "FAIL: checksum mismatch was not rejected" }
  Write-Host "ok: checksum mismatch rejected"

  Write-Host "All Windows installer checks passed."
}
finally {
  Remove-Item -Recurse -Force -LiteralPath $sbx -ErrorAction SilentlyContinue
}
