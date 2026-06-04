$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$Shell = New-Object -ComObject WScript.Shell

function New-Shortcut($Name, $Target, $Args = "") {
  $ShortcutPath = Join-Path $Desktop $Name
  $Shortcut = $Shell.CreateShortcut($ShortcutPath)
  $Shortcut.TargetPath = $Target
  $Shortcut.Arguments = $Args
  $Shortcut.WorkingDirectory = $ScriptDir
  $Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
  $Shortcut.Save()
  Write-Host "Created: $ShortcutPath"
}

New-Shortcut "AIPS Backend 8999.lnk" "$env:ComSpec" "/k `"$ScriptDir\start_backend_windows.bat`""
New-Shortcut "AIPS Frontend 5074.lnk" "$env:ComSpec" "/k `"$ScriptDir\start_frontend_windows.bat`""

Write-Host "Done. Desktop shortcuts created."
