"""Read the cut straight from its cached segments (work/cut/segments/*.mkv) without a big intermediate MP4.

A slow disk can take longer to write one 8 GB MP4 than the whole render, and seeking inside a long concat list is slow.
Here a mini-list starts at the segment that contains the requested instant (every segment starts on a keyframe), and
the frames before the instant are dropped with trim. NEVER the concat demuxer's 'inpoint': it starts at the previous
keyframe and the picture drifted up to 2 s from the voice (docs/known_problems.md).

input_args(video, t0, dur) -> (ffmpeg input arguments, skip seconds); then prefix the filter chain with skip_filter(skip).
"""
import hashlib

from .kit import load

_cache = {}


def segments(video):
    key = str(video.dir)
    if key not in _cache:
        j = load(video.cut / "segments.json")
        if not j:
            raise SystemExit("Missing work/cut/segments.json: run build_cut.py <video> video first.")
        _cache[key] = [(video.cut / "segments" / s["file"], s["t0"], s["dur"]) for s in j["segments"]]
    return _cache[key]


def input_args(video, t0, dur):
    segs = segments(video)
    k = max([i for i, (_, a, _) in enumerate(segs) if a <= t0 + 1e-6] or [0])
    skip = max(0.0, t0 - segs[k][1])
    lines, covered = [], 0.0
    for i in range(k, len(segs)):
        f, a, d = segs[i]
        lines.append(f"file '{f.as_posix()}'")
        covered += d - (skip if i == k else 0.0)
        if covered >= dur + 0.5:
            break
    tmp = video.cut / "_lists"
    tmp.mkdir(exist_ok=True)
    txt = "\n".join(lines) + "\n"
    path = tmp / (hashlib.sha1(txt.encode()).hexdigest()[:12] + ".txt")
    if not path.exists():
        path.write_text(txt, encoding="utf-8")
    return ["-f", "concat", "-safe", "0", "-i", str(path)], skip


def skip_filter(skip):
    return f"trim=start={skip:.6f},setpts=PTS-STARTPTS"
