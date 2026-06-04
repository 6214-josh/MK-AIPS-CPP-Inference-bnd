param(
  [string]$ScriptDir = ""
)

if ([string]::IsNullOrWhiteSpace($ScriptDir)) {
  $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$Parent = Split-Path -Parent $ScriptDir

if (Test-Path (Join-Path $Parent "app\main.py")) {
  return (Split-Path -Parent $Parent)
}

return $Parent
