"""Stage 4 · edit/sheet.json → work/sheet_resolved.json: every element at its exact time in the cut (rules H22, H24, D10).

edit/sheet.json (written by Claude, SOP Stage 4):
{
  "elements": [
    {"block": "B02", "type": "BROLL", "anchor": "So this is the market", "until": "since five a.m.",
     "clip": "0008", "from": 2.0, "place": "CENTRAL MARKET", "source": "own",
     "what_to_see": "the market stalls, wide", "level": 1, "why": "the place he names", "note": ""},
    {"block": "B02", "type": "G-WAFFLE", "anchor": "out of a hundred stalls", "until": "sell coffee",
     "title": "100 STALLS", "subtitle": "AT THE MARKET", "total": 100, "source": "sign",
     "groups": [{"n": 62, "text": "FOOD", "color": "dark", "anchor": "sixty two"}, ...]},
    {"block": "B03", "type": "LOWER", "anchor": "link in the description", "until": "in the description",
     "text": "LINK IN DESCRIPTION", "style": "accent"},
    {"block": "B03", "type": "PUNCH", "anchor": "So was it worth it", "until": "worth it"}
  ],
  "subtitles": [{"block": "B02", "clip": "0012", "from": 4.0, "to": 7.6, "text": "English translation"}],
  "sources": {"sign": "The market's sign, filmed in clip 0009: 100 stalls, 62 food ..."},
  "decisions": [{"default": "D9", "what": "...", "why": "...", "lesson": "...", "date": "..."}]
}
Anchors:
  "anchor"      the first words of the line the element supports (searched in that block's words, ±0.6 s);
                "occurrence": n for the n-th time; "@<clip>:<seconds>" = a moment of an original clip; "@end" = end of the cut
  "until"       the last words of the line it covers: the element leaves with the end of that line's last word and never
                over the next word (rules H22). Without "until": "dur" seconds (lower thirds: 2.5–5 s)
  items of a graphic ("lines", "rows", "groups", "items", "steps", "nodes", "bars", "questions", "parts") may carry
  their own "anchor": they enter on that word.
  PHOTO "place_anchor": the place name appears on that word.
Rights (rules H9): PHOTO / WEB / PEOPLE / BROLL from a file need "source_url" + "licence" (+ "author") — e.g. copied from
the .json record that commons.py and record_web.py write — or "source": "own" for the channel's own material.
Checks: two full-screen elements less than 1.5 s apart are joined (no host "flash", H24); 1.5–4 s of host between two
full screens is reported ("ping-pong", D10); an overlay that would run into the next one is shortened.
An END element (end screen) is added at the end of the cut if the sheet has none.

Usage: python tools/build_sheet.py <video>
"""
import re
import sys
from fractions import Fraction

from vfk.kit import Video, fmt, load, save
from vfk.media import output_fps
from vfk.profile import load_profile

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
SHEET = load(v.edit / "sheet.json")
if not SHEET:
    raise SystemExit("Missing edit/sheet.json (SOP Stage 4).")
G = v.script_resolved()
EDL = v.edl()
CW = load(v.cut / "words.json")
if not CW:
    raise SystemExit("Run cut_words.py first.")
prof = load_profile()
WORDS = CW["words"]
DUR = CW["duration_s"]
BLOCKS = {b["id"]: b for b in G["blocks"]}
FULL = {"BROLL", "PHOTO", "WEB", "PEOPLE", "END"}           # + every G-* graphic
OVERLAY = {"LOWER", "LINK", "NAME", "SUB"}


def is_full(t):
    return t in FULL or t.startswith("G-")


def toks(w):
    return [x for x in re.split(r"[^a-z0-9]+", w.lower().replace("’", "'").replace("'", "")) if x]


TOK = [(t, i) for i, w in enumerate(WORDS) for t in toks(w["w"])]


def block_range(bid):
    b = BLOCKS.get(bid)
    if not b:
        return 0.0, DUR
    return b["start_in_cut"], b["start_in_cut"] + b["dur"]


