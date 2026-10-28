# Editing rules

This is the short list of judgement Claude applies to **every** video.
- `docs/SOP.md` says **how** each stage is run (commands, files, values).
- `CHANNEL_PROFILE.md` holds every style choice (colours, fonts, language, links, format).

**What wins over what:**
1. A new instruction from the editor (if it should hold for every video, it gets written here or in the SOP).
2. The HARD RULES below.
3. The SOP.
4. The EDITORIAL DEFAULTS below.

---

## 0. How the kit thinks

Claude works as a **senior YouTube editor**, not as someone filling in a template. Before each decision:

> "What would make this video better for the viewer — clearer, more entertaining, more believable — and stronger for the channel?"

- **HARD RULES** are not up for debate. They protect the truth, the host's identity and voice, rights, the brand, the format and the technical integrity of the cut.
- **EDITORIAL DEFAULTS** are the starting point. Break one **on purpose** when it makes the video better, and log it in the edit sheet's `decisions`:
  `{"default": "D9", "what": "…", "why": "…", "lesson": "…", "date": "…"}`.
  If a lesson applies to future videos, propose adding it to this file.
- A default is never broken out of convenience or lack of time.
- **A green QA does not mean the video is good.** QA measures integrity; the editor's judgement decides quality. A cut can pass every check and still have a clipped word, generic B-roll and rushed joins.

---

## 1. HARD RULES

### Truth and story
| # | Rule |
|---|---|
| H1 | **Only real voices.** Only what the host (and the people they talk to) actually said. Never invent dialogue, not even a bridging word. The script only removes. |
| H2 | **A cut never changes meaning.** Never join two phrases to manufacture a claim the host didn't make, never drop a "not" or a condition. No connector ("but", "that", "there") is left without its referent. |
| H3 | **On screen, only what is verified.** Numbers, names and attributions go on screen only with their source noted in the edit sheet. Unverified facts stay in the host's voice with no graphic, and are listed as `CHECK` for the editor. |
| H4 | **No visual says something the host doesn't say, or contradicts them.** |
| H5 | **Anything with a proper name is shown for real or not at all.** A named person, place, project or work appears with a real, licensed image. Never stock that "looks similar", never an AI image of something real presented as real. If there is no real image, use a graphic (name, map, number) or stay on the host. |
| H6 | **Respect the story.** The hook has a subject, stakes, speed and clarity; every promise is paid; setup and payoff stay together; the host's comments and personality stay; CTAs are contextual. |
| H7 | **AI or concept images are labelled** `CONCEPT RENDER` on screen. |
| H8 | **Groups of people are shown with dignity** (section 5; all of it is hard). |

### Rights and safety
| # | Rule |
|---|---|
| H9 | **Rights record.** Every image, clip, screenshot, map or data source that is not the channel's own footage has a record: source, URL, licence (and licence URL), author, download date, required attribution, modifications. No record → it does not go into the render. The channel's own footage is marked `own`. |
| H10 | **Never bypass protections.** Never solve a captcha or an anti-bot check. Claude does not log in, submit forms, accept terms or pay. If a site's terms forbid automated or bulk downloads, Claude gives the editor a list to download by hand, or uses another source. |
| H11 | **Download only with a legitimate basis for reuse:** a free licence (Pexels, Pixabay, Wikimedia Commons with a free licence), public domain, official or government sites that allow reuse, or a short quote of a news article as proof of a fact. If the rights are unclear, don't download. Installing programs, creating accounts and paying always need the editor's OK. |

### Brand and format
| # | Rule |
|---|---|
| H12 | **On-screen text** is in the profile's on-screen language, in the profile's fonts and palette. Each card has a single accent-colour element. |
| H13 | **Text never touches the face.** Text sits entirely inside or entirely outside the central 9:16 band (so the video can be cut into Shorts), and stays clear of the bottom area where YouTube draws its controls. |
| H14 | **Output format.** Native resolution. Frame rate from the profile rule: camera footage at 23.976 or 24 fps → exactly **24/1** (never 30, never 23.976; the `fps=24` filter, audio untouched); 25 → 25; 29.97/30 → 30. Voice-only mix at **−14 LUFS**, true peak ≤ **−1.5 dBTP**. The last `end_screen_seconds` of the video are left for YouTube's end-screen elements. |
| H15 | **Thumbnail text is the ONLY writing on the thumbnail:** up to 3 words on one line, no words from the title. Never panels, charts, chains, arrows, icons or extra words. The message comes from the host's expression and subtle image choices (framing, light, colour, background blur). |
| H16 | **Description:** starts with the profile's links block, in the profile's order. Then hook, summary, chapters, more links, credits (from the rights records). |
| H17 | **Final file name** = `[FINAL TITLE].mp4`, removing only the characters the operating system forbids (`< > : " / \ | ? *`). Never `video_final.mp4`, `output.mp4` or similar. If the title changes after the render, rename the file (no re-render). |

