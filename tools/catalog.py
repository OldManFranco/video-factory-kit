"""Stage 9 · videos/catalog.json: one line per published video (title, date, URL, stock clips used, CTA used).
Stock clips are not reused across videos unless the editor asks (rules D17): build_sheet / Claude check this list.
Usage:
  python tools/catalog.py add <video> [--url https://youtu.be/...]
  python tools/catalog.py used          the stock files already used (to avoid repeating them)"""
import sys
from datetime import date

from vfk.kit import ROOT, Video, load, save

CAT = ROOT / "videos" / "catalog.json"
cat = load(CAT, {"videos": []})
if len(sys.argv) >= 2 and sys.argv[1] == "used":
    for x in cat["videos"]:
        for s in x.get("stock", []):
            print(f"{x['title'][:40]:<40}  {s}")
    raise SystemExit(0)
if len(sys.argv) < 3 or sys.argv[1] != "add":
    raise SystemExit(__doc__)
v = Video(sys.argv[2])
P = load(v.edit / "package.json", {})
S = load(v.work / "sheet_resolved.json", {})
stock = sorted({e.get("source_url") or e.get("file") for e in S.get("elements", [])
                if e["type"] in ("BROLL", "PHOTO", "WEB") and e.get("source") != "own" and (e.get("source_url") or e.get("file"))})
row = {"folder": v.name, "title": P.get("final_title", v.name), "date": date.today().isoformat(),
       "url": sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else "", "stock": stock,
       "cta": [e.get("text") for e in S.get("elements", []) if e["type"] == "LINK"]}
cat["videos"] = [x for x in cat["videos"] if x.get("folder") != v.name] + [row]
save(CAT, cat)
print(f"catalog: {row['title']} ({len(stock)} stock files)")
