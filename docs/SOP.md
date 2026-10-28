# SOP — from camera footage to a finished vlog

How a vlog goes from a folder of camera clips (the host talking + their own B-roll) to a finished,
published video. The judgement behind each step is in `docs/rules.md`; the style comes from
`CHANNEL_PROFILE.md`. Examples of every file Claude writes are in `templates/edit/`.

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
| `py-audio` | transcription, alignment, cut, audio QA (WhisperX, faster-whisper, yt-dlp) | `tools\venv_audio\Scripts\python.exe` | `tools/venv_audio/bin/python` |
| `py-render` | graphics, storyboard, render, video QA (OpenCV, MediaPipe, Pillow, Playwright) | `tools\venv_render\Scripts\python.exe` | `tools/venv_render/bin/python` |
| `python` | small tools with no special needs (status, pages, sheet) | either venv works | either venv works |

All commands are run from the kit's root folder and take the video folder as their first argument
(`"videos/<name>"`, or just a unique part of the name). In the examples, `V` = `"videos/2026-11-02 Street Food Tour"`.
Every tool explains itself: the top of each file in `tools/` says what it does, its options and the format it reads.

**One folder per video**, created by `tools/new_video.py`:

```
videos/<date> <short name>/
  footage/          camera clips as they came off the card (never modified)
  host_script/      the host's outline or script, if there is one
  edit/             what Claude writes for this video (examples in templates/edit/):
    script.json       the segments of the cut       gate1.json / gate2.json   notes for the gate pages
    sheet.json        the edit sheet                audio_notes.json          Whisper differences explained
    package.json      titles, thumbnails, description data                gates.json  which gates are approved
  photos/ web/      licensed photos and screen recordings used in the sheet, each with its .json rights record
  work/             generated files (can be rebuilt): audio, transcripts, alignment, cut, graphics, render parts, QA
  render/final/     the final MP4: "[FINAL TITLE].mp4"
  publish/          the publishing package (copy_paste.html, texts, reference frames, thumbnails/)
  gate1.html  storyboard.html  gate3.html    the review pages for each gate
  <name> - cut (audio only).mp3              the cut, to listen to at Gate 1
  audio_flags.md    joins the editor must listen to (rules H20)
  people_pending.md named people and their cutouts (rules §4)
  STATUS.md         where this video stands and where to resume
```

**Long jobs** (render, transcribing many clips on a CPU) run detached so they survive if Claude or the app closes:
`python tools/job.py V <stage> -- py-render tools/render_all.py V` → log in `work/jobs/`; `python tools/job.py V list`.

**Resuming:** the first command of any session about a video is `python tools/status.py V`. It checks the disk and
says what's done and what's next. Never start over, never re-analyse what's on disk.

**Gates:** when the editor writes "approved", Claude records it: `python tools/status.py V approve 1` (or 2, 3).
If they ask for changes after approving, `python tools/status.py V reopen 2`.

**Review pages** (gates, storyboard, publishing package) are single HTML files with everything embedded. In the Claude
desktop app Claude publishes them as a private Artifact page and gives the link; otherwise the editor opens the file.

---

## Stage 0 · New video + footage check

