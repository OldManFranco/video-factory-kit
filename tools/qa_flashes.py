"""No host "flashes" (rules H24).
  sheet          before the render: between two full-screen elements, no gap of host shorter than 0.5 s.
  mp4 [file]     after the render: finds shot changes (ffmpeg scene detection) and lists shots of 3 frames or less.
Usage: py-render tools/qa_flashes.py <video> sheet|mp4 [file.mp4]"""
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from vfk.kit import Video, fmt, load, save
from vfk.media import probe, tool

if len(sys.argv) < 3:
    raise SystemExit(__doc__)
v = Video(sys.argv[1])
if sys.argv[2] == "sheet":
    S = load(v.work / "sheet_resolved.json")
    full = sorted((e for e in S["elements"] if e["type"] in ("BROLL", "PHOTO", "WEB", "PEOPLE") or e["type"].startswith("G-")),
                  key=lambda e: e["t"])
    bad = [(a, b, b["t"] - a["t"] - a["dur"]) for a, b in zip(full, full[1:]) if 0 < b["t"] - a["t"] - a["dur"] < 0.5]
    for a, b, g in bad:
        print(f"FLASH {fmt(a['t'] + a['dur'])}: {g:.2f} s of host between {a['id']} and {b['id']} → stretch {a['id']} to {b['id']}")
    print("OK: no flashes in the sheet" if not bad else f"{len(bad)} flashes")
    sys.exit(1 if bad else 0)
mp4 = Path(sys.argv[3]) if len(sys.argv) > 3 else sorted(v.final_dir.glob("*.mp4"))[-1]
fps = float(Fraction(probe(mp4)["fps"]))
r = subprocess.run([tool("ffmpeg"), "-nostats", "-i", str(mp4), "-vf", "scale=320:180,select='gt(scene,0.30)',showinfo",
                    "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace")
cuts = [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]
short = [(a, b) for a, b in zip(cuts, cuts[1:]) if round((b - a) * fps) <= 3]
res = {"file": mp4.name, "shot_changes": len(cuts), "flashes": [{"at": fmt(a), "frames": round((b - a) * fps)} for a, b in short]}
save(v.qa / "flashes.json", res)
for f in res["flashes"]:
    print(f"FLASH at {f['at']}: a shot of {f['frames']} frame(s)")
print(f"{len(cuts)} shot changes · {len(short)} flashes → work/qa/flashes.json")
