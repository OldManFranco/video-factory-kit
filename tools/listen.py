"""Claude's "ear": Whisper large-v3 + wav2vec2 in a short window, with exact word times.

  py-audio tools/listen.py <video> cut <time> [<time> ...]       ±2.2 s around points of the cut (seconds or m:ss.s),
                                                                 plus the edit-list segments there
  py-audio tools/listen.py <video> clip <clip> <from> <to> [lang] a window of an original clip (clip seconds)
"""
import sys

from vfk.asr import align, transcribe
from vfk.kit import Video, fmt, parse_time
from vfk.media import read_wav
from vfk.profile import load_profile, whisper_prompt
from vfk.words import spoken_text

if len(sys.argv) < 4:
    raise SystemExit(__doc__)
v = Video(sys.argv[1])
prof = load_profile()
LANG = prof.get("spoken_language", "en")


def hear(x, a, b, lang):
    a, b = max(0.0, a), min(len(x) / 16000, b)
    chunk = x[int(a * 16000):int(b * 16000)]
    text = " ".join(s.text.strip() for s in transcribe(chunk, language=lang, prompt=whisper_prompt(prof, v), words=False)).strip()
    if not text:
        return "(nothing)"
    ws = align(spoken_text(text, lang), chunk, a, lang)
    return " ".join(f"{w}[{s:.2f}-{e:.2f}]" if s is not None else w for w, s, e in ws)


if sys.argv[2] == "cut":
    x, _ = read_wav(v.cut / "voice16.wav")
    E = v.edl()["segments"]
    for t in map(parse_time, sys.argv[3:]):
        print(f"\n{fmt(t)}")
        for s in E:
            if s["t0"] - 2.3 < t < s["t1"] + 2.3:
                w = " ".join(x_["w"] for x_ in s["words"])
                print(f"   seg {s['t0']:.2f}-{s['t1']:.2f} {s['block']} {v.short(s['clip'])}@{s['a']:.2f}-{s['b']:.2f} "
                      f"in={s['in_type']} out={s['out_type']} «{w[:50]}{'…' + w[-40:] if len(w) > 90 else w[50:90]}»")
        print("   HEARD: " + hear(x, t - 2.2, t + 2.2, LANG))
elif sys.argv[2] == "clip":
    c = v.clip_id(sys.argv[3])
    lang = sys.argv[6] if len(sys.argv) > 6 else LANG
    x, _ = read_wav(v.audio16_of(c))
    print(hear(x, parse_time(sys.argv[4]), parse_time(sys.argv[5]), lang))
else:
    raise SystemExit(__doc__)
