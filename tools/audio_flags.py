"""Stage 3 · audio_flags.md: the joins the editor's ear must decide (rules H20). Built from qa_cut.py, the script and
Claude's notes. It never hides a Whisper alarm: differences Claude hasn't explained are listed first, as UNRESOLVED.

Listed:
  0. UNRESOLVED differences (Whisper heard something other than the script) that aren't in edit/audio_notes.json
     → fix them in edit/script.json before Gate 1, or explain them in audio_notes.json after listening;
  1. cuts that land ON the host's voice (they ran straight on: no silence to cut in);
  2. edges set by hand ("force": true) and points removed by hand;
  3. host voice with no written word inside a kept segment ("hidden": maybe a false start Whisper didn't write);
  4. breathing room (rules H19): joins with < 300 ms after a finished sentence, and silences over 3 s;
  5. things kept on purpose (edit/audio_notes.json → "kept_on_purpose").

edit/audio_notes.json (optional, written by Claude):
  {"checked": [{"at": "4:12.5", "note": "Whisper writes 'gonna' for 'going to'"}],
   "kept_on_purpose": [{"block": "B12", "phrase": "i wouldn't live in in", "note": "the double 'in' is the host's, inside the take"}]}

Usage: py-audio tools/audio_flags.py <video>
"""
import re
import sys

import numpy as np

from vfk.kit import Video, fmt, load, parse_time
from vfk.media import read_wav

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
EDL = v.edl()["segments"]
Q = load(v.cut / "qa_cut.json")
if Q is None:
    raise SystemExit("Run qa_cut.py first.")
HEARD = load(v.cut / "qa_cut_heard.json", {}).get("heard", [])
G = v.script_resolved()
NOTES = load(v.edit / "audio_notes.json", {})
checked = [parse_time(c["at"]) for c in NOTES.get("checked", [])]


def context(t, r=1.6):
    a = [o for o in HEARD if t - r <= o[1] < t]
    b = [o for o in HEARD if t <= o[1] <= t + r]
    return f"«…{' '.join(o[0] for o in a[-4:])} │ {' '.join(o[0] for o in b[:4])}…»"


unresolved = [d for d in Q["differences"] if not any(abs(d["t"] - c) < 1.0 for c in checked)]
items, seen = [], set()
for c in Q["cuts_on_sound"]:
    if not c["on_voice"] or round(c["t"], 1) in seen:
        continue
    seen.add(round(c["t"], 1))
    items.append((c["t"], f"{context(c['t'])} · the cut lands on the voice ({v.short(c['clip'])}, {c['side']}): no silence "
                          f"to cut in. Listen for a click or a clipped sound."))
for b in G["blocks"]:
    for p in b["pieces"]:
        if p["edges"].get("in") == "manual":
            items.append((p["at_cut"], f"{context(p['at_cut'])} · start set by hand ({v.short(p['clip'])} {p['in']:.2f} s)"
                                       f"{': ' + p['why'] if p.get('why') else ''}."))
        if p["edges"].get("out") == "manual":
            end = p["at_cut"] + p["dur"]
            items.append((end, f"{context(end)} · end set by hand ({v.short(p['clip'])} {p['out']:.2f} s)"
                               f"{': ' + p['why'] if p.get('why') else ''}."))
        for g0, g1, ms in p["edges"].get("hidden", []):
            # clip time → cut time
            t = next((s["t0"] + (g0 - s["a"]) for s in EDL if s["clip"] == p["clip"] and s["a"] <= g0 <= s["b"]), None)
            if t is not None:
                items.append((t, f"{context(t)} · {ms:.2f} s of voice with no written word ({v.short(p['clip'])} {g0:.2f}–{g1:.2f} s): "
                                 f"a false start or filler? Removed if it was; otherwise it is the host's."))
# breathing room
x, _ = read_wav(v.cut / "voice16.wav")
hop = 160
n = len(x) // hop
e = 20 * np.log10(np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12))
floor = np.percentile(e, 10)
voiced = e > floor + 8
for k, s in enumerate(EDL[1:], 1):
    prev = EDL[k - 1]
    if s["join"] != "cut" or not prev["words"] or not re.search(r"[.?!]$", prev["words"][-1]["w"]):
        continue
    t = s["t0"]
    i, j = int(t * 100), int(t * 100)
    while i > 0 and not voiced[i - 1]:
        i -= 1
    while j < len(voiced) and not voiced[j]:
        j += 1
    if (j - i) / 100 < 0.30:
        items.append((t, f"{context(t)} · only {(j - i) * 10} ms of air after a finished sentence (rule: at least 300 ms). "
                         f"There was no more silence in the original."))
run = 0
for i, vv in enumerate(np.append(voiced, True)):
    if not vv:
        run += 1
        continue
    if run > 300:
        items.append(((i - run) / 100, f"{run / 100:.1f} s of silence (over 3 s of dead air)."))
    run = 0
for k in NOTES.get("kept_on_purpose", []):
    for s in EDL:
        if s["block"] == k["block"] and k["phrase"].lower().split()[0] in " ".join(w["w"].lower() for w in s["words"]):
            items.append((s["t0"], f"kept on purpose: {k['note']}"))
            break
items.sort()
mp3 = f"{v.name} - cut (audio only).mp3"
L = [f"# Audio flags · {v.name} (rule H20)\n",
     f"Times are in `{mp3}`. Whisper listened to the whole cut and every difference at a join was re-listened in a "
     f"±2 s window. These are the spots where there was no clean silence to cut in, or that were set by hand. "
     f"For each one: OK, or say what you hear.\n"]
if unresolved:
    L += ["## UNRESOLVED (fix before Gate 1)\n"] + [
        f"- {d['at']} · {d['kind']}{' · at a join' if d['at_join'] else ''} · script «{d['script']}» → heard «{d['heard']}»"
        for d in unresolved] + [""]
L += ["## To listen to\n"] + [f"- {fmt(t)} · {txt}" for t, txt in items]
(v.dir / "audio_flags.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"{len(items)} flags{f' · {len(unresolved)} UNRESOLVED differences' if unresolved else ''} → audio_flags.md")
