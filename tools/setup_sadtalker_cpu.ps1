$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$EngineHome = Join-Path $env:LOCALAPPDATA 'RS-ai\engines\SadTalker'
$PythonHome = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python38'
$Python38 = Join-Path $PythonHome 'python.exe'
$VenvPython = Join-Path $EngineHome '.venv\Scripts\python.exe'
$CheckpointDir = Join-Path $EngineHome 'checkpoints'
New-Item -ItemType Directory -Force -Path $EngineHome | Out-Null

function Get-Python38Path {
    if (Test-Path $Python38) { return $Python38 }
    $pyLauncher = Get-Command 'py.exe' -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $candidate = (& $pyLauncher.Source -3.8 -c "import sys; print(sys.executable)" 2>$null | Select-Object -Last 1)
            $candidate = [string]$candidate
            $candidate = $candidate.Trim()
            if ($candidate -and (Test-Path $candidate)) { return $candidate }
        } catch {}
    }
    return $null
}

Write-Host 'RS ai - SadTalker CPU engine installer' -ForegroundColor Cyan
Write-Host 'This mode runs without an NVIDIA GPU and mainly animates the face, lips and head.' -ForegroundColor Yellow
Write-Host 'Allow 5-10 GB of free disk space and a stable internet connection.' -ForegroundColor Yellow

$Python38 = Get-Python38Path
if (-not $Python38) {
    $Installer = Join-Path $env:TEMP 'python-3.8.10-amd64.exe'
    $InstallerUrl = 'https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe'
    Write-Host '[1/6] Downloading isolated Python 3.8.10 from python.org...' -ForegroundColor Cyan
    if (-not (Test-Path $Installer) -or (Get-Item $Installer).Length -lt 10MB) {
        if (Get-Command 'curl.exe' -ErrorAction SilentlyContinue) {
            & curl.exe -fL --retry 4 --retry-delay 2 --retry-connrefused -o $Installer $InstallerUrl
            if ($LASTEXITCODE -ne 0) { throw 'Could not download Python 3.8.10 from python.org.' }
        } else {
            Invoke-WebRequest -Uri $InstallerUrl -OutFile $Installer -UseBasicParsing
        }
    }
    New-Item -ItemType Directory -Force -Path $PythonHome | Out-Null
    & $Installer /quiet 'InstallAllUsers=0' "TargetDir=$PythonHome" 'Include_launcher=0' 'Include_test=0' 'PrependPath=0'
    $pythonInstallExitCode = $LASTEXITCODE
    # Get-Python38Path returns null when Python is not installed yet; set the target
    # path explicitly before checking the result of the installer.
    $Python38 = Join-Path $PythonHome 'python.exe'
    if ($pythonInstallExitCode -ne 0 -or -not (Test-Path -LiteralPath $Python38)) {
        throw "Python 3.8 was not installed (installer exit code: $pythonInstallExitCode). Install Python 3.8.10 x64 from python.org and rerun this script."
    }
} else {
    Write-Host "Using Python 3.8: $Python38"
}

Write-Host '[2/6] Getting official SadTalker source...' -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $EngineHome 'inference.py'))) {
    $RepoZip = Join-Path $env:TEMP 'RS-ai-SadTalker-main.zip'
    $ExtractDir = Join-Path $env:TEMP 'RS-ai-SadTalker-extract'
    if (Test-Path $ExtractDir) { Remove-Item $ExtractDir -Recurse -Force }
    if (Get-Command 'curl.exe' -ErrorAction SilentlyContinue) {
        & curl.exe -fL --retry 5 --retry-delay 2 --retry-connrefused -o $RepoZip 'https://github.com/OpenTalker/SadTalker/archive/refs/heads/main.zip'
        if ($LASTEXITCODE -ne 0) { throw 'Could not download the official SadTalker source archive.' }
    } else {
        Invoke-WebRequest -Uri 'https://github.com/OpenTalker/SadTalker/archive/refs/heads/main.zip' -OutFile $RepoZip -UseBasicParsing
    }
    Expand-Archive -LiteralPath $RepoZip -DestinationPath $ExtractDir -Force
    $ExtractedRepo = Join-Path $ExtractDir 'SadTalker-main'
    if (-not (Test-Path (Join-Path $ExtractedRepo 'inference.py'))) { throw 'The SadTalker source archive was incomplete.' }
    Copy-Item -Path (Join-Path $ExtractedRepo '*') -Destination $EngineHome -Recurse -Force
}
if (-not (Test-Path (Join-Path $EngineHome 'inference.py'))) { throw 'SadTalker inference.py is missing.' }

