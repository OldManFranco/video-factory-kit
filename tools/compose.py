"""Stages 6–7 · the COMPLETE video in one MP4: the cut + every element of the sheet + the voice-only mix.

Picture: the cut's segments (work/cut/segments.json), converted to the output frame rate (rules H14: 23.976 → exactly 24
with fps=24; audio untouched). On top, each element of work/graphics/registry.json at its frame:
  - full-screen elements (MP4: BROLL, PHOTO, WEB, PEOPLE, END, G-*) cover the frame; the later one wins on overlap;
  - overlays (MOV with alpha: LOWER, LINK, NAME, SUB) go on top; never on top of a full-screen element;
  - PUNCH zooms the picture (112–115 %) for its line.
Rendered in parts of 60 s with a cache: a part is only redone if something inside it changed. Then the parts are joined
without re-encoding, the mix is added, and the QA runs.

Usage: py-render tools/compose.py <video> plan|parts|final|qa|all     ("all" is what render_all.py runs, detached)
Output: render/final/<FINAL TITLE>.mp4 (title from edit/package.json "final_title", else the script's title) + qa.json
"""
import hashlib
import json
import re
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import numpy as np

from vfk import cutreader
from vfk.kit import Video, fmt, load, save
from vfk.media import probe, tool, vcodec_args

if len(sys.argv) < 3:
    raise SystemExit(__doc__)
v = Video(sys.argv[1])
S = load(v.work / "sheet_resolved.json")
REG = load(v.work / "graphics" / "registry.json", {})
SEGJ = load(v.cut / "segments.json")
if not (S and SEGJ):
    raise SystemExit("Needs work/sheet_resolved.json, work/graphics/registry.json and work/cut/segments.json.")
G = v.work / "graphics"
FPS = Fraction(S["fps_out"])
FPS_S = str(FPS)
W, H = SEGJ["width"], SEGJ["height"]
PART = int(round(60 * FPS))
CUT_FRAMES = int(round(S["duration_cut_s"] * FPS))
MIX = v.work / "mix.wav"
PARTS = v.parts
VCODEC = vcodec_args("final", gop=int(round(float(FPS) * 2)))
COLOUR = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
LAYOUT_VERSION = 1      # bump when the way layers are composed changes (invalidates the cache)
BAD = '<>:"/\\|?*'


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(f"failed: {' '.join(map(str, cmd[:6]))}…\n{r.stderr[-3000:]}")
    return r


def final_path():
    pk = load(v.edit / "package.json", {})
    title = pk.get("final_title") or (v.script_resolved() or {}).get("title") or v.name
    name = "".join(c for c in title if c not in BAD and ord(c) >= 32).strip().rstrip(".")
    return v.final_dir / f"{name}.mp4"


# ---------------------------------------------------------------- plan
def make_plan():
    current = {e["id"]: e for e in S["elements"]}
    layers, notes = [], []
    for r in sorted((r for r in REG.values() if r["id"] in current), key=lambda x: x["t"]):
        f = next((a for a in r["files"] if a.endswith((".mp4", ".mov"))), None)
        if f is None:
            raise SystemExit(f"{r['id']}: no MP4/MOV in the registry (run render_graphics.py at full resolution)")
        f0 = int(round(r["t"] * FPS))
        layers.append({"id": r["id"], "type": r["type"], "tc": r["tc"], "file": f, "f0": f0, "f1": f0 + int(r["frames"]),
                       "src0": 0, "cover": not f.endswith(".mov")})
    missing = [i for i, e in current.items() if e["type"] != "PUNCH" and i not in REG]
    if missing:
        raise SystemExit(f"Not rendered yet: {missing}. Run render_graphics.py.")
    covers = [c for c in layers if c["cover"]]
    for a, b in zip(covers, covers[1:]):                     # full screen vs full screen: the later one wins
        if a["f1"] > b["f0"]:
            notes.append(f"{a['id']} cut {a['f1'] - b['f0']} frames: {b['id']} enters")
            a["f1"] = b["f0"]
    for o in [c for c in layers if not c["cover"]]:          # an overlay is never on top of a full screen
        for c in covers:
            lo, hi = max(o["f0"], c["f0"]), min(o["f1"], c["f1"])
            if lo >= hi:
                continue
            if c["f0"] <= o["f0"] and c["f1"] >= o["f1"]:
                notes.append(f"{o['id']} REMOVED: entirely under {c['id']}")
                o["f1"] = o["f0"]
            elif c["f0"] <= o["f0"]:
                notes.append(f"{o['id']} enters {c['f1'] - o['f0']} frames late: {c['id']} is on screen")
                o["src0"] += c["f1"] - o["f0"]
                o["f0"] = c["f1"]
            else:
                notes.append(f"{o['id']} leaves {o['f1'] - c['f0']} frames early: {c['id']} enters")
                o["f1"] = c["f0"]
    layers = [c for c in layers if c["f1"] > c["f0"]]
    punches = []
    for e in S["elements"]:
        if e["type"] == "PUNCH":
            f0 = int(round(e["t"] * FPS))
            punches.append({"id": e["id"], "f0": f0, "f1": f0 + int(round(e["dur"] * FPS)), "zoom": float(e.get("zoom", 1.13)),
                            "y": float(e.get("y", 0.35))})
    total = max([c["f1"] for c in layers] + [CUT_FRAMES])
    plan = {"fps": FPS_S, "width": W, "height": H, "total_frames": total, "duration_s": round(float(total / FPS), 3),
            "cut_frames": CUT_FRAMES, "layers": layers, "punches": punches, "notes": notes}
    save(v.work / "compose_plan.json", plan)
    return plan


