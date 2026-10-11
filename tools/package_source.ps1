$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$parent = Split-Path -Parent $root
$name = 'RS-ai-source-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.zip'
$out = Join-Path $parent $name
$exclusions = @('.venv','__pycache__','.pytest_cache','dist','build','outputs','data','pretrained_models','models','.git')
$temp = Join-Path $env:TEMP ('RS-ai-package-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $temp | Out-Null
try {
  Get-ChildItem -Force $root | Where-Object { $_.Name -notin $exclusions } | ForEach-Object { Copy-Item $_.FullName -Destination $temp -Recurse -Force }
  Compress-Archive -Path (Join-Path $temp '*') -DestinationPath $out -CompressionLevel Optimal
  Write-Host "Created: $out" -ForegroundColor Green
} finally { Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue }
