$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$BuildDir = Join-Path $Root 'dist\RS-ai'
$Exe = Join-Path $BuildDir 'RS-ai.exe'
if (-not (Test-Path $Exe)) { throw 'Missing dist\RS-ai\RS-ai.exe. Run BUILD_EXE_WINDOWS.bat first.' }
$Out = Join-Path $Root 'dist-packages'
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Base = 'RS-ai-Windows-Portable'
$Zip = Join-Path $Out ($Base + '.zip')
$HashFile = Join-Path $Out ($Base + '.sha256.txt')
Get-ChildItem -LiteralPath $Out -File | Where-Object { $_.Name -like ($Base + '.part*') } | Remove-Item -Force
if (Test-Path -LiteralPath $Zip) { Remove-Item -LiteralPath $Zip -Force }
if (Test-Path -LiteralPath $HashFile) { Remove-Item -LiteralPath $HashFile -Force }
Compress-Archive -Path (Join-Path $BuildDir '*') -DestinationPath $Zip -CompressionLevel Optimal
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Missing virtual environment Python. Run INSTALL_RS-ai.bat first.' }
$Digest = (Get-FileHash -LiteralPath $Zip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath (Join-Path $Out ($Base + '.sha256.txt')) -Value ("{0}  {1}" -f $Digest, ($Base + '.zip')) -Encoding ascii
if ((Get-Item $Zip).Length -ge 180000000) {
  & $Python (Join-Path $Root 'tools\split_package.py') $Zip --part-size 180000000
  if ($LASTEXITCODE -ne 0) { throw 'Failed to split the Windows portable package.' }
  Remove-Item -LiteralPath $Zip -Force
}
Get-ChildItem -LiteralPath $Out -File | Where-Object { $_.Name -eq ($Base + '.zip') -or $_.Name -like ($Base + '.part*') } | ForEach-Object {
  if ($_.Length -ge 200000000) { throw "Download file exceeds 200 MB: $($_.Name)" }
  Write-Host ("{0}: {1:N2} MB" -f $_.Name, ($_.Length / 1MB)) -ForegroundColor Green
}
Write-Host "Package output: $Out" -ForegroundColor Cyan
Write-Host "SHA-256: $Digest"
