# First session: getting to know the channel

Claude runs this when `CHANNEL_PROFILE.md` still says `"status": "EMPTY"`. The goal: by the end, the
profile is filled in, the brand kit exists, and the editor is ready to drop in the footage of their first video.

Keep it friendly and short. Ask **a few questions at a time**, in plain words, in the editor's language.
Suggest an answer when you can (from the channel study) so the editor only has to confirm or correct.

---

## Step 1 · Who's who (ask first)

1. What's your name? Are you the person on camera (the host), or do you edit for someone else?
2. What language would you like me to talk to you in?
3. **What's the YouTube channel's URL?** (If the channel is new or has no videos yet, that's fine: skip Step 2.)

## Step 2 · Study the channel (Claude does this on its own)

With the URL, Claude studies the channel before asking more questions, so the interview is mostly confirming:

1. `py-audio tools/channel_study.py <channel URL>` (uses yt-dlp, reads public data only; no login):
   - the list of videos: titles, length, upload date, views → `work/channel_study/videos.json`;
   - the 5 most viewed + the 5 most recent: description, chapters, auto-captions → `work/channel_study/`;
   - their thumbnails → `work/channel_study/thumbnails/`.
2. Claude reads it and writes section 3 of the profile ("What Claude learned from the channel"):
   - recurring formats and typical length;
   - how videos open (cold open? greeting?) and close (CTA, end screen);
   - title patterns that get more views than the channel's median, and those that don't;
   - thumbnail style (look at the images): host's expression, framing, text, colours;
   - the host's tone and pacing (from the captions);
   - CTAs and links that repeat in the descriptions (proposed as the links block).
3. If the study fails (private channel, no internet, yt-dlp blocked), say so in one line and just ask the questions.

## Step 3 · Interview (confirm and fill the gaps)

Show what the study found, then ask what's missing. Group the questions like this:

**Audience and content**
- Who watches (age, where they live, what they want from the channel)?
- What is the channel about? What's a typical video?
- How would you describe the host on camera (calm, funny, high energy…)?
- Which videos worked best, and why do you think so?
- Anything the channel never does (topics, language, kinds of jokes, kinds of images)?

**Look**
- Do you already have a brand kit: colours, fonts, a logo or banner? If yes: ask for the files (they go into `assets/brand/`) and the colour codes. If no: Step 4.
- What should on-screen text be written in (which language)?
- What style should graphics have (clean and minimal, playful, newsy…)?

**Links and calls to action**
- Which links go at the top of every description, in which order (website, social, a product, a newsletter…)?
- What does the host usually ask viewers to do (subscribe, comment, visit a site…)?

**Titles and thumbnails**
- Do you use a title-scoring tool (like vidIQ)? Which image tool do you use for thumbnails (like ChatGPT)?
- Anything you always or never do in thumbnails?

**Format**
- Long videos only, or Shorts too?
- Which camera(s) do you film with, and at what frame rate (if you know)? (Claude will check the files anyway.)
- How many seconds at the end for YouTube's end screen? (Default: 20.)
- Music: the kit renders **voice only** and doesn't choose music. You add music in your own editor if you want. OK?

## Step 4 · Brand kit (only if they don't have one)

1. Propose **3 simple palettes** that fit the channel (from the study and the answers). Each palette = 5 colours:
   `background` (light), `dark`, `accent` (one strong colour for the one word that matters), `neutral`, `light` (white).
   Check contrast: text in `dark` on `background`, and `light` on `dark`/`accent`, must be easy to read.
2. Propose **2 font pairs** from Google Fonts (free licence, OFL): a bold heading font and a readable body font.
3. `py-render tools/make_brand.py --preview` shows the 3 palettes × 2 font pairs on a sample lower third, name card, timeline and end card → `work/brand_preview.html`. The editor picks one.
4. `py-render tools/make_brand.py` downloads the chosen fonts to `assets/fonts/` and makes a simple banner (channel name + palette) in `assets/brand/` for the end card.

## Step 5 · Write the profile and confirm

1. Fill in every section of `CHANNEL_PROFILE.md` and the JSON block at its end (change `"status"` to `"READY"`).
2. Show a summary as a checklist (channel, host, audience, language, colours, fonts, links, format) and ask: "Is this right?"
3. Fix what they say, then explain the next step in 3 lines:
   - create a video: "Make a new video called <name>";
   - copy the camera clips into its `footage/` folder;
   - say "Start editing <name>". Claude takes it from there and stops at the 3 gates.

The profile can be changed at any time ("change the accent colour to green", "add my Instagram link").
