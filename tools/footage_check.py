"""Stage 0 · footage check: for every clip in footage/
  - file info (length, frame rate, size, codecs) and a full decode to find damaged files;
  - audio extracted once: work/audio16/<clip>.wav (16 kHz mono, for Whisper) and work/audio48/<clip>.wav (for the cut);
  - transcript with faster-whisper large-v3, word by word → work/transcripts/<clip>.words.json;
  - spoken language in 10 s windows (another language = probably someone the host talks to);
  - level of each sentence (a much quieter sentence = a second, more distant voice);
  - clip type: A-ROLL (host talking), B-ROLL (no speech), INTERVIEW, MIXED.
Output: work/footage.json + work/footage_check/summary.md (+ one .txt transcript per clip).
Resumable: clips already done are skipped. Long on a CPU: run it as a detached job (tools/job.py).

Usage: py-audio tools/footage_check.py <video> [clip ...] [--fast]
  --fast  decode only keyframes for the integrity check (much quicker, catches truncated files)
"""
import subprocess
import sys

import numpy as np

from vfk.asr import device, transcribe, whisper
from vfk.kit import Video, fmt, load, now, save
from vfk.media import extract_audio, probe, read_wav, tool
from vfk.profile import load_profile, whisper_prompt

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
only = [a for a in sys.argv[2:] if not a.startswith("--")]
FAST = "--fast" in sys.argv
prof = load_profile()
LANG = prof.get("spoken_language", "en")
PROMPT = whisper_prompt(prof, v)
db = lambda x: float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)) if len(x) else -99.0

clips = v.clips()
if not clips:
    raise SystemExit(f"No video files in {v.footage}. Copy the camera clips there first.")
state = load(v.work / "footage.json", {"clips": {}})
todo = [c for c in clips if (not only or any(o in c for o in only)) and (only or c not in state["clips"])]
print(f"{len(clips)} clips · {len(todo)} to check · Whisper on {device()[0]}", flush=True)
(v.work / "footage_check").mkdir(parents=True, exist_ok=True)
v.transcripts.mkdir(parents=True, exist_ok=True)

