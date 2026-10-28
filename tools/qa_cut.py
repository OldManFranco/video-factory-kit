"""Stages 3 and 7 · audio QA: Whisper hears the WHOLE cut (or the final render) and it is compared word by word with
what the script says should be there (rules H20). A difference is an error to fix, not a "maybe".

1. DIFFERENCES: extra word (false start, half word, filler), missing word (cut off) or changed word (garble), with the
   time in the cut. Numbers written differently don't count.
2. CONFIDENCE: low-probability words within 1 s of a join.
3. AIR: silences between words over 1.5 s (rules H19: dead air) .
4. CUTS ON SOUND (measured in the ORIGINAL clip at every cut point):
   on_voice   the cut lands on the host's voice;
   voice_next host voice within 120 ms on the side that was removed (a word was nicked / glued);
   leftover   a short piece of voice (≤ 250 ms) stuck to the edge, separated by silence (half a word of a bad take).
Output: work/cut/qa_cut.json + qa_cut.md (with --final: work/cut/qa_final.json + qa_final.md).
The transcript of the cut is cached and reused while the audio doesn't change.

Usage: py-audio tools/qa_cut.py <video> [--final [file.mp4]]   (--final alone: the newest MP4 in render/final/)
"""
import difflib
import sys
from pathlib import Path

from vfk import edges
from vfk.asr import transcribe
from vfk.kit import Video, fmt, load, rel, save
from vfk.media import ffmpeg, read_wav
from vfk.profile import load_profile, whisper_prompt
from vfk.words import load_words, norm_spoken, tokens

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
prof = load_profile()
LANG = prof.get("spoken_language", "en")
EDL = v.edl()["segments"]
FINAL = "--final" in sys.argv
SMALL = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

