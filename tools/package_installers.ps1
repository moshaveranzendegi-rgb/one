$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $Root 'dist-packages'
New-Item -ItemType Directory -Force -Path $Dist | Out-Null
Get-ChildItem -LiteralPath $Dist -File | Remove-Item -Force
function New-InstallerZip([string]$Name, [string[]]$IncludePaths) {
  $Staging = Join-Path $Dist ($Name + '-staging')
  if (Test-Path $Staging) { Remove-Item -LiteralPath $Staging -Recurse -Force }
  New-Item -ItemType Directory -Path $Staging | Out-Null
  foreach ($Relative in $IncludePaths) {
    $Source = Join-Path $Root $Relative
    if (-not (Test-Path $Source)) { throw "Missing packaging source: $Relative" }
    $Destination = Join-Path $Staging $Relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
    if ((Get-Item $Source).PSIsContainer) { Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force } else { Copy-Item -LiteralPath $Source -Destination $Destination -Force }
  }
  Get-ChildItem -LiteralPath $Staging -Recurse -Force | Where-Object { $_.FullName -match '[\\/](__pycache__|\.venv|\.git|dist|build|\.gradle|app[\\/]build)[\\/]' -or $_.Extension -in @('.pyc','.pyo','.sqlite3') } | Sort-Object FullName -Descending | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  $Zip = Join-Path $Dist ($Name + '.zip')
  Compress-Archive -Path (Join-Path $Staging '*') -DestinationPath $Zip -CompressionLevel Optimal
  Remove-Item -LiteralPath $Staging -Recurse -Force
  if ((Get-Item $Zip).Length -ge 180000000) { & python (Join-Path $PSScriptRoot 'split_package.py') $Zip --part-size 180000000; if ($LASTEXITCODE -ne 0) { throw "Failed to split $Zip" }; Remove-Item -LiteralPath $Zip -Force }
  Get-ChildItem -LiteralPath $Dist -File | Where-Object { $_.Name -like ($Name + '.zip') -or $_.Name -like ($Name + '.part*') } | ForEach-Object { if ($_.Length -ge 200000000) { throw "Download exceeds 200 MB: $($_.Name)" } }
}
New-InstallerZip 'RS-ai-Windows-Setup' @('app','web','tools','tests','requirements.txt','requirements-vision.txt','requirements-captions.txt','INSTALL_RS-ai.bat','BUILD_EXE_WINDOWS.bat','PACKAGE_EXE_WINDOWS.bat','RUN_RS-ai.bat','RUN_RS-ai_LAN.bat','RUN_RS-ai_Portable.bat','JOIN_PARTS.bat','JOINER_README_FA.txt','install_windows.bat','install_tts.bat','install_vision.bat','install_captions.bat','README.md','START_HERE_FA.md','INSTALLER_NOTES_FA.md','STATUS.md','CHANGELOG.md','run.py','.gitignore')
New-InstallerZip 'RS-ai-Android-Studio-Source' @('android','INSTALLER_NOTES_FA.md')
Write-Host "Output: $Dist" -ForegroundColor Cyan
