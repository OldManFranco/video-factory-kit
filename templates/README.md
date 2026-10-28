# templates/

Examples of the files Claude writes in each video's `edit/` folder, for a made-up video ("I Ate Only Street Food for
a Day"). They show the exact format; every real video gets its own.

| File | Written at | Read by | Format explained in |
|---|---|---|---|
| `edit/script.json` | Stage 2 | `build_script.py` | `tools/build_script.py` (top of the file) |
| `edit/audio_notes.json` | Stage 3 | `audio_flags.py` | `tools/audio_flags.py` |
| `edit/gate1.json` | Gate 1 | `gate1_page.py` | `tools/gate1_page.py` |
| `edit/sheet.json` | Stage 4 | `build_sheet.py`, `render_graphics.py` | `tools/build_sheet.py`, `tools/render_graphics.py` |
| `edit/gate2.json` | Gate 2 | `storyboard.py` | `tools/storyboard.py` |
| `edit/package.json` | Stage 2 (draft) → Stage 8 | `build_package.py`, `compose.py` (file name) | `tools/build_package.py` |

The review pages (gates, storyboard, publishing package) take their look from `CHANNEL_PROFILE.md`
(`tools/vfk/page.py`), so there are no HTML templates to edit.
