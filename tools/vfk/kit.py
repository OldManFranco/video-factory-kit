"""Kit root, video folder layout, clip lookup and small helpers used by every tool.

A video folder (docs/SOP.md §0):
  footage/  host_script/  edit/  work/  render/final/  publish/  + gate pages, audio_flags.md, people_pending.md, STATUS.md
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".mts", ".m4v", ".avi"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def fmt(t):
    """Seconds → m:ss.s"""
    t = max(0.0, float(t))
    return f"{int(t // 60)}:{t % 60:04.1f}"


def parse_time(x):
    """'289.7' or '4:49.7' → seconds"""
    x = str(x)
    if ":" in x:
        m, s = x.split(":", 1)
        return float(m) * 60 + float(s)
    return float(x)


def load(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save(path, data, indent=1):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent), encoding="utf-8")
    tmp.replace(p)


def rel(p):
    """Path relative to the kit root when possible (works across drives on Windows)."""
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


class Video:
    """A video folder. `Video(sys.argv[1])` accepts 'videos/<name>', the bare name, or an absolute path."""

    def __init__(self, arg):
        p = Path(arg)
        cands = [p, ROOT / p, ROOT / "videos" / p]
        hit = next((c for c in cands if c.is_dir()), None)
        if hit is None:
            # a unique partial name inside videos/
            found = [d for d in (ROOT / "videos").iterdir() if d.is_dir() and str(arg).lower() in d.name.lower()]
            if len(found) != 1:
                raise SystemExit(f"Video folder not found: {arg}" + (f" (several match: {[d.name for d in found]})" if found else ""))
            hit = found[0]
        self.dir = hit.resolve()
        self.name = self.dir.name
        self.footage = self.dir / "footage"
        self.host_script = self.dir / "host_script"
        self.edit = self.dir / "edit"
        self.work = self.dir / "work"
        self.audio16 = self.work / "audio16"
        self.audio48 = self.work / "audio48"
        self.transcripts = self.work / "transcripts"
        self.aligned = self.work / "aligned"
        self.cut = self.work / "cut"
        self.graphics = self.work / "graphics"
        self.parts = self.work / "render_parts"
        self.qa = self.work / "qa"
        self.jobs = self.work / "jobs"
        self.final_dir = self.dir / "render" / "final"
        self.publish = self.dir / "publish"
        self._clips = None

    # --- clips
    def clips(self):
        """{clip_id: path}; clip_id = file name without extension."""
        if self._clips is None:
            files = sorted(f for f in self.footage.rglob("*") if f.is_file() and f.suffix.lower() in VIDEO_EXT)
            self._clips = {f.stem: f for f in files}
        return self._clips

    def clip_id(self, key):
        """Exact clip id, or a unique part of it ('0014' → 'DJI_20000604070801_0014_D')."""
        cs = self.clips()
        if key in cs:
            return key
        hits = [c for c in cs if key.lower() in c.lower()]
        if len(hits) == 1:
            return hits[0]
        raise SystemExit(f"Clip '{key}' " + ("not found in footage/" if not hits else f"is ambiguous: {hits[:5]}"))

    def clip_path(self, key):
        return self.clips()[self.clip_id(key)]

    def short(self, clip_id):
        """Shortest unique label for a clip (for pages and tables)."""
        cs = list(self.clips())
        for part in reversed(clip_id.replace("-", "_").split("_")):
            if part and sum(part in c for c in cs) == 1:
                return part
        return clip_id

    # --- files
    def audio16_of(self, clip_id):
        return self.audio16 / f"{clip_id}.wav"

    def audio48_of(self, clip_id):
        return self.audio48 / f"{clip_id}.wav"

    def footage_info(self):
        return load(self.work / "footage.json", {}).get("clips", {})

    def script_resolved(self):
        return load(self.work / "script_resolved.json")

    def edl(self):
        return load(self.cut / "edl.json")

    def gates(self):
        return load(self.edit / "gates.json", {})


def video_from_argv(usage):
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        raise SystemExit(usage)
    return Video(sys.argv[1])
