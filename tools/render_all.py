"""Stage 6 · the whole render in one go, meant to run as a DETACHED job (it survives if Claude or the app closes):
graphics at full resolution → voice-only mix → compose (parts + final + QA).
Usage: python tools/job.py <video> render -- py-render tools/render_all.py <video>"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if len(sys.argv) < 2:
    raise SystemExit(__doc__)
for step in (["render_graphics.py"], ["mix.py"], ["compose.py", "all"]):
    print(">>>", *step, flush=True)
    r = subprocess.run([sys.executable, str(HERE / step[0]), sys.argv[1], *step[1:]], cwd=HERE.parent)
    if r.returncode:
        raise SystemExit(f"{step[0]} failed ({r.returncode})")
print("render_all: done", flush=True)
