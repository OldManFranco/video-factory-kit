"""Cut edges and pauses from the AUDIO ENERGY (rules H18, H19).

Whisper stretches words over silences: its times only say where to look. Here the voice is measured:
energy every 10 ms (16 kHz audio of the clip), noise floor (10th percentile in ±1.5 s), and
"host voice" = energy > floor + 6 dB AND > the host's speaking level − 20 dB (crowd murmur doesn't count).
Word times come from wav2vec2 (work/aligned/), re-measured locally at each edge (local_edges.py).

  out-point: the REAL end of the last word (the voice is followed up to +0.3 s: soft consonants) + the natural silence
             up to 100 ms before the host's next sound, capped at AIR_OUT (rule H19, case a). With no silence: the
             lowest point between the end of the word and the next sound ("tight"), never inside a word.
  in-point:  the same backwards, up to AIR_IN of air, never before the host's previous sound.
  internal pauses longer than PAUSE_MAX become TAIL + AIR (silence kept on both sides).
  host voice with no written word inside a segment ("hidden"): a false start or filler Whisper didn't write → reported.
"""
import numpy as np

from .media import read_wav

HOP = 0.01
TH = 8.0
PAUSE_MAX, TAIL, AIR = 1.5, 0.6, 0.6       # internal pauses > 1.5 s become 0.6 + 0.6 s
AIR_IN, AIR_OUT = 0.30, 1.00               # defaults; a segment can ask for more (up to 3 s, rule H19 case b)
_cache = {}