# ---------------------------------------------------------------- one part
def signature(p0, p1, inside, punches):
    h = hashlib.sha1(json.dumps([LAYOUT_VERSION, VCODEC, p0, p1, FPS_S, SEGJ["segments"], punches]).encode())
    for c in inside:
        f = G / c["file"]
        h.update(json.dumps([c["id"], c["file"], c["f0"], c["f1"], c["src0"], f.stat().st_size, f.stat().st_mtime_ns]).encode())
    return h.hexdigest()[:16]


def frames_of(path):
    r = run([tool("ffprobe"), "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries",
             "stream=nb_read_packets", "-of", "csv=p=0", path])
    return int(r.stdout.strip() or 0)


def render_range(p0, p1, plan, out):
    n = p1 - p0
    inside = [c for c in plan["layers"] if c["f0"] < p1 and c["f1"] > p0]
    pun = [p for p in plan["punches"] if p["f0"] < p1 and p["f1"] > p0]
    stamp = out.with_suffix(".json")
    sig = signature(p0, p1, inside, pun)
    if out.exists() and stamp.exists() and load(stamp, {}).get("signature") == sig:
        return False
    cmd = [tool("ffmpeg"), "-v", "error", "-nostats", "-y"]
    chains = []
    in_cut = min(p1, CUT_FRAMES) - p0
    if in_cut > 0:
        args, skip = cutreader.input_args(v, float(p0 / FPS), float(n / FPS))
        cmd += args
        ch = f"[0:v]{cutreader.skip_filter(skip)},fps={FPS_S},trim=end_frame={in_cut},settb=1/{FPS_S},setpts=N"
        if in_cut < n:
            ch += f",tpad=stop_mode=add:stop={n - in_cut}:color=black"
        chains.append(ch + ",format=yuv420p[b0]")
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS_S}"]
        chains.append(f"[0:v]trim=end_frame={n},settb=1/{FPS_S},setpts=N,format=yuv420p[b0]")
    prev = "b0"
    for i, p in enumerate(pun):                                # punch-in: a zoomed copy on top, only during its frames
        a, b = max(p["f0"], p0) - p0, min(p["f1"], p1) - p0
        cw, chh = f"iw/{p['zoom']:.4f}", f"ih/{p['zoom']:.4f}"
        chains.append(f"[{prev}]split[pa{i}][pb{i}]")
        chains.append(f"[pb{i}]crop={cw}:{chh}:(iw-{cw})/2:(ih-{chh})*{p['y']:.3f},scale={W}:{H}:flags=lanczos[pz{i}]")
        chains.append(f"[pa{i}][pz{i}]overlay=0:0:enable='between(n,{a},{b - 1})'[pp{i}]")
        prev = f"pp{i}"
    for k, c in enumerate(inside, start=1):
        lo, hi = max(c["f0"], p0), min(c["f1"], p1)
        s0 = c["src0"] + (lo - c["f0"])
        cmd += ["-i", G / c["file"]]
        chains.append(f"[{k}:v]trim=start_frame={s0}:end_frame={s0 + hi - lo},settb=1/{FPS_S},setpts=N+{lo - p0}[e{k}]")
        chains.append(f"[{prev}][e{k}]overlay=0:0:eof_action=pass:repeatlast=0:format=yuv420[v{k}]")
        prev = f"v{k}"
    chains.append(f"[{prev}]format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(chains), "-map", "[v]", "-frames:v", n, "-an", *VCODEC, *COLOUR,
            "-r", FPS_S, "-video_track_timescale", str(FPS.numerator * (640 if FPS.denominator == 1 else 1)), out]
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    run(cmd)
    got = frames_of(out)
    if got != n:
        raise RuntimeError(f"{out.name}: {got} frames, expected {n}")
    save(stamp, {"signature": sig, "p0": p0, "p1": p1, "frames": n, "layers": [c["id"] for c in inside],
                 "seconds": round(time.time() - t0, 1)})
    return True


