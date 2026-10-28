"""ffmpeg / ffprobe helpers, WAV in/out, encoder choice (NVENC → VideoToolbox → libx264) and the output frame rate rule."""
import json
import os
import platform
import shutil
import subprocess
import tempfile
import wave
from fractions import Fraction
from pathlib import Path

import numpy as np

from .kit import ROOT, load, save


def _refresh_windows_path():
    """A terminal opened before ffmpeg was installed doesn't see it: re-read PATH from the registry."""
    if os.name != "nt":
        return
    try:
        import winreg
        parts = []
        for hive, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                          (winreg.HKEY_CURRENT_USER, r"Environment")):
            with winreg.OpenKey(hive, key) as k:
                parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
        os.environ["PATH"] = os.pathsep.join([os.environ.get("PATH", "")] + parts)
    except OSError:
        pass


def tool(name):
    exe = shutil.which(name)
    if not exe:
        _refresh_windows_path()
        exe = shutil.which(name)
    if not exe:
        raise SystemExit(f"{name} not found. Run the installer (install.bat / install.sh) or the check (check.bat / check.sh).")
    return exe


def ffmpeg(*args, quiet=True):
    cmd = [tool("ffmpeg"), "-hide_banner", *(["-v", "error"] if quiet else []), *map(str, args)]
    subprocess.run(cmd, check=True)


def probe(path):
    """Duration, frame rate (exact fraction), size, codec and audio of a media file."""
    out = subprocess.run([tool("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    info = {"duration": float(j["format"].get("duration", 0) or 0), "size_bytes": int(j["format"].get("size", 0) or 0)}
    if v:
        fr = v.get("avg_frame_rate") or v.get("r_frame_rate") or "0/1"
        if fr in ("0/0", "0/1"):
            fr = v.get("r_frame_rate", "0/1")
        info.update({"width": int(v["width"]), "height": int(v["height"]), "fps": fr,
                     "fps_float": round(float(Fraction(fr)), 3) if fr != "0/0" else 0.0, "vcodec": v["codec_name"],
                     "rotation": int((v.get("tags") or {}).get("rotate", 0) or 0)})
    if a:
        info.update({"acodec": a["codec_name"], "sample_rate": int(a.get("sample_rate", 0)), "channels": a.get("channels", 0)})
    return info


def output_fps(src_fps):
    """Profile rule (rules H14): 23.976/24 → exactly 24; 25 → 25; 29.97/30 → 30; 50 → 50; 59.94/60 → 60."""
    f = float(Fraction(src_fps)) if isinstance(src_fps, str) else float(src_fps)
    for target in (24, 25, 30, 50, 60):
        if abs(f - target) < 0.1 or abs(f - target * 1000 / 1001) < 0.01:
            return Fraction(target)
    return Fraction(src_fps).limit_denominator(1001) if isinstance(src_fps, str) else Fraction(round(f))


# ------------------------------------------------------------------------------------------------ WAV
def read_wav(path, mono=True):
    with wave.open(str(path)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch)
        if mono:
            x = x.mean(1)
    return x, sr


def write_wav(path, x, sr):
    x = np.asarray(x, np.float32)
    ch = 1 if x.ndim == 1 else x.shape[1]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def extract_audio(src, dst, sr=16000, channels=1):
    if Path(dst).exists():
        return dst
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(dst).with_suffix(".tmp.wav")
    ffmpeg("-y", "-i", src, "-vn", "-ac", channels, "-ar", sr, "-c:a", "pcm_s16le", tmp)
    tmp.replace(dst)
    return dst


# ------------------------------------------------------------------------------------------------ encoder
CANDIDATES = {
    "nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "{q}", "-b:v", "0"],
    "videotoolbox": ["-c:v", "h264_videotoolbox", "-q:v", "{vt}", "-allow_sw", "1"],
    "libx264": ["-c:v", "libx264", "-preset", "fast", "-crf", "{q}"],
}


def _works(name):
    args = [a.format(q=23, vt=60) for a in CANDIDATES[name]]
    with tempfile.TemporaryDirectory() as d:
        r = subprocess.run([tool("ffmpeg"), "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=640x360:d=0.2",
                            *args, "-pix_fmt", "yuv420p", str(Path(d) / "t.mp4")], capture_output=True)
        return r.returncode == 0


def encoder():
    """The fastest H.264 encoder that really works on this computer (tested once, remembered in work/encoder.json)."""
    cache = ROOT / "work" / "encoder.json"
    c = load(cache, {})
    host = f"{platform.node()}|{platform.system()}"
    if c.get("host") == host and c.get("encoder") in CANDIDATES:
        return c["encoder"]
    order = (["videotoolbox"] if platform.system() == "Darwin" else ["nvenc"]) + ["libx264"]
    enc = next((e for e in order if _works(e)), "libx264")
    save(cache, {"host": host, "encoder": enc})
    return enc


def vcodec_args(quality="high", gop=None):
    """Video codec arguments. quality: 'high' (intermediates, ~visually lossless) or 'final'."""
    enc = encoder()
    q = 17 if quality == "high" else 19
    vt = 75 if quality == "high" else 68
    args = [a.format(q=q, vt=vt) for a in CANDIDATES[enc]]
    if gop:
        args += ["-g", str(gop)]
    return args + ["-pix_fmt", "yuv420p"]
