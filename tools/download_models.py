"""Downloads the speech models once, so the first video doesn't wait for them (run by the installers, in venv_audio):
faster-whisper large-v3 (~3 GB) and the wav2vec2 alignment model for the profile's spoken language (~0.4 GB).
Usage: py-audio tools/download_models.py"""
import sys

from vfk.asr import aligner, device, whisper
from vfk.profile import load_profile

sys.stdout.reconfigure(encoding="utf-8")
lang = load_profile().get("spoken_language", "en")
print(f"Device: {device()[0]}. Downloading Whisper large-v3 …", flush=True)
whisper()
print(f"Downloading the alignment model for '{lang}' …", flush=True)
aligner(lang)
print("Models ready.")
