$ErrorActionPreference = 'Stop'
$target = [IO.Path]::GetFullPath($PSScriptRoot)
if (-not (Test-Path -LiteralPath (Join-Path $target '.jev-install'))) { throw 'Installer marker missing; refusing removal.' }
if ((Get-Content -LiteralPath (Join-Path $target '.jev-install') -Raw).Trim() -ne 'JevAdvisorCommunity-0.2.0') { throw 'Invalid installer marker.' }
if ($target -eq [IO.Path]::GetPathRoot($target) -or $target -eq $env:USERPROFILE -or $target -eq $env:LOCALAPPDATA) { throw 'Unsafe uninstall path.' }
Write-Host "Remove app, downloaded dependencies and app settings from: $target"
Write-Host 'Shared model API keys in Windows user environment are retained.'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Uninstall Jev Advisor Community'
$form.ClientSize = New-Object System.Drawing.Size(520, 190)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$info = New-Object System.Windows.Forms.Label
$info.Text = 'Close Jev first. The app and installation settings will be removed. Saved advisor profiles are kept unless you select the option below. Shared API keys are retained.'
$info.SetBounds(16, 16, 488, 65)
$form.Controls.Add($info)
$erase = New-Object System.Windows.Forms.CheckBox
$erase.Text = 'Also permanently delete all saved advisor profiles for this Windows user'
$erase.SetBounds(16, 88, 488, 40)
$erase.Checked = $false
$form.Controls.Add($erase)
$ok = New-Object System.Windows.Forms.Button
$ok.Text = 'Uninstall'
$ok.SetBounds(300, 145, 95, 30)
$ok.DialogResult = [System.Windows.Forms.DialogResult]::OK
$form.Controls.Add($ok)
$cancel = New-Object System.Windows.Forms.Button
$cancel.Text = 'Cancel'
$cancel.SetBounds(405, 145, 95, 30)
$cancel.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
$form.Controls.Add($cancel)
$form.CancelButton = $cancel
if ($form.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { $form.Dispose(); exit }
$deleteProfiles = $erase.Checked
$form.Dispose()
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
    $path = Join-Path $folder 'Jev Advisor Community.lnk'
    if ((Test-Path -LiteralPath $path) -and $shell.CreateShortcut($path).TargetPath -eq (Join-Path $target 'Launch.cmd')) { Remove-Item -LiteralPath $path }
}
Set-Location $env:TEMP
Remove-Item -LiteralPath $target -Recurse -Force
if ($deleteProfiles) {
    # Only the two known profile-store files under this user's fixed app-data directory.
    $profileRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'JevAdvisorCommunity\advisor'))
    foreach ($name in @('profiles.dat', 'profiles.lock')) {
        $file = [IO.Path]::GetFullPath((Join-Path $profileRoot $name))
        if ([IO.Path]::GetDirectoryName($file) -ne $profileRoot) { throw 'Unsafe profile path.' }
        if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force }
    }
}
Write-Host 'Uninstalled.'