def cut_time_of(clip, t, end=False):
    segs = [s for s in EDL["segments"] if s["clip"] == v.clip_id(clip)]
    for s in segs:
        if s["a"] - 1e-3 <= t <= s["b"] + 1e-3:
            return s["t0"] + (t - s["a"])
    if not segs:
        return None
    s = min(segs, key=lambda s: min(abs(t - s["a"]), abs(t - s["b"])))
    return s["t1"] if (end or t > s["b"]) else s["t0"]


def find(bid, anchor, n=1, after=None, last_token=False):
    """Time of the n-th occurrence of `anchor` in block bid (start of its first word, or (start, index of last word))."""
    if anchor == "@end":
        return DUR - 0.05
    if anchor.startswith("@"):
        clip, t = anchor[1:].rsplit(":", 1)
        return cut_time_of(clip, float(t))
    lo, hi = block_range(bid)
    if after is not None:
        lo = max(lo, after)
    target = [t for w in anchor.split() for t in toks(w)]
    seen = 0
    for k in range(len(TOK) - len(target) + 1):
        s = WORDS[TOK[k][1]]["s"]
        if s < lo - 0.6 or s > hi + 0.6:
            continue
        if [TOK[k + j][0] for j in range(len(target))] == target:
            seen += 1
            if seen == n:
                return (s, TOK[k + len(target) - 1][1]) if last_token else s
    return None


warnings, out = [], []
for i, el in enumerate(SHEET.get("elements", []), 1):
    e = dict(el)
    bid, typ = e.get("block"), e["type"]
    e["id"] = e.get("id") or f"E{i:03d}"
    if typ == "END":
        e["t"] = round(find(bid, e["anchor"]) if e.get("anchor") else DUR, 2)
    else:
        t = find(bid, e.get("anchor", ""), e.get("occurrence", 1)) if e.get("anchor") else None
        if t is None:
            warnings.append(f"{e['id']} {bid} {typ} «{e.get('anchor')}»: not found in the cut → start of the block (BY HAND)")
            t = block_range(bid)[0]
            e["placed"] = "BY HAND"
        e["t"] = round(t, 2)
    lo = e["t"] - 0.3
    for key in ("lines", "rows", "groups", "items", "steps", "nodes", "bars", "questions", "parts"):
        for it in e.get(key, []) if isinstance(e.get(key), list) else []:
            if isinstance(it, dict) and it.get("anchor"):
                tt = find(bid, it["anchor"], 1, after=lo)
                if tt is None:
                    warnings.append(f"{e['id']} {typ} item «{it['anchor']}» not found → enters with the element")
                it["t"] = round(tt if tt is not None else e["t"], 2)
    if e.get("place_anchor"):
        tt = find(bid, e["place_anchor"], 1, after=lo)
        e["place_t"] = round(max(0.0, tt - e["t"]), 2) if tt is not None else 0.0
    if e.get("until"):
        hit = find(bid, e["until"], 1, after=e["t"] + 0.2, last_token=True)
        if hit is None:
            warnings.append(f"{e['id']} {typ}: until «{e['until']}» not found → {e.get('dur', 4)} s")
            e["dur"] = e.get("dur", 4.0)
        else:
            k = hit[1]
            end_w = WORDS[k]["e"]
            nxt = WORDS[k + 1]["s"] if k + 1 < len(WORDS) else end_w + 1.0
            e["dur"] = round(min(end_w + 0.12, max(end_w, nxt - 0.02)) - e["t"], 2)   # leaves with the last word
            e["until_ok"] = True
    elif typ == "END":
        e["dur"] = float(prof["output"]["end_screen_seconds"]) + (DUR - e["t"])
    else:
        e["dur"] = float(e.get("dur", 4.0))
    if typ in OVERLAY and typ != "SUB":
        e["dur"] = round(max(1.5, e["dur"]) if e.get("until_ok") else min(5.0, max(2.5, e["dur"])), 2)
        if e["dur"] > 8:
            warnings.append(f"{fmt(e['t'])} {e['id']} {typ}: {e['dur']} s on screen (long line)")
    # the deepest item enters late: keep it at least 1 s on screen
    last_item = max([it.get("t", e["t"]) for key in ("lines", "rows", "groups", "items", "steps", "nodes", "bars", "questions", "parts")
                     for it in (e.get(key) if isinstance(e.get(key), list) else []) if isinstance(it, dict)] + [e["t"]])
    if last_item + 1.0 > e["t"] + e["dur"]:
        e["dur"] = round(last_item + 1.0 - e["t"], 2)
    if e.get("source") and e["source"] in SHEET.get("sources", {}):
        e["source_text"] = SHEET["sources"][e["source"]]
    if "CHECK" in (e.get("note") or ""):
        warnings.append(f"{fmt(e['t'])} {bid}: {e['note']}")
    e["tc"] = fmt(e["t"])
    out.append(e)