1. `python tools/new_video.py "<short name>"` → creates the folder (today's date in front).
2. The editor copies the camera clips into `footage/` (A-roll and B-roll together is fine) and the host's outline, if any, into `host_script/`.
3. `py-audio tools/footage_check.py V` — for each clip:
   - checks that the file decodes completely (damaged clips are reported: copy them again from the card);
   - extracts the audio (16 kHz mono for Whisper, 48 kHz stereo for the cut);
   - transcribes with faster-whisper large-v3 (word timestamps) → `work/transcripts/`;
   - detects the language in 10 s windows (another language = probably someone the host talks to; that clip also gets a
     transcript in the other language: `<clip>.<lang>.words.json`);
   - measures each sentence's level (a much quieter voice = a second person);
   - classifies the clip: **A-ROLL** (host talking), **B-ROLL** (no speech), **INTERVIEW**, **MIXED**.
   Output: `work/footage.json` + `work/footage_check/summary.md`. On a Mac (CPU) run it as a detached job.
4. Claude tells the editor in plain words what it found (number of clips, total length, damaged files, interviews, languages).

## Stage 1 · Precise word times

1. `py-audio tools/align.py V` re-aligns the same text to the audio with **wav2vec2** (WhisperX align), segment by
   segment → `work/aligned/`. Numbers are aligned as spoken words. Words it couldn't place are interpolated.
2. If the host gave an outline (`host_script/`), it is the backbone, but **what the host actually said on camera wins**.

## Stage 2 · Script (choose what goes in the video)

1. Claude reads the transcripts (`work/footage_check/<clip>.txt` is the easy read) and the outline, and writes
   `edit/script.json` (format: top of `tools/build_script.py`; example: `templates/edit/script.json`): blocks with a role,
   and in each block the segments `{clip, from, to, occurrence}`; optional `remove`, hand-set `in`/`out` with `"force": true`
   and a `why`, `air_out` for a longer pause, `lang` for an interviewee in another language, `whole` for a whole clip.
   Interviews go in `"interviews"` (the full answer's clip seconds) so Gate 2 can report how much was kept.
2. Rules applied: last complete take (H21), interviewees keep their full answers (H23), no reformulations, a promise
   paid by the host's own line (D1), named people listed in `people_pending.md` (rules §4), facts to check (H3).
3. Packaging first (rules §7): Claude drafts title options + thumbnail texts + blurb in `edit/package.json`.

## Stage 3 · Cut + audio QA

Order (re-run from step 1 whenever `script.json` changes):

1. `py-audio tools/build_script.py V --no-local` — first pass: every phrase is found in the transcript (**a phrase that
   isn't there FAILS: zero invented words**) and the list of edges to measure is written.
2. `py-audio tools/local_edges.py V` — re-measures **every edge** in a ±2 s window (Whisper large-v3 + wav2vec2).
3. `py-audio tools/build_script.py V` — final edges from the audio energy (rules H18, H19): voice measured against the
   host's own level; out-point after the last word = natural silence (min 300 ms at a join, up to 1 s by default, up to
   3 s with `air_out`), never reaching the next sound; internal pauses over 1.5 s become 1.2 s; host voice with no
   written word inside a kept segment is reported ("hidden").
4. `py-audio tools/build_cut.py V audio` — the cut audio, sample-accurate, 10 ms fades → `work/cut/voice48.wav`,
   `voice16.wav` and `<name> - cut (audio only).mp3`.
5. `py-audio tools/qa_cut.py V` — Whisper hears the **whole cut** and compares it word by word with the script:
   DIFFERENCES (extra / missing / changed word), CUTS ON SOUND (measured in the original clip), LOW CONFIDENCE near
   joins, AIR over 1.5 s → `qa_cut.md`.
6. Every difference and every hidden-voice spot: `py-audio tools/listen.py V cut <time> …` (Whisper + wav2vec2 in a ±2.2 s
   window, plus the segments there) or `listen.py V clip <clip> <from> <to>`. A real difference is fixed in `script.json`
   (back to step 3). A Whisper spelling difference is explained in `edit/audio_notes.json`.
7. `py-audio tools/audio_flags.py V` → `audio_flags.md`: unexplained differences first (as UNRESOLVED), then cuts on
   voice, hand-set edges, hidden voice, joins with < 300 ms after a finished sentence, silences over 3 s, things kept
   on purpose. Never hide a Whisper alarm.
8. `python tools/gate1_page.py V` → `gate1.html` (with `edit/gate1.json`: brief, open choices, facts, not filmed).
9. While the editor listens: `python tools/job.py V cut -- py-audio tools/build_cut.py V video` (the cut video, cached per segment).

### ⛔ GATE 1 — brief + script + takes + people + audio

The page shows the brief; the script block by block with the clip and seconds of every segment; chosen and borderline
takes (H21); named people (`people_pending.md`); facts to check (H3); the audio of the cut; `audio_flags.md`.
Claude STOPS. Fixes are done and the page is updated. Only **"approved"** moves on (`status.py V approve 1`).

---

## Stage 4 · Edit sheet

1. `python tools/cut_words.py V` → `work/cut/words.json`: every word of the cut with start and end.
2. Claude writes `edit/sheet.json` (format: top of `tools/build_sheet.py` and `tools/render_graphics.py`; example:
   `templates/edit/sheet.json`). Each element is anchored to the host's words (`anchor` … `until`), never to seconds.
   Types: `BROLL`, `PHOTO`, `WEB`, `PEOPLE`, the graphics `G-TITLE`, `G-LIST`, `G-COUNTER`, `G-COMPARE`, `G-BARS`,
   `G-TIMELINE`, `G-LINE`, `G-WAFFLE`, `G-ICONS`, `G-FLOW`, `G-VENN`, `G-QUESTION`, `G-MAP` (rules §3.3, D13),
   the overlays `LOWER`, `LINK`, `NAME`, and `PUNCH` (punch-in, D10). Subtitles for another language go in `"subtitles"`.
3. Every element says what the viewer must see, its level, its source (rules §3). Assets that aren't the channel's own
   footage carry their rights record (H9): `source_url`, `licence`, `author` — or `"source": "own"`.
   - Licensed photos of people and places: `python tools/commons.py search "<query>"` → `commons.py get "<File:…>" "V/photos/<name>.jpg"`
     (writes the record next to the image).
   - A website or document: `py-render tools/record_web.py V <url> <name>` → `web/<name>.mp4` + record.
   - Stock clips used before: `python tools/catalog.py used` (rules D17).
4. `python tools/build_sheet.py V` resolves every anchor in the cut, applies H22 (whole line, never over the next word),
   joins two full screens less than 1.5 s apart (H24), warns about ping-pong (D10), adds the end screen →
   `work/sheet_resolved.json` + warnings.

## Stage 5 · Graphics previews + storyboard

1. `py-render tools/render_graphics.py V --scale 0.25 --no-motion` — quick stills of every element in the profile's style.
2. `py-render tools/storyboard.py V` → `storyboard.html` (optional `edit/gate2.json` with the editor's notes and what changed).
   It starts with **the whole video at a glance**: one tile per beat, in order (every insert, and the host on camera
   between them with lower thirds, name cards, subtitles and punch-ins), drawn the way the edit will look, with block,
   start, length and the host's words under each tile (also saved as `work/qa/storyboard_sheet.jpg`).
   Then (H26): the **SEQUENCE** of blocks; the **B-ROLL COVERAGE MAP** (what covers which words, in/out);
   **interviews kept** (% of each answer, H23); the **cut-off flags** (H20); warnings; choices and defaults broken;
   then one row per element with its thumbnail on the real frame of the cut.

### ⛔ GATE 2 — edit sheet + storyboard (before any full render)

Claude STOPS. Changes are applied and listed at the top of the page (`edit/gate2.json`). Only **"approved"** moves on.
**From here the order is locked** (H26): if it must change, Claude stops and asks again.

---

## Stage 6 · Render

1. `python tools/preflight.py V` must say PREFLIGHT OK (Gate 2 approved; cut video = cut audio; audio QA up to date;
   sheet up to date and every element on its word; files exist; rights records; no emojis; no flashes; final title).
2. The render, detached: `python tools/job.py V render -- py-render tools/render_all.py V`, which runs
   - `render_graphics.py V` — every element at full resolution and at the output frame rate (H14);
   - `mix.py V` — the voice-only mix at the profile's loudness (−14 LUFS, true peak ≤ −1.5 dBTP) + the end-screen seconds;
   - `compose.py V all` — plan → parts of 60 s (cached) → final MP4 named after the final title → QA.
3. **Encoder:** picked automatically — NVENC on NVIDIA, VideoToolbox on Mac, libx264 otherwise (`tools/vfk/media.py`).
4. A fix after the render: change the sheet, `build_sheet.py`, `render_graphics.py V --only E012`, `compose.py V all`:
   only the parts that contain the change are rebuilt. A new title only renames the file.

## Stage 7 · QA

- `compose.py` QA → `render/final/qa.json`: format, loudness, final audio = mix, picture = the cut's frames, every
  element at its time, decodes fully, no black frames; contact sheet `work/qa/final_sheet.jpg` (Claude looks at all of it).
- `py-audio tools/qa_cut.py V --final` — rule H20 on the final render's audio → `qa_final.md`.
- `py-render tools/qa_flashes.py V mp4` — shots of ≤ 3 frames (H24).
- `py-render tools/lip_sync_check.py V` — mouth vs. voice at 3 words → `work/qa/lip_sync.jpg`; Claude looks at it
  (in sync, the lips are closed just before the voice rises). The lag numbers are only a hint.
- `python tools/gate3_page.py V` → `gate3.html`.

### ⛔ GATE 3 — final render + QA report

Claude STOPS. Only **"approved"** moves on. (The editor may take the render into their own editor, for example to add
music; the publishing package can still be built — re-time the chapters if the length changes.)

---

## Stage 8 · Publishing package

`py-render tools/build_package.py V` (from `edit/package.json`, example in `templates/edit/`) → `publish/copy_paste.html`
(one "Copy" button per field, in YouTube Studio order) + the same texts as files:
- **title** + 2 alternatives to test;
- **description**: the profile's links block first (H16), blurb, summary, **chapters** (from the blocks), sources,
  credits from the rights records, disclaimer, hashtags;
- **3 thumbnail prompts** for the profile's image tool, each with a sharp real reference frame of the host
  (`publish/reference_frames/`), three very different concepts (rules §7);
- tags (≤ 500 characters), pinned comment (the profile's links marked "pinned"), end-screen note;
- `package_qa.json`: links first, chapters, lengths, thumbnail text ≤ 3 words and not repeating the title.

When the thumbnails are made, they go in `publish/thumbnails/`; re-running `build_package.py` checks their size
(1280×720) and weight (< 2 MB).

## Stage 9 · After publishing

- `python tools/catalog.py add V --url <YouTube link>` → `videos/catalog.json` (title, date, stock used, CTA).
- Lessons from the editor's notes go into `docs/rules.md` or this SOP if they should hold for every video
  (on a git branch, see `docs/git_workflow.md`).

---

## Quick reference: tool → what it does

| Tool | Stage | Env | What it does |
|---|---|---|---|
| `new_video.py` | 0 | python | creates the video folder |
| `status.py` | any | python | what's done, what's next; `approve N` / `reopen N` |
| `job.py` | any | python | runs a long command detached, with a log; `list` |
| `footage_check.py` | 0 | py-audio | integrity, audio, transcript, language, clip type |
| `align.py` | 1 | py-audio | wav2vec2 word times |
| `build_script.py` | 2–3 | py-audio | segments → edges from audio energy (H18, H19) |
| `local_edges.py` | 3 | py-audio | re-measures each edge in a ±2 s window |
| `build_cut.py` | 3 | py-audio | cut audio (+ MP3) and cut video |
| `qa_cut.py` | 3, 7 | py-audio | Whisper on the whole cut / the final vs. the script (H20) |
| `listen.py` | 3 | py-audio | Claude's "ear": Whisper + wav2vec2 in a short window |
| `audio_flags.py` | 3 | py-audio | writes `audio_flags.md` |
| `gate1_page.py` | 3 | python | Gate 1 page |
| `cut_words.py`, `build_sheet.py` | 4 | python | the edit sheet resolved in the cut |
| `commons.py` | 4 | python | Wikimedia Commons search + download with licence record |
| `record_web.py` | 4 | py-render | screen recording of a public web page |
| `render_graphics.py` | 5–6 | py-render | every element in the profile's style |
| `storyboard.py` | 5 | py-render | Gate 2 page |
| `preflight.py` | 6 | python | checks before the render |
| `mix.py` | 6 | py-render | voice-only mix at the profile's loudness |
| `compose.py` | 6–7 | py-render | final MP4 by cached parts + QA |
| `render_all.py` | 6 | py-render | graphics + mix + compose, for a detached job |
| `qa_flashes.py`, `lip_sync_check.py` | 7 | py-render | visual QA |
| `gate3_page.py` | 7 | python | Gate 3 page |
| `build_package.py` | 8 | py-render | publishing package |
| `catalog.py` | 9 | python | record of published videos; `used` lists stock already used |
| `channel_study.py` | first session | py-audio | studies the YouTube channel |
| `make_brand.py` | first session | py-render | simple brand kit (palette, fonts, end card, banner) |
| `check.py` | install | python | health check |
