"""Stage 1 · precise word times for every clip (rules H18).

faster-whisper's word times drift up to 0.5 s: cutting on them clipped word endings and let half-words of bad takes in.
Here the SAME text of work/transcripts/ is re-aligned to the audio with wav2vec2 (WhisperX align), segment by segment,
and saved with the same word list in work/aligned/ (so phrases in edit/script.json are found the same way).
Each word gets "aligned": true when wav2vec2 placed it; the others (rare) are interpolated between their neighbours
("aligned": false). Numbers are aligned as spoken words ('$3,750' → 'three thousand seven hundred fifty dollars').

Usage: py-audio tools/align.py <video> [clip ...]   (no clips: all clips with speech, skipping those already done)
"""
import re
import sys

import numpy as np

from vfk.asr import align, device
from vfk.kit import Video, load, save
from vfk.media import read_wav
from vfk.profile import load_profile
from vfk.words import spoken_word

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
LANG = load_profile().get("spoken_language", "en")
only = sys.argv[2:]
v.aligned.mkdir(parents=True, exist_ok=True)


def cap(w):
    letters = len(re.sub(r"[^\w]", "", w["w"]))
    return max(0.9, 0.11 * letters + 0.35)


def align_clip(c):
    x, _ = read_wav(v.audio16_of(c))
    j = load(v.transcripts / f"{c}.words.json")
    for sg in j["segments"]:
        ws = sg["words"]
        for w in ws:
            w["s_whisper"], w["e_whisper"], w["aligned"] = w["s"], w["e"], False
        # written words (tokens with no space in front stick to the previous one: '$210' + ',000.')
        groups = []
        for i, w in enumerate(ws):
            if not groups or w["w"][:1].isspace():
                groups.append([i])
            else:
                groups[-1].append(i)
        text, spans = [], []
        for g in groups:
            said = "".join(ws[i]["w"] for i in g).strip()
            said = (spoken_word(said) if LANG == "en" else said).split()
            spans.append((len(text), len(text) + len(said)))
            text += said
        a, b = max(0.0, sg["s"] - 0.6), min(len(x) / 16000, sg["e"] + 0.6)
        try:
            wa = align(" ".join(text), x[int(a * 16000):int(b * 16000)], a, LANG) if text else []
        except Exception as e:  # noqa: BLE001
            print(f"  [{v.short(c)}] segment {sg['s']:.1f}: not aligned ({e})")
            wa = []
        if len(wa) != len(text):
            if text:
                print(f"  [{v.short(c)}] segment {sg['s']:.1f}: {len(wa)} of {len(text)} words, keeping Whisper's times")
            wa = []
        for g, (r0, r1) in zip(groups, spans):
            ts = [w for w in wa[r0:r1] if w[1] is not None]
            if not ts:
                continue
            s0, e0 = ts[0][1], ts[-1][2]
            total = sum(len(ws[i]["w"].strip()) for i in g) or 1
            acc = 0
            for i in g:
                n = len(ws[i]["w"].strip())
                ws[i]["s"] = round(s0 + (e0 - s0) * acc / total, 3)
                acc += n
                ws[i]["e"] = round(s0 + (e0 - s0) * acc / total, 3)
                ws[i]["aligned"] = True
        # a word stretched over a long silence: Whisper is the second witness
        for w in ws:
            if w["aligned"] and w["e"] - w["s"] > cap(w):
                w["s"] = round(max(w["s"], w["s_whisper"] - 0.3), 3)
                w["e"] = round(min(w["e"], max(w["e_whisper"] + 0.3, w["s"] + 0.1)), 3)
                if w["e"] - w["s"] > cap(w):
                    w["e"] = round(w["s"] + cap(w), 3)
                w["aligned"] = "stretched"
        for i, w in enumerate(ws):
            if w["aligned"]:
                continue
            p = next((ws[q] for q in range(i - 1, -1, -1) if ws[q]["aligned"]), None)
            n = next((ws[q] for q in range(i + 1, len(ws)) if ws[q]["aligned"]), None)
            lo = p["e"] if p else min(w["s_whisper"], n["s"] if n else w["s_whisper"])
            hi = n["s"] if n else max(w["e_whisper"], lo + 0.2)
            w["s"], w["e"] = round(lo + 0.01, 3), round(max(lo + 0.05, hi - 0.01), 3)
    allw = [w for s in j["segments"] for w in s["words"]]
    # two words that overlap: the boundary goes to the quietest point between them
    hop = 160
    n = len(x) // hop
    e = 20 * np.log10(np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12))
    for p, q in zip(allw, allw[1:]):
        if p["e"] > q["s"]:
            lo, hi = int(min(p["e"], q["s"]) * 100), int(max(p["e"], q["s"]) * 100) + 1
            k = lo + int(np.argmin(e[lo:hi])) if hi > lo else lo
            t = round(k / 100 + 0.005, 3)
            p["e"], q["s"] = max(p["s"] + 0.03, t), min(q["e"] - 0.03, t)
    save(v.aligned / f"{c}.words.json", j, indent=None)
    print(f"{v.short(c)}: {sum(w['aligned'] is True for w in allw)}/{len(allw)} aligned · "
          f"{sum(w['aligned'] == 'stretched' for w in allw)} stretched", flush=True)


info = v.footage_info()
todo = [c for c in v.clips() if info.get(c, {}).get("words", 0) > 0 and (v.transcripts / f"{c}.words.json").exists()]
if only:
    todo = [c for c in todo if any(o in c for o in only)]
else:
    todo = [c for c in todo if not (v.aligned / f"{c}.words.json").exists()]
print(f"{len(todo)} clips to align on {device()[0]}", flush=True)
for c in todo:
    align_clip(c)
