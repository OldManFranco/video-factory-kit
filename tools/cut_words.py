"""Stage 4 · every word of the cut with its start and end (wav2vec2 times, from work/cut/edl.json) → work/cut/words.json.
build_sheet.py and render_graphics.py anchor every element to these words.
Usage: python tools/cut_words.py <video>"""
import sys

from vfk.kit import Video, save

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
E = v.edl()
if not E:
    raise SystemExit("Missing work/cut/edl.json: run build_script.py first.")
words = [{"w": w["w"], "s": w["s"], "e": w.get("e", w["s"] + 0.3), "block": s["block"], "lang": s.get("lang")}
         for s in E["segments"] for w in s["words"] if w["w"]]
save(v.cut / "words.json", {"duration_s": E["duration_s"], "words": words}, indent=None)
print(f"{len(words)} words → work/cut/words.json")
