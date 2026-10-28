"""Stages 2–3 · edit/script.json → the cut's edit list, with every edge measured on the audio (rules H18, H19).

edit/script.json (written by Claude, SOP Stage 2):
{
  "title": "working title",
  "blocks": [
    {"id": "B01", "role": "COLD OPEN", "section": "§1 · Opening",
     "segments": [
       {"clip": "0001", "from": "There are 178 projects", "to": "the nearby area.", "occurrence": 1},
       {"clip": "0002", "from": "So we're in", "to": "over time.", "remove": [[14.65, 19.30]]},
       {"clip": "0005", "from": "before we get", "to": "building.", "occurrence": 3, "in": 32.43, "force": true,
        "why": "earlier take ends right before"},
       {"clip": "0019", "from": "so if you're", "to": "small town.", "air_out": 1.6},
       {"clip": "0083", "lang": "es", "from": "...", "to": "..."},
       {"clip": "intro_card", "whole": true}
     ],
     "note": "what was left out and why", "check": "facts to check (H3)"}
  ]
}
Segment options:
  clip         any unique part of the clip's file name
  from / to    the first and last words of the segment, as written in the transcript (found without punctuation);
               a phrase that isn't in the transcript FAILS: zero invented words (rules H1)
  occurrence   which occurrence of "from" in the clip (takes: usually the last complete one, rules H21)
  in / out     hand-set edge in clip seconds, used only with "force": true (measured on the audio energy)
  remove       [[a, b], ...] clip seconds to cut out inside the segment (a hidden bad take, a filler);
               each point moves to the quietest instant within ±80 ms unless "remove_fixed": true
  air_in/out   seconds of air at that edge (default 0.30 in / up to 1.0 out; up to 3 s for a pause to check notes)
  keep_pauses  true: don't shorten internal pauses
  lang         the transcript in another language (an interviewee): uses work/transcripts/<clip>.<lang>.words.json
  whole        true: the whole clip, start to end

Output: work/script_resolved.json · work/cut/edl.json (for build_cut.py) · work/cut/cuts.csv · work/cut/edges_requested.json

Usage: py-audio tools/build_script.py <video> [--no-local]
  --no-local  ignore work/cut/local_edges.json (first pass: writes the list of edges for local_edges.py)
"""
import csv
import re
import sys
from collections import Counter
from fractions import Fraction

from vfk import edges
from vfk.kit import Video, fmt, load, save
from vfk.media import probe
from vfk.words import load_words, norm, spoken_word

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
SCRIPT = load(v.edit / "script.json")
if not SCRIPT:
    raise SystemExit(f"Missing {v.edit / 'script.json'} (SOP Stage 2).")
INFO = v.footage_info()
LOCAL = {} if "--no-local" in sys.argv else load(v.cut / "local_edges.json", {})
_words = {}


def clip_fps(c):
    fr = INFO.get(c, {}).get("fps") or probe(v.clips()[c]).get("fps", "24000/1001")
    return float(Fraction(fr))


def words_of(c, lang=None):
    key = (c, lang)
    if key not in _words:
        name = f"{c}.{lang}.words.json" if lang else f"{c}.words.json"
        f = v.aligned / name
        if not f.exists():
            f = v.transcripts / name
        if not f.exists():
            raise SystemExit(f"No transcript for {c}{' (' + lang + ')' if lang else ''}: run footage_check.py / align.py")
        ws = load_words(f)
        _words[key] = (ws, [norm(w["w"]) for w in ws])
    return _words[key]


def find(c, phrase, lang=None, start=0):
    """Phrase without spaces or punctuation → [(first_token, last_token)] on word boundaries."""
    ws, ns = words_of(c, lang)
    s, starts = "", []
    for n in ns:
        starts.append(len(s))
        s += n
    q = norm(phrase.replace(" ", ""))
    at = {p: i for i, p in enumerate(starts)}
    out, pos = [], s.find(q)
    while pos != -1 and q:
        if pos in at and at[pos] >= start:
            end = pos + len(q) - 1
            out.append((at[pos], max(i for i, p in enumerate(starts) if p <= end)))
        pos = s.find(q, pos + 1)
    return out


