# Channel profile

> **Status: EMPTY.** Claude fills this in during the first session (see `docs/first_session.md`).
> While this line says EMPTY, Claude runs the first-session interview before doing any editing.

Everything about *style* in this kit comes from this file: colours, fonts, on-screen language, links,
title and thumbnail habits, output format. The tools read the JSON block at the bottom; the text
sections are for Claude and for you. Change anything here at any time; the next render uses it.

---

## 1. Channel

- **Channel name:**
- **YouTube URL:**
- **Host (the person on camera):**
- **Name shown on screen for the host** (lower third, only when they introduce themselves):
- **Who edits with this kit** (who approves the gates):
- **Language to talk to the editor in:**

## 2. Audience and content

- **Who watches** (age, where they live, what they want):
- **Niche / topics:**
- **Typical video** (length, format, what happens in it):
- **What the host is like on camera** (tone, humour, energy):
- **Videos that worked best and why:**
- **Things the channel never does:**

## 3. What Claude learned from the channel

(Filled in by Claude after studying the YouTube channel: recurring formats, title patterns,
thumbnail style, typical length, pacing, how videos open and close, recurring CTAs.)

## 4. Look and brand

- **Brand kit:** (existing / created with Claude on <date>)
- **Colours:** see JSON (`background`, `dark`, `accent`, `neutral`, `light`)
- **Fonts:** see JSON
- **Logo / banner files:** in `assets/brand/`
- **Graphics style notes** (clean, playful, newsy, minimal…):

## 5. Calls to action and links

The description always starts with the links block below, in this order.
Pinned comment = the CTAs, never a discussion question.

| # | Label | URL | Where (description / pinned / on screen) |
|---|---|---|---|
| 1 | | | |

## 6. Titles and thumbnails

- **Title habits that work for this channel:**
- **Thumbnail style** (host's expression, framing, text colour, background):
- **Title-scoring tool** (e.g. vidIQ, none):
- **Image tool used for thumbnails** (e.g. ChatGPT, Midjourney, none):

## 7. Upload format

- **Main format:** long-form 16:9 (Shorts: yes/no)
- **Camera(s) and frame rate:**
- **End screen:** seconds left at the end for YouTube's end-screen elements
- **Music:** the kit does not choose or ship music. The render is voice only; you add music in your own editor if you want.

---

## Style settings (machine-readable — the tools read this block)

```json
{
  "status": "EMPTY",
  "channel_name": "",
  "channel_url": "",
  "host_name": "",
  "host_on_screen_name": "",
  "editor_name": "",
  "chat_language": "en",
  "on_screen_language": "en",
  "colors": {
    "background": "#F2F2EF",
    "dark": "#16181D",
    "accent": "#2F6FED",
    "neutral": "#8A8F98",
    "light": "#FFFFFF"
  },
  "fonts": {
    "heading": "Inter ExtraBold",
    "body": "Inter SemiBold",
    "heading_file": "assets/fonts/Inter-ExtraBold.ttf",
    "body_file": "assets/fonts/Inter-SemiBold.ttf"
  },
  "logo_file": "",
  "banner_file": "",
  "output": {
    "resolution": "native",
    "fps_rule": "24 for 23.976/24 camera footage; 25 for 25; 30 for 29.97/30",
    "loudness_lufs": -14.0,
    "true_peak_db": -1.5,
    "end_screen_seconds": 20
  },
  "thumbnail": {
    "max_words": 3,
    "text_color": "#FFFFFF",
    "last_word_color": "accent"
  },
  "title_max_chars": 60,
  "links": [],
  "title_scoring_tool": "",
  "thumbnail_image_tool": ""
}
```
