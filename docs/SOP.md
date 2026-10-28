# SOP — from camera footage to a finished vlog

How a vlog goes from a folder of camera clips (the host talking + their own B-roll) to a finished,
published video. The judgement behind each step is in `docs/rules.md`; the style comes from
`CHANNEL_PROFILE.md`.

**Golden rule:** the full render is the last thing, after a green preflight and the editor's approval at Gate 2.
There are **3 hard gates**. At each one Claude stops and waits for the word **"approved"** (rules H25).

```
footage check → transcript → script → cut + audio QA → GATE 1
→ edit sheet + storyboard → GATE 2
→ render → QA → GATE 3
→ publishing package (title + 3 thumbnail prompts + description)
```

---

## 0. Conventions

**Two Python environments** (created by the installer):

| Short name in this SOP | What it runs | Windows | Mac |
|---|---|---|---|
| `py-audio` | transcription, alignment, cut, audio QA (WhisperX, faster-whisper) | `tools\venv_audio\Scripts\python.exe` | `tools/venv_audio/bin/python` |
| `py-render` | graphics, storyboard, render, video QA (OpenCV, MediaPipe, Pillow, Playwright) | `tools\venv_render\Scripts\python.exe` | `tools/venv_render/bin/python` |

All commands are run from the kit's root folder and take the video folder as their first argument.
In the examples, `V` = `"videos/2026-11-02 Street Food Tour"`.

**One folder per video**, created by `tools/new_video.py`:

```
videos/<date> <short name>/
  footage/          camera clips as they came off the card (never modified)
  host_script/      the host's outline or script, if there is one (.docx / .txt / .md)
  edit/             what Claude writes for this video:
    script.json       the segments of the cut (which clip, from which words to which words)
    sheet.json        the edit sheet: every B-roll, graphic, lower third, subtitle, anchored to phrases
    package.json      titles, thumbnails, description data
  work/             generated files (can be rebuilt): audio, transcripts, alignment, cut, graphics, render parts, QA
  render/final/     the final MP4: "[FINAL TITLE].mp4"
  publish/          the publishing package (copy-paste page, thumbnail prompts, reference frames)
  gate1.html  storyboard.html  gate3.html    the review pages for each gate
  audio_flags.md    joins the editor must listen to (rule H20)
  people_pending.md named people and their cutouts (rules §4)
  STATUS.md         where this video stands and where to resume
```

**Long jobs** (render, transcribing many clips) run detached so they survive if Claude or the app closes:
`py-render tools/job.py V <stage> -- <command…>` → log in `work/jobs/`, state readable by `tools/status.py`.

**Resuming:** the first command of any session about a video is `python tools/status.py V`. It checks the
disk and says what's done and what's next. Never start over, never re-analyse what's on disk.

**Review pages** (gates, storyboard, publishing package) are HTML files. In the Claude desktop app Claude
publishes them as a private Artifact page and gives the link; otherwise the editor opens the HTML file.

---

## Stage 0 · New video + footage check

