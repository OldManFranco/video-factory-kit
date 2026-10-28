# Video Factory Kit

A kit that lets **Claude Code** edit your YouTube vlogs: you drop in the camera clips (the host talking +
their own B-roll), and Claude transcribes, builds the script, cuts the audio cleanly, plans the B-roll and
graphics, renders the video and prepares the title, thumbnail prompts and description.

You stay in control: Claude **stops at 3 approval gates** and waits for you to write **"approved"**.

Maintained by Franco.

> **Status:** work in progress. The docs, rules, channel profile and tools are in. The installers for Windows and Mac
> and a full end-to-end test arrive in the next phases.

---

## What is Claude Code?

Claude Code is Claude working directly on your computer: it can read and write files and run programs in a
folder you choose. You talk to it in plain language ("start editing my Paris video") and it does the work,
asking you before anything important. You can use it in the **Claude desktop app** (the "Code" tab) or in a
terminal. You need a Claude subscription (Pro or Max).

## What you need

- A Windows PC or a Mac, with ~20 GB free for the tools plus space for your videos (a 4K vlog can need 25+ GB while rendering).
- Windows with an NVIDIA graphics card is fastest. A Mac works too (transcription is slower).
- The Claude desktop app: <https://claude.ai/download>.

## Install (once)

1. Download this kit (green "Code" button → Download ZIP, or `git clone`) and put the folder somewhere with space.
2. Install the tools:
   - **Windows:** double-click `install.bat`.
   - **Mac:** open Terminal in the kit folder and run `bash install.sh`.

   It installs Python 3.12, ffmpeg, the transcription tools (WhisperX, faster-whisper), yt-dlp, Node.js +
   HyperFrames and a browser for rendering graphics. It takes a while (big downloads).
3. Check everything works:
   - **Windows:** double-click `check.bat`.
   - **Mac:** `bash check.sh`.

   It writes `check_report.txt`. Every line should say OK. If not, open Claude in the kit folder and say
   "the check failed, help me fix it".

## Your first session

1. Open the Claude desktop app → **Code** tab → choose the kit folder.
2. Say: **"Hi, let's set up my channel."**
3. Claude asks for your **YouTube channel URL** and studies your channel (titles, thumbnails, how your videos
   start and end). Then it asks a few questions to fill in `CHANNEL_PROFILE.md`: who watches, the host's tone,
   on-screen language, colours, fonts, links for the description, upload format.
4. No brand kit? Claude proposes a few colour palettes and fonts, you pick one, and it makes a simple banner.

## Editing a video

1. Say: **"New video: Street food tour"**. Claude creates `videos/<date> Street food tour/`.
2. Copy your camera clips into its `footage/` folder (and the host's outline, if any, into `host_script/`).
3. Say: **"Start editing Street food tour."**

### What each gate looks like

| Gate | When | What you get | What you do |
|---|---|---|---|
| **Gate 1** | after the cut | a page with the script block by block, the takes Claude chose (and the borderline ones), named people, facts to check, and an **MP3 of the cut** | listen to the MP3, read the flagged joins (`audio_flags.md`), ask for changes, then write **approved** |
| **Gate 2** | before rendering | the **storyboard**: every B-roll clip and graphic next to the exact line it covers, the order of the blocks, how much of each interview was kept | reorder or change anything, then write **approved** (the order is locked from here) |
| **Gate 3** | after rendering | the final MP4 and its QA report (sound level, sync, no cut-off words) | watch it, ask for fixes, then write **approved** |

After Gate 3 Claude prepares the **publishing package**: a page with the title (+ 2 alternatives), the
description with your links and chapters, tags, pinned comment, and **3 thumbnail prompts** with real frames
of the host to use in your image tool. Each field has a "Copy" button.

**Music:** the kit renders the video with voice only. Add music in your own editor if you want it.

## Folder map

| Folder / file | What's in it |
|---|---|
| `CLAUDE.md` | instructions Claude reads at the start of every session |
| `CHANNEL_PROFILE.md` | your channel: style, colours, fonts, links, format (filled in during the first session) |
| `docs/rules.md` | the editing rules (hard rules + editorial defaults) |
| `docs/SOP.md` | the step-by-step method and its tools |
| `docs/first_session.md` | the first-session interview |
| `docs/git_workflow.md` | how changes to the kit are versioned |
| `docs/known_problems.md` | things that went wrong before, and the fixes |
| `tools/` | the Python tools |
| `templates/` | examples of the files Claude writes for each video |
| `assets/` | your brand files, fonts, people cutouts, maps |
| `videos/` | one folder per video (not uploaded to git) |

## Tips

- Long jobs (rendering, transcribing a lot of footage) keep running even if you close Claude. Keep the
  computer awake. To pick up later, say "continue editing <name>".
- If your Claude plan's usage runs out often, edit a video in three sessions: up to Gate 1, up to Gate 2, then the rest.
- You can change your profile any time: "change the accent colour to green", "add my Instagram link".
