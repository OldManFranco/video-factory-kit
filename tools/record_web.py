"""Screen recording of a public web page for a WEB element (rules §3: "the document or website"), with Playwright's own
Chromium (installed by the installer, not the system browser). The page loads, waits, then scrolls slowly.
No logins, no forms, no cookie banners accepted on the editor's behalf (rules H10): if the page needs any of that, use
another source. A rights record (<file>.json: URL, date, site) is written next to the video.

Usage: py-render tools/record_web.py <video> <url> <name> [--seconds 8] [--scroll 900] [--width 1920] [--height 1080]
  → <video>/web/<name>.mp4 (+ <name>.json). In the sheet: {"type": "WEB", "file": "web/<name>.mp4", ...}
"""
import shutil
import sys
import time
from datetime import date

from vfk.kit import Video, save
from vfk.media import ffmpeg

if len(sys.argv) < 4:
    raise SystemExit(__doc__)
v = Video(sys.argv[1])
url, name = sys.argv[2], sys.argv[3]
opt = lambda k, d: type(d)(sys.argv[sys.argv.index(k) + 1]) if k in sys.argv else d
SECS, SCROLL, W, H = opt("--seconds", 8.0), opt("--scroll", 900), opt("--width", 1920), opt("--height", 1080)
out_dir = v.dir / "web"
tmp = out_dir / f"_{name}"
tmp.mkdir(parents=True, exist_ok=True)
from playwright.sync_api import sync_playwright  # noqa: E402

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(tmp), record_video_size={"width": W, "height": H},
                              device_scale_factor=1)
    page = ctx.new_page()
    page.goto(url, wait_until="networkidle", timeout=60000)
    title = page.title()
    if any(x in title.lower() for x in ("just a moment", "verify you are human", "access denied")):
        ctx.close()
        browser.close()
        shutil.rmtree(tmp, ignore_errors=True)
        raise SystemExit(f"The page asks for a human check («{title}»): don't insist, use another source (rules H10).")
    time.sleep(1.5)
    steps = int(SECS * 10)
    for _ in range(steps):
        page.mouse.wheel(0, SCROLL / steps)
        time.sleep(0.1)
    time.sleep(0.5)
    ctx.close()
    browser.close()
webm = next(tmp.glob("*.webm"))
dst = out_dir / f"{name}.mp4"
ffmpeg("-y", "-ss", "1.2", "-i", webm, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-an", dst)
shutil.rmtree(tmp, ignore_errors=True)
save(dst.with_suffix(".json"), {"source": title, "source_url": url, "licence": "screen recording of a public page (check the site's terms)",
                                "downloaded": date.today().isoformat(), "modifications": "screen recording, scrolled"})
print(f"web/{name}.mp4 · «{title}»")
