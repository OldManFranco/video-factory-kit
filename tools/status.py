"""Where a video stands, checked on disk, and what comes next. The first command of any session about a video.

Usage:
  python tools/status.py <video>                 status + next step
  python tools/status.py <video> approve <1|2|3> record that the editor wrote "approved" at that gate
  python tools/status.py <video> reopen <1|2|3>  a gate is open again (the editor asked for changes after approving)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vfk.kit import Video, load, now, save  # noqa: E402
from job import jobs  # noqa: E402


def newer(a, b):
    """a exists and is at least as new as b (or b doesn't exist)."""
    a, b = Path(a), Path(b)
    return a.exists() and (not b.exists() or a.stat().st_mtime >= b.stat().st_mtime - 1)


def check(v):
    clips = v.clips()
    fj = load(v.work / "footage.json", {}).get("clips", {})
    speech = [c for c, i in fj.items() if i.get("words", 0) > 0]
    sheet, script = v.edit / "sheet.json", v.edit / "script.json"
    finals = sorted(v.final_dir.glob("*.mp4")) if v.final_dir.exists() else []
    g = v.gates()
    steps = [
        ("Camera clips in footage/", bool(clips), "copy the camera clips into footage/"),
        ("0 · Footage check + transcripts", bool(clips) and all(c in fj for c in clips),
         "py-audio tools/footage_check.py V"),
        ("1 · Precise word times (wav2vec2)", bool(speech) and all((v.aligned / f"{c}.words.json").exists() for c in speech),
         "py-audio tools/align.py V"),
        ("2 · Script (edit/script.json)", script.exists(), "Claude writes edit/script.json (SOP Stage 2)"),
        ("3 · Edges re-measured locally", newer(v.cut / "local_edges.json", script), "py-audio tools/build_script.py V --no-local, then py-audio tools/local_edges.py V"),
        ("3 · Script resolved + edit list", newer(v.work / "script_resolved.json", script) and newer(v.work / "script_resolved.json", v.cut / "local_edges.json"),
         "py-audio tools/build_script.py V"),
        ("3 · Cut audio", newer(v.cut / "voice16.wav", v.cut / "edl.json"), "py-audio tools/build_cut.py V audio"),
        ("3 · Audio QA of the cut", newer(v.cut / "qa_cut.json", v.cut / "voice16.wav"), "py-audio tools/qa_cut.py V"),
        ("3 · audio_flags.md", newer(v.dir / "audio_flags.md", v.cut / "qa_cut.json"), "py-audio tools/audio_flags.py V"),
        ("3 · Gate 1 page", newer(v.dir / "gate1.html", v.dir / "audio_flags.md"), "python tools/gate1_page.py V"),
        ("GATE 1 approved", bool(g.get("1", {}).get("approved")), "show gate1.html and WAIT for 'approved'"),
        ("3 · Cut video", newer(v.cut / "video_list.txt", v.cut / "edl.json"), "py-audio tools/build_cut.py V video (detached job)"),
        ("4 · Edit sheet (edit/sheet.json)", sheet.exists(), "Claude writes edit/sheet.json (SOP Stage 4)"),
        ("4 · Sheet resolved", newer(v.work / "sheet_resolved.json", sheet), "py-audio tools/cut_words.py V, then py-render tools/build_sheet.py V"),
        ("5 · Storyboard", newer(v.dir / "storyboard.html", v.work / "sheet_resolved.json"), "py-render tools/render_graphics.py V --scale 0.25 --no-motion, then py-render tools/storyboard.py V"),
        ("GATE 2 approved", bool(g.get("2", {}).get("approved")), "show storyboard.html and WAIT for 'approved'"),
        ("6 · Final render", bool(finals) and newer(finals[-1], v.work / "sheet_resolved.json"),
         "py-render tools/preflight.py V, then python tools/job.py V render -- py-render tools/render_all.py V"),
        ("7 · QA + Gate 3 page", newer(v.dir / "gate3.html", finals[-1] if finals else v.dir / "_none_"),
         "py-audio tools/qa_cut.py V --final, py-render tools/qa_flashes.py V mp4, py-render tools/gate3_page.py V"),
        ("GATE 3 approved", bool(g.get("3", {}).get("approved")), "show gate3.html and WAIT for 'approved'"),
        ("8 · Publishing package", (v.publish / "copy_paste.html").exists(), "py-render tools/build_package.py V"),
    ]
    return steps


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    v = Video(sys.argv[1])
    if len(sys.argv) >= 4 and sys.argv[2] in ("approve", "reopen"):
        g = v.gates()
        n = sys.argv[3]
        if sys.argv[2] == "approve":
            g[n] = {"approved": now()}
        else:
            g[n] = {"approved": None, "reopened": now()}
        save(v.edit / "gates.json", g)
        print(f"Gate {n}: {'approved' if sys.argv[2] == 'approve' else 'open again'} ({now()})")
        return
    print(f"# {v.name}")
    nxt = None
    for label, ok, todo in check(v):
        print(f"  [{'x' if ok else ' '}] {label}")
        if not ok and nxt is None:
            nxt = (label, todo)
    js = jobs(v) if v.jobs.exists() else []
    if js:
        print("\nJobs:")
        for j in js[-5:]:
            print(f"  {j['id']}  {j['state']:<8} {j['last_line']}")
    running = [j for j in js if j["state"] in ("launched", "running")]
    print()
    if running:
        print(f"Running now: {', '.join(j['id'] for j in running)}. Wait for it (python tools/job.py V list).")
    if nxt:
        print(f"NEXT: {nxt[0]} → {nxt[1].replace(' V', ' \"videos/' + v.name + '\"')}")
    else:
        print("All done: the video is published-ready. After publishing: python tools/catalog.py add <video>")


if __name__ == "__main__":
    main()
