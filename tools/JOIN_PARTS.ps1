param(
  [Parameter(Mandatory=$true)][string]$BaseName,
  [string]$Directory = (Get-Location).Path
)
$ErrorActionPreference = 'Stop'
if ($BaseName -notmatch '^[A-Za-z0-9_.-]+$') { throw 'BaseName may contain only letters, digits, dot, underscore and hyphen.' }
$Parts = Get-ChildItem -LiteralPath $Directory -File | Where-Object { $_.Name -match ('^' + [regex]::Escape($BaseName) + '\.part(\d{3,})$') } | Sort-Object { [int]([regex]::Match($_.Name, '\.part(\d{3,})$').Groups[1].Value) }
if ($Parts.Count -eq 0) { throw "No parts found: $BaseName.part001" }
for ($i = 0; $i -lt $Parts.Count; $i++) {
  $num = [int]([regex]::Match($Parts[$i].Name, '\.part(\d{3,})$').Groups[1].Value)
  if ($num -ne ($i + 1)) { throw ('Missing part {0:D3}' -f ($i + 1)) }
  if ($Parts[$i].Length -le 0 -or $Parts[$i].Length -ge 200000000) { throw "Invalid part length: $($Parts[$i].Name)" }
}
$HashFile = Join-Path $Directory ($BaseName + '.sha256.txt')
if (-not (Test-Path $HashFile)) { throw "Missing checksum file: $HashFile" }
$Match = [regex]::Match((Get-Content -Raw -LiteralPath $HashFile), '\b([a-fA-F0-9]{64})\b')
if (-not $Match.Success) { throw 'Checksum file does not contain a valid SHA-256 digest.' }
$Expected = $Match.Groups[1].Value.ToLowerInvariant()
$Out = Join-Path $Directory ($BaseName + '.zip')
$Temp = $Out + '.partial'
if (Test-Path $Temp) { Remove-Item -LiteralPath $Temp -Force }
try {
  $Stream = [System.IO.File]::Open($Temp, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
  try {
    foreach ($Part in $Parts) {
      $InputStream = [System.IO.File]::OpenRead($Part.FullName)
      try { $InputStream.CopyTo($Stream) } finally { $InputStream.Dispose() }
    }
  } finally { $Stream.Dispose() }
  $Actual = (Get-FileHash -LiteralPath $Temp -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($Actual -ne $Expected) { throw "SHA-256 mismatch. Expected $Expected got $Actual." }
  Move-Item -LiteralPath $Temp -Destination $Out -Force
  Write-Host "Reassembled and verified: $Out" -ForegroundColor Green
} catch {
  if (Test-Path $Temp) { Remove-Item -LiteralPath $Temp -Force }
  if (Test-Path $Out) { Remove-Item -LiteralPath $Out -Force }
  throw
}