class Audio:
    def __init__(self, path):
        a, sr = read_wav(path)
        hop = int(sr * HOP)
        n = len(a) // hop
        rms = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
        e = 20 * np.log10(rms)
        e = np.median(np.stack([np.roll(e, -1), e, np.roll(e, 1)]), 0)
        self.e = e
        self.dur = n * HOP
        blk = 50
        nb = max(1, n // blk)
        p10 = np.array([np.percentile(e[max(0, (k - 3) * blk):(k + 4) * blk], 10) for k in range(nb)])
        self.floor = np.interp(np.arange(n), np.arange(nb) * blk + blk / 2, p10)
        v = e > self.floor + TH
        v = self._close(v, 8, True)      # fill gaps < 80 ms (a plosive is not a pause)
        v = self._close(v, 4, False)     # drop voice islands < 40 ms
        self.voice = v
        self._hv = None

    @staticmethod
    def _close(v, nmin, gap_value):
        v = v.copy()
        target = not gap_value
        i, n = 0, len(v)
        while i < n:
            if v[i] == target:
                j = i
                while j < n and v[j] == target:
                    j += 1
                if j - i < nmin and i > 0 and j < n:
                    v[i:j] = not target
                i = j
            else:
                i += 1
        return v

    def db(self, t):
        k = min(max(int(t / HOP), 0), len(self.e) - 1)
        return float(self.e[k] - self.floor[k])


def audio(video, clip_id):
    key = (str(video.dir), clip_id)
    if key not in _cache:
        _cache[key] = Audio(video.audio16_of(clip_id))
    return _cache[key]


def host_voice(A, ws):
    """Frames with the host's voice (close to the mic): energy > floor + 6 dB AND > the host's level − 20 dB."""
    if A._hv is None:
        centres = [int((w["s"] + w["e"]) / 2 / HOP) for w in ws if w.get("aligned", True) and w["e"] > w["s"]]
        centres = [c for c in centres if c < len(A.e)]
        level = float(np.median(A.e[centres])) if centres else float(A.e.max() - 20)
        A.level = level
        A._hv = (A.e > A.floor + 6) & (A.e > level - 20)
    return A._hv


def is_voice(V, t):
    k = int(t / HOP)
    return 0 <= k < len(V) and bool(V[k])


def valley(A, t0, t1):
    """The quietest instant in [t0, t1]."""
    i0, i1 = max(0, int(t0 / HOP)), min(len(A.e), int(t1 / HOP) + 1)
    if i1 <= i0:
        return (t0 + t1) / 2
    return (i0 + int(np.argmin(A.e[i0:i1]))) * HOP + HOP / 2


def real_end(V, ws, i):
    """End of word i: wav2vec2 ends soft consonants (t/d/s/-tion) early, so follow the voice up to +0.30 s."""
    e = ws[i]["e"]
    cap = min(ws[i + 1]["s"] - 0.04 if i + 1 < len(ws) else e + 0.3, e + 0.30)
    t = e
    while t + HOP <= cap and is_voice(V, t):
        t += HOP
    return max(e, t)


def real_start(V, ws, i):
    s = ws[i]["s"]
    low = max(ws[i - 1]["e"] + 0.04 if i > 0 else s - 0.15, s - 0.15)
    t = s
    while t - HOP >= low and is_voice(V, t - HOP):
        t -= HOP
    return min(s, t)


def out_point(A, ws, i1, air=None):
    V = host_voice(A, ws)
    e2 = real_end(V, ws, i1)
    ns = ws[i1 + 1]["s"] if i1 + 1 < len(ws) else min(A.dur, e2 + 4)
    if i1 + 1 < len(ws):
        ns = min(ns, real_start(V, ws, i1 + 1))
    onset, t = ns, e2 + 0.05
    while t < ns:
        if is_voice(V, t):
            onset = t
            break
        t += HOP
    gap = onset - e2
    cap = AIR_OUT if air is None else air
    if gap >= 0.20:
        return e2 + min(max(gap - 0.10, gap * 0.5), cap), "pause", round(gap, 2), e2
    lo = ws[i1]["e"] - 0.02
    hi = min(ws[i1 + 1]["s"] if i1 + 1 < len(ws) else onset, max(onset, lo + 0.04)) + 0.02
    t = valley(A, lo, hi) if hi - lo > 0.03 else (lo + hi) / 2
    return t, "tight", round(gap, 2), t


def in_point(A, ws, i0, air=None):
    V = host_voice(A, ws)
    s2 = real_start(V, ws, i0)
    pe = real_end(V, ws, i0 - 1) if i0 > 0 else max(0.0, s2 - 4)
    off, t = pe, s2 - 0.05
    while t > pe:
        if is_voice(V, t):
            off = t + HOP
            break
        t -= HOP
    gap = s2 - off
    cap = AIR_IN if air is None else air
    if gap >= 0.20:
        return s2 - min(max(gap - 0.10, gap * 0.5), cap), "pause", round(gap, 2), s2
    lo = max(ws[i0 - 1]["e"] if i0 > 0 else off, min(off, ws[i0]["s"] - 0.04)) - 0.02
    hi = ws[i0]["s"] + 0.02
    t = valley(A, lo, hi) if hi - lo > 0.03 else (lo + hi) / 2
    return t, "tight", round(gap, 2), t


def to_frames(A, x, y, fps, fixed_in=False, fixed_out=False):
    """Make the segment a whole number of source frames (≤ half a frame) by moving the quieter edge.
    Audio and video then have the same length, sync is exact and the render cache survives later fixes.
    A hand-set edge only moves if the other one is hand-set too."""
    n = max(1, round((y - x) * fps))
    delta = n / fps - (y - x)
    if abs(delta) < 1e-6:
        return x, y

    def loud(t0, t1):
        i0, i1 = int(min(t0, t1) / HOP), int(max(t0, t1) / HOP) + 1
        seg = A.e[i0:i1] - A.floor[i0:i1]
        return float(seg.max()) if len(seg) else 0.0
    r_in = loud(x, x - delta) + (40 if fixed_in else 0)
    r_out = loud(y, y + delta) + (40 if fixed_out else 0)
    return (x - delta, y) if r_in < r_out else (x, y + delta)


def segment(A, ws, i0, i1, fps, cin=None, cout=None, air_in=None, air_out=None, pause_max=None):
    """Edges of one script segment (words i0..i1 of a clip) → ([(a, b), ...] pieces in clip time, info)."""
    V = host_voice(A, ws)
    pmax = PAUSE_MAX if pause_max is None else pause_max
    a, ta, xa, s_in = (cin, "manual", 0, cin) if cin is not None else in_point(A, ws, i0, air_in)
    b, tb, xb, e_out = (cout, "manual", 0, cout) if cout is not None else out_point(A, ws, i1, air_out)
    pieces, cur, hidden = [], a, []
    for k in range(i0, i1):
        g0, g1 = real_end(V, ws, k), real_start(V, ws, k + 1)
        if g1 - g0 < 0.15 or g0 < a + 0.05 or g1 > b - 0.05:
            continue
        t, run, mx = g0 + 0.06, 0, 0
        while t < g1 - 0.06:
            run = run + 1 if is_voice(V, t) else 0
            mx = max(mx, run)
            t += HOP
        if mx * HOP >= 0.15:
            hidden.append((round(g0, 2), round(g1, 2), round(mx * HOP, 2)))
        if g1 - g0 > pmax:
            pieces.append((cur, g0 + TAIL))
            cur = g1 - AIR
    pieces.append((cur, b))
    # the segment's outer edges are preferred fixed: internal pause edges absorb the rounding
    pieces = [to_frames(A, x, y, fps, fixed_in=(k == 0), fixed_out=(k == len(pieces) - 1))
              for k, (x, y) in enumerate(pieces)]
    return [(round(x, 5), round(y, 5)) for x, y in pieces], {
        "in": ta, "out": tb, "air_in": round(s_in - a, 2) if cin is None else None,
        "air_out": round(b - e_out, 2) if cout is None else None, "gap_in": xa, "gap_out": xb,
        "hidden": hidden, "db_in": round(A.db(a), 1), "db_out": round(A.db(b), 1)}
