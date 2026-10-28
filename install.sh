#!/bin/bash
# Video Factory Kit - Mac installer. In Terminal, inside the kit's folder:  bash install.sh
# Installs what's missing and skips what's already there. Safe to run again. Log: install_log.txt
#   1. Homebrew (asks for your Mac password once), then Python 3.12, ffmpeg, Node.js and Git
#   2. tools/venv_audio  : PyTorch (CPU / Apple) + WhisperX + faster-whisper + yt-dlp
#   3. tools/venv_render : Pillow, OpenCV, MediaPipe, Playwright + its own Chromium
#   4. HyperFrames (npx), the speech models, then the health check
set -e
KIT="$(cd "$(dirname "$0")" && pwd)"
cd "$KIT"
exec > >(tee -a install_log.txt) 2>&1
step() { echo; echo "==> $1"; }

step "1/6 Programs (Homebrew, Python 3.12, ffmpeg, Node.js, Git)"
if ! command -v brew >/dev/null 2>&1; then
  echo "    Homebrew is missing: installing it (it will ask for your Mac password)."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"; elif [ -x /usr/local/bin/brew ]; then eval "$(/usr/local/bin/brew shellenv)"; fi
for pkg in python@3.12 ffmpeg node git; do
  if brew list "$pkg" >/dev/null 2>&1; then echo "    $pkg: already installed"; else brew install "$pkg"; fi
done
PY="$(brew --prefix python@3.12)/bin/python3.12"
echo "    Python 3.12: $PY"

step "2/6 Audio environment (tools/venv_audio) - this is the big download"
[ -x tools/venv_audio/bin/python ] || "$PY" -m venv tools/venv_audio
PA="tools/venv_audio/bin/python"
"$PA" -m pip install --upgrade pip
"$PA" -m pip install torch==2.8.0 torchaudio==2.8.0
"$PA" -m pip install -r tools/requirements_audio.txt

step "3/6 Render environment (tools/venv_render)"
[ -x tools/venv_render/bin/python ] || "$PY" -m venv tools/venv_render
PR="tools/venv_render/bin/python"
"$PR" -m pip install --upgrade pip
"$PR" -m pip install -r tools/requirements_render.txt
"$PR" -m playwright install chromium

step "4/6 HyperFrames (animated graphics, via Node.js)"
npx --yes hyperframes --version || echo "    (HyperFrames could not start: the check will say why)"

step "5/6 Speech models (Whisper large-v3 + alignment, ~3.5 GB, once)"
"$PA" tools/download_models.py

step "6/6 Health check"
"$PR" tools/check.py || true
echo
echo "Done. Read check_report.txt: every line should say OK."
