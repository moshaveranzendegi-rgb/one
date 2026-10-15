$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Run install_windows.bat first.' }

# PowerShell 7 can turn native stderr output into terminating errors even when
# a command succeeds. Keep explicit exit-code checks as the source of truth.
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$PyInstallerCheck = & $Python -c "import PyInstaller; print(PyInstaller.__version__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host 'PyInstaller is missing; installing it into the project virtual environment.'
    & $Python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw 'Installing PyInstaller failed.' }
} else {
    Write-Host ("Using PyInstaller " + (($PyInstallerCheck | Out-String).Trim()))
}

$VisionArgs = @()
$VisionProbe = & $Python -c "import importlib.util; print('yes' if importlib.util.find_spec('rembg') and importlib.util.find_spec('onnxruntime') else 'no')" 2>$null
if ($LASTEXITCODE -eq 0 -and (($VisionProbe | Out-String).Trim() -eq 'yes')) {
    $VisionArgs = @(
        '--collect-all', 'rembg',
        '--collect-binaries', 'onnxruntime',
        # pymatting calls importlib.metadata.version() at import time. Copying
        # its dist-info metadata is required for the frozen rembg import to work.
        '--copy-metadata', 'pymatting'
    )
    Write-Host 'Including CPU background-removal support (rembg + ONNX Runtime).' -ForegroundColor Cyan
} else {
    Write-Host 'Vision packages not installed; background-removal support will be omitted. Run install_vision.bat before building to include it.' -ForegroundColor Yellow
}
$BuildArgs = @(
    '--noconfirm', '--clean', '--onedir', '--name', 'RS-ai',
    '--add-data', 'web;web',
    '--add-data', 'tools;tools',
    '--collect-all', 'edge_tts',
    '--collect-all', 'gtts',
    '--collect-all', 'fastapi',
    '--collect-all', 'starlette',
    '--collect-all', 'uvicorn',
    '--hidden-import', 'app.api',
    '--hidden-import', 'app.pipeline',
    '--hidden-import', 'uvicorn.logging',
    '--hidden-import', 'uvicorn.loops',
    '--hidden-import', 'uvicorn.loops.auto',
    '--hidden-import', 'uvicorn.protocols.http.auto',
    '--hidden-import', 'uvicorn.lifespan.on'
) + $VisionArgs + @('run.py')
& $Python -m PyInstaller @BuildArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed with exit code $LASTEXITCODE." }

$portable = Join-Path (Get-Location) 'dist\RS-ai'
Copy-Item -LiteralPath 'RUN_RS-ai_Portable.bat' -Destination $portable -Force
Copy-Item -LiteralPath 'tools\setup_sadtalker_cpu.bat' -Destination $portable -Force
Copy-Item -LiteralPath 'tools\setup_sadtalker_cpu.ps1' -Destination $portable -Force
@'
RS ai portable build 0.4.4
- Start with RUN_RS-ai_Portable.bat or RS-ai.exe.
- Local-first: the app uses the engine installed on this computer; it does not start a cloud workflow automatically.
- On Intel HD 4000 systems, SadTalker CPU animates face/lips/head only. It cannot generate realistic hands or full-body motion.
- Legacy dual-core CPUs are very slow for SadTalker. Verify the engine with a 3–5 second test audio before attempting long speech.
- FFmpeg is required and is not bundled.
- OmniAvatar GPU model weights are not bundled; the full-motion GPU engine requires a compatible NVIDIA GPU.
- Keep the whole dist\RS-ai folder together; do not move RS-ai.exe alone.
'@ | Set-Content -LiteralPath (Join-Path $portable 'INSTALL_README.txt') -Encoding UTF8
Write-Host 'Build finished at dist\RS-ai. The launcher and README were copied beside RS-ai.exe.' -ForegroundColor Green