1. `python tools/new_video.py "<short name>"` → creates the folder (today's date in front).
2. The editor copies the camera clips into `footage/` (A-roll and B-roll together is fine) and the host's outline, if any, into `host_script/`.
3. `py-audio tools/footage_check.py V` — for each clip:
   - checks that the file decodes completely (damaged clips are reported: get a fresh copy from the card);
   - extracts the audio (16 kHz mono for Whisper, 48 kHz stereo for the cut);
   - transcribes with faster-whisper large-v3 (word timestamps) → `work/transcripts/`;
   - detects the language in 10 s windows (another language = probably an interviewee);
   - measures each sentence's level (a distant or quieter voice = a second person);
   - classifies the clip: **A-roll** (host talking), **B-roll** (no speech / ambience), **interview**, **mixed**.
   Output: `work/footage_check/summary.md` — list of clips, length, frame rate, type, first words.
4. Claude tells the editor in plain words what it found (number of clips, total length, damaged files, interviews, languages) and continues.

---

## Stage 1 · Transcript and precise word times

1. Raw transcripts come from Stage 0 (faster-whisper large-v3; on Mac it runs on CPU and takes longer).
2. **Precise alignment:** `py-audio tools/align.py V` re-aligns the same text to the audio with **wav2vec2** (WhisperX align), segment by segment → `work/aligned/`. Numbers are spelled out as words first (`tools/numbers_to_words.py`). Words wav2vec2 couldn't place are interpolated and marked `"aligned": false`.
3. If the host gave an outline (`host_script/`), it is the backbone, but **what the host actually said on camera wins**.

---

## Stage 2 · Script (choose what goes in the video)

1. Claude reads the transcripts and the outline and writes `edit/script.json`: blocks (with a role: cold open, intro, sections, CTA, closing) and, in each block, the segments `{clip, from_words, to_words, occurrence}` in order. Optional per segment: `"remove"` (a bad take inside a line), hand-set `"in"`/`"out"` with `"force": true` and the reason.
2. Rules applied: last complete take (H21), interviewees keep their full answers (H23), no reformulations, a promise paid by the host's own line (D1), named people listed in `people_pending.md` (rules §4).
3. `py-audio tools/build_script.py V` looks up every phrase in the transcript (**if a phrase isn't found, it fails: zero invented words**) and writes the segment list with word times.
4. Packaging first (rules §7): Claude drafts title options + thumbnail text + blurb in `edit/package.json`.

---

## Stage 3 · Cut + audio QA

Order (re-run from step 1 whenever `script.json` changes):

1. `py-audio tools/build_script.py V --no-local` — first pass, writes the list of edges to measure.
2. `py-audio tools/local_edges.py V` — re-measures **every edge** in a ±2 s window (Whisper large-v3 + wav2vec2) → `work/cut/local_edges.json`. Only plausible times are used (not squashed, not stretched).
3. `py-audio tools/build_script.py V` — final edges from the audio energy (`tools/edges.py`):
   - voice = energy above the noise floor + 6 dB **and** above the host's level − 20 dB;
   - out-point after the last word: natural silence, min 300 ms, max 1.0 s by default (up to 3 s for a "checking notes" pause, H19); never reaching the next sound;
   - internal pauses over 1.5 s become 1.2 s; no silence over 3 s;
   - hidden takes: host voice with no written word inside a kept segment is reported (`hidden`) to be listened to.
4. `py-audio tools/build_cut.py V audio` — the cut audio, sample-accurate, 10 ms fades → `work/cut/voice48.wav` + `voice16.wav`.
5. `py-audio tools/qa_cut.py V` — Whisper hears the **whole cut** and compares word by word with the script:
   - DIFFERENCES: extra word (false start, half word, filler), missing word (cut off), changed word (garble), with the time in the cut. Spelling of numbers doesn't count.
   - CONFIDENCE: low-probability words within 1 s of a join (H20).
   - AIR: silences over 1.5 s, joins with < 300 ms after a finished thought (H19).
6. For each difference at a join: `py-audio tools/listen.py V cut <time> …` (Whisper + wav2vec2 in a ±2.2 s window, plus the segments of the edit list there). A real difference is fixed in `script.json` and the loop goes back to step 3.
7. `py-audio tools/audio_flags.py V` → `audio_flags.md`: only what may still sound wrong (cut on voice with no silence available, hand-set edges, things kept on purpose). Never hide a Whisper alarm.
8. `py-audio tools/build_cut.py V video` — the cut video (each segment at the source's frames, cached per segment). Can run detached.
9. `py-audio tools/gate1_page.py V` → `gate1.html`, plus an MP3 of the cut audio for listening.

### ⛔ GATE 1 — brief + script + takes + people + audio

The page shows:
- the **brief**: one paragraph on what the video is, the promise, the proposed title;
- the **script** block by block, with the clip and time of every segment;
- **chosen takes** and **borderline takes** (H21) with options;
- **named people** (`people_pending.md`): which cutouts exist, which are missing and where a licensed photo is;
- facts to **CHECK** (H3);
- the **audio of the cut** (MP3) and **audio_flags.md**.

Claude STOPS. Fixes asked by the editor are done and the page is updated. Only **"approved"** moves on.

---

## Stage 4 · Edit sheet

1. `py-audio tools/cut_words.py V` → `work/cut/words.json`: every word of the cut with start and end (from the alignment).
2. Claude writes the sheet's data in `edit/sheet.json`: each element = `{block, type, anchor phrase, until_phrase, occurrence, content, source, note}`. Types:
   - `BROLL` (host's clip or licensed stock), `PHOTO`, `WEB` (screen recording);
   - graphics (rules §3.3): `G-TIMELINE`, `G-COUNTER`, `G-BARS`, `G-COMPARE`, `G-VENN`, `G-WAFFLE`, `G-ICONS`, `G-FLOW`, `G-MAP`, `G-QUESTION`, `G-LIST`;
   - `LOWER` (short lower-third text), `NAME` (name card, D14), `SUB` (subtitles for another language, D15), `LINK` ("link in description" style callouts), `PEOPLE` (named-person card with cutout);
   - `PUNCH` (punch-in, D10).
3. Every element: what the viewer must see (rules §3), the relevance level, the source and its rights record (H9).
4. `py-audio tools/build_sheet.py V` resolves every anchor to the cut, applies H22 (whole line, never over the next line's first word), merges two full screens less than 1.5 s apart, checks H24 (flashes) and D10 (ping-pong), and warns about collisions → `work/sheet_resolved.json`.

---

## Stage 5 · Graphics previews + storyboard

1. `py-render tools/render_graphics.py V --scale 0.25 --no-motion` — quick previews of every graphic in the profile's style.
2. `py-render tools/storyboard.py V` → `storyboard.html`: one row per element with its thumbnail (on the real frame of the cut), the host's exact phrase, in/out times, source and note.
3. The storyboard page also shows (H26):
   - the **SEQUENCE** of blocks (the editor can reorder here);
   - the **B-ROLL COVERAGE MAP** (which clip/graphic covers which line, with in/out);
   - **interviewee coverage**: % of each answer kept (H23);
   - the **cut-off flags** from `audio_flags.md` (H20);
   - the graphic treatments Claude chose (D13) and any default broken (`decisions`).

### ⛔ GATE 2 — edit sheet + storyboard (before any full render)

Claude STOPS. Changes are applied (and logged in a "changes" table at the top of the page). Only **"approved"** moves on.
**From here the order is locked** (H26): if it must change, Claude stops and asks again.

---

## Stage 6 · Render

1. `py-render tools/preflight.py V` must say OK: cut audio = cut video; QA of the whole cut up to date; every photo/clip in the sheet exists and has a rights record; no emojis on screen; no unresolved anchors; no flashes; title present in `package.json`.
2. Long render, detached:
   `py-render tools/job.py V render -- py-render tools/render_all.py V`
   which runs:
   - `render_graphics.py V` — every graphic at full resolution, at the output frame rate (H14);
   - `mix.py V` — the voice-only mix at −14 LUFS, true peak ≤ −1.5 dBTP, plus the end-screen seconds;
   - `compose.py V all` — plan → parts of 60 s (cached by fingerprint) → final MP4 → QA.
3. **Encoder:** picked automatically — NVENC on NVIDIA GPUs, VideoToolbox on Mac, libx264 otherwise (`tools/encoder.py`).
4. A fix after the render: re-render that element (`render_graphics.py V --only E012`) and `compose.py V all`; only the parts that contain it are rebuilt.

---

## Stage 7 · QA

- `compose.py V qa` → `render/final/qa.json`: format (resolution, frame rate, codec), loudness, true peak, final audio = mix, every frame = the cut's frame, every element at its time, decodes fully with no black frames.
- `py-render tools/qa_flashes.py V mp4` — shots of ≤ 3 frames (H24).
- `py-audio tools/qa_cut.py V --final` — Whisper on the final render's audio vs. the script (H20) → `qa_final.md`.
- `py-render tools/lip_sync_check.py V` — mouth vs. voice at start, middle, end.
- Contact sheet of the final (one frame per element) → `work/qa/final_sheet.jpg`, looked at in full by Claude.
- `py-render tools/gate3_page.py V` → `gate3.html`.

### ⛔ GATE 3 — final render + QA report

The page shows the path of the final MP4, the QA results, the contact sheet and the remaining audio flags.
Claude STOPS. Only **"approved"** moves on. (The editor may also take the render into their own editor to add music; the publishing package can still be built.)

---

## Stage 8 · Publishing package

`py-render tools/build_package.py V` → `publish/` + `publish/copy_paste.html` (one "Copy" button per field, in YouTube Studio order):
- **title** (final) + 2 alternatives to test;
- **3 thumbnail prompts** for the profile's image tool, each with a real reference frame of the host (`publish/reference_frames/`), three very different concepts (rules §7), the recommended one first;
- **description**: the profile's links block first (H16), hook, summary, **chapters** (from the blocks, re-measured on the final), more links, credits from the rights records;
- tags (≤ 500 characters), pinned comment (the CTAs), end-screen notes.

When the editor has made the thumbnails, they go in `publish/thumbnails/`; Claude checks size (1280×720), weight (< 2 MB) and that the text matches.

---

## Stage 9 · After publishing

- `python tools/catalog.py add V` → `videos/catalog.json`: title, date, URL, stock clips used (D17), CTA used.
- Lessons from the editor's notes go into `docs/rules.md` or this SOP if they should hold for every video (on a git branch, see `docs/git_workflow.md`).

---

## Quick reference: tool → what it does

| Tool | Stage | What it does |
|---|---|---|
| `new_video.py` | 0 | creates the video folder |
| `status.py` | any | what's done, what's next |
| `job.py` | any | runs a long command detached, with a log |
| `footage_check.py` | 0 | integrity, audio, transcript, language, clip type |
| `align.py` + `numbers_to_words.py` | 1 | wav2vec2 word times |
| `build_script.py` + `edges.py` | 2–3 | segments → edges from audio energy (H18, H19) |
| `local_edges.py` | 3 | re-measures each edge in a ±2 s window |
| `build_cut.py` | 3 | cut audio and video |
| `qa_cut.py` | 3, 7 | Whisper on the whole cut / final vs. script (H20) |
| `listen.py` | 3 | Claude's "ear": Whisper in a short window |
| `audio_flags.py` | 3 | writes `audio_flags.md` |
| `gate1_page.py` | 3 | Gate 1 page |
| `cut_words.py`, `build_sheet.py` | 4 | edit sheet resolved to the cut |
| `render_graphics.py` | 5–6 | graphics in the profile's style |
| `storyboard.py` | 5 | Gate 2 page |
| `preflight.py` | 6 | checks before the render |
| `mix.py` | 6 | voice-only mix |
| `compose.py` | 6–7 | final MP4 by cached parts + QA |
| `render_all.py` | 6 | graphics + mix + compose, for a detached job |
| `qa_flashes.py`, `lip_sync_check.py` | 7 | visual QA |
| `gate3_page.py` | 7 | Gate 3 page |
| `build_package.py` | 8 | publishing package |
| `catalog.py` | 9 | record of published videos |
| `channel_study.py` | first session | studies the YouTube channel |
| `make_brand.py` | first session | simple brand kit (palette, fonts, banner) |
| `check.py` | install | health check |