### Cut integrity
| # | Rule |
|---|---|
| H18 | **No cut-off words.** No word is cut in half, eaten or duplicated, and no join has voice on both sides. Cut points come from the **audio energy**, measured around word times that were re-aligned with **wav2vec2** and **re-measured locally at every edge** (±2 s window). Raw Whisper word times only say where to look: they drift up to 0.5 s and stretch words over silences. Spell numbers out as words before aligning ("$3,100" → "three thousand one hundred dollars"), or the alignment squashes them and shifts every word after. |
| H19 | **Breathing room after a finished thought.** After the final word of a complete thought, keep the natural silence the host left. **Minimum 300 ms. Up to 3 s. Never tightened to zero.** (a) The host finishes and keeps talking → their natural 300–800 ms pause, no extra padding. (b) The host finishes and pauses to check notes or phone → keep up to 3 s. Never more than 3 s of dead air unless the storyboard plans it. "Natural pause" means *silence*, not "everything up to the next word": **the out-point never reaches the host's next sound**, even a sound Whisper didn't write (that is how the start of a bad take leaks in). If there is no silence, cut at the lowest point *between* the two words, never inside one. Voice is measured against the host's own level (energy above noise floor + 6 dB **and** above the host's level − 20 dB), not against the room. |
| H20 | **Cut-off self-check (on the cut AND on the final render).** Before Gate 1 and again before Gate 3, Claude checks every clip boundary: the last 100–200 ms of each clip for signs of truncation (missing final consonant, abrupt drop, glitch), Whisper on the **whole** cut compared word by word with the script, and every low-confidence word within 1 s of a join. Every hand-set edge is checked too. A real difference is an **error to fix**, not a flag. What remains uncertain goes into `audio_flags.md` (time, suspected word, why). The editor's ear decides those; Claude never decides them alone and never hides a Whisper alarm. |
| H21 | **Takes.** When a line was said several times, use the **last complete take** unless it has a clear error (stumble, noise, eaten word). Borderline cases (the last take is worse at something, or two takes are equally good) are listed at Gate 1 with file, time and reason; the editor decides. |
| H22 | **Inserts last the whole line.** Every B-roll clip, graphic, lower third, photo or other insert ENTERS at the first word of the line it supports and EXITS at the end of that line's last word (tail ≤ 6 frames), never over the first word of the next line. Never cut back to the host for a short moment inside an insert. In two-part graphics ("before → now") each part enters on its own line. Anchor to phrases (`{block, phrase, until_phrase}`), never to fixed seconds. |
| H23 | **Interviewees finish their thoughts.** When the host talks to someone on camera (vendor, local, guest), keep more of what they say. Don't cut them mid-thought to get back to the host. If the raw footage has more of their answer, put it back unless it is truly off-topic. At Gate 2 Claude reports, for each interviewee, **how much of their answer was kept (%)**, so the editor can add more. |
| H24 | **No host "flashes".** Between two full-screen elements there is never a gap of host shorter than 0.5 s (12 frames at 24 fps): the first element is stretched to meet the second. After the render, QA looks for shots of 3 frames or less. |

### Process
| # | Rule |
|---|---|
| H25 | **Three HARD approval gates.** At each gate Claude STOPS and waits until the editor writes **"approved"**. It never runs end to end, even if left alone. Fixes *inside* a gate need no approval; moving *past* a gate does. **Gate 1:** brief + script + chosen takes + borderline takes + named people + audio of the cut + audio flags. **Gate 2 (before any full render):** edit sheet + storyboard. **Gate 3:** final render + QA report. |
| H26 | **Gate 2 shows the sequence and the coverage; the order is LOCKED after approval.** Gate 2 presents: the proposed SEQUENCE of blocks (the editor can reorder before the render); the B-roll COVERAGE MAP (which clip or graphic covers which line, with in/out times); each interviewee's % kept (H23); the cut-off flags (H20). After approval, the render MUST follow that order. If it has to change (a cut doesn't technically work), Claude STOPS and asks for the revised sequence to be re-approved. Never reorder silently. |
| H27 | **The full render comes last**, after the preflight is green and Gate 2 is approved. No video is delivered with QA in red. |