for c in todo:
    f = clips[c]
    info = probe(f)
    # integrity: decode everything (or only keyframes) and count errors
    dec = ["-skip_frame", "nokey"] if FAST else []
    r = subprocess.run([tool("ffmpeg"), "-v", "error", "-hwaccel", "auto", *dec, "-i", str(f), "-f", "null", "-"],
                       capture_output=True, text=True)
    errors = [l for l in r.stderr.splitlines() if l.strip()]
    rec = {"file": f.relative_to(v.dir).as_posix(), **info, "decode_errors": len(errors),
           "decode_sample": errors[:3], "checked": now()}
    if "acodec" not in info:
        rec.update({"type": "B-ROLL", "words": 0, "speech_s": 0.0, "note": "no audio track"})
        state["clips"][c] = rec
        save(v.work / "footage.json", state)
        print(f"{v.short(c):>10} {fmt(info['duration']):>7}  no audio → B-ROLL", flush=True)
        continue
    extract_audio(f, v.audio16_of(c), 16000, 1)
    extract_audio(f, v.audio48_of(c), 48000, 2)
    x, _ = read_wav(v.audio16_of(c))
    dur = len(x) / 16000
    # language per 10 s window (windows with sound only)
    langs = []
    for t in np.arange(0, max(dur - 2, 0.1), 10):
        seg = x[int(t * 16000): int((t + 10) * 16000)]
        if len(seg) < 32000 or db(seg) < -45:
            continue
        lang, p, allp = whisper().detect_language(seg)
        langs.append({"t": round(float(t), 1), "lang": lang, "p": round(p, 2)})
    segs = transcribe(x, language=LANG, prompt=PROMPT, vad=True)
    segs = [{"s": round(s.start, 2), "e": round(s.end, 2), "text": s.text.strip(), "no_speech": round(s.no_speech_prob, 2),
             "db": round(db(x[int(s.start * 16000): int(s.end * 16000)]), 1),
             "words": [{"w": w.word, "s": round(w.start, 3), "e": round(w.end, 3), "p": round(w.probability, 3)} for w in s.words]}
            for s in segs]
    save(v.transcripts / f"{c}.words.json", {"language": LANG, "segments": segs}, indent=None)
    (v.work / "footage_check" / f"{c}.txt").write_text(
        "\n".join(f"[{s['s']:7.2f}] ({s['db']:5.1f} dB) {s['text']}" for s in segs), encoding="utf-8")
    speech = sum(s["e"] - s["s"] for s in segs)
    nwords = sum(len(s["words"]) for s in segs)
    other = [l for l in langs if l["lang"] != LANG and l["p"] > 0.5]
    level = float(np.median([s["db"] for s in segs])) if segs else -99.0
    quiet = [s for s in segs if s["db"] < level - 9 and len(s["words"]) >= 3]
    ratio = speech / dur if dur else 0
    if nwords < 5 or ratio < 0.1:
        kind = "B-ROLL"
    elif other and len(other) >= max(1, len(langs) // 3):
        kind = "INTERVIEW"
    elif len(quiet) >= max(2, len(segs) // 3):
        kind = "MIXED"
    else:
        kind = "A-ROLL"
    if other:   # the other speaker's language gets its own transcript (for subtitles and interview coverage)
        lang2 = max({l["lang"] for l in other}, key=lambda L: sum(l["lang"] == L for l in other))
        s2 = transcribe(x, language=lang2, vad=True)
        save(v.transcripts / f"{c}.{lang2}.words.json", {"language": lang2, "segments": [
            {"s": round(s.start, 2), "e": round(s.end, 2), "text": s.text.strip(),
             "words": [{"w": w.word, "s": round(w.start, 3), "e": round(w.end, 3), "p": round(w.probability, 3)} for w in s.words]}
            for s in s2]}, indent=None)
        rec["other_language"] = lang2
    rec.update({"type": kind, "words": nwords, "speech_s": round(speech, 1), "level_db": round(level, 1),
                "other_language_windows": other, "quiet_sentences": [{"s": s["s"], "db": s["db"], "text": s["text"]} for s in quiet],
                "first_words": " ".join(s["text"] for s in segs)[:120]})
    state["clips"][c] = rec
    save(v.work / "footage.json", state)
    print(f"{v.short(c):>10} {fmt(dur):>7} {info.get('fps_float', 0):>6} fps  {kind:<9} {nwords:4d} words"
          f"{'  DAMAGED (' + str(len(errors)) + ' errors)' if errors else ''}", flush=True)

# summary
C = state["clips"]
tot = sum(i["duration"] for i in C.values())
lines = [f"# Footage check · {v.name}\n", f"{len(C)} clips · {fmt(tot)} in total · checked {now()}\n",
         "| Clip | Length | fps | Size | Type | Words | Notes |", "|---|---|---|---|---|---|---|"]
for c, i in sorted(C.items()):
    notes = []
    if i.get("decode_errors"):
        notes.append(f"DAMAGED ({i['decode_errors']} decode errors): copy it again from the card")
    if i.get("other_language_windows"):
        notes.append("other language at " + ", ".join(fmt(l["t"]) for l in i["other_language_windows"][:4]))
    if i.get("quiet_sentences"):
        notes.append(f"{len(i['quiet_sentences'])} quiet sentences (second voice?)")
    lines.append(f"| {v.short(c)} | {fmt(i['duration'])} | {i.get('fps_float', '')} | {i.get('width', '')}×{i.get('height', '')} "
                 f"| {i['type']} | {i.get('words', 0)} | {'; '.join(notes) or (i.get('first_words', '')[:60] + '…')} |")
fps = sorted({i.get("fps") for i in C.values() if i.get("fps")})
lines += ["", f"Frame rates: {', '.join(fps)}."]
(v.work / "footage_check" / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"\nSummary: {(v.work / 'footage_check' / 'summary.md').relative_to(v.dir).as_posix()}")
