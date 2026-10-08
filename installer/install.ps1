param([string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'Programs\JevAdvisorCommunity'), [switch]$NoShortcuts, [string]$DownloadCache)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { throw 'Windows x64 is required.' }
if (Test-Path -LiteralPath $InstallDir) { throw 'Installation directory already exists. Choose a new directory; existing settings will not be overwritten.' }
function Run([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
}
try {
    Write-Host 'Jev Advisor Community 0.2.0 - online installation'
    Write-Host 'Downloads: Astral uv/Python from GitHub; dependencies from PyPI. No API key is included.'
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'payload.json') -Raw | ConvertFrom-Json
    $payload = Join-Path $PSScriptRoot 'source.zip'
    if ((Get-FileHash -LiteralPath $payload -Algorithm SHA256).Hash -ne $manifest.source_sha256) { throw 'Source checksum mismatch.' }
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
    Set-Content -LiteralPath (Join-Path $InstallDir '.jev-install') -Value 'JevAdvisorCommunity-0.2.0' -Encoding ASCII
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination $InstallDir
    $appDir = Join-Path $InstallDir 'app'
    Expand-Archive -LiteralPath $payload -DestinationPath $appDir
    $archive = Join-Path $InstallDir 'uv.zip'
    Write-Host '[1/4] Downloading verified installer helper...'
    Invoke-WebRequest -UseBasicParsing -Uri $manifest.uv_url -OutFile $archive
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $manifest.uv_sha256) { throw 'uv checksum mismatch.' }
    Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $InstallDir 'tools')
    $uv = Join-Path $InstallDir 'tools\uv.exe'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $InstallDir 'python'
    $env:UV_CACHE_DIR = if ($DownloadCache) { [IO.Path]::GetFullPath($DownloadCache) } else { Join-Path $InstallDir 'cache' }
    $env:UV_PYTHON_PREFERENCE = 'only-managed'
    $env:UV_PYTHON_INSTALL_REGISTRY = 'false'
    Write-Host '[2/4] Installing private Python runtime...'
    Run $uv @('venv','--no-config','--python','3.11.17', (Join-Path $appDir '.venv'))
    $python = Join-Path $appDir '.venv\Scripts\python.exe'
    Write-Host '[3/4] Installing pinned dependencies (may take several minutes)...'
    Run $uv @('pip','install','--no-config','--python',$python,'--index-url','https://pypi.org/simple','--only-binary',':all:','--require-hashes','-r',(Join-Path $appDir 'installer\requirements-hashed.txt'))
    Run $uv @('pip','check','--python',$python)
    Run $python @('-c','import PySide6, qfluentwidgets, rapidocr_onnxruntime, windows_capture, openai')
    Write-Host 'Dependency imports OK.'
    Write-Host '[4/4] Creating launchers...'
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination $InstallDir
    $launcher = '@echo off' + "`r`n" + 'cd /d "%~dp0app"' + "`r`n" + 'start "" ".venv\Scripts\pythonw.exe" "main.py"' + "`r`n"
    Set-Content -LiteralPath (Join-Path $InstallDir 'Launch.cmd') -Value $launcher -Encoding ASCII
    $uninstall = '@echo off' + "`r`n" + 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"' + "`r`n" + 'pause'
    Set-Content -LiteralPath (Join-Path $InstallDir 'Uninstall.cmd') -Value $uninstall -Encoding ASCII
    if (-not $NoShortcuts) {
        $shell = New-Object -ComObject WScript.Shell
        foreach ($folder in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
            $link = $shell.CreateShortcut((Join-Path $folder 'Jev Advisor Community.lnk'))
            $link.TargetPath = Join-Path $InstallDir 'Launch.cmd'
            $link.WorkingDirectory = $appDir
            $link.Save()
        }
    }
    Set-Content -LiteralPath (Join-Path $InstallDir 'INSTALL-COMPLETE.txt') -Value '0.2.0' -Encoding ASCII
    Write-Host "Installation complete: $InstallDir"
    Write-Host 'Open Launch.cmd or the desktop shortcut. Configure your own model API key in Settings.'
} catch {
    Write-Host "Installation failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Partial files may remain at: $InstallDir. No existing installation was overwritten."
    exit 1
}
