"""Stage 5 · the Gate 2 page (rules H25, H26): storyboard.html — self-contained (images embedded), ready to publish.

Shows, in this order:
  0. THE WHOLE VIDEO AT A GLANCE: one tile per beat, in order — each full-screen element, and the host on camera between
     them (split at block boundaries) — drawn the way the edit will look: the graphic or B-roll, or the host's real frame
     with the lower thirds / name cards / subtitles on it and punch-ins zoomed; labelled with block, start, length and
     type, with the host's words under each tile → also saved full size as work/qa/storyboard_sheet.jpg;
  1. the SEQUENCE of blocks (the editor may reorder before the render; locked after approval);
  2. the B-ROLL COVERAGE MAP: which clip or graphic covers which line, with in/out times;
  3. INTERVIEWEE COVERAGE: % of each answer kept (rules H23) — from "interviews" in edit/script.json:
       "interviews": [{"name": "Maria", "clip": "0083", "from": 10.0, "to": 64.5}]   (the full answer, clip seconds)
  4. the CUT-OFF FLAGS from audio_flags.md (rules H20);
  5. one row per element: thumbnail on the real frame of the cut, the host's exact words, in/out, source, note;
  plus warnings from build_sheet.py, the graphic choices (D13) and the decisions (defaults broken).
Optional edit/gate2.json: {"changes": [["E002", "what the editor asked", "what was done"]], "intro": "..."}
Needs the previews: py-render tools/render_graphics.py <video> --scale 0.25 --no-motion
Usage: py-render tools/storyboard.py <video>
"""
import base64
import io
import subprocess
import sys
from fractions import Fraction

from PIL import Image

from vfk import cutreader
from vfk.kit import Video, fmt, load
from vfk.media import tool
from vfk.page import E, page

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
S = load(v.work / "sheet_resolved.json")
PREV = v.work / "graphics_preview"
REG = load(PREV / "registry.json", {})
if not S or not REG:
    raise SystemExit("Run build_sheet.py and render_graphics.py --scale 0.25 --no-motion first.")
G = v.script_resolved()
SCRIPT = load(v.edit / "script.json", {})
EDL = v.edl()["segments"]
WORDS = load(v.cut / "words.json")["words"]
D = load(v.edit / "gate2.json", {})
TW, TH = 480, 270


def cut_frame(t):
    try:
        args, skip = cutreader.input_args(v, max(0.0, t), 0.3)
    except SystemExit:
        return None
    r = subprocess.run([tool("ffmpeg"), "-v", "error", *args, "-frames:v", "1", "-vf",
                        f"{cutreader.skip_filter(skip)},scale={TW}:{TH}", "-f", "rawvideo", "-pix_fmt", "rgba", "-"],
                       capture_output=True)
    if len(r.stdout) < TW * TH * 4:
        return None
    return Image.frombytes("RGBA", (TW, TH), r.stdout[: TW * TH * 4])


def thumb(e):
    r = REG.get(e["id"])
    png = next((PREV / f for f in (r or {}).get("files", []) if f.endswith(".png")), None)
    if png is None or not png.exists():
        im = cut_frame(e["t"] + 0.5) or Image.new("RGBA", (TW, TH), (40, 40, 40, 255))
    else:
        el = Image.open(png).convert("RGBA").resize((TW, TH))
        if r.get("overlay"):
            im = cut_frame(e["t"] + min(1.0, e["dur"] / 2)) or Image.new("RGBA", (TW, TH), (60, 60, 60, 255))
            im.alpha_composite(el)
        else:
            im = el
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=78)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def words_between(a, b):
    return " ".join(w["w"] for w in WORDS if a - 0.05 <= w["s"] < b - 0.1)


def png_of(e):
    r = REG.get(e["id"]) or {}
    return next((PREV / f for f in r.get("files", []) if f.endswith(".png")), None)


