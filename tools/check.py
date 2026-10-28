"""Health check of the kit on this computer → check_report.txt (run by check.bat / check.sh and at the end of the installer).
Plain Python only (no packages), so it runs even before the environments exist. Every line: OK, WARN or FAIL + how to fix.
Usage: python tools/check.py"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIN, MAC = os.name == "nt", platform.system() == "Darwin"
INSTALL = "run install.bat" if WIN else "run: bash install.sh"
rows = []


for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def add(status, name, detail="", fix=""):
    rows.append((status, name, detail, fix))
    print(f"[{status:<4}] {name}{' - ' + detail if detail else ''}{('  -> fix: ' + fix) if fix and status != 'OK' else ''}", flush=True)


def refresh_path():
    if WIN:
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
    elif MAC:
        os.environ["PATH"] = os.pathsep.join([os.environ.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin"])


def run(cmd, timeout=120, **kw):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, **kw)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def venv_python(name):
    p = ROOT / "tools" / name / ("Scripts/python.exe" if WIN else "bin/python")
    return p if p.exists() else None


refresh_path()
add("OK", "System", f"{platform.system()} {platform.release()} · {platform.machine()} · kit in {ROOT}")

# ---------------------------------------------------------------- programs
ver = sys.version_info
add("OK" if (ver.major, ver.minor) == (3, 12) else "WARN", "Python running this check", f"{ver.major}.{ver.minor}.{ver.micro}",
    "the kit's environments use Python 3.12: " + INSTALL)
ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
if ff and fp:
    code, out = run([ff, "-hide_banner", "-encoders"])
    have = {e: e in out for e in ("libx264", "prores_ks", "aac", "libmp3lame", "h264_nvenc", "h264_videotoolbox")}
    v = re.search(r"ffmpeg version (\S+)", run([ff, "-version"])[1])
    add("OK" if all(have[e] for e in ("libx264", "prores_ks", "aac", "libmp3lame")) else "FAIL", "ffmpeg",
        f"{v.group(1) if v else '?'} · " + ", ".join(e for e, ok in have.items() if ok), "install a full ffmpeg build: " + INSTALL)
    gpu = "h264_videotoolbox" if MAC else "h264_nvenc"
    if have[gpu]:
        with tempfile.TemporaryDirectory() as d:
            args = ["-c:v", gpu] + (["-q:v", "60"] if MAC else ["-preset", "p5"])
            code, out = run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=640x360:d=0.2", *args, "-pix_fmt", "yuv420p",
                             str(Path(d) / "t.mp4")])
        add("OK" if code == 0 else "WARN", "Fast video encoder", gpu if code == 0 else f"{gpu} listed but failed: {out.strip()[-120:]}",
            "renders still work with libx264, only slower (update the graphics driver for NVENC)")
    else:
        add("WARN", "Fast video encoder", f"no {gpu}: renders use libx264 (slower but fine)")
else:
    add("FAIL", "ffmpeg", "not found", INSTALL)
node = shutil.which("node")
if node:
    nv = run([node, "--version"])[1].strip()
    major = int(re.sub(r"\D", "", nv.split(".")[0]) or 0)
    add("OK" if major >= 22 else "WARN", "Node.js", nv, "Node.js 22 or newer: " + INSTALL)
    npx = shutil.which("npx")
    code, out = run([npx, "--yes", "hyperframes", "--version"], timeout=240) if npx else (1, "npx missing")
    add("OK" if code == 0 else "WARN", "HyperFrames", out.strip().splitlines()[-1][:80] if out.strip() else "",
        "optional (animated HTML graphics): npx --yes hyperframes --version")
else:
    add("WARN", "Node.js", "not found (only needed for HyperFrames)", INSTALL)
add("OK" if shutil.which("git") else "WARN", "Git", "found" if shutil.which("git") else "not found",
    "needed to update the kit from GitHub: " + INSTALL)

# ---------------------------------------------------------------- environments
pa = venv_python("venv_audio")
if pa:
    code, out = run([str(pa), "-c", "import json, torch, faster_whisper, whisperx, yt_dlp, numpy; print(json.dumps({'torch': torch.__version__, "
                     "'cuda': torch.cuda.is_available(), 'gpu': torch.cuda.get_device_name(0) if torch.cuda.is_available() else '', "
                     "'whisperx': getattr(whisperx, '__version__', '?'), 'yt_dlp': yt_dlp.version.__version__}))"], timeout=300)
    j = json.loads(out.strip().splitlines()[-1]) if code == 0 and out.strip().endswith("}") else None
    if j:
        add("OK", "Audio environment (venv_audio)", f"torch {j['torch']} · yt-dlp {j['yt_dlp']}")
        nvidia = WIN and shutil.which("nvidia-smi")
        if nvidia:
            add("OK" if j["cuda"] else "FAIL", "Whisper on the NVIDIA card", j["gpu"] or "CUDA not available",
                "reinstall PyTorch with CUDA: " + INSTALL)
        else:
            add("OK", "Whisper", "runs on the CPU (slower: long transcriptions as detached jobs)")
    else:
        add("FAIL", "Audio environment (venv_audio)", out.strip().splitlines()[-1][:160] if out.strip() else "import failed", INSTALL)
else:
    add("FAIL", "Audio environment (venv_audio)", "missing", INSTALL)
pr = venv_python("venv_render")
if pr:
    code, out = run([str(pr), "-c", "import cv2, mediapipe, PIL, numpy, fontTools, playwright; print('ok', cv2.__version__, PIL.__version__)"], timeout=180)
    add("OK" if code == 0 and "ok" in out else "FAIL", "Render environment (venv_render)",
        out.strip().splitlines()[-1][:120] if out.strip() else "", INSTALL)
    code, out = run([str(pr), "-c", "from playwright.sync_api import sync_playwright\nwith sync_playwright() as p:\n b = p.chromium.launch(); "
                     "print('chromium', b.version); b.close()"], timeout=180)
    add("OK" if code == 0 and "chromium" in out else "FAIL", "Playwright's Chromium", out.strip().splitlines()[-1][:80] if out.strip() else "",
        "tools/venv_render: python -m playwright install chromium")
else:
    add("FAIL", "Render environment (venv_render)", "missing", INSTALL)

# ---------------------------------------------------------------- models and kit files
hf = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub" / "models--Systran--faster-whisper-large-v3"
add("OK" if hf.exists() else "WARN", "Whisper large-v3 model", "downloaded" if hf.exists() else "not downloaded yet (~3 GB on first use)",
    "tools/venv_audio: python tools/download_models.py")
th = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache" / "torch")) / "hub" / "checkpoints"
al = list(th.glob("wav2vec2*")) if th.exists() else []
add("OK" if al else "WARN", "Alignment model (wav2vec2)", "downloaded" if al else "not downloaded yet (on first use)",
    "tools/venv_audio: python tools/download_models.py")
for f, what in (("assets/fonts/Poppins-ExtraBold.ttf", "Default fonts"), ("assets/models/face_landmarker.task", "Face model (lip-sync check)"),
                ("assets/maps/ne_110m_admin_0_countries.geojson", "World map (G-MAP)")):
    add("OK" if (ROOT / f).exists() else "FAIL", what, f, "download the kit again (git pull)")
prof = (ROOT / "CHANNEL_PROFILE.md").read_text(encoding="utf-8") if (ROOT / "CHANNEL_PROFILE.md").exists() else ""
m = re.search(r'"status":\s*"(\w+)"', prof)
st = m.group(1) if m else "?"
add("OK" if st == "READY" else "WARN", "Channel profile", st,
    "open Claude in this folder and say: Hi, let's set up my channel" if st != "READY" else "")
free = shutil.disk_usage(ROOT).free / 1e9
add("OK" if free >= 40 else "WARN", "Free disk space", f"{free:.0f} GB on the kit's drive",
    "a 4K vlog needs ~25 GB while rendering: free some space or move the kit")

fails = sum(r[0] == "FAIL" for r in rows)
warns = sum(r[0] == "WARN" for r in rows)
lines = [f"Video Factory Kit · health check · {platform.node()}", ""]
lines += [f"[{s:<4}] {n}{' - ' + d if d else ''}" + (f"\n        fix: {f}" if f and s != "OK" else "") for s, n, d, f in rows]
lines += ["", "ALL GOOD" if not fails else f"{fails} problem(s) to fix" + (f", {warns} warning(s)" if warns else ""),
          "If something fails: open Claude in the kit folder and say «the check failed, help me fix it»." if fails else ""]
(ROOT / "check_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print()
print("ALL GOOD" if not fails else f"{fails} problem(s), {warns} warning(s)", "-> check_report.txt")
sys.exit(1 if fails else 0)
