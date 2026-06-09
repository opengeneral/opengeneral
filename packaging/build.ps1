<#
.SYNOPSIS
Build a self-contained opengeneral.exe for Windows with PyInstaller.

.DESCRIPTION
Output: dist\opengeneral.exe (a single-file executable).
PyInstaller does not cross-compile — run this on Windows to produce the Windows
binary. Override the Python used with -Python or the PYTHON env var.
#>
[CmdletBinding()]
param(
  [string]$Python = $(if ($env:PYTHON) { $env:PYTHON } else { 'python' })
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "PyInstaller is not installed for $Python."
  Write-Host "Install the build extra first:  $Python -m pip install -e '.[build]'"
  exit 1
}

# litellm, keyring and tiktoken pull in data files and lazy/plugin imports that
# PyInstaller's static analysis misses. collect-all bundles them wholesale; only
# request packages that are actually importable so the build degrades gracefully.
$collectPkgs = @('litellm', 'keyring', 'tiktoken')
$collectArgs = @()
foreach ($pkg in $collectPkgs) {
  & $Python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$pkg') else 1)" 2>$null
  if ($LASTEXITCODE -eq 0) {
    $collectArgs += '--collect-all'; $collectArgs += $pkg
    if ($pkg -eq 'keyring') {
      $collectArgs += '--collect-submodules'; $collectArgs += 'keyring.backends'
    }
  }
  else {
    Write-Host "Note: '$pkg' not importable; skipping its data files in this build."
  }
}

Write-Host "Building opengeneral.exe with $Python ..."
& $Python -m PyInstaller `
  --noconfirm --clean --onefile `
  --name opengeneral `
  --paths src `
  --distpath dist `
  --workpath build\pyinstaller `
  --specpath build\pyinstaller `
  @collectArgs `
  packaging\entry.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed with exit code $LASTEXITCODE" }

Write-Host ""
Write-Host "Built: $RepoRoot\dist\opengeneral.exe"
Write-Host "Try it:  .\dist\opengeneral.exe --help"
