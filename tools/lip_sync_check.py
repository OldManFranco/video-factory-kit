"""Voice–picture sync of the final video, looking at the host's mouth.

At 3 points (start, middle, end) it picks a word starting with p/b/m (the lips close before the sound) after a pause,
with nothing covering the host. It takes 18 frames around the word, crops the mouth (MediaPipe FaceLandmarker:
inner-lip opening / mouth width) and draws the voice energy of the SAME file under each frame. In sync, the mouth is
closed just before the energy rises and opens with it. A lag of ±1 frame is normal for cameras.
Output: work/qa/lip_sync.jpg + lip_sync.json (with the estimated lag in frames).
Usage: py-render tools/lip_sync_check.py <video>"""
import subprocess
import sys
from fractions import Fraction

import cv2
import numpy as np

from vfk.kit import ROOT, Video, fmt, load, save
from vfk.media import probe, tool

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
mp4 = sorted(v.final_dir.glob("*.mp4"))[-1]
info = probe(mp4)
FPS = float(Fraction(info["fps"]))
PLAN = load(v.work / "compose_plan.json")
WORDS = load(v.cut / "words.json")["words"]
N = 18
FW, FH = 1280, int(round(1280 * info["height"] / info["width"] / 2) * 2)


USED = set()


def pick(t_target):
    busy = lambda a, b: any(c["cover"] and c["f0"] <= b and c["f1"] >= a for c in PLAN["layers"]) or \
        any(p["f0"] <= b and p["f1"] >= a for p in PLAN["punches"])
    cands = []
    for i in range(1, len(WORDS)):
        w, prev = WORDS[i], WORDS[i - 1]
        if w["s"] - prev["e"] < 0.2 or w.get("lang") or i in USED:
            continue
        k = round(w["s"] * FPS)
        if not busy(k - N, k + N):
            # p/b/m words first (the lips close before the sound), then any word after a pause
            cands.append((w["w"].strip()[:1].lower() not in "pbm", abs(w["s"] - t_target), i, w))
    if not cands:
        return None
    best = min(cands, key=lambda x: x[:2])
    USED.add(best[2])
    return best[3]


def frames(k0):
    r = subprocess.run([tool("ffmpeg"), "-v", "error", "-ss", f"{(k0 - 0.25) / FPS:.6f}", "-i", str(mp4), "-frames:v", str(N),
                        "-vf", f"scale={FW}:{FH},format=rgb24", "-f", "rawvideo", "-"], capture_output=True)
    return np.frombuffer(r.stdout, np.uint8).reshape(-1, FH, FW, 3)


def energy(k0):
    r = subprocess.run([tool("ffmpeg"), "-v", "error", "-ss", f"{k0 / FPS:.4f}", "-t", f"{N / FPS:.4f}", "-i", str(mp4),
                        "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.float32)
    hop = int(48000 / FPS)
    return [20 * np.log10(float(np.sqrt(np.mean(a[j * hop:(j + 1) * hop] ** 2) + 1e-12))) for j in range(N)]


import mediapipe as mp  # noqa: E402
from mediapipe.tasks.python import BaseOptions, vision  # noqa: E402
lm = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=str(ROOT / "assets" / "models" / "face_landmarker.task")),
    running_mode=vision.RunningMode.IMAGE, num_faces=1))
cut_s = PLAN["cut_frames"] / FPS
rows, out = [], []
for t in (min(10.0, cut_s * 0.2), cut_s / 2, max(0.0, cut_s - 15)):
    w = pick(t)
    if not w:
        continue
    k0 = round(w["s"] * FPS) - N // 2
    fr = frames(k0)
    if len(fr) < N:
        continue
    opening, boxes = [], []
    for j in range(N):
        r = lm.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(fr[j])))
        if not r.face_landmarks:
            opening.append(None)
            continue
        p = np.array([[q.x * FW, q.y * FH] for q in r.face_landmarks[0]])
        opening.append(float(np.linalg.norm(p[13] - p[14]) / np.linalg.norm(p[61] - p[291])))
        boxes.append(p[[61, 291, 0, 17]])
    if not boxes:
        continue
    db = energy(k0)
    c = np.array(boxes).reshape(-1, 2)
    cx, cy, wd = c[:, 0].mean(), c[:, 1].mean(), (c[:, 0].max() - c[:, 0].min()) * 1.6
    bx0, bx1, by0, by1 = int(cx - wd / 2), int(cx + wd / 2), int(cy - wd * 0.35), int(cy + wd * 0.35)
    # lag: frame where the mouth starts opening vs frame where the voice rises
    op = [o if o is not None else 0 for o in opening]
    mouth_k = next((j for j in range(1, N) if op[j] - min(op[:j + 1]) > 0.08), None)
    voice_k = next((j for j in range(1, N) if db[j] - min(db[:j + 1]) > 10), None)
    # only when the voice clearly stands out from the background: in street noise the guess is unreliable (look at the image)
    lag = (voice_k - mouth_k) if mouth_k is not None and voice_k is not None and max(db) - min(db) > 15 else None
    strips = []
    for j in range(N):
        crop = cv2.resize(fr[j, max(0, by0):by1, max(0, bx0):bx1], (160, 112))
        bar = np.full((48, 160, 3), 25, np.uint8)
        h = int(np.clip((db[j] + 60) / 50, 0, 1) * 44)
        cv2.rectangle(bar, (16, 46 - h), (144, 46), (90, 220, 90), -1)
        lab = np.full((24, 160, 3), 25, np.uint8)
        cv2.putText(lab, f"{k0 + j}{' <word' if k0 + j == round(w['s'] * FPS) else ''}", (5, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (230, 230, 230), 1, cv2.LINE_AA)
        strips.append(np.vstack([lab, crop, bar]))
    title = np.full((30, 160 * 9, 3), 10, np.uint8)
    cv2.putText(title, f"{fmt(w['s'])}  \"{w['w'].strip()}\"  lag estimate {lag if lag is not None else '?'}", (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 200, 80), 2, cv2.LINE_AA)
    rows += [title, np.hstack(strips[:9]), np.hstack(strips[9:])]
    out.append({"t": round(w["s"], 2), "word": w["w"].strip(), "lag_frames": lag, "mouth_opening": [None if o is None else round(o, 3) for o in opening],
                "energy_db": [round(d, 1) for d in db]})
v.qa.mkdir(parents=True, exist_ok=True)
if rows:
    cv2.imwrite(str(v.qa / "lip_sync.jpg"), cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
# no automatic verdict: the lag estimate is only a hint (noise fools it). Claude looks at the image: in sync, the lips
# are closed just before the voice bar rises and open with it.
ok = None
save(v.qa / "lip_sync.json", {"ok": ok, "points": out})
for o in out:
    print(f"{fmt(o['t'])} «{o['word']}» lag estimate {o['lag_frames']} frame(s)")
print(f"{len(out)} points → look at work/qa/lip_sync.jpg (the lag numbers are only a hint)")
