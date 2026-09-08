[CmdletBinding()]
param(
    [switch]$CpuOnly
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3.10+ from https://www.python.org/downloads/windows/ and enable 'Add python.exe to PATH'."
}

if (-not (Test-Path '.venv')) {
    py -3 -m venv .venv
}

$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
& $Python -m pip install --upgrade pip

if ($CpuOnly) {
    # PyTorch CPU wheels must be installed before the remaining packages.
    & $Python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
}

& $Python -m pip install -r requirements.txt

Write-Host ''
Write-Host 'Installation completed.' -ForegroundColor Green
Write-Host 'Next steps:'
Write-Host '  1. Edit the single .\config.json file to match your camera filenames.'
Write-Host '  2. Double-click .\run_video_sorter.bat, or run the command below.'
Write-Host '  3. .\.venv\Scripts\python.exe .\video_sorter.py --input-dir "D:\Camera" --config .\config.json --output-dir .\reports'

if (-not $CpuOnly) {
    Write-Host ''
    Write-Host 'GPU verification (run after installation):' -ForegroundColor Yellow
    Write-Host '  .\.venv\Scripts\python.exe -c ''import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CUDA unavailable")'''
    Write-Host 'If CUDA is unavailable, see docs\DEPLOYMENT.md for the matching PyTorch CUDA wheel command.' -ForegroundColor Yellow
}
