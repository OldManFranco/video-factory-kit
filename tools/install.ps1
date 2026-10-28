# Video Factory Kit - Windows installer (run it with install.bat, from the kit's folder).
# Installs what's missing and skips what's already there. Safe to run again.
#   1. Python 3.12, ffmpeg, Node.js (LTS) and Git, with winget
#   2. tools\venv_audio  : PyTorch (CUDA if there's an NVIDIA card) + WhisperX + faster-whisper + yt-dlp
#   3. tools\venv_render : Pillow, OpenCV, MediaPipe, Playwright + its own Chromium
#   4. HyperFrames (npx), the speech models, then the health check
# Everything is logged to install_log.txt.
$ErrorActionPreference = "Stop"
$Kit = Split-Path -Parent $PSScriptRoot
Set-Location $Kit
Start-Transcript -Path (Join-Path $Kit "install_log.txt") -Append | Out-Null

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Have($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Winget-Install($id, $name) {
    Write-Host "    installing $name ($id) ..."
    winget install --id $id -e --silent --accept-source-agreements --accept-package-agreements | Out-Host
    Refresh-Path
}

Step "1/6 Programs (Python 3.12, ffmpeg, Node.js, Git)"
if (-not (Have "winget")) {
    Write-Host "winget is missing. Install 'App Installer' from the Microsoft Store, then run install.bat again." -ForegroundColor Red
    Stop-Transcript | Out-Null; exit 1
}
$py = $null
try { $py = (& py -3.12 -c "import sys; print(sys.executable)") 2>$null } catch {}
if (-not $py) { Winget-Install "Python.Python.3.12" "Python 3.12"; $py = (& py -3.12 -c "import sys; print(sys.executable)") }
Write-Host "    Python 3.12: $py"
if (-not (Have "ffmpeg")) { Winget-Install "Gyan.FFmpeg" "ffmpeg" } else { Write-Host "    ffmpeg: already installed" }
$nodeOk = $false
if (Have "node") { $nodeOk = ([int]((node --version).TrimStart("v").Split(".")[0]) -ge 22) }
if (-not $nodeOk) { Winget-Install "OpenJS.NodeJS.LTS" "Node.js LTS" } else { Write-Host "    Node.js: $(node --version)" }
if (-not (Have "git")) { Winget-Install "Git.Git" "Git" } else { Write-Host "    Git: already installed" }
Refresh-Path

Step "2/6 Audio environment (tools\venv_audio) - this is the big download"
$va = Join-Path $Kit "tools\venv_audio"
if (-not (Test-Path "$va\Scripts\python.exe")) { & py -3.12 -m venv $va }
$pa = "$va\Scripts\python.exe"
& $pa -m pip install --upgrade pip | Out-Host
$nvidia = Have "nvidia-smi"
if ($nvidia) {
    Write-Host "    NVIDIA card found: PyTorch with CUDA"
    & $pa -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128 | Out-Host
} else {
    Write-Host "    No NVIDIA card: PyTorch for the CPU (transcription will be slower)"
    & $pa -m pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cpu | Out-Host
}
& $pa -m pip install -r "tools\requirements_audio.txt" | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "Audio packages failed (see install_log.txt)." -ForegroundColor Red; Stop-Transcript | Out-Null; exit 1 }

Step "3/6 Render environment (tools\venv_render)"
$vr = Join-Path $Kit "tools\venv_render"
if (-not (Test-Path "$vr\Scripts\python.exe")) { & py -3.12 -m venv $vr }
$pr = "$vr\Scripts\python.exe"
& $pr -m pip install --upgrade pip | Out-Host
& $pr -m pip install -r "tools\requirements_render.txt" | Out-Host
if ($LASTEXITCODE -ne 0) { Write-Host "Render packages failed (see install_log.txt)." -ForegroundColor Red; Stop-Transcript | Out-Null; exit 1 }
& $pr -m playwright install chromium | Out-Host

Step "4/6 HyperFrames (animated graphics, via Node.js)"
& npx --yes hyperframes --version | Out-Host

Step "5/6 Speech models (Whisper large-v3 + alignment, ~3.5 GB, once)"
& $pa "tools\download_models.py" | Out-Host

Step "6/6 Health check"
& $pr "tools\check.py" | Out-Host
Stop-Transcript | Out-Null
Write-Host ""
Write-Host "Done. Read check_report.txt: every line should say OK." -ForegroundColor Green
