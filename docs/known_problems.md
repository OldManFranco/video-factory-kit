# Known problems and their fixes

Things that went wrong in real productions, so they don't go wrong again. Add to this list when you
find a new one (what happened, why, the fix).

## Transcription and alignment
- **Whisper word times drift up to 0.5 s** and stretch words over silences. Never cut on them: re-align with wav2vec2 and re-measure each edge locally (rules H18).
- **Whole-clip alignment can still slip up to 1 s or squash words** ("things" in 30 ms). That's why every edge is re-measured in a ±2 s window (`local_edges.py`), and implausible times are rejected.
- **Numbers without letters can't be aligned** ("$3,100"): wav2vec2 squashes them and shifts every following word. Spell them out first (`numbers_to_words.py`).
- **Whisper writes a repeated phrase once** ("That's the luxury. That's the luxury tax." → once) and skips fillers and asides. Only Whisper on the *whole cut* shows them (as extra words), and short-window listening finds them inside a clip.
- **WhisperX can drift ~10 s on a long clip or invent a number.** The source for the script is faster-whisper large-v3 per clip; WhisperX/wav2vec2 is used for *timing* only.
- **Whisper gives duration 0 to some real words** (and also invents some). Don't drop zero-length words blindly; check them against the energy.
- **A strange word in QA is a mutilated word** until proven otherwise ("bent" for "percent").
- faster-whisper can fail reading WAV through PyAV: read the WAV with numpy and pass the array.

## Cut
- **The start of a bad take leaks in** when the out-point is placed "up to the next written word". The out-point never reaches the host's next *sound* (rules H19).
- **Street or crowd noise read as voice** (or a soft word tail read as silence) when voice is measured against the room. Measure against the host's own level (floor + 6 dB and host level − 20 dB).
- **Fixing one edge can eat the neighbouring word.** When moving an edge, re-check the word on the other side, and listen with Whisper in a short window.
- **Two consecutive segments of the same clip can overlap** once breathing room is added (the same word plays twice). `build_script.py` prevents it; check after manual edits.
- **Hand-set in/out points skip the energy search.** They are always listed in `audio_flags.md`.

## Video and ffmpeg
- **Never use the concat demuxer's `inpoint` to seek:** it starts at the previous keyframe and the picture drifted up to 2 s from the voice. Start the list at the beginning of the segment that contains the instant and drop the extra with `trim=start=…,setpts=PTS-STARTPTS`.
- **23.976 → 24 fps:** use the `fps=24` filter (repeats one frame every ~42 s; audio untouched, sync exact). Never speed the video up 0.1 % (it forces an audio stretch and drift).
- **One frame short at the end** when the mixed audio is a few ms shorter than the video and `-shortest` is used. Pad the audio to the video's exact length.
- In ffmpeg, `-ss`/`-t` for an input go **before** its `-i`; after it, they apply to the output (and the file can come out empty).
- Concat lists need **absolute paths** (relative paths are resolved from the list's folder).
- A slow disk (external or almost full) can make writing one big intermediate MP4 slower than the render: read the cut from its cached segments instead.
- Check every camera clip decodes fully before starting (`footage_check.py`): damaged files from a card exist; get a fresh copy.

## Windows / Mac
- `os.path.relpath` fails between drives on Windows (C: vs E:): use paths relative to the kit root built with `pathlib`, and fall back to absolute when on another drive.
- PowerShell 5.1 breaks JSON passed on the command line: pass JSON in a file.
- File names: Windows forbids `< > : " / \ | ? *` in names; strip only those for the final file (rules H17).
- Claude's background commands die when the app closes: long work goes through `tools/job.py` (detached).
- On Mac, Whisper runs on the CPU: a 20-minute vlog can take a long time to transcribe. Run it as a detached job and let the computer stay awake.

## Graphics and images
- Measure text only after the font has loaded (the fallback font is narrower and the text overflows later).
- Commons may answer 429 "Too many requests" for big originals: use its standard thumbnail sizes and wait between requests.
- A page titled "Just a moment…" is an anti-bot check: change source, don't insist (rules H10).
- Stock clips with readable brands or screens: check every frame for logos and legible text before using them.
