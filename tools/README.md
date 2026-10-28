# tools/

The Python tools of the kit. What each one does and when it runs: `docs/SOP.md` (quick reference table at the end).
The top of every file explains its options and the format of the files it reads.

Run them from the kit's root folder with one of the two environments the installer creates:
- `py-audio` = `tools/venv_audio` (transcription, alignment, cut, audio QA, channel study)
- `py-render` = `tools/venv_render` (graphics, storyboard, render, video QA, publishing package)

Windows: `tools\venv_audio\Scripts\python.exe tools\status.py "videos/<name>"`
Mac: `tools/venv_audio/bin/python tools/status.py "videos/<name>"`

`vfk/` is the shared library: video folder layout (`kit.py`), the channel profile (`profile.py`), ffmpeg and the
encoder choice (`media.py`), words and numbers (`words.py`), cut edges from the audio energy (`edges.py`), Whisper and
wav2vec2 (`asr.py`), reading the cut (`cutreader.py`), the graphics engine (`gfx.py`) and the review pages' look (`page.py`).