def beats():
    """The whole video cut into beats: every full-screen element is one; the host on camera between them is split at the
    block boundaries (and every 20 s) — like a shot list of the finished edit."""
    dur = S["duration_cut_s"]
    covers = sorted((e for e in els if e["type"] in FULL_TYPES or e["type"].startswith("G-")), key=lambda e: e["t"])
    cuts = {0.0, dur} | {b["start"] for b in S["sequence"]}
    for e in covers + [e for e in els if e["type"] in ("PUNCH", "LOWER", "LINK", "NAME", "SUB")]:
        cuts |= {e["t"], min(dur, e["t"] + e["dur"])}       # punch-ins and overlays get their own beat on the host
    out, pts = [], sorted(c for c in cuts if 0 <= c <= dur)
    for a, b in zip(pts, pts[1:]):
        if b - a < 0.4:
            continue
        cov = next((e for e in covers if e["t"] <= a + 0.05 and a + 0.05 < e["t"] + e["dur"]), None)
        if cov is None and b - a > 20:                       # long host stretches: one tile every ~15 s
            n = int((b - a) // 15) + 1
            out += [(a + (b - a) * k / n, a + (b - a) * (k + 1) / n, None) for k in range(n)]
        else:
            out.append((a, b, cov))
    merged = []
    for a, b, cov in out:                                    # one tile per full-screen element, even if split above
        if merged and cov is not None and merged[-1][2] is cov:
            merged[-1] = (merged[-1][0], b, cov)
        else:
            merged.append((a, b, cov))
    end = next((e for e in els if e["type"] == "END"), None)
    if end:
        merged.append((end["t"], end["t"] + end["dur"], end))
    return merged


def tile(a, b, cov):
    """How the edit will look in the middle of the beat: the element, or the host's frame with the overlays and punch-in."""
    mid = (a + b) / 2
    if cov is not None and png_of(cov) and png_of(cov).exists():
        im = Image.open(png_of(cov)).convert("RGBA").resize((TW, TH))
        kind = cov["type"]
    else:
        im = cut_frame(mid) or Image.new("RGBA", (TW, TH), (40, 40, 40, 255))
        kind = "HOST"
        p = next((e for e in els if e["type"] == "PUNCH" and e["t"] <= mid < e["t"] + e["dur"]), None)
        if p:
            z, y = float(p.get("zoom", 1.13)), float(p.get("y", 0.35))
            cw, ch = TW / z, TH / z
            x0, y0 = (TW - cw) / 2, (TH - ch) * y
            im = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((TW, TH), Image.LANCZOS)
            kind = "HOST · PUNCH-IN"
        for o in els:
            if o["type"] in ("LOWER", "LINK", "NAME", "SUB") and o["t"] <= mid < o["t"] + o["dur"] and png_of(o) and png_of(o).exists():
                im.alpha_composite(Image.open(png_of(o)).convert("RGBA").resize((TW, TH)))
                kind += f" + {o['type']}"
    block = next((s["id"] for s in S["sequence"] if s["start"] <= mid < s["end"] + 0.01), "")
    if cov is not None and cov["type"] == "END":
        block, kind = "", "END SCREEN"
    label = f"{block}  {fmt(a)}  {b - a:.1f}s  {kind if cov is None or kind == 'END SCREEN' else cov['id'] + ' ' + kind}".strip()
    return im, label, words_between(a, b)


def sheet(cols=5):
    """One image of the whole video (The Standard-style storyboard): a tile per beat, with label and the host's words."""
    from PIL import ImageDraw, ImageFont
    from vfk.kit import ROOT
    from vfk.profile import load_profile
    prof = load_profile()
    fb = ROOT / prof["fonts"].get("body_file", "")
    font_path = fb if fb.is_file() else ROOT / "assets" / "fonts" / "Poppins-SemiBold.ttf"
    f_lab, f_txt = ImageFont.truetype(str(font_path), 17), ImageFont.truetype(str(font_path), 15)
    items = [tile(*b) for b in beats()]
    gap, strip = 8, 74
    rows = -(-len(items) // cols)
    out = Image.new("RGB", (cols * TW + (cols + 1) * gap, rows * (TH + strip + 34) + (rows + 1) * gap), (25, 25, 25))
    d = ImageDraw.Draw(out)
    for i, (im, label, words) in enumerate(items):
        x = gap + (i % cols) * (TW + gap)
        y = gap + (i // cols) * (TH + strip + 34 + gap)
        d.rectangle([x, y, x + TW, y + 34], fill=(0, 0, 0))
        d.text((x + 10, y + 7), label, font=f_lab, fill=(255, 220, 90))
        out.paste(im.convert("RGB"), (x, y + 34))
        line, lines = "", []
        for w in f"«{words}»".split() if words else ["(no words)"]:
            if d.textlength(line + " " + w, font=f_txt) > TW - 16:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        lines.append(line)
        if len(lines) > 3:
            lines = lines[:3]
            lines[-1] = lines[-1][: max(0, len(lines[-1]) - 2)] + "…"
        for k, l in enumerate(lines):
            d.text((x + 8, y + 34 + TH + 6 + k * 21), l, font=f_txt, fill=(225, 225, 225))
    v.qa.mkdir(parents=True, exist_ok=True)
    out.save(v.qa / "storyboard_sheet.jpg", quality=86)
    small = out.resize((min(out.width, 1800), int(out.height * min(out.width, 1800) / out.width)), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=80)
    return len(items), "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


FULL_TYPES = ("BROLL", "PHOTO", "WEB", "PEOPLE")
els = [e for e in S["elements"]]
full = [e for e in els if e["type"] in FULL_TYPES or e["type"].startswith("G-")]
n_beats, sheet_img = sheet()

# interviewee coverage (H23)
cover = []
for it in SCRIPT.get("interviews", []):
    c = v.clip_id(str(it["clip"]))
    kept = sum(max(0.0, min(s["b"], it["to"]) - max(s["a"], it["from"])) for s in EDL if s["clip"] == c)
    total = max(0.01, it["to"] - it["from"])
    cover.append((it["name"], v.short(c), kept, total))
flags = [l[2:] for l in (v.dir / "audio_flags.md").read_text(encoding="utf-8").splitlines() if l.startswith("- ")] \
    if (v.dir / "audio_flags.md").exists() else []

body = [f"""<header><h1>{E(S.get('title') or v.name)} · <span>Gate 2</span></h1>
<p class="lede">{E(D.get('intro', 'The edit sheet as a storyboard: every B-roll clip and graphic next to the exact words it covers. Nothing is rendered at full size before your approval.'))}</p></header>
<div class="facts"><span>Cut <b>{fmt(S['duration_cut_s'])}</b></span><span><b>{len(els)}</b> elements</span>
<span>Full-screen inserts <b>{len(full)}</b> ({len(full) / max(S['duration_cut_s'] / 60, 0.01):.1f}/min)</span>
<span>Output <b>{float(Fraction(S['fps_out'])):g} fps</b></span></div>
<div class="gate"><b>How to approve.</b><p>Check the order of the blocks, the coverage map and the flags; say what to change
(element ids like E012), or write <b>approved</b>. After approval the order is locked: if it has to change, I stop and ask.</p></div>"""]
if D.get("changes"):
    body.append("<section><h2>Your notes and what changed</h2><div class=\"scroll\"><table><tr><th>Id</th><th>You asked</th><th>Done</th></tr>"
                + "".join(f"<tr><td class=\"m\">{E(a)}</td><td>{E(b)}</td><td>{E(c)}</td></tr>" for a, b, c in D["changes"])
                + "</table></div></section>")
body.append(f"<section><h2>The whole video at a glance</h2><p class=\"lede\" style=\"margin:0 0 8px\">{n_beats} beats, in order, "
            "each drawn the way the edit will look (graphic, B-roll, or the host with lower thirds and punch-ins), with its "
            "block, start, length and the words under it. Full size: <code>work/qa/storyboard_sheet.jpg</code>.</p>"
            f"<img src=\"{sheet_img}\" alt=\"Storyboard of the whole video\"></section>")
body.append("<section><h2>1 · Sequence</h2><div class=\"scroll\"><table><tr><th>#</th><th>Block</th><th>Time</th><th>What</th></tr>"
            + "".join(f"<tr><td class=\"m\">{i}</td><td class=\"m\">{E(b['id'])} · {E(b['role'])}</td><td class=\"m\">{fmt(b['start'])}–{fmt(b['end'])}</td>"
                      f"<td>{E(b.get('section') or '')}</td></tr>" for i, b in enumerate(S["sequence"], 1)) + "</table></div></section>")
body.append("<section><h2>2 · B-roll coverage</h2><div class=\"scroll\"><table><tr><th>In–out</th><th>Covers</th><th>With</th></tr>"
            + "".join(f"<tr><td class=\"m\">{fmt(e['t'])}–{fmt(e['t'] + e['dur'])}</td><td>«{E(words_between(e['t'], e['t'] + e['dur'])[:140])}»</td>"
                      f"<td>{E(e['id'])} {E(e['type'])}{(' · ' + E(v.short(v.clip_id(str(e['clip']))) if e.get('clip') else '')) if e.get('clip') else ''}"
                      f"{' · ' + E(e.get('file', '')) if e.get('file') else ''}</td></tr>" for e in full) + "</table></div></section>")
body.append("<section><h2>3 · Interviews kept</h2>" + (
    "<div class=\"scroll\"><table><tr><th>Who</th><th>Clip</th><th>Kept</th></tr>" + "".join(
        f"<tr><td>{E(n)}</td><td class=\"m\">{E(c)}</td><td class=\"m{' bad' if k / t < 0.6 else ''}\">{100 * k / t:.0f}% ({k:.0f} of {t:.0f} s)</td></tr>"
        for n, c, k, t in cover) + "</table></div><p class=\"note\">Rule H23: interviewees finish their thoughts. Ask to put more back if needed.</p>"
    if cover else "<p class=\"lede\" style=\"margin:0\">No interviews in this video.</p>") + "</section>")
body.append("<section><h2>4 · Cut-off flags</h2>" + ("<ul>" + "".join(f"<li>{E(f)}</li>" for f in flags) + "</ul>" if flags else "<p>None.</p>") + "</section>")
if S.get("warnings"):
    body.append("<section><h2>Warnings</h2><ul>" + "".join(f"<li>{E(w)}</li>" for w in S["warnings"]) + "</ul></section>")
if S.get("decisions"):
    body.append("<section><h2>Choices and defaults broken</h2><ul>" + "".join(
        f"<li><b>{E(d.get('default', ''))}</b> {E(d.get('what', ''))} — {E(d.get('why', ''))}</li>" for d in S["decisions"]) + "</ul></section>")
rows = []
for e in els:
    if e["type"] == "PUNCH":
        what = f"punch-in {float(e.get('zoom', 1.13)) * 100:.0f}%"
    else:
        what = e.get("text") or e.get("title") or e.get("line2") or e.get("name") or e.get("place") or e.get("number") or ""
    src = e.get("source_text") or e.get("source") or ""
    img = "" if e["type"] == "PUNCH" else f'<img src="{thumb(e)}" alt="{E(e["id"])}" loading="lazy">'
    rows.append(f'<section class="block"><div class="head"><span class="t">{fmt(e["t"])}–{fmt(e["t"] + e["dur"])}</span>'
                f'<span class="id">{E(e["id"])}</span><span class="tag">{E(e["type"])}</span><span class="dur">{e["dur"]:.1f}s</span></div>'
                f'<div class="piece"><div>{img}</div><div class="txt"><b>{E(str(what))}</b><p class="note">«{E(words_between(e["t"], e["t"] + e["dur"])[:220])}»</p>'
                + (f'<p class="note">Source: {E(src)}</p>' if src else "") + (f'<p class="note">{E(e["note"])}</p>' if e.get("note") else "")
                + (f'<p class="warn">{E(e["placed"])}</p>' if e.get("placed") else "") + "</div></div></section>")
body.append("<section><h2>5 · Storyboard</h2>" + "".join(rows) + "</section>")
html_ = page(f"{S.get('title') or v.name} · Gate 2", "\n".join(body))
html_ = html_.replace("grid-template-columns:150px 1fr", "grid-template-columns:minmax(0,300px) 1fr")
(v.dir / "storyboard.html").write_text(html_, encoding="utf-8")
print(f"storyboard.html ({len(html_) // 1024} KB) · {len(els)} elements · {len(cover)} interviews · {len(flags)} flags")