def all_parts(plan):
    total = plan["total_frames"]
    ranges = [(a, min(a + PART, total)) for a in range(0, total, PART)]
    for old in PARTS.glob("part_*.mp4"):                     # parts beyond the new length
        if int(old.stem.split("_")[1]) >= len(ranges):
            old.unlink()
            old.with_suffix(".json").unlink(missing_ok=True)
    for i, (a, b) in enumerate(ranges):
        t = time.time()
        done = render_range(a, b, plan, PARTS / f"part_{i:03d}.mp4")
        log(f"part {i + 1}/{len(ranges)} {fmt(a / FPS)}–{fmt(b / FPS)}", f"rendered in {time.time() - t:.0f} s" if done else "from cache")


def join(plan):
    parts = sorted(PARTS.glob("part_*.mp4"))
    expected = -(-plan["total_frames"] // PART)
    if len(parts) != expected:
        raise SystemExit(f"{len(parts)} parts, expected {expected}: run 'parts' first")
    if not MIX.exists():
        raise SystemExit("Missing work/mix.wav: run mix.py first.")
    lst = PARTS / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    out = final_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name("_joining.mp4")
    dur = plan["total_frames"] / FPS
    run([tool("ffmpeg"), "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", MIX, "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy", "-af", f"apad=whole_dur={float(dur):.4f}", "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-ac", "2",
         "-t", f"{float(dur):.4f}", "-movflags", "+faststart", tmp])
    for old in out.parent.glob("*.mp4"):                       # one final at a time (the title may have changed)
        if old != tmp and old != out:
            old.unlink()
    tmp.replace(out)
    log("FINAL", out.relative_to(v.dir).as_posix())
    return out


# ---------------------------------------------------------------- QA
def frame(path, k, rgba=False, size=(960, 540), from_cut=False):
    vf = [f"scale={size[0]}:{size[1]}:flags=area", "format=rgba" if rgba else "format=rgb24"]
    t = max(k - 0.25, 0) / float(FPS)
    if from_cut:
        args, skip = cutreader.input_args(v, t, 0.5)
        vf = [cutreader.skip_filter(skip), f"fps={FPS_S}"] + vf
    else:
        args = ["-ss", f"{t:.6f}", "-i", str(path)]
    r = subprocess.run([tool("ffmpeg"), "-v", "error", *args, "-frames:v", "1", "-vf", ",".join(vf), "-f", "rawvideo", "-"],
                       capture_output=True)
    ch = 4 if rgba else 3
    if len(r.stdout) < size[0] * size[1] * ch:
        raise RuntimeError(f"could not read frame {k} of {Path(path).name if path else 'the cut'}")
    return np.frombuffer(r.stdout[: size[0] * size[1] * ch], np.uint8).reshape(size[1], size[0], ch)


def psnr(a, b):
    m = np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2)
    return 99.0 if m == 0 else float(10 * np.log10(255 ** 2 / m))