def locate(c, frm, to, occ, lang):
    hits = find(c, frm, lang)
    if not hits:
        raise ValueError(f"[{v.short(c)}] not in the transcript: «{frm}»")
    if occ > len(hits):
        raise ValueError(f"[{v.short(c)}] «{frm}» appears {len(hits)} time(s), occurrence {occ} was asked")
    i0 = hits[occ - 1][0]
    h2 = find(c, to, lang, i0)
    if not h2:
        raise ValueError(f"[{v.short(c)}] not found after «{frm}»: «{to}»")
    return i0, h2[0][1]


def plausible(ws, k, se):
    """A local time is used only if believable: at least 60 % of the time it takes to SAY the word (~55 ms per spoken
    letter: '$210,000' = 'two hundred ten thousand dollars'), not stretched, and moved less than 2 s."""
    g = [k]
    while g[0] > 0 and ws[g[0]]["w"][:1] in ",.-":
        g.insert(0, g[0] - 1)
    while g[-1] + 1 < len(ws) and ws[g[-1] + 1]["w"][:1] in ",.-":
        g.append(g[-1] + 1)
    txt = "".join(ws[i]["w"].strip() for i in g)
    letters = len(re.sub(r"[^a-z]", "", spoken_word(txt).lower()))
    s, e = se
    return 0.6 * max(0.06, 0.055 * letters) <= e - s <= max(1.2, 0.12 * letters + 0.4) and abs(s - ws[k]["s"]) < 2.0


