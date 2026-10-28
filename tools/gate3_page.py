"""Stage 7 · the Gate 3 page: final render + QA report (rules H25) → gate3.html (self-contained).
Reads render/final/qa.json (compose.py qa), qa_final.md (qa_cut.py --final, rule H20 on the final), work/qa/flashes.json,
work/qa/lip_sync.json + .jpg, work/qa/final_sheet.jpg (one frame per element), work/mix_qa.json and audio_flags.md.
Usage: python tools/gate3_page.py <video>"""
import base64
import sys

from vfk.kit import Video, fmt, load
from vfk.page import E, page

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
finals = sorted(v.final_dir.glob("*.mp4"))
if not finals:
    raise SystemExit("No final render in render/final/.")
mp4 = finals[-1]
Q = load(v.final_dir / "qa.json", {})
FL = load(v.qa / "flashes.json", {})
LS = load(v.qa / "lip_sync.json", {})
MX = load(v.work / "mix_qa.json", {})
QF = load(v.cut / "qa_final.json", {})


def img(p, width=1400):
    """Embedded, resized so the page stays light enough to publish and open anywhere."""
    if not p.exists():
        return ""
    import io
    from PIL import Image
    im = Image.open(p).convert("RGB")
    if im.width > width:
        im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72)
    return f'<img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}" alt="{E(p.stem)}">'


def mark(ok):
    if ok is None:
        return "<b>LOOK</b>"
    return '<b style="color:var(--accent)">OK</b>' if ok else '<b class="bad">CHECK</b>'


ch = Q.get("checks", {})
rows = [("Format", ch.get("format", {}).get("ok"), f"{ch.get('format', {}).get('size', '')} · {ch.get('format', {}).get('fps', '')} fps · "
                                                    f"{fmt(ch.get('format', {}).get('duration_s', 0))} · {ch.get('format', {}).get('gb', '')} GB"),
        ("Loudness", ch.get("loudness", {}).get("ok"), f"{ch.get('loudness', {}).get('lufs')} LUFS · true peak {ch.get('loudness', {}).get('true_peak')} dBTP"),
        ("Sync (sound and picture)", ch.get("sync", {}).get("ok"), "final audio = mix; picture = the cut's frames"),
        ("Every element at its time", ch.get("elements", {}).get("ok"), f"{ch.get('elements', {}).get('checked', 0)} checked · failed: "
                                                                        f"{', '.join(ch.get('elements', {}).get('failed', [])) or 'none'}"),
        ("Decodes fully, no black frames", ch.get("decodes", {}).get("ok") and ch.get("no_black", {}).get("ok"), ""),
        ("No host flashes (H24)", not FL.get("flashes"), f"{len(FL.get('flashes', []))} short shots" if FL else "not run"),
        ("Lip sync (Claude looked at the image below)", None, ", ".join(f"{p['word']}: ~{p['lag_frames']} fr" for p in LS.get("points", [])) or "not run"),
        ("Cut-off words on the final (H20)", QF is not None and not [d for d in QF.get("differences", []) if d.get("at_join")],
         f"{len(QF.get('differences', []))} differences, {len(QF.get('low_confidence', []))} low-confidence words" if QF else "not run")]
diffs = QF.get("differences", []) if QF else []
flags = [l[2:] for l in (v.dir / "audio_flags.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")] \
    if (v.dir / "audio_flags.md").exists() else []
body = f"""<header><h1>{E(mp4.stem)} · <span>Gate 3</span></h1>
<p class="lede">The final render and its QA. Watch it in full, then write <b>approved</b> (or say what to fix).</p></header>
<div class="facts"><span>File <b>{E(mp4.relative_to(v.dir).as_posix())}</b></span><span>QA <b>{'OK' if Q.get('ok') else 'see below'}</b></span></div>
<div class="gate"><b>How to approve.</b><p>Open <code>{E(mp4.relative_to(v.dir).as_posix())}</code> in the video folder and watch it
with sound. Fixes re-render only the parts they touch. Write <b>approved</b> when it's right.</p></div>
<section><h2>QA</h2><div class="scroll"><table><tr><th>Check</th><th>Result</th><th>Detail</th></tr>
{"".join(f"<tr><td>{E(a)}</td><td>{mark(b)}</td><td>{E(str(c))}</td></tr>" for a, b, c in rows)}</table></div></section>
<section><h2>Words on the final vs the script</h2>{"<ul>" + "".join(f"<li>{E(d['at'])} · {E(d['kind'])} · «{E(d['script'])}» → «{E(d['heard'])}»</li>" for d in diffs) + "</ul>" if diffs else "<p>Whisper hears exactly the script.</p>"}</section>
<section><h2>Joins you were asked to listen to</h2>{"<ul>" + "".join(f"<li>{E(x)}</li>" for x in flags) + "</ul>" if flags else "<p>None.</p>"}</section>
<section><h2>Every element in the final</h2>{img(v.qa / "final_sheet.jpg")}</section>
<section><h2>Lip sync</h2>{img(v.qa / "lip_sync.jpg")}</section>
{"<section><h2>Layer notes</h2><ul>" + "".join(f"<li>{E(n)}</li>" for n in Q.get("notes", [])) + "</ul></section>" if Q.get("notes") else ""}"""
(v.dir / "gate3.html").write_text(page(f"{mp4.stem} · Gate 3", body), encoding="utf-8")
print("gate3.html")