$PatchScript = Join-Path $PSScriptRoot 'patch_sadtalker_cpu.py'
if (-not (Test-Path -LiteralPath $PatchScript)) {
    throw "RS ai CPU optimization patcher is missing: $PatchScript"
}
Write-Host '[3/6] Applying RS ai low-resource CPU preset...' -ForegroundColor Cyan
& $Python38 $PatchScript $EngineHome
if ($LASTEXITCODE -ne 0) { throw 'Could not apply the RS ai CPU preset to SadTalker.' }

Write-Host '[4/6] Creating isolated CPU-only Python environment...' -ForegroundColor Cyan
if (-not (Test-Path $VenvPython)) {
    & $Python38 -m venv (Join-Path $EngineHome '.venv')
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) { throw 'Could not create the SadTalker virtual environment.' }
}
& $VenvPython -m pip install --timeout 120 --retries 10 --upgrade 'pip<25' 'setuptools<60' wheel
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare pip/build dependencies.' }
& $VenvPython -m pip install --timeout 120 --retries 10 'torch==1.12.1+cpu' 'torchvision==0.13.1+cpu' --extra-index-url 'https://download.pytorch.org/whl/cpu'
if ($LASTEXITCODE -ne 0) { throw 'Could not install CPU-only PyTorch. Review the error above and rerun.' }
& $VenvPython -m pip install --timeout 120 --retries 10 -r (Join-Path $EngineHome 'requirements.txt') 'opencv-python==4.8.1.78'
if ($LASTEXITCODE -ne 0) { throw 'SadTalker dependencies did not install. Rerun to retry or send the complete error.' }

Write-Host '[5/6] Downloading the 256px inference checkpoint and full-frame mapping weights...' -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $CheckpointDir | Out-Null

function Get-ModelFile {
    param([string]$Url, [string]$Destination, [long]$ExpectedBytes)
    if ((Test-Path $Destination) -and (Get-Item $Destination).Length -eq $ExpectedBytes) {
        Write-Host "Already downloaded: $(Split-Path $Destination -Leaf)" -ForegroundColor Green
        return
    }
    if ((Test-Path $Destination) -and (Get-Item $Destination).Length -gt $ExpectedBytes) {
        Remove-Item -LiteralPath $Destination -Force
    }
    Write-Host "Downloading $(Split-Path $Destination -Leaf); rerun this script to resume if interrupted..." -ForegroundColor Cyan
    if (Get-Command 'curl.exe' -ErrorAction SilentlyContinue) {
        if ((Test-Path $Destination) -and (Get-Item $Destination).Length -gt 0) {
            & curl.exe -fL -C - --retry 5 --retry-delay 3 --retry-connrefused -o $Destination $Url
        } else {
            & curl.exe -fL --retry 5 --retry-delay 3 --retry-connrefused -o $Destination $Url
        }
        if ($LASTEXITCODE -ne 0) { throw "Download failed for $(Split-Path $Destination -Leaf). Rerun to resume." }
    } else {
        Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
    }
    if (-not (Test-Path $Destination) -or (Get-Item $Destination).Length -ne $ExpectedBytes) {
        throw "Model file size does not match the official release: $(Split-Path $Destination -Leaf). Rerun to resume."
    }
}

Get-ModelFile 'https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors' (Join-Path $CheckpointDir 'SadTalker_V0.0.2_256.safetensors') 725066984
Get-ModelFile 'https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00109-model.pth.tar' (Join-Path $CheckpointDir 'mapping_00109-model.pth.tar') 155779231

Write-Host '[6/6] Checking downloaded models and inference imports...' -ForegroundColor Cyan
& $VenvPython -c "import inference; import torch; print('SadTalker ready; PyTorch', torch.__version__); print('CUDA available:', torch.cuda.is_available())"
if ($LASTEXITCODE -ne 0) { throw 'Model files downloaded but SadTalker imports failed. Save the complete error before retrying.' }

Write-Host ''
Write-Host 'SUCCESS: SadTalker CPU engine installed.' -ForegroundColor Green
Write-Host "Engine path: $EngineHome"
Write-Host 'Close and reopen RS ai, then click "وضعیت موتور‌ها".'
Write-Host 'Limit: face/lips/head animation only; realistic hands/full-body gesture generation is not included in this CPU engine.'
