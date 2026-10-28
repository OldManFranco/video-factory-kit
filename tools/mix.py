"""Stage 6 · the voice-only mix: the cut's voice at the profile's loudness (default −14 LUFS, true peak ≤ −1.5 dBTP),
plus silence for the end screen. The kit picks no music: the editor adds it in their own editor if they want.
Two-pass loudnorm (linear when possible). → work/mix.wav (48 kHz stereo) + work/mix_qa.json
Usage: py-render tools/mix.py <video>"""
import json
import re
import subprocess
import sys

from vfk.kit import Video, load, save
from vfk.media import read_wav, tool, write_wav
from vfk.profile import load_profile

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
prof = load_profile()
L, TP = float(prof["output"]["loudness_lufs"]), float(prof["output"]["true_peak_db"])
S = load(v.work / "sheet_resolved.json")
end = max((e["t"] + e["dur"] for e in S["elements"] if e["type"] == "END"), default=None) if S else None
voice, sr = read_wav(v.cut / "voice48.wav", mono=False)
total = max(len(voice) / sr, end or 0.0)
src = v.work / "_voice_padded.wav"
import numpy as np  # noqa: E402
pad = int(round(total * sr)) - len(voice)
write_wav(src, np.pad(voice, ((0, max(0, pad)), (0, 0))) if voice.ndim == 2 else np.pad(voice, (0, max(0, pad))), sr)


def measure(path, extra=""):
    af = (extra + "," if extra else "") + f"loudnorm=I={L}:TP={TP}:LRA=11:print_format=json"
    r = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(path), "-af", af, "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return json.loads(r[r.rfind("{"):r.rfind("}") + 1])


m = measure(src)
af = (f"loudnorm=I={L}:TP={TP}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
      f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=json")
out = v.work / "mix.wav"
r = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-y", "-i", str(src), "-af", af, "-ar", str(sr), "-ac", "2",
                    "-c:a", "pcm_s16le", str(out)], capture_output=True, text=True, encoding="utf-8", errors="replace")
if r.returncode:
    raise SystemExit(r.stderr[-2000:])
src.unlink()
st = subprocess.run([tool("ffmpeg"), "-hide_banner", "-nostats", "-i", str(out), "-af", "ebur128=peak=true", "-f", "null", "-"],
                    capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
summ = st[st.rfind("Summary:"):]
lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1))
peak = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1))
qa = {"lufs": lufs, "true_peak_dbtp": peak, "target_lufs": L, "target_tp": TP, "seconds": round(total, 3),
      "ok": abs(lufs - L) <= 0.7 and peak <= TP + 0.3}
save(v.work / "mix_qa.json", qa)
print(f"mix.wav · {lufs} LUFS · true peak {peak} dBTP · {total:.1f} s {'OK' if qa['ok'] else 'CHECK'}")