def audio(path, start, dur, sr=16000):
    r = subprocess.run([tool("ffmpeg"), "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(path),
                        "-map", "0:a:0", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.float32)


def offset_ms(ref, other, sr=16000, max_ms=200):
    n = min(len(ref), len(other))
    a, b = ref[:n] - ref[:n].mean(), other[:n] - other[:n].mean()
    m = int(sr * max_ms / 1000)
    best = max(range(-m, m + 1), key=lambda L: float(np.dot(a[max(0, -L): n - max(0, L)], b[max(0, L): n - max(0, -L)])))
    return round(best * 1000 / sr, 2)


def qa(plan):
    import cv2
    from vfk.profile import load_profile
    out = final_path()
    prof = load_profile()
    Q = v.qa
    Q.mkdir(parents=True, exist_ok=True)
    chk = {}
    p = probe(out)
    chk["format"] = {"ok": abs(p["duration"] - plan["duration_s"]) < 0.1 and (p["width"], p["height"]) == (W, H)
                     and Fraction(p["fps"]) == FPS and p.get("acodec") == "aac",
                     "duration_s": p["duration"], "fps": p["fps"], "size": f"{p['width']}x{p['height']}", "gb": round(p["size_bytes"] / 1e9, 2)}
    r = subprocess.run([tool("ffmpeg"), "-nostats", "-i", str(out), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    s = r[r.rfind("Summary:"):]
    lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", s).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", s).group(1))
    target = float(prof["output"]["loudness_lufs"])
    chk["loudness"] = {"ok": abs(lufs - target) <= 0.7 and tp <= float(prof["output"]["true_peak_db"]) + 0.5, "lufs": lufs, "true_peak": tp}
    cut_s = CUT_FRAMES / float(FPS)
    pts = [min(5.0, cut_s / 4), cut_s / 2, max(0.0, cut_s - 8)]
    sync = [{"t": round(t, 1), "final_vs_mix_ms": offset_ms(audio(MIX, t, 6), audio(out, t, 6))} for t in pts]
    busy = lambda k: any(c["f0"] <= k < c["f1"] for c in plan["layers"]) or any(q["f0"] <= k < q["f1"] for q in plan["punches"])
    pics = []
    for k in [int(t * float(FPS)) for t in pts]:
        if busy(k) or k + 2 >= CUT_FRAMES:
            continue
        fin = frame(out, k)
        ps = max(psnr(fin, frame(None, kk, from_cut=True)) for kk in (k - 1, k, k + 1))
        pics.append({"frame": k, "psnr_vs_cut": round(ps, 1), "ok": ps >= 30})
    chk["sync"] = {"ok": all(abs(x["final_vs_mix_ms"]) <= 1 for x in sync) and all(x["ok"] for x in pics), "audio": sync, "picture": pics}
    rows = []
    for c in plan["layers"]:
        k = (c["f0"] + c["f1"]) // 2
        src = c["src0"] + (k - c["f0"])
        fin = frame(out, k)
        if c["cover"]:
            val = psnr(fin, frame(G / c["file"], src))
            ok, det = val >= 28, {"psnr": round(val, 1)}
        else:
            el = frame(G / c["file"], src, rgba=True)
            full = el[..., 3] > 240
            diff = float(np.abs(fin[full].astype(np.float32) - el[..., :3][full]).mean()) if full.any() else 99
            ok, det = full.sum() > 100 and diff < 12, {"text_px": int(full.sum()), "diff": round(diff, 1)}
        rows.append({"id": c["id"], "type": c["type"], "tc": c["tc"], "frame": k, "ok": ok, **det, "_img": fin})
    chk["elements"] = {"ok": all(r_["ok"] for r_ in rows), "checked": len(rows), "failed": [r_["id"] for r_ in rows if not r_["ok"]],
                       "detail": [{k: x for k, x in r_.items() if k != "_img"} for r_ in rows]}
    tw, th = 480, 270
    rows.sort(key=lambda r_: r_["frame"])
    cols = 4
    sheet = np.full((max(1, -(-len(rows) // cols)) * (th + 36), cols * tw, 3), 24, np.uint8)
    for j, r_ in enumerate(rows):
        y, x = (j // cols) * (th + 36), (j % cols) * tw
        sheet[y + 36: y + 36 + th, x: x + tw] = cv2.resize(r_["_img"], (tw, th), interpolation=cv2.INTER_AREA)
        cv2.putText(sheet, f"{r_['id']} {r_['tc']} {r_['type']}", (x + 6, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (90, 230, 90) if r_["ok"] else (255, 70, 70), 2, cv2.LINE_AA)
    cv2.imwrite(str(Q / "final_sheet.jpg"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    r = subprocess.run([tool("ffmpeg"), "-v", "info", "-nostats", "-i", str(out), "-map", "0:v:0",
                        "-vf", "scale=480:270,blackdetect=d=0:pix_th=0.05", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)
    errs = [l for l in r.stderr.splitlines() if re.search(r"error|corrupt|invalid", l, re.I)]
    chk["decodes"] = {"ok": r.returncode == 0 and not errs, "errors": errs[:20]}
    chk["no_black"] = {"ok": not blacks, "ranges": blacks}
    res = {"file": out.name, "ok": all(c["ok"] for c in chk.values()), "checks": chk, "notes": plan["notes"]}
    save(v.final_dir / "qa.json", res)
    log("QA", "OK" if res["ok"] else "FAILS", {k: c["ok"] for k, c in chk.items()})
    return res


def main():
    what = sys.argv[2]
    plan = make_plan()
    if what == "plan":
        print(f"{len(plan['layers'])} layers ({sum(c['cover'] for c in plan['layers'])} full screen) · {len(plan['punches'])} punch-ins · "
              f"{plan['total_frames']} frames = {fmt(plan['duration_s'])} @ {float(FPS):g} fps · {W}x{H}")
        for n_ in plan["notes"]:
            print("  ", n_)
    elif what == "parts":
        all_parts(plan)
    elif what == "final":
        join(plan)
    elif what == "qa":
        qa(plan)
    elif what == "all":
        log("START", plan["total_frames"], "frames")
        all_parts(plan)
        join(plan)
        res = qa(plan)
        log("END", "QA OK" if res["ok"] else "QA FAILS")
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
