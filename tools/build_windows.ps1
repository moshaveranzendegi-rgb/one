$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run install_windows.bat first.' }
. .\.venv\Scripts\Activate.ps1
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean --onedir --name RS-ai `
  --add-data 'web;web' `
  --add-data 'tools;tools' `
  --collect-all edge_tts --collect-all fastapi --collect-all starlette --collect-all uvicorn `
  --hidden-import app.api --hidden-import app.pipeline `
  --hidden-import uvicorn.logging --hidden-import uvicorn.loops --hidden-import uvicorn.loops.auto `
  --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.lifespan.on `
  run.py
$portable = Join-Path (Get-Location) 'dist\RS-ai'
Copy-Item -LiteralPath 'RUN_RS-ai_Portable.bat' -Destination $portable -Force
# Expose the CPU fallback installer beside the portable executable for Intel-only PCs.
Copy-Item -LiteralPath 'tools\setup_sadtalker_cpu.bat' -Destination $portable -Force
Copy-Item -LiteralPath 'tools\setup_sadtalker_cpu.ps1' -Destination $portable -Force
@'
RS ai portable build
- Start with RUN_RS-ai_Portable.bat or RS-ai.exe.
- For PCs without a compatible NVIDIA GPU, run setup_sadtalker_cpu.bat beside this file. It downloads an isolated CPU environment and SadTalker model weights.
- SadTalker CPU animates the face, lips and head; it does not generate realistic full-body or hand motion.
- FFmpeg is required and is not bundled.
- OmniAvatar GPU model weights are not bundled; the full-motion GPU engine requires a compatible NVIDIA GPU.
- Keep the whole dist\RS-ai folder together; do not move RS-ai.exe alone.
'@ | Set-Content -LiteralPath (Join-Path $portable 'INSTALL_README.txt') -Encoding UTF8
Write-Host 'Build finished at dist\RS-ai. The launcher and README were copied beside RS-ai.exe.' -ForegroundColor Green
