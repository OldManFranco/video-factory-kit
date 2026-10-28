"""First session · a simple brand kit for a channel that has none (docs/first_session.md, Step 4).

Claude writes the options to work/brand/options.json:
  {"palettes": [{"name": "Ocean", "colors": {"background": "#F2F2EF", "dark": "#16181D", "accent": "#2F6FED",
                                             "neutral": "#8A8F98", "light": "#FFFFFF"}}, ...],
   "fonts": [{"heading": "Montserrat", "body": "Inter"}, ...]}            (Google Fonts families, free OFL licence)

  py-render tools/make_brand.py --preview
      downloads the fonts (Google Fonts, into work/brand/fonts/) and renders every palette × font pair on a sample
      lower third, name card, number card and end card → work/brand/preview.html (images embedded)
  py-render tools/make_brand.py --apply <palette number> <font pair number>     (numbers start at 1)
      copies the chosen fonts to assets/fonts/, makes assets/brand/end_card.png (the video's end screen) and
      assets/brand/youtube_banner.png (2560×1440, text inside YouTube's safe area), and writes colours, fonts and
      banner_file into the JSON block of CHANNEL_PROFILE.md.
"""
import base64
import io
import json
import re
import shutil
import sys
import urllib.request

from PIL import Image, ImageDraw

from vfk.gfx import Canvas, box
from vfk.kit import ROOT, load
from vfk.profile import load_profile

OPT = ROOT / "work" / "brand" / "options.json"
FONTS = ROOT / "work" / "brand" / "fonts"
WEIGHTS = {"heading": (800, 700), "body": (600, 500), "light": (500, 400)}


def fetch_family(family):
    """Static TTF files of a Google Fonts family (CSS2 API) → {weight: path}."""
    FONTS.mkdir(parents=True, exist_ok=True)
    have = {int(m.group(1)): p for p in FONTS.glob(f"{family.replace(' ', '')}-*.ttf") if (m := re.search(r"-(\d+)\.ttf$", p.name))}
    need = {w for pair in WEIGHTS.values() for w in pair}
    if need <= set(have):
        return have
    url = "https://fonts.googleapis.com/css2?family=" + family.replace(" ", "+") + ":wght@" + ";".join(map(str, sorted(need)))
    try:
        css = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/4.0"}), timeout=30).read().decode()
    except Exception as e:  # noqa: BLE001
        raise SystemExit(f"Could not get «{family}» from Google Fonts ({e}). Check the name at fonts.google.com.")
    for block in css.split("@font-face")[1:]:
        w = re.search(r"font-weight:\s*(\d+)", block)
        src = re.search(r"url\((https://[^)]+\.ttf)\)", block)
        if w and src and int(w.group(1)) not in have:
            dst = FONTS / f"{family.replace(' ', '')}-{w.group(1)}.ttf"
            dst.write_bytes(urllib.request.urlopen(src.group(1), timeout=60).read())
            have[int(w.group(1))] = dst
    if not have:
        raise SystemExit(f"«{family}» has no downloadable TTF files.")
    return have


def font_files(pair):
    out = {}
    for role, fam in (("heading", pair["heading"]), ("body", pair["body"]), ("light", pair["body"])):
        files = fetch_family(fam)
        w = next((w for w in WEIGHTS[role] if w in files), min(files, key=lambda x: abs(x - WEIGHTS[role][0])))
        out[role] = files[w]
    return out


def profile_with(colors, files):
    p = load_profile()
    p["colors"] = dict(colors)
    p["fonts"] = {"heading_file": str(files["heading"]), "body_file": str(files["body"]), "light_file": str(files["light"])}
    return p


def sample(prof, name):
    cv = Canvas(1280, 720, 24, prof)
    U, W, H = cv.U, cv.W, cv.H
    im = Image.new("RGBA", (W, H), cv.BG + (255,))
    t, m = cv.line([("178", cv.ACC)], "heading", 16 * U)
    im.alpha_composite(t, (int(6 * U - m["pad"]), int(0.30 * H - m["base"] + m["cap"])))
    t, m = cv.line([("PROJECTS AT THE FAIR", cv.DARK)], "heading", 3.4 * U)
    im.alpha_composite(t, (int(6 * U - m["pad"]), int(0.40 * H - m["base"] + m["cap"])))
    t, m = cv.line([("Body text looks like this", cv.DARK)], "body", 2.6 * U)
    im.alpha_composite(t, (int(6 * U - m["pad"]), int(0.50 * H - m["base"] + m["cap"])))
    t, m = cv.line([("LINK IN ", cv.LIGHT), ("DESCRIPTION", cv.ACC)], "heading", 3.0 * U)
    b = box(m["w"] + 3 * U, m["cap"] + 2.4 * U, cv.DARK, 255, 0.3 * U)
    b.alpha_composite(t, (int(1.5 * U - m["pad"]), int(1.2 * U + m["cap"] - m["base"])))
    im.alpha_composite(b, (int(6 * U), int(0.62 * H)))
    end = Image.new("RGBA", (int(0.40 * W), int(0.40 * H)), cv.DARK + (255,))
    t, m = cv.line([((name or "CHANNEL NAME").upper(), cv.LIGHT)], "heading", 3.0 * U)
    end.alpha_composite(t, (int(end.width / 2 - m["w"] / 2 - m["pad"]), int(0.25 * end.height - m["base"] + m["cap"])))
    ImageDraw.Draw(end).rectangle([end.width * 0.4, end.height * 0.36, end.width * 0.6, end.height * 0.36 + 0.5 * U], fill=cv.ACC + (255,))
    im.alpha_composite(end, (int(0.55 * W), int(0.12 * H)))
    t, m = cv.line([("MARIA LOPEZ", cv.LIGHT)], "heading", 2.2 * U)
    nb = box(m["w"] + 3 * U, m["cap"] + 2.0 * U, cv.DARK, 235, 0.3 * U)
    ImageDraw.Draw(nb).rectangle([0, 0, int(0.35 * U), nb.height], fill=cv.ACC + (255,))
    nb.alpha_composite(t, (int(1.6 * U - m["pad"]), int(1.0 * U + m["cap"] - m["base"])))
    im.alpha_composite(nb, (int(0.55 * W), int(0.62 * H)))
    return im.convert("RGB")