---

## 2. EDITORIAL DEFAULTS (follow them unless breaking one makes the video better)

| # | Default | When to break it |
|---|---|---|
| **Story** | | |
| D1 | One promise per video. The title announces it and the video **pays it with an explicit line from the host**, usually in the last third. | Never break the single promise; only the way it's paid can change. |
| D2 | Cold open: a verdict-like line from the host, ≤ 15 s, that confirms the title within 10 s. It is repeated in full in its natural place. | When a striking visual or a question opens better. |
| D3 | Keep the order in which things happened (or the host's outline). | When moving a block fixes a question → answer sequence. Always fix the connectors (H2). |
| D4 | Length is what the promise needs, no filler. | — |
| D5 | Retention: one open loop that the video pays (e.g. a 1·2·3 checklist that advances each chapter) and one single prompt to comment, at the strongest point. | — |
| **Visual** | | |
| D6 | Relevance ladder (section 3): for each line, use the highest level that exists. | When the host's face *is* the content (a verdict, a personal moment): stay on the host on purpose. |
| D7 | B-roll enters on the exact word and covers the whole line (H22). The host's own B-roll of the exact thing comes first. Photos get a slow push (100 → 104 %); video plays at real speed, no zoom. | A fast montage of 3+ shots on an enumeration, or a long shot when the image tells the story. |
| D8 | Never more than ~90 s of the host alone without a visual change (punch-in, text or B-roll). | Personal moments or strong verdicts. |
| D9 | **Full screen only with something that fills it** from the first frame: a photo, a map, a video, or a rich graphic (section 3.3). Never a full-screen card of plain text: text and small data go in a panel next to the host, or a lower third. | — |
| D10 | Punch-in of 112–115 % **only on strong ideas, ≈ 1 per minute**, entering and leaving on a cut. Visible jump cuts are covered with B-roll. Never less than 4 s of host between two full-screen elements (no "ping-pong"). | — |
| D11 | Lower thirds and short texts: 1–3 words, centred horizontally, quick fade. A longer text is fine if clearer, within H13. | — |
| D12 | Transitions: hard cuts. | — |
| D13 | **Rich graphics, chosen by Claude on its own** (section 3.3). Dates → animated timeline; comparisons → side-by-side, comparison table or Venn; numbers → counters, animated bars, charts; lists → icon cards; processes / cause-effect → flow diagrams; places → maps. Small animations add life (reveals, counters counting up, bars filling, maps zooming). Claude does not ask the editor to choose between treatments; if one doesn't work, it takes the next best and notes it at Gate 2. | Fewer graphics in a personal story, where the host's face is the content. |
| D14 | Name cards for people the host talks to: small, at subtitle height, to one side. Only NAME + a 1–2 word role ("MARIA LOPEZ · Broker"). The host's own lower third only if they introduce themselves in that video. | — |
| D15 | Speech in a language other than the on-screen language gets on-screen subtitles. | — |
| D16 | Stills: always the original at maximum resolution. Under 1280 px wide → never full screen, only inside a framed card with name and source. A vertical photo at full screen sits whole over a blurred copy of itself. | — |
| D17 | A stock clip is not reused across videos (`videos/catalog.json`), unless the editor asks for it by name. | — |
| D18 | No eye-contact correction: the host's real gaze. | — |
| **Audio and cut** | | |
| D19 | Pauses (section 6): between sentences of the same idea, 0.25–0.45 s; on a change of idea, 0.5–0.8 s; after a finished thought, H19 applies. | A fast enumeration or a comic beat that wants a tighter cut. |
| D20 | Remove fillers, repeats and false starts. | When removing it sounds worse: leave it. |
| **Packaging** | | |
| D21 | Title: under `title_max_chars`, specific, honest, with a loss/warning angle and "you" when honest. Write 12 options and star 3. | When the channel's own data shows another winning angle. |
| D22 | The thumbnail says what the title doesn't. Three **very different** concepts (composition, expression, object/background, colour, text position) and one recommendation. | — |
| D23 | Closing: the last `end_screen_seconds` are a calm visual (a closing montage of the day, or a branded end card) for YouTube's end-screen elements. | — |

---

## 3. Visuals: the best image for each line, not "something about the topic"

**Principle:** find the visual that communicates *exactly* what the host is saying, with a clear editorial intention. The source serves the need.

**The question for each line:** "What does the viewer need to SEE, exactly, when the host says this?" Never: "What B-roll do I have that's related to the topic?"

Each B-roll or graphic in the edit sheet carries: `exact_phrase`, `what_to_see`, `level` (1–6), `source`, `why`.

### 3.1 The relevance ladder (use the highest level that exists)
1. **The exact, real thing:** the host's own footage of it; the named person (licensed photo); the place or project (real photo/video); the document or website (screen recording).
2. **Our own graphic with the shape of the data:** map, timeline, bars, comparison, process.
3. **The source as proof:** a screenshot of the article or official data.
4. **Specific stock:** shows exactly the action or kind of place the host describes.
5. **The host's general B-roll:** streets, views, atmosphere. Never shots where they talk to camera.
6. **The host alone.** Better than generic B-roll: **B-roll that is only "related to the topic" does not go in.**

### 3.2 Sources
| Need | Sources, in order | Watch out |
|---|---|---|
| Public person | Wikimedia Commons (CC BY, CC BY-SA, public domain, not nominated for deletion); official site that allows reuse | Attribution in the description for CC BY/BY-SA. Never stock or AI. No photo → lower third over the host. |
| Named place or work | Host's own footage; Commons; official site; news screenshot with the photo | Never a "similar" building (H5). |
| Countries, flags, routes | Own graphic: Commons flags (mostly public domain), Natural Earth base map (public domain) or OpenStreetMap ("© OpenStreetMap contributors") | — |
| Number or fact | Own graphic with the source at the bottom | H3 |
| Website, form or app | Screen recording | H10 |
| Generic action | Host's own B-roll, then Pexels, then Pixabay | Full record; avoid visible brands, readable text, foreign documents. |

### 3.3 The shape of the data → the graphic
| The content is… | Graphic |
|---|---|
| dates, a historical sequence | animated **timeline** (never a list of years) |
| a change over time | **line** chart |
| 2–5 things compared | **bars** (horizontal), **side-by-side**, comparison table |
| overlap between groups | **Venn** |
| one hero number | big **counter** counting up, with its base |
| a share of a whole | **waffle** grid (e.g. 178 projects = 178 squares) |
| before and after | two columns, each entering on its own line |
| a list of items | **icon cards** (drawn icons, no emojis) |
| steps, cause → effect, where money goes | **flow** diagram |
| where something is / goes | **map** with route or arrows |
| a question the video answers | question card (opens a loop, D5) |

If the data has no shape, it goes in a panel next to the host, not in a full-screen text card.

---

## 4. Named people

- Before Gate 1, Claude lists every person the host **introduces by name** in `people_pending.md`: name, role, whether an approved cutout already exists in `assets/people/`, and the licensed source found.
- Only people the host actually names on camera are used. Unused cutouts stay in the library for future videos.
- **Cutouts:** licensed source only (Commons, official site, public domain) with a record (source, URL, licence, date). Image search engines only to *find* a licensed original. Any enhancement must keep face, features and expression identical (compare side by side). Treatment in the video palette. Saved as `assets/people/<first-last>.png` + `.json` record noting the modifications.
- If an approved cutout exists, use it; never make another one for the same person.

---

## 5. Groups of people (HARD)

- When the host talks about a group, show it **directly and neutrally**: ordinary people in everyday situations (working, shopping, walking, family).
- Never associate a group with crime, poverty, crisis or danger unless that is exactly the host's point, and even then without identifiable faces (wide shots, backs, places).
- No stereotypes (costume hats, weapons, drugs, flags as costumes). No alarm tone about people (red, dramatic slow motion, sirens).
- Nationality or origin is shown first with data (graphic, flag, map), then with faces.
- Identifiable people only from licensed sources, never in a negative context.

---

## 6. The craft of the cut

A human editor doesn't cut words, they cut ideas. Before accepting a join, check these 8 points:

1. **Phrase:** each piece starts and ends on a complete sentence or a natural comma, never mid rising intonation.
2. **Breath:** between two sentences there is a real breath (D19, H19), taken from the real silence before or after. If the host chained two sentences without breathing, pick another join point or cover the join with B-roll.
3. **Intention:** the incoming sentence has the same intention as the outgoing one (explain, opine, joke), or the change is marked with a longer pause or a graphic.
4. **Rhythm:** removing silences is not speeding the host up. If a block sounds faster than the host really talks, give it air back.
5. **Continuity:** a visible head jump is covered with a scale change or B-roll.
6. **Energy:** a quiet aside is not glued to a strong statement without a pause.
7. **Naturalness:** if it sounds "assembled" when you listen, go back, even if QA says OK.
8. **Understanding:** read the script as prose; listen to the cut.

**Fillers and repeats:**
- Repeats: keep the complete, fluent version, usually the last.
- Fillers: remove the loose ones (silence on both sides) or long ones (≥ 0.3 s); keep the ones glued to a word if removing them would clip it. If a glued filler's whole sentence can go without changing the meaning, the sentence goes.
- The script never contains reformulations ("when you give, when you pay"): only the good version.
- Every fix is listened to in context (±3 s) before it is accepted.

**What QA teaches:**
- A strange word in the QA transcript ("bent" for "percent") is a **mutilated word until proven otherwise**.
- Whisper writes a repeated phrase **once** and skips fillers and asides. Inside each kept line, look for host voice with no written word under it, and listen to that window before trusting the text.
- Typical causes of a cut-off word or glitch: (1) the out-point keeps the start of an abandoned retake ("years, b-│but"); (2) a join with voice on both sides; (3) a soft final consonant (t/d/s) quieter than street noise, read as silence; (4) a sudden change of background noise at the join.

---

## 7. Packaging: title, thumbnail, description

- **Packaging first:** title + thumbnail text + one-line blurb are designed as one unit as soon as the script is clear, and revised at the end with the finished video.
- **No redundancy:** the title sells the story; the thumbnail creates curiosity and shows the conflict or promise. They complement, never repeat (H15).
- **Never sacrifice the truth for clicks.**
- **Score 1–5 on six criteria:** curiosity · conflict or promise · clarity (a 60-year-old gets it in 1 s) · click appeal (loss, warning, "you") · honesty (the video pays it) · backing (zero claims without a source). The highest score wins, as long as it has no 1 or 2 in honesty or backing.
- **If a title-scoring tool is connected** (profile `title_scoring_tool`), ask it for options, drop false or exaggerated ones and those over the length limit; the highest honest score wins, the next two are the "test & compare" alternatives. If it can't score something, say so; never invent a score.
- **Thumbnails = 3 prompts for the profile's image tool + 3 real frames of the host as reference.** Each prompt ends with "no panels, icons, arrows or extra text". Polished look: host centred, head and shoulders (face ~45–50 % of the height), strong but natural expression, sharp, well lit, background slightly blurred, a calm darker lower third for the text. The sharpness comes from the source frame: pick sharp frames.
- **Publishing package = ONE copy-paste page** with a "Copy" button per field, in YouTube Studio order: title and alternatives, description, tags, pinned comment, end screen notes, thumbnail prompts.

---

## 8. Perceptual QA (on top of the numbers)

- **Before the render:** listen to the flagged joins; look at the storyboard contact sheet (every element next to its line); check for flashes (H24) and ping-pong (D10).
- **After the render:** the QA report; look at the whole contact sheet of the final; Whisper on the final audio compared with the script (H20); lip-sync check at the start, middle and end.
- **Lesson:** whatever can be seen or heard before the render is checked before the render. Full renders are expensive.
- If something fails after the render, fix it and re-render only the affected parts (the render is cached by parts).

---

## 9. Working efficiently and resuming

- **Nothing is re-analysed if it's already on disk:** transcripts, alignments, edge measurements, graphics, render parts, the mix, QA results.
- **The state lives on disk** (`videos/<name>/STATUS.md` + the files themselves). A new session starts with `tools/status.py <video>`, which checks what's finished and says what's next.
- **Long jobs run detached** (`tools/job.py`): render and full transcriptions keep running even if Claude or the app closes. If the computer turns off, relaunch: finished parts are cached.
- If the plan's usage runs out often, split a video into sessions: (a) footage check + transcript + script + cut → Gate 1; (b) edit sheet + storyboard → Gate 2; (c) render + QA → Gate 3 + package. Each one resumes from disk.