def main():
    resolved, edl, rows, requested, errors = [], [], [], [], []
    t_cut, last = 0.0, None
    fps_main = Counter(INFO[c]["fps"] for c in INFO if INFO[c].get("type") in ("A-ROLL", "MIXED", "INTERVIEW") and INFO[c].get("fps"))
    fps_main = fps_main.most_common(1)[0][0] if fps_main else "24000/1001"
    for b in SCRIPT["blocks"]:
        pieces = []
        for sg in b["segments"]:
            try:
                c = v.clip_id(str(sg["clip"]))
            except SystemExit as e:
                errors.append(f"{b['id']}: {e}")
                continue
            fps = clip_fps(c)
            if sg.get("whole"):
                dur = round(INFO.get(c, {}).get("duration") or probe(v.clips()[c])["duration"], 3)
                dur = max(1, int(dur * fps) - 1) / fps
                try:
                    ws = words_of(c)[0]
                except SystemExit:
                    ws = []
                segs, info, i0, i1 = [(0.0, round(dur, 5))], {"in": "whole", "out": "whole", "hidden": []}, 0, len(ws) - 1
            else:
                lang = sg.get("lang")
                try:
                    i0, i1 = locate(c, sg["from"], sg["to"], sg.get("occurrence", 1), lang)
                except ValueError as e:
                    errors.append(f"{b['id']}: {e}")
                    continue
                ws = words_of(c, lang)[0]
                span = lambda i, j: [(k, ws[k]["w"].strip(), ws[k]["s"]) for k in range(max(0, i), min(len(ws), j))]
                requested.append({"clip": c, "lang": lang, "in": span(i0 - 1, i0 + 2), "out": span(i1 - 1, i1 + 2)})
                loc = LOCAL.get(c if not lang else f"{c}.{lang}", {})
                if loc:
                    ws = [dict(w, s=loc[str(k)][0], e=loc[str(k)][1], local=True)
                          if str(k) in loc and plausible(ws, k, loc[str(k)]) else w for k, w in enumerate(ws)]
                A = edges.audio(v, c)
                f_ = sg.get("force")
                segs, info = edges.segment(A, ws, i0, i1, fps, sg.get("in") if f_ else None, sg.get("out") if f_ else None,
                                           sg.get("air_in"), sg.get("air_out"), 99.0 if sg.get("keep_pauses") else None)
                for qa, qb in sg.get("remove", []):
                    if not sg.get("remove_fixed"):
                        qa, qb = edges.valley(A, qa - 0.08, qa + 0.08), edges.valley(A, qb - 0.08, qb + 0.08)
                    new = []
                    for x, y in segs:
                        if qb <= x or qa >= y:
                            new.append((x, y))
                            continue
                        if qa > x:
                            new.append((x, qa))
                        if qb < y:
                            new.append((qb, y))
                    segs = [tuple(round(t, 5) for t in edges.to_frames(A, x, y, fps)) for x, y in new]
                # with generous air, the out of one segment and the in of the next one from the SAME clip can overlap
                # (the same word would play twice): the next one starts where the previous one ended
                if last and last[0] == c and last[1] - 3.5 < segs[0][0] < last[1]:
                    segs[0] = tuple(round(t, 5) for t in edges.to_frames(A, last[1], segs[0][1], fps, fixed_in=True))
            last = (c, segs[-1][1])
            dur = sum(y - x for x, y in segs)
            text = "".join(w["w"] for w in ws[i0:i1 + 1]).strip()
            pieces.append({"clip": c, "lang": sg.get("lang"), "in": segs[0][0], "out": segs[-1][1], "dur": round(dur, 4),
                           "text": text, "at_cut": round(t_cut, 3), "segments": segs, "edges": info, "why": sg.get("why")})
            wl = [[] for _ in segs]
            for w in ws[i0:i1 + 1]:
                k = next((k for k, (x, y) in enumerate(segs) if w["s"] < y), len(segs) - 1)
                wl[k].append(w)
            for k, (x, y) in enumerate(segs):
                edl.append({"block": b["id"], "clip": c, "lang": sg.get("lang"), "a": x, "b": y, "t0": round(t_cut, 4),
                            "t1": round(t_cut + y - x, 4), "join": "pause" if k else "cut",
                            "in_type": info["in"] if k == 0 else "pause", "out_type": info["out"] if k == len(segs) - 1 else "pause",
                            "words": [{"w": w["w"].strip(), "s": round(t_cut + max(0.0, w["s"] - x), 3),
                                       "e": round(t_cut + min(y - x, max(0.0, w["e"] - x)), 3)} for w in wl[k]]})
                rows.append([b["id"], b.get("role", ""), v.short(c), round(x, 3), round(y, 3), round(y - x, 3), fmt(t_cut),
                             text if k == 0 else "(continues)"])
                t_cut += y - x
        if pieces:
            resolved.append({"id": b["id"], "role": b.get("role", ""), "section": b.get("section", ""),
                             "start_in_cut": pieces[0]["at_cut"], "dur": round(sum(p["dur"] for p in pieces), 2),
                             "pieces": pieces, "note": b.get("note"), "check": b.get("check")})
    if errors:
        raise SystemExit("Script errors (fix edit/script.json):\n  " + "\n  ".join(errors))
    v.cut.mkdir(parents=True, exist_ok=True)
    save(v.cut / "edges_requested.json", requested, indent=None)
    save(v.work / "script_resolved.json", {"title": SCRIPT.get("title", ""), "duration_s": round(t_cut, 2),
                                           "fps_main": fps_main, "blocks": resolved})
    save(v.cut / "edl.json", {"fps_main": fps_main, "duration_s": round(t_cut, 4), "segments": edl})
    with open(v.cut / "cuts.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["block", "role", "clip", "in_s", "out_s", "dur_s", "in_the_cut", "text"])
        w.writerows(rows)
    print(f"Cut {fmt(t_cut)} · {len(edl)} segments · {len(resolved)} blocks"
          f"{' · local edges NOT used (first pass)' if not LOCAL else ''}")
    for g in resolved:
        hidden = sum(len(p["edges"].get("hidden", [])) for p in g["pieces"])
        print(f"  {g['id']} {fmt(g['start_in_cut']):>7} {g['dur']:6.1f}s  {g['role']:<12} {g['section']}"
              f"{f'  · {hidden} hidden voice spot(s) to listen to' if hidden else ''}")


if __name__ == "__main__":
    main()