# subtitles for speech in another language (D15), in cut time; one never runs into the next
subs = []
for k, s in enumerate(SHEET.get("subtitles", []), 1):
    t0, t1 = cut_time_of(s["clip"], s["from"]), cut_time_of(s["clip"], s["to"], end=True)
    if t0 is None:
        warnings.append(f"subtitle {k}: clip {s['clip']} {s['from']} s is not in the cut")
        continue
    subs.append({"id": f"S{k:03d}", "block": s.get("block"), "type": "SUB", "t": round(t0, 2), "tc": fmt(t0),
                 "dur": round(max(0.6, t1 - t0 + 0.15), 2), "text": s["text"]})
for a, b in zip(subs, subs[1:]):
    if a["t"] + a["dur"] > b["t"] - 0.03:
        a["dur"] = round(max(0.4, b["t"] - a["t"] - 0.03), 2)
out += subs
if not any(e["type"] == "END" for e in out):
    out.append({"id": "END", "type": "END", "block": None, "t": round(DUR, 2), "tc": fmt(DUR),
                "dur": float(prof["output"]["end_screen_seconds"]), "note": "end screen (added automatically)"})
out.sort(key=lambda e: e["t"])

# overlays never run into the next overlay (subtitles live in their own band)
ov = [e for e in out if e["type"] in OVERLAY and e["type"] != "SUB"]
for a, b in zip(ov, ov[1:]):
    gap = round(b["t"] - a["t"] - 0.05, 2)
    if a["dur"] > gap:
        warnings.append(f"{a['tc']} {a['id']} {a['type']} shortened to {max(gap, 0.8)} s: {b['id']} enters")
        a["dur"] = max(gap, 0.8)
# full screens: < 1.5 s of host between two → joined (no flash, H24); 1.5–4 s → ping-pong warning (D10)
full = [e for e in out if is_full(e["type"])]
for a, b in zip(full, full[1:]):
    gap = b["t"] - (a["t"] + a["dur"])
    if gap < 1.5:
        a["dur"] = round(b["t"] - a["t"] + 0.1, 2)          # compose.py cuts it on the exact frame where b enters
    elif gap < 4.0:
        warnings.append(f"{a['tc']} {a['id']} → {b['id']}: only {gap:.1f} s of host between two full screens (D10 ping-pong)")

fps_out = output_fps(EDL["fps_main"])
count = {}
for e in out:
    count[e["type"]] = count.get(e["type"], 0) + 1
res = {"title": G.get("title", ""), "duration_cut_s": DUR, "fps_out": str(fps_out), "elements": out,
       "sequence": [{"id": b["id"], "role": b["role"], "section": b["section"], "start": b["start_in_cut"],
                     "end": round(b["start_in_cut"] + b["dur"], 2)} for b in G["blocks"]],
       "sources": SHEET.get("sources", {}), "decisions": SHEET.get("decisions", []), "count": count, "warnings": warnings}
save(v.work / "sheet_resolved.json", res)
n_full = sum(is_full(e["type"]) and e["type"] != "END" for e in out)
print(f"{len(out)} elements · {count}")
print(f"Full-screen inserts: {n_full} ({n_full / max(DUR / 60, 0.01):.1f}/min) · output {float(Fraction(fps_out)):g} fps")
for w in warnings:
    print("WARNING", w)
