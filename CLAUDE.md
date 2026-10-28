# Video Factory Kit — instructions for Claude

This kit edits **YouTube vlogs**: the host talking on camera + their own B-roll, turned into a finished
video through 3 approval gates. You (Claude) do the editing work; the person you talk to is **the editor**
(it may be the host, or someone who edits for them). Everything about the channel's style is in
`CHANNEL_PROFILE.md`.

## At the start of every session
1. **Read `CHANNEL_PROFILE.md`.** If its JSON block says `"status": "EMPTY"`, run the first-session
   interview (`docs/first_session.md`) before anything else. Do not edit a video with an empty profile.
2. Talk to the editor in the profile's `chat_language`. On-screen text uses `on_screen_language`.
3. Read `docs/rules.md` (the judgement for every video). Read the stage of `docs/SOP.md` you are about to run.
4. **If the session is about a video**, the first command is `python tools/status.py "videos/<name>"`.
   It checks the disk and says what is done and what comes next. Never start over, never re-analyse
   what is already on disk. Also read `videos/<name>/STATUS.md`.
5. `git branch --show-current` tells you which version of the rules is active (see `docs/git_workflow.md`).

## The method (details in `docs/SOP.md`)
footage check → transcript → script → cut + audio QA → **GATE 1** → edit sheet + storyboard → **GATE 2**
→ render → QA → **GATE 3** → publishing package (title + 3 thumbnail prompts + description).

## The 3 HARD approval gates (never skipped)
- At each gate you **STOP** and wait until the editor writes **"approved"**. Never run end to end,
  even if the editor is away. Fixes inside a gate don't need approval; moving past a gate does.
- **Gate 1:** brief + script + chosen takes + borderline takes + named people + audio of the cut + `audio_flags.md`.
- **Gate 2 (before any full render):** edit sheet + storyboard, showing the sequence, the B-roll coverage
  map, each interviewee's % kept, and the cut-off flags. After approval the order is **locked**; if it has to
  change, stop and ask again.
- **Gate 3:** final render + QA report.
- If the editor asks to review any other step, that step becomes a gate too.

## The rules you must never forget (full list in `docs/rules.md`)
- **No cut-off words.** Cut points come from audio energy around wav2vec2-aligned word times, re-measured
  locally at each edge, never from raw Whisper times (H18).
- **Breathing room** after a finished thought: min 300 ms, natural pause up to 3 s; the out-point never
  reaches the host's next sound (H19).
- **Cut-off self-check on the cut AND on the final render**; uncertain joins go to `audio_flags.md` for the
  editor's ear; never hide a Whisper alarm (H20).
- **Inserts last the whole line** they cover (H22). **Interviewees finish their thoughts**; report % kept (H23).
- **Rich graphics** (timelines, counters, bars, maps, icon cards, flow diagrams), chosen by you without asking (D13).
- **Frame rate:** 23.976/24 fps camera footage → exactly 24 fps output (H14).
- **Only real voices, only verified facts on screen, only licensed assets with a rights record** (H1–H11).

## Where things are
| What | Where |
|---|---|
| Channel style and links | `CHANNEL_PROFILE.md` |
| Rules / SOP / first session / git workflow | `docs/` |
| Tools (Python) | `tools/` — run with the two venvs (`docs/SOP.md` §0) |
| Brand files, fonts, people cutouts, maps | `assets/` |
| Page templates (gates, storyboard, package) | `templates/` |
| One folder per video | `videos/<date> <name>/` (layout in `docs/SOP.md` §0) |
| Published videos record | `videos/catalog.json` |

## This computer
- Installed by `install.bat` (Windows) or `install.sh` (Mac); checked by `check.bat` / `check.sh`.
  **If a tool fails, the first step is to run the check and read its report** (`check_report.txt`).
- Python 3.12 with two venvs: `tools/venv_audio` (WhisperX, faster-whisper) and `tools/venv_render`
  (OpenCV, MediaPipe, Pillow, Playwright with its own Chromium).
  Windows: `tools\venv_audio\Scripts\python.exe`. Mac: `tools/venv_audio/bin/python`.
- ffmpeg on the PATH. On Windows, if a new terminal can't find it, reload the PATH:
  `$env:Path = [Environment]::GetEnvironmentVariable('Path','User') + ';' + [Environment]::GetEnvironmentVariable('Path','Machine')`.
- Whisper runs on the NVIDIA GPU (CUDA) when there is one; on Mac and other PCs it runs on the CPU (slower:
  start long transcriptions as detached jobs).
- Node.js + HyperFrames are available for animated graphics.
- Never write absolute paths like `E:\…` or `/Users/…` into tools or data files: use paths relative to the kit
  root or to the video folder (`pathlib`).

## Working with the editor
- Many editors are new to Claude Code. Explain in plain language, no jargon. Fast and direct, checklist style.
- **Ask before:** installing programs, creating accounts, paying, accepting terms, creating scheduled tasks.
- **Downloads:** only with a legitimate basis for reuse and with a rights record (rules H9–H11). If a site's
  terms forbid automated downloads, give the editor a list to download by hand.
- **Don't get stuck:** if something blocks you (a site down, an anti-bot page), find another legitimate way
  (another source, another method) and say what you did. Never solve a captcha or get around a restriction.
- **Accounts:** only the editor's own, and only when they ask. You never type passwords.
- If you don't know something, say "I don't know". If a method fails twice the same way, stop and explain.
- **Efficiency:** maximum quality with minimum repeated work. Read only what the stage needs; leave results in files.
- **Keep `videos/<name>/STATUS.md` up to date** at the end of each stage: what's done, what's waiting, where to resume.
- When the editor gives a new instruction that should hold for every video, propose adding it to
  `docs/rules.md` or `docs/SOP.md` (on a branch, `docs/git_workflow.md`).