src, cache, name = v.cut / "voice16.wav", v.cut / "qa_cut_heard.json", "qa_cut"
if FINAL:
    i = sys.argv.index("--final")
    mp4 = Path(sys.argv[i + 1]) if len(sys.argv) > i + 1 and not sys.argv[i + 1].startswith("--") else None
    if mp4 is None:
        finals = sorted(v.final_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not finals:
            raise SystemExit("No MP4 in render/final/.")
        mp4 = finals[-1]
    src, cache, name = v.cut / "final16.wav", v.cut / "qa_final_heard.json", "qa_final"
    ffmpeg("-y", "-i", mp4, "-vn", "-ac", 1, "-ar", 16000, "-c:a", "pcm_s16le", src)

# what must be heard: the words of the edit list (other-language segments are skipped: they are someone else's speech)
expected = [(t, w["s"]) for s in EDL if not s.get("lang") for w in s["words"] for t in tokens(w["w"])]
joins = [s["t0"] for s in EDL[1:]]
foreign = [(s["t0"], s["t1"]) for s in EDL if s.get("lang")]

stamp = src.stat().st_size
heard = None
c = load(cache)
if c and c.get("stamp") == stamp:
    heard = [tuple(o) for o in c["heard"]]
if heard is None:
    x, _ = read_wav(src)
    heard = []
    for sg in transcribe(x, language=LANG, prompt=whisper_prompt(prof, v)):
        for w in sg.words:
            if any(a - 0.3 <= w.start <= b + 0.3 for a, b in foreign):
                continue
            for t in tokens(w.word):
                heard.append((t, w.start, w.end, w.probability))
    save(cache, {"stamp": stamp, "heard": heard}, indent=None)
print(f"Whisper: {len(heard)} words heard · script: {len(expected)}", flush=True)


def same(a, b):
    if a == b:
        return True
    eq = {("gonna", "going"), ("wanna", "want"), ("ok", "okay"), ("alright", "all"), ("percent", "")}
    return (a, b) in eq or (b, a) in eq or (a.isdigit() and b in SMALL) or (b.isdigit() and a in SMALL)


sm = difflib.SequenceMatcher(a=[e[0] for e in expected], b=[o[0] for o in heard], autojunk=False)
diffs = []
for op, a0, a1, b0, b1 in sm.get_opcodes():
    if op == "equal":
        continue
    ea, ob = [e[0] for e in expected[a0:a1]], [o[0] for o in heard[b0:b1]]
    if len(ea) == len(ob) and all(same(p, q) for p, q in zip(ea, ob)):
        continue
    if "".join(ea).replace("000", "") == "".join(ob).replace("000", ""):   # '105000' / '105 000'
        continue
    if norm_spoken(" ".join(ea)) == norm_spoken(" ".join(ob)):           # '178' / 'a hundred and seventy eight'
        continue
    t = heard[b0][1] if b0 < len(heard) else (expected[a0][1] if a0 < len(expected) else 0)
    if b0 >= len(heard) and a0 < len(expected):
        t = expected[a0][1]
    near = min((abs(t - u) for u in joins), default=99)
    diffs.append({"t": round(t, 2), "at": fmt(t), "kind": {"replace": "changed", "delete": "missing", "insert": "extra"}[op],
                  "script": " ".join(ea), "heard": " ".join(ob), "at_join": bool(near < 1.2)})
low = [{"t": round(o[1], 2), "at": fmt(o[1]), "word": o[0], "p": round(o[3], 2)}
       for o in heard if o[3] < 0.45 and min((abs(o[1] - u) for u in joins), default=99) < 1.0]
air = [{"t": round(a[2], 2), "at": fmt(a[2]), "seconds": round(b[1] - a[2], 2), "before": a[0], "after": b[0]}
       for a, b in zip(heard, heard[1:]) if b[1] - a[2] > 1.5]

# cuts on sound, in the original clip at every cut point
sound = []
for k, s in enumerate(EDL):
    if s.get("lang"):
        continue
    f = v.aligned / f"{s['clip']}.words.json"
    if not f.exists():
        f = v.transcripts / f"{s['clip']}.words.json"
    if not f.exists() or not v.audio16_of(s["clip"]).exists():
        continue
    A = edges.audio(v, s["clip"])
    V = edges.host_voice(A, load_words(f))
    prev, nxt = (EDL[k - 1] if k else None), (EDL[k + 1] if k + 1 < len(EDL) else None)
    for side, t, away in (("in", s["a"], -1), ("out", s["b"], 1)):
        if (side == "in" and prev is None) or (side == "out" and nxt is None):
            continue
        # the next piece continues the same clip right there: not a cut
        if (side == "in" and prev["clip"] == s["clip"] and abs(prev["b"] - s["a"]) < 0.03) or \
           (side == "out" and nxt["clip"] == s["clip"] and abs(nxt["a"] - s["b"]) < 0.03):
            continue
        on = edges.is_voice(V, t)
        next_to = any(edges.is_voice(V, t + away * d / 100) for d in range(1, 13))
        inside, run, gap = -away, 0, 0
        for d in range(1, 40):
            if edges.is_voice(V, t + inside * d / 100):
                if gap:
                    break
                run += 1
            elif run:
                gap += 1
                if gap >= 8:
                    break
        leftover = 0 < run <= 25 and gap >= 8
        if on or next_to or leftover:
            tc = s["t0"] if side == "in" else s["t1"]
            sound.append({"t": round(tc, 2), "at": fmt(tc), "clip": s["clip"], "src": round(t, 2), "side": side,
                          "on_voice": bool(on), "voice_next": bool(next_to), "leftover_ms": run * 10 if leftover else 0})

res = {"cuts_on_sound": sound, "differences": diffs, "low_confidence": low, "air": air}
save(v.cut / f"{name}.json", res)
title = "final render (audio of the MP4)" if FINAL else "cut"
L = [f"# Audio QA · {title} · {len(diffs)} differences ({sum(d['at_join'] for d in diffs)} at joins) · "
     f"{len(sound)} cuts on sound · {len(low)} low-confidence · {len(air)} silences > 1.5 s\n",
     "## Differences (script → what Whisper hears)"]
L += [f"- {d['at']} · {d['kind']}{' · AT A JOIN' if d['at_join'] else ''} · script «{d['script']}» → heard «{d['heard']}»" for d in diffs]
L += ["\n## Cuts on sound (original clip)"] + [
    f"- {c_['at']} · {c_['side']} {v.short(c_['clip'])}@{c_['src']}s · "
    + ", ".join(x for x, ok in (("on voice", c_["on_voice"]), ("voice next to it", c_["voice_next"]),
                                (f"leftover {c_['leftover_ms']} ms", c_["leftover_ms"])) if ok) for c_ in sound]
L += ["\n## Air > 1.5 s"] + [f"- {a['at']} · {a['seconds']} s between «{a['before']}» and «{a['after']}»" for a in air]
L += ["\n## Low confidence near joins"] + [f"- {b['at']} «{b['word']}» p={b['p']}" for b in low]
(v.dir / f"{name}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"{len(diffs)} differences · {len(sound)} cuts on sound · {len(low)} low confidence · {len(air)} air > 1.5 s → {rel(v.dir / (name + '.md'))}")