def preview():
    o = load(OPT)
    if not o:
        raise SystemExit(f"Write the options first: {OPT}")
    name = load_profile().get("channel_name")
    cells = []
    for i, pal in enumerate(o["palettes"], 1):
        for j, pair in enumerate(o["fonts"], 1):
            img = sample(profile_with(pal["colors"], font_files(pair)), name)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=82)
            cells.append(f'<figure><img src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}" alt="Palette {i}, fonts {j}">'
                         f'<figcaption><b>Palette {i} · {pal["name"]}</b> + <b>fonts {j}</b>: {pair["heading"]} / {pair["body"]}</figcaption></figure>')
    page = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Brand options</title>"
            "<style>body{margin:0;font:15px/1.5 system-ui;background:#f4f4f2;color:#111}main{max-width:1100px;margin:0 auto;padding:24px 16px;"
            "display:grid;gap:22px}img{width:100%;border-radius:6px}figcaption{margin-top:6px}</style><main><h1>Pick a palette and a font pair</h1>"
            "<p>Say for example: «palette 2 with fonts 1».</p>" + "".join(cells) + "</main>")
    out = ROOT / "work" / "brand" / "preview.html"
    out.write_text(page, encoding="utf-8")
    print(f"{len(cells)} combinations → {out.relative_to(ROOT).as_posix()}")


def apply(pi, fj):
    o = load(OPT)
    pal, pair = o["palettes"][pi - 1], o["fonts"][fj - 1]
    files = font_files(pair)
    dest = {}
    for role, f in files.items():
        d = ROOT / "assets" / "fonts" / f.name
        shutil.copy2(f, d)
        dest[role] = d
    prof = profile_with(pal["colors"], dest)
    name = (prof.get("channel_name") or "").upper() or "CHANNEL NAME"
    brand = ROOT / "assets" / "brand"
    brand.mkdir(parents=True, exist_ok=True)
    for fname, (w, h), safe in (("end_card.png", (3840, 2160), 0.8), ("youtube_banner.png", (2560, 1440), 1546 / 2560)):
        cv = Canvas(w, h, 24, prof)
        im = Image.new("RGBA", (w, h), cv.DARK + (255,))
        px = cv.fit([name], "heading", 7 * cv.U, safe * w * 0.85)
        t, m = cv.line([(name, cv.LIGHT)], "heading", px)
        y = (0.16 * h) if fname == "end_card.png" else (h / 2 - m["cap"] / 2)     # end card: name on top, room for YouTube's elements
        im.alpha_composite(t, (int(w / 2 - m["w"] / 2 - m["pad"]), int(y + m["cap"] - m["base"])))
        ImageDraw.Draw(im).rectangle([w / 2 - 0.04 * w, y + m["cap"] + 0.02 * h, w / 2 + 0.04 * w, y + m["cap"] + 0.02 * h + 0.006 * w],
                                     fill=cv.ACC + (255,))
        im.convert("RGB").save(brand / fname)
    pf = ROOT / "CHANNEL_PROFILE.md"
    txt = pf.read_text(encoding="utf-8")
    mt = re.search(r"```json\s*\n(.*?)```", txt, re.S)
    j = json.loads(mt.group(1))
    j["colors"] = pal["colors"]
    j["fonts"] = {"heading": f"{pair['heading']} ExtraBold", "body": f"{pair['body']} SemiBold",
                  "heading_file": f"assets/fonts/{dest['heading'].name}", "body_file": f"assets/fonts/{dest['body'].name}",
                  "light_file": f"assets/fonts/{dest['light'].name}"}
    j["banner_file"] = "assets/brand/end_card.png"
    txt = txt[:mt.start(1)] + json.dumps(j, ensure_ascii=False, indent=2) + "\n" + txt[mt.end(1):]
    pf.write_text(txt, encoding="utf-8")
    print(f"Applied palette «{pal['name']}» + {pair['heading']} / {pair['body']}: fonts in assets/fonts/, "
          f"assets/brand/end_card.png + youtube_banner.png, CHANNEL_PROFILE.md updated.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--preview" in sys.argv:
        preview()
    elif "--apply" in sys.argv and len(sys.argv) >= 4:
        i = sys.argv.index("--apply")
        apply(int(sys.argv[i + 1]), int(sys.argv[i + 2]))
    else:
        raise SystemExit(__doc__)
