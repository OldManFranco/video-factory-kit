"""Create a video folder: videos/<YYYY-MM-DD> <name>/ with the standard layout (docs/SOP.md §0).
Usage: python tools/new_video.py "<short name>" [--date YYYY-MM-DD]"""
import sys
from datetime import date

from vfk.kit import ROOT, now, save

if len(sys.argv) < 2:
    raise SystemExit(__doc__)
name = sys.argv[1].strip()
d = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else date.today().isoformat()
bad = '<>:"/\\|?*'
folder = ROOT / "videos" / ("".join(c for c in f"{d} {name}" if c not in bad).strip())
if folder.exists():
    raise SystemExit(f"Already exists: {folder}")
for sub in ("footage", "host_script", "edit", "work", "render/final", "publish"):
    (folder / sub).mkdir(parents=True)
save(folder / "edit" / "gates.json", {})
(folder / "STATUS.md").write_text(
    f"# {name}\n\nCreated {now()}.\n\n## Where it stands\n- Waiting for the camera clips in `footage/` "
    f"(and the host's outline, if any, in `host_script/`).\n\n## Next\n- Stage 0: footage check.\n", encoding="utf-8")
print(f"Created: videos/{folder.name}")
print("Next: copy the camera clips into its footage/ folder, then: python tools/footage_check.py "
      f"\"videos/{folder.name}\"")
