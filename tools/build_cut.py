"""Stage 3 · the cut, from work/cut/edl.json (written by build_script.py).

  audio: every segment sample-accurate from the clip's 48 kHz stereo WAV (work/audio48/), 10 ms fades
         → work/cut/voice48.wav and work/cut/voice16.wav (mono, for Whisper) + "<video> - cut (audio only).mp3"
  video: every segment at the source's frames (the main clips' frame rate, rules H14: the output frame rate is applied
         later by compose.py). It enters on the frame nearest the audio and lasts what the audio timeline says.
         Cached per segment (work/cut/segments/<fingerprint>.mkv): if one edge changes, only that segment is redone.
         Clips with another size or frame rate are scaled/converted to the main ones.
         → work/cut/video_list.txt (concat list read by the render; no big intermediate MP4 unless --mp4)
Usage: py-audio tools/build_cut.py <video> audio|video [--mp4]     (video is long: run it as a detached job)
"""
import hashlib
import sys
from collections import Counter
from fractions import Fraction

import numpy as np

from vfk.kit import Video, fmt, rel, save
from vfk.media import extract_audio, ffmpeg, read_wav, vcodec_args, write_wav

if len(sys.argv) < 3 or sys.argv[2] not in ("audio", "video"):
    raise SystemExit(__doc__)
v = Video(sys.argv[1])
EDL = v.edl()
if not EDL:
    raise SystemExit("Missing work/cut/edl.json: run build_script.py first.")
SR = 48000
SEG = v.cut / "segments"


def audio():
    cache, parts = {}, []
    for s in EDL["segments"]:
        n = round((s["t1"] - s["t0"]) * SR)
        c = s["clip"]
        if c not in cache:
            extract_audio(v.clips()[c], v.audio48_of(c), SR, 2)
            cache[c] = read_wav(v.audio48_of(c), mono=False)[0]
            if cache[c].ndim == 1:
                cache[c] = np.stack([cache[c], cache[c]], 1)
        i0 = round(s["a"] * SR)
        x = cache[c][i0:i0 + n].copy()
        if len(x) < n:
            x = np.pad(x, ((0, n - len(x)), (0, 0)))
        f = min(int(0.010 * SR), len(x) // 4)
        if f:
            x[:f] *= np.linspace(0, 1, f)[:, None]
            x[-f:] *= np.linspace(1, 0, f)[:, None]
        parts.append(x)
    x = np.concatenate(parts)
    write_wav(v.cut / "voice48.wav", x, SR)
    write_wav(v.cut / "voice16.wav", x.mean(1)[::3], 16000)
    mp3 = v.dir / f"{v.name} - cut (audio only).mp3"
    ffmpeg("-y", "-i", v.cut / "voice48.wav", "-c:a", "libmp3lame", "-b:a", "160k", mp3)
    print(f"audio {fmt(len(x) / SR)} · {len(EDL['segments'])} segments → {rel(v.cut / 'voice48.wav')} + {mp3.name}", flush=True)


def video():
    SEG.mkdir(parents=True, exist_ok=True)
    info = v.footage_info()
    fps = Fraction(EDL["fps_main"])
    sizes = Counter((info[c]["width"], info[c]["height"]) for c in info if info[c].get("type") in ("A-ROLL", "MIXED", "INTERVIEW") and "width" in info[c])
    W, H = sizes.most_common(1)[0][0] if sizes else (1920, 1080)
    codec = vcodec_args("high", gop=int(round(float(fps) * 2)))
    listing, segs, index = [], EDL["segments"], []
    for k, s in enumerate(segs):
        f0, f1 = round(s["t0"] * fps), round(s["t1"] * fps)
        n = f1 - f0
        if n <= 0:
            continue
        ci = info.get(s["clip"], {})
        same = ci.get("fps") == EDL["fps_main"] and (ci.get("width"), ci.get("height")) == (W, H)
        fa = round(s["a"] * Fraction(ci.get("fps", EDL["fps_main"])))
        fp = hashlib.sha1(f"{s['clip']}|{fa}|{n}|{W}x{H}|{fps}|{codec}".encode()).hexdigest()[:12]
        dst = SEG / f"{fp}.mkv"
        listing.append(dst)
        index.append({"file": dst.name, "t0": float(f0 / fps), "dur": float(n / fps), "frames": n})
        if dst.exists():
            continue
        vf = [] if same else ["-vf", f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
                                     f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1"]
        tmp = dst.with_suffix(".tmp.mkv")
        ffmpeg("-y", "-ss", f"{s['a']:.4f}", "-i", v.clips()[s["clip"]], "-an", *vf, "-frames:v", n, *codec,
               "-r", str(fps), tmp)
        tmp.replace(dst)
        print(f"OK {k + 1:03d}/{len(segs)} {s['block']} {v.short(s['clip'])} {n} frames", flush=True)
    lst = v.cut / "video_list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in listing), encoding="utf-8")
    save(v.cut / "segments.json", {"fps": str(fps), "width": W, "height": H, "segments": index})
    print(f"video: {len(listing)} segments, {W}x{H} @ {float(fps):.3f} → {rel(lst)}", flush=True)
    if "--mp4" in sys.argv:
        out = v.cut / "cut.mp4"
        ffmpeg("-y", "-f", "concat", "-safe", "0", "-i", lst, "-i", v.cut / "voice48.wav", "-map", "0:v:0", "-map", "1:a:0",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out)
        print("MP4:", rel(out))


{"audio": audio, "video": video}[sys.argv[2]]()
