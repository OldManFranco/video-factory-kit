"""First session · study the channel from its public YouTube page (yt-dlp, no login, public data only).

  1. the list of videos: title, length, upload date, views → work/channel_study/videos.json
  2. the 5 most viewed + the 5 most recent: description, chapters, auto-captions (as text) and thumbnail
     → work/channel_study/<id>.json / .txt / .jpg
  3. work/channel_study/summary.md: median views, titles above and below the median, typical length,
     links that repeat in the descriptions (to propose the links block).
Claude reads the summary, the captions and looks at the thumbnails, then writes section 3 of CHANNEL_PROFILE.md.

Usage: py-audio tools/channel_study.py <channel URL> [--top 5] [--recent 5]
"""
import json
import re
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

from vfk.kit import ROOT, save

if len(sys.argv) < 2:
    raise SystemExit(__doc__)
url = sys.argv[1].rstrip("/")
TOP = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 5
RECENT = int(sys.argv[sys.argv.index("--recent") + 1]) if "--recent" in sys.argv else 5
OUT = ROOT / "work" / "channel_study"
OUT.mkdir(parents=True, exist_ok=True)
YTDLP = [sys.executable, "-m", "yt_dlp"]


def ytdlp(*args, capture=True):
    r = subprocess.run([*YTDLP, "--no-warnings", *args], capture_output=capture, text=True, encoding="utf-8", errors="replace")
    if r.returncode and capture:
        print(r.stderr[-800:])
    return r


listing = url if re.search(r"/(videos|streams|shorts)$", url) else url + "/videos"
r = ytdlp("--flat-playlist", "-J", listing)
if r.returncode:
    raise SystemExit("Could not read the channel (private, wrong URL, or no internet). Continue with the interview questions.")
j = json.loads(r.stdout)
vids = [{"id": e["id"], "title": e.get("title"), "duration": e.get("duration"), "views": e.get("view_count"),
         "url": e.get("url") or f"https://www.youtube.com/watch?v={e['id']}"} for e in j.get("entries", []) if e.get("id")]
save(OUT / "videos.json", {"channel": j.get("channel") or j.get("uploader") or j.get("title"), "url": url, "videos": vids})
print(f"{len(vids)} videos on {j.get('channel') or j.get('title')}")
with_views = [x for x in vids if x["views"]]
top = sorted(with_views, key=lambda x: -x["views"])[:TOP]
recent = vids[:RECENT]
chosen = {x["id"]: x for x in top + recent}
links = Counter()
for vid in chosen.values():
    base = OUT / vid["id"]
    ytdlp("--skip-download", "--write-info-json", "--write-auto-subs", "--write-subs", "--sub-langs", "en.*,es.*,.*-orig",
          "--sub-format", "vtt", "--write-thumbnail", "--convert-thumbnails", "jpg", "-o", str(base) + ".%(ext)s", vid["url"])
    info = json.loads(Path(str(base) + ".info.json").read_text(encoding="utf-8")) if Path(str(base) + ".info.json").exists() else {}
    vtt = sorted(OUT.glob(f"{vid['id']}*.vtt"))
    text = []
    if vtt:
        seen = set()
        for line in vtt[0].read_text(encoding="utf-8", errors="replace").splitlines():
            line = re.sub(r"<[^>]+>", "", line).strip()
            if not line or "-->" in line or line.startswith(("WEBVTT", "Kind:", "Language:")) or line in seen:
                continue
            seen.add(line)
            text.append(line)
    (OUT / f"{vid['id']}.txt").write_text(" ".join(text), encoding="utf-8")
    keep = {k: info.get(k) for k in ("title", "duration", "view_count", "like_count", "upload_date", "description", "chapters", "tags")}
    save(OUT / f"{vid['id']}.json", keep)
    for u in re.findall(r"https?://\S+", info.get("description") or ""):
        links[u.rstrip(").,")] += 1
    for f in Path(OUT).glob(f"{vid['id']}*.info.json"):
        f.unlink()
    print(f"  {vid['title'][:70]} · {vid.get('views') or '?'} views · captions {'yes' if text else 'no'}")
durs = [x["duration"] for x in vids if x["duration"]]
med = statistics.median([x["views"] for x in with_views]) if with_views else 0
L = [f"# Channel study · {j.get('channel') or j.get('title')}\n", f"- Videos: {len(vids)}",
     f"- Median views: {med:,.0f}" if with_views else "- Views: not available",
     f"- Typical length: {statistics.median(durs) / 60:.1f} min (shortest {min(durs) / 60:.1f}, longest {max(durs) / 60:.1f})" if durs else "",
     "", "## Above the median (title · views · length)"]
L += [f"- {x['title']} · {x['views']:,} · {(x['duration'] or 0) / 60:.0f} min" for x in sorted(with_views, key=lambda x: -x["views"]) if x["views"] > med][:25]
L += ["", "## Below the median"] + [f"- {x['title']} · {x['views']:,}" for x in sorted(with_views, key=lambda x: x["views"]) if x["views"] <= med][:15]
L += ["", "## Links that repeat in descriptions (proposed links block)"] + [f"- {u} ({n}×)" for u, n in links.most_common(12)]
L += ["", f"Studied in detail (captions + thumbnails in this folder): " + ", ".join(chosen)]
(OUT / "summary.md").write_text("\n".join(x for x in L if x is not None) + "\n", encoding="utf-8")
print("→ work/channel_study/summary.md")
