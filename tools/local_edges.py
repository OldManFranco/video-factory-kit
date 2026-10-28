"""Stage 3 · exact times ONLY at the edges of each segment (rules H18).

Aligning a whole clip sometimes slips up to 1 s or squashes words ('things' in 30 ms). In a short window (±2 s),
Whisper large-v3 + wav2vec2 give the exact time. build_script.py writes work/cut/edges_requested.json (the words at each
edge); here one window per edge is transcribed, those words are located, and work/cut/local_edges.json
{clip: {word_index: [start, end]}} is saved. build_script.py uses it on its next pass.

Usage: py-audio tools/local_edges.py <video>
"""
import sys

from vfk.asr import align, transcribe
from vfk.kit import Video, load, save
from vfk.media import read_wav
from vfk.profile import load_profile, whisper_prompt
from vfk.words import norm_spoken, spoken_text

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
prof = load_profile()
LANG = prof.get("spoken_language", "en")
HINT = whisper_prompt(prof, v)
_aud = {}


def audio(c):
    if c not in _aud:
        _aud[c] = read_wav(v.audio16_of(c))[0]
    return _aud[c]


def window(c, a, b, lang, hint=HINT):
    x = audio(c)
    a, b = max(0.0, a), min(len(x) / 16000, b)
    chunk = x[int(a * 16000):int(b * 16000)]
    text = spoken_text(" ".join(s.text.strip() for s in transcribe(chunk, language=lang, prompt=hint, words=False)).strip(), lang)
    if not text:
        return []
    # one piece for the whole window: Whisper's own segment limits (off by up to 0.9 s) misled the aligner
    return [(norm_spoken(w), s, e) for w, s, e in align(text, chunk, a, lang) if s is not None and norm_spoken(w)]


def locate(local, words, t_ref):
    """words: [(index, text, global_start)] in a row. Compared LETTER by letter (the window may write 'short-term' as one
    word or 'overtime' as two): the glued text is searched and each word takes the time of its letters."""
    L, owner = "", []
    for k, (n, s, e) in enumerate(local):
        L += n
        owner += [k] * len(n)
    groups = []
    for p in words:   # '$5' + ',300' / 'short' + '-term': tokens starting with , . - follow the previous word
        if groups and p[1][:1] in ",.-":
            groups[-1] = (groups[-1][0] + [p[0]], groups[-1][1] + p[1])
        else:
            groups.append(([p[0]], p[1]))
    target = [norm_spoken(g[1]) for g in groups]
    T = "".join(target)
    if len(T) < 4:
        return {}
    pos, best = L.find(T), None
    while pos != -1:
        d = abs(local[owner[pos]][1] - t_ref)
        if best is None or d < best[0]:
            best = (d, pos)
        pos = L.find(T, pos + 1)
    if best is None or best[0] > 3.0:
        return {}

    def t_char(c, end):
        k = owner[c]
        n, s, e = local[k]
        c0 = c - sum(len(local[q][0]) for q in range(k))
        return s + (e - s) * (c0 + (1 if end else 0)) / max(1, len(n))
    out, c = {}, best[1]
    for (idxs, _), o in zip(groups, target):
        if o:
            for idx in idxs:
                out[idx] = (round(t_char(c, False), 3), round(t_char(c + len(o) - 1, True), 3))
        c += len(o)
    return out


req = load(v.cut / "edges_requested.json")
if req is None:
    raise SystemExit("Run build_script.py --no-local first (it writes the list of edges).")
out = {}
for r in req:
    c, lang = r["clip"], r.get("lang") or LANG
    o = out.setdefault(c if not r.get("lang") else f"{c}.{r['lang']}", {})
    for side, grp in (("in", r["in"]), ("out", r["out"])):
        if not grp:
            continue
        a, b = grp[0][2] - 2.0, grp[-1][2] + 2.0
        loc = window(c, a, b, lang)
        hits = locate(loc, grp, grp[0][2])
        if len(hits) < len(grp):   # try without the outside word (it may be inaudible: a false start, a bad take)
            sub = grp[1:] if side == "in" else grp[:-1]
            h2 = locate(loc, sub, sub[0][2]) if sub else {}
            if len(h2) > len(hits) - (1 if hits else 0):
                hits = {**hits, **h2}
        if not hits:   # the filler hint sometimes makes Whisper skip the phrase: once more with no hint
            loc = window(c, a, b, lang, None)
            hits = locate(loc, grp, grp[0][2])
            if len(hits) < len(grp):
                sub = grp[1:] if side == "in" else grp[:-1]
                hits = {**(locate(loc, sub, sub[0][2]) if sub else {}), **hits}
        for i, (s, e) in hits.items():
            o[str(i)] = [s, e]
        print(f"{v.short(c)} {side} «{' '.join(g[1] for g in grp)}»: {len(hits)}/{len(grp)}"
              + ("" if hits else f" · heard [{a:.1f}-{b:.1f}]: " + " ".join(f"{n}@{s:.1f}" for n, s, _ in loc)), flush=True)
save(v.cut / "local_edges.json", out, indent=None)
print(f"{sum(len(x) for x in out.values())} words with a local time → work/cut/local_edges.json")
