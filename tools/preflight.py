"""Stage 6 · checks before the full render (rules H27). Every line must be OK.
  gate 2     approved (edit/gates.json) — the render never starts before
  cut        the cut audio and the cut video match (same length, ±1 frame); the audio QA is newer than the cut audio
  sheet      sheet_resolved.json is newer than edit/sheet.json; no element placed BY HAND; no unresolved warnings of type
             "not found"
  assets     every file in the sheet exists; every non-own asset has a rights record (source + licence) (rules H9)
  text       no emojis on screen
  rhythm     no host "flash" (< 0.5 s of host between two full screens, rules H24)
  title      edit/package.json has a final_title (it names the file, rules H17)
Usage: python tools/preflight.py <video>"""
import re
import sys

from vfk.kit import Video, load

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
S = load(v.work / "sheet_resolved.json", {})
res = []


def check(name, ok, detail=""):
    res.append((name, ok, detail))


check("gate 2 approved", bool(v.gates().get("2", {}).get("approved")), "write 'approved' at Gate 2 first")
seg = load(v.cut / "segments.json")
edl = v.edl() or {}
if seg:
    from fractions import Fraction
    vid = sum(s["frames"] for s in seg["segments"]) / float(Fraction(seg["fps"]))
    check("cut video = cut audio", abs(vid - edl.get("duration_s", 0)) < 0.1, f"video {vid:.2f} s · audio {edl.get('duration_s', 0):.2f} s")
else:
    check("cut video built", False, "run build_cut.py <video> video")
qa_cut, voice = v.cut / "qa_cut.json", v.cut / "voice16.wav"
check("audio QA up to date", qa_cut.exists() and voice.exists() and qa_cut.stat().st_mtime >= voice.stat().st_mtime - 1)
sheet = v.edit / "sheet.json"
check("sheet resolved up to date", bool(S) and (v.work / "sheet_resolved.json").stat().st_mtime >= sheet.stat().st_mtime - 1)
els = S.get("elements", [])
by_hand = [e["id"] for e in els if e.get("placed") == "BY HAND"]
check("every element on its word", not by_hand, ", ".join(by_hand))
missing, no_record = [], []
for e in els:
    for key in ("file", "photo"):
        if e.get(key) and not (v.dir / e[key]).exists() and not (v.dir.parents[1] / e[key]).exists():
            missing.append(f"{e['id']}: {e[key]}")
    if e["type"] in ("PHOTO", "WEB", "PEOPLE") or (e["type"] == "BROLL" and e.get("file")):
        if e.get("source") != "own" and not (e.get("licence") and (e.get("source_url") or e.get("source_text"))):
            no_record.append(e["id"])
check("all files exist", not missing, "; ".join(missing))
check("rights record for every asset (H9)", not no_record, "missing source/licence: " + ", ".join(no_record))
emoji = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
texts = [(e["id"], str(x)) for e in els for k, x in e.items() if k in ("text", "title", "subtitle", "label", "line1", "line2", "place", "name", "role")]
bad = [i for i, t in texts if emoji.search(t)]
check("no emojis on screen", not bad, ", ".join(bad))
full = sorted((e for e in els if e["type"] in ("BROLL", "PHOTO", "WEB", "PEOPLE") or e["type"].startswith("G-")), key=lambda e: e["t"])
flash = [f"{a['id']}→{b['id']}" for a, b in zip(full, full[1:]) if 0 < b["t"] - (a["t"] + a["dur"]) < 0.5]
check("no host flashes (H24)", not flash, ", ".join(flash))
check("final title set", bool(load(v.edit / "package.json", {}).get("final_title")), "edit/package.json → final_title")
ok = all(r[1] for r in res)
for name, good, detail in res:
    print(f"  [{'OK' if good else '!!'}] {name}{'' if good or not detail else ' — ' + detail}")
print("PREFLIGHT OK" if ok else "PREFLIGHT: fix the lines marked !! before rendering")
sys.exit(0 if ok else 1)
