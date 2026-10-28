"""Reads the machine-readable JSON block at the end of CHANNEL_PROFILE.md. Every style choice comes from here."""
import json
import re

from .kit import ROOT

DEFAULTS = {
    "status": "EMPTY",
    "channel_name": "",
    "channel_url": "",
    "host_name": "",
    "host_on_screen_name": "",
    "editor_name": "",
    "chat_language": "en",
    "spoken_language": "en",
    "on_screen_language": "en",
    "vocabulary": [],
    "colors": {"background": "#F2F2EF", "dark": "#16181D", "accent": "#2F6FED", "neutral": "#8A8F98", "light": "#FFFFFF"},
    "fonts": {"heading": "Inter ExtraBold", "body": "Inter SemiBold",
              "heading_file": "assets/fonts/Inter-ExtraBold.ttf", "body_file": "assets/fonts/Inter-SemiBold.ttf"},
    "logo_file": "",
    "banner_file": "",
    "output": {"resolution": "native", "fps_rule": "24 for 23.976/24 camera footage; 25 for 25; 30 for 29.97/30",
               "loudness_lufs": -14.0, "true_peak_db": -1.5, "end_screen_seconds": 20},
    "thumbnail": {"max_words": 3, "text_color": "#FFFFFF", "last_word_color": "accent"},
    "title_max_chars": 60,
    "links": [],
    "title_scoring_tool": "",
    "thumbnail_image_tool": "",
}


def _merge(base, extra):
    out = dict(base)
    for k, v in (extra or {}).items():
        out[k] = _merge(base[k], v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return out


def load_profile(path=None):
    p = path or ROOT / "CHANNEL_PROFILE.md"
    if not p.exists():
        return dict(DEFAULTS)
    m = re.search(r"```json\s*\n(.*?)```", p.read_text(encoding="utf-8"), re.S)
    if not m:
        return dict(DEFAULTS)
    return _merge(DEFAULTS, json.loads(m.group(1)))


def color(prof, name):
    """A palette colour by role ('accent') or a literal '#RRGGBB'."""
    if isinstance(name, str) and name.startswith("#"):
        return name
    return prof["colors"].get(name, DEFAULTS["colors"].get(name, "#000000"))


def rgb(hexcode):
    h = hexcode.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def font_path(prof, which="heading"):
    """Absolute path of the heading/body font file, or None when it isn't installed in assets/fonts/."""
    f = prof["fonts"].get(f"{which}_file", "")
    p = (ROOT / f) if f else None
    return p if p and p.exists() else None


def whisper_prompt(prof, video=None):
    """Hint for Whisper: fillers (so it writes them) + channel names/places (profile vocabulary) + edit/vocabulary.txt."""
    words = list(prof.get("vocabulary") or [])
    if video is not None:
        f = video.edit / "vocabulary.txt"
        if f.exists():
            words += [w.strip() for w in f.read_text(encoding="utf-8").replace("\n", ",").split(",") if w.strip()]
    base = "Um, uh, so, the the, I I, a a." if prof.get("spoken_language", "en") == "en" else ""
    return (base + (" " + ", ".join(words) + "." if words else "")).strip() or None
