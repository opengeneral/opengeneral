<#
Shared helpers for the Windows install/uninstall scripts: detect whether the
current session is elevated, and run the daemon's service-registration commands
with a UAC prompt when it is not.
#>

function Test-IsAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}

function Invoke-ServiceCommand {
  <#
  Run `<Binary> <Action...>` (e.g. opengeneral.exe daemon install). Registering a
  Windows service requires Administrator rights, so when the current session is
  not elevated this re-launches the command through UAC (Start-Process -Verb
  RunAs) and streams the elevated process's output back. Returns the command's
  exit code (1 if the user cancels the elevation prompt).
  #>
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
    # ShellExecute (Start-Process -Verb RunAs) cannot redirect streams, so run the
    # command under cmd.exe and have cmd redirect output to a temp file we can read.
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
