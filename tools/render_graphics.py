"""Stages 5–6 · every element of the edit sheet rendered in the channel's style (CHANNEL_PROFILE.md: palette + fonts).

Usage: py-render tools/render_graphics.py <video> [--only E005,E007] [--types G-,LOWER] [--scale 0.25] [--no-motion]
  --scale 0.25 --no-motion  quick previews for the storyboard (Gate 2): stills only → work/graphics_preview/
  (no options)              full resolution, at the output frame rate → work/graphics/ + registry.json

Output per element:
  full-screen (BROLL, PHOTO, WEB, PEOPLE, END, every G-*)  → <id>.mp4 + <id>.png (last frame)
  overlays (LOWER, LINK, NAME, SUB)                        → <id>.mov (ProRes 4444 with alpha) + <id>.png
  PUNCH is not a graphic: compose.py zooms the picture.

Element fields by type (besides block / anchor / until / dur, see build_sheet.py):
  LOWER   text, style: dark (default: light text on dark, "accent": "word" in the accent colour) | accent | light; "high": true
  LINK    text (default "LINK IN DESCRIPTION")      NAME  name, role       SUB  text
  BROLL   clip (footage clip) or file (path inside the video folder), from (s), place (lower text burned in), credit
  WEB     file (a screen recording), place, credit
  PHOTO   file, place, place_anchor, credit, crop [x0,y0,x1,y1] (fractions)
  PEOPLE  photo (cutout PNG, assets/people/...), name, role
  G-TITLE line1, line2                              G-LIST   title, lines [{text, anchor}]
  G-COUNTER number ("$105,000", "178", "16%"), label
  G-COMPARE title, rows [[left, right] or {left, right, anchor}], highlight (row index), note
  G-BARS  title, subtitle, bars [{label, sublabel, value, value_text, anchor}], highlight [indices], max
  G-TIMELINE title, nodes [{label, text, anchor}]
  G-LINE  title, subtitle, points [[x_label, value]], highlight_last (true)
  G-WAFFLE title, subtitle, total, columns, groups [{n, text, color: dark|accent|neutral, anchor}]
  G-ICONS title, subtitle, items [{text, detail, icon: check|cross|dot|number, anchor}]
  G-FLOW  title, steps [{title, detail, anchor}]
  G-VENN  title, parts [{text, anchor}] × 3 (left, right, both)
  G-QUESTION title, questions [{text, translation, anchor}]
  G-MAP   title, countries [ISO A3 codes to highlight], points [{lon, lat, label, anchor}] (arrows from one to the next)
  END     (nothing: banner_file from the profile, or a card with the channel name)
"""
import json
import math
import sys
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from vfk import gfx
from vfk.gfx import Canvas, Layer, box, ease_inout, ease_out
from vfk.kit import ROOT, Video, load, save
from vfk.media import ffmpeg
from vfk.profile import load_profile

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
S = load(v.work / "sheet_resolved.json")
if not S:
    raise SystemExit("Run build_sheet.py first.")
prof = load_profile()
SCALE = float(sys.argv[sys.argv.index("--scale") + 1]) if "--scale" in sys.argv else 1.0
NO_MOTION = "--no-motion" in sys.argv
info = v.footage_info()
sizes = Counter((i["width"], i["height"]) for i in info.values() if i.get("type") in ("A-ROLL", "MIXED", "INTERVIEW") and "width" in i)
W0, H0 = sizes.most_common(1)[0][0] if sizes else (1920, 1080)
FPS_F = Fraction(S["fps_out"])
cv = Canvas(round(W0 * SCALE / 2) * 2, round(H0 * SCALE / 2) * 2, float(FPS_F), prof)
W, H, U = cv.W, cv.H, cv.U
FPS_STR = str(FPS_F)
OUT = v.work / ("graphics" if SCALE == 1 else "graphics_preview")
DARK, ACC, BG, LIGHT, NEU = cv.DARK, cv.ACC, cv.BG, cv.LIGHT, cv.NEU


def rel(e, item):
    return max(0.0, item.get("t", e["t"]) - e["t"])


def colour_by_name(n):
    return {"dark": DARK, "accent": ACC, "neutral": NEU, "light": LIGHT, "background": BG}.get(n, DARK)


def header(e, y=0.12, col=None):
    """Title + small subtitle at the top left."""
    col = col or DARK
    layers = []
    if e.get("title"):
        px = cv.fit([e["title"]], "heading", 4.4 * U, 0.86 * W, track=0.04)
        c, _ = cv.text_layer([(e["title"], col)], "heading", px, x=0.07 * W, cap_cy=y * H, track=0.04)
        layers.append(c)
    if e.get("subtitle"):
        c, _ = cv.text_layer([(e["subtitle"], col + (150,))], "light", 2.4 * U, x=0.07 * W, cap_cy=y * H + 5.2 * U, anim="fade")
        layers.append(c)
    return layers


# ---------------------------------------------------------------- overlays
def lower(e):
    style = e.get("style", "accent" if e["type"] == "LINK" else "dark")
    txt = e.get("text") or ("LINK IN DESCRIPTION" if e["type"] == "LINK" else "")
    if style == "dark":
        word = e.get("accent") or ""
        i = txt.find(word) if word else -1
        segs = [(txt, LIGHT)] if i < 0 else [(txt[:i], LIGHT), (word, ACC), (txt[i + len(word):], LIGHT)]
        segs, fill = [s for s in segs if s[0]], DARK
    elif style == "light":
        segs, fill = [(txt, DARK)], LIGHT
    else:
        segs, fill = [(txt, LIGHT)], ACC
    px = 3.45 * U
    padx, pady = px * 0.48, px * 0.40
    a = cv.width(segs, "heading", px)
    if a + 2 * padx > 0.88 * W:
        px *= (0.88 * W - 2 * padx) / (a + 2 * padx)
        padx, pady = px * 0.48, px * 0.40
    im, m = cv.line(segs, "heading", px)
    bw, bh = m["w"] + 2 * padx, m["cap"] + 2 * pady
    b = box(bw, bh, fill, 255, 0.35 * U)
    b.alpha_composite(im, (int(round(padx - m["pad"])), int(round(pady + m["cap"] - m["base"]))))
    y = H * (1 - (0.19 if e.get("high") else 0.10)) - bh      # clear of YouTube's controls; "high": above subtitles
    return ("clear", None), [Layer(cv, b, (W - bw) / 2, y)], {"text": txt}


def subtitle(e):
    px = 3.0 * U
    rows = [" ".join(l) for l in cv.wrap(e["text"].split(), "body", px, 0.80 * W)]
    if len(rows) > 2:
        px *= 0.86
        rows = [" ".join(l) for l in cv.wrap(e["text"].split(), "body", px, 0.86 * W)]
    padx, pady, lh = px * 0.55, px * 0.32, px * 1.32
    ims = [cv.line([(r, LIGHT)], "body", px) for r in rows]
    bw = max(m["w"] for _, m in ims) + 2 * padx
    bh = lh * len(ims) + 2 * pady - (lh - px * 1.05)
    b = box(bw, bh, DARK, 200, 0.5 * U)
    y = pady
    for im, m in ims:
        b.alpha_composite(im, (int(round((bw - m["w"]) / 2 - m["pad"])), int(round(y + px * 0.86 - m["base"]))))
        y += lh
    return ("clear", None), [Layer(cv, b, (W - bw) / 2, H * (1 - 0.06) - bh, 0.0, "none")], {"text": e["text"]}


def name_card(e):
    """Small card for someone the host talks to: NAME + a 1–2 word role (rules D14), left, above the subtitle band."""
    p1, p2 = 2.5 * U, 1.75 * U
    im1, m1 = cv.line([(e["name"].upper(), LIGHT)], "heading", p1)
    im2, m2 = cv.line([(e.get("role", ""), BG)], "light", p2)
    padx, pady, bar = 1.4 * U, 1.0 * U, 0.35 * U
    bw = max(m1["w"], m2["w"]) + 2 * padx + bar
    bh = m1["cap"] + p2 + 0.9 * U + 2 * pady
    b = box(bw, bh, DARK, 235, 0.45 * U)
    ImageDraw.Draw(b).rectangle([0, 0, int(bar), b.height - 1], fill=ACC + (255,))
    x0 = bar + padx
    b.alpha_composite(im1, (int(round(x0 - m1["pad"])), int(round(pady + m1["cap"] - m1["base"]))))
    b.alpha_composite(im2, (int(round(x0 - m2["pad"])), int(round(pady + m1["cap"] + 0.9 * U + p2 * 0.78 - m2["base"]))))
    return ("clear", None), [Layer(cv, b, 4 * U, H * 0.66 - bh)], {"text": f'{e["name"]} · {e.get("role", "")}'}


# ---------------------------------------------------------------- graphics
def g_title(e):
    p1 = 4.4 * U
    p2 = cv.fit([e["line2"]], "heading", 10 * U, 0.9 * W)
    tot = p1 * 1.35 + p2
    y = (H - tot) / 2
    c1, _ = cv.text_layer([(e.get("line1", ""), DARK)], "body", p1, cx=W / 2, cap_cy=y + p1 * 0.6, track=0.06)
    c2, _ = cv.text_layer([(e["line2"], ACC)], "heading", p2, cx=W / 2, cap_cy=y + p1 * 1.35 + p2 * 0.42, t0=0.15)
    return ("colour", BG), [c1, c2], {"line1": e.get("line1"), "line2": e["line2"]}


def g_list(e):
    lines = [x if isinstance(x, dict) else {"text": x} for x in e["lines"]]
    px = cv.fit([x["text"] for x in lines], "heading", 6 * U, 0.86 * W)
    gap = 1.2 * U
    tot = len(lines) * px * 1.05 + gap * (len(lines) - 1) + (4.2 * U * 1.2 + gap if e.get("title") else 0)
    y = (H - tot) / 2
    layers = []
    if e.get("title"):
        c, _ = cv.text_layer([(e["title"], LIGHT + (170,))], "body", 4.2 * U, cx=W / 2, cap_cy=y + 4.2 * U * 0.6, track=0.12)
        layers.append(c)
        y += 4.2 * U * 1.2 + gap
    for x in lines:
        c, _ = cv.text_layer([(x["text"], ACC)], "heading", px, cx=W / 2, cap_cy=y + px * 0.52, t0=rel(e, x))
        layers.append(c)
        y += px * 1.05 + gap
    return ("colour", DARK), layers, {"lines": [x["text"] for x in lines]}


def g_counter(e):
    num, label = str(e["number"]), e.get("label", "")
    npx = cv.fit([num], "heading", 17 * U, 0.9 * W)
    lpx = cv.fit([label], "heading", 4.6 * U, 0.9 * W, track=0.06) if label else 0
    gap = 4.2 * U
    tot = npx * 0.72 + (gap + lpx * 0.72 if label else 0)
    y = (H - tot) / 2
    import re
    m_ = re.fullmatch(r"(\D*)([\d,]+)(\D*)", num)              # "$105,000" → "$", "105,000", ""
    target = int(m_.group(2).replace(",", "")) if m_ else 0
    cache = {}

    def counting(dt):
        val = int(round(target * ease_out(min(1.0, dt / 0.9))))
        body = f"{val:,}" if "," in m_.group(2) else str(val)
        txt = m_.group(1) + body + m_.group(3)
        if txt not in cache:
            im, m = cv.line([(txt, ACC)], "heading", npx)
            cache[txt] = (im, m)
        return cache[txt][0]
    _, mfull = cv.line([(num, ACC)], "heading", npx)
    layers = [Layer(cv, None, W / 2 - mfull["w"] / 2 - mfull["pad"], y + npx * 0.36 + mfull["cap"] / 2 - mfull["base"], 0.0, "pop",
                    fn=counting if target and not NO_MOTION else (lambda dt: cv.line([(num, ACC)], "heading", npx)[0]), fn_dur=1.0)]
    if label:
        c, _ = cv.text_layer([(label, LIGHT)], "heading", lpx, cx=W / 2, cap_cy=y + npx * 0.72 + gap + lpx * 0.36, t0=0.25, track=0.06)
        layers.append(c)
    return ("colour", DARK), layers, {"number": num, "label": label}


def g_compare(e):
    rows = [r if isinstance(r, dict) else {"left": r[0], "right": r[1]} for r in e["rows"]]
    x0, x1 = 0.07 * W, 0.93 * W
    rpx = 5.2 * U
    for r in rows:
        need = cv.width([(r["left"], DARK)], "body", rpx) + cv.width([(r["right"], DARK)], "heading", rpx) + 3 * U
        if need > x1 - x0:
            rpx *= (x1 - x0) / need
    tpx = cv.fit([e.get("title", "")], "heading", 5 * U, x1 - x0, track=0.04)
    gap = 1.6 * U
    while True:
        row_h = rpx * 1.25 + 1.3 * U
        tot = tpx * 1.2 + 1 * U + gap + len(rows) * row_h + (len(rows) - 1) * gap + (gap + 3.4 * U * 1.3 if e.get("note") else 0)
        if tot <= 0.86 * H:
            break
        rpx, tpx, gap = rpx * 0.95, tpx * 0.97, gap * 0.95
    y = (H - tot) / 2
    layers = []
    if e.get("title"):
        c, _ = cv.text_layer([(e["title"], DARK)], "heading", tpx, x=x0, cap_cy=y + tpx * 0.6, track=0.04)
        layers.append(c)
    y += tpx * 1.2 + 1 * U + gap
    for i, r in enumerate(rows):
        col = ACC if i == e.get("highlight") else DARK
        t0 = rel(e, r) if r.get("anchor") else 0.45 * i
        row = Image.new("RGBA", (int(x1 - x0), int(row_h)), (0, 0, 0, 0))
        ia, ma = cv.line([(r["left"], col)], "body", rpx)
        ib, mb = cv.line([(r["right"], col)], "heading", rpx)
        cy = rpx * 0.62
        row.alpha_composite(ia, (int(-ma["pad"]), int(cy + ma["cap"] / 2 - ma["base"])))
        row.alpha_composite(ib, (int(row.width - mb["w"] - mb["pad"]), int(cy + mb["cap"] / 2 - mb["base"])))
        ImageDraw.Draw(row).rectangle([0, int(row_h - 0.3 * U), row.width, int(row_h)], fill=DARK + (34,))
        layers.append(Layer(cv, row, x0, y, t0))
        y += row_h + gap
    if e.get("note"):
        c, _ = cv.text_layer([(e["note"], DARK + (153,))], "light", 3.4 * U, x=x0, cap_cy=y + 1.7 * U, t0=0.5, anim="fade")
        layers.append(c)
    return ("colour", BG), layers, {"title": e.get("title"), "rows": [[r["left"], r["right"]] for r in rows]}


def g_bars(e):
    bars = e["bars"]
    hi = set(e.get("highlight", []))
    vmax = e.get("max") or max(b["value"] for b in bars) * 1.1
    layers = header(e)
    n = len(bars)
    y0, y1 = 0.26 * H, 0.92 * H
    row = (y1 - y0) / n
    bx0, bx1 = 0.37 * W, 0.80 * W
    npx = cv.fit([b["label"] for b in bars], "heading", 2.9 * U, bx0 - 0.07 * W - 1.6 * U)
    thick = row * 0.56
    for i, b in enumerate(bars):
        cy = y0 + row * (i + 0.5)
        col = ACC if i in hi else DARK
        t0 = rel(e, b) if b.get("anchor") else 0.35 * i
        c, _ = cv.text_layer([(b["label"], col)], "heading", npx, x=0.07 * W, cap_cy=cy - (1.3 * U if b.get("sublabel") else 0), t0=t0, anim="fade")
        layers.append(c)
        if b.get("sublabel"):
            c, _ = cv.text_layer([(b["sublabel"], DARK + (150,))], "body", 2.0 * U, x=0.07 * W, cap_cy=cy + 2.0 * U, t0=t0, anim="fade")
            layers.append(c)
        length = (bx1 - bx0) * b["value"] / vmax

        def bar(dt, length=length, col=col):
            f = 1.0 if NO_MOTION else ease_out(min(1.0, dt / 0.6))
            w = max(2, int(length * f))
            im = Image.new("RGBA", (w, int(thick)), (0, 0, 0, 0))
            ImageDraw.Draw(im).rounded_rectangle([0, 0, w - 1, int(thick) - 1], int(thick * 0.18), fill=col + (255,))
            return im
        layers.append(Layer(cv, None, bx0, cy - thick / 2, t0, "none", fn=bar, fn_dur=0.7))
        txt = b.get("value_text") or f"{b['value']:g}"
        im, m = cv.line([(txt, col)], "heading", 2.6 * U)
        layers.append(Layer(cv, im, bx0 + length + 0.8 * U - m["pad"], cy + m["cap"] / 2 - m["base"], t0 + 0.55))
    return ("colour", BG), layers, {"title": e.get("title"), "bars": [(b["label"], b["value"]) for b in bars]}


def g_timeline(e):
    nodes = e["nodes"]
    layers = header(e)
    n = len(nodes)
    xs = [0.12 * W + i * (0.76 * W) / max(1, n - 1) for i in range(n)] if n > 1 else [W / 2]
    y = 0.58 * H
    times = [rel(e, nd) if nd.get("anchor") else 0.5 * i for i, nd in enumerate(nodes)]
    thick = max(3, int(0.45 * U))
    cache = {}

    def track(dt):
        k = int(round(dt * cv.FPS))
        if k in cache:
            return cache[k]
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.line([(0.06 * W, y), (0.94 * W, y)], fill=DARK + (45,), width=thick)
        reached = 0.06 * W
        for x, t in zip(xs, times):
            f = 1.0 if NO_MOTION else min(1.0, max(0.0, (dt - (t - 0.35)) / 0.35))
            if f <= 0:
                break
            reached = reached + (x - reached) * ease_out(f)
            if f < 1:
                break
        d.line([(0.06 * W, y), (reached, y)], fill=ACC + (255,), width=thick)
        cache[k] = im
        return im
    layers.append(Layer(cv, None, 0, 0, 0.0, "none", fn=track, fn_dur=max(times) + 0.5))
    lpx = cv.fit([nd["label"] for nd in nodes], "heading", 6.5 * U, 0.8 * W / max(1, n))
    tpx = 2.6 * U
    for i, (nd, x, t0) in enumerate(zip(nodes, xs, times)):
        dot = Image.new("RGBA", (int(2.6 * U), int(2.6 * U)), (0, 0, 0, 0))
        ImageDraw.Draw(dot).ellipse([0, 0, dot.width - 1, dot.height - 1], fill=ACC + (255,))
        layers.append(Layer(cv, dot, x - dot.width / 2, y - dot.height / 2, t0))
        up = i % 2 == 0
        c, _ = cv.text_layer([(nd["label"], DARK)], "heading", lpx, cx=x, cap_cy=y + (-6.0 if up else 6.0) * U, t0=t0)
        layers.append(c)
        if nd.get("text"):
            rows = [" ".join(l) for l in cv.wrap(nd["text"].split(), "body", tpx, 0.84 * W / max(1, n))]
            for j, r in enumerate(rows[:3]):
                yy = y + ((-12.0 - 3.4 * (len(rows[:3]) - 1 - j)) if up else (11.0 + 3.4 * j)) * U
                c, _ = cv.text_layer([(r, DARK + (190,))], "body", tpx, cx=x, cap_cy=yy, t0=t0 + 0.12, anim="fade")
                layers.append(c)
    return ("colour", BG), layers, {"title": e.get("title"), "nodes": [(nd["label"], nd.get("text")) for nd in nodes]}


def g_line(e):
    pts = e["points"]
    layers = header(e)
    vals = [p[1] for p in pts]
    vmin, vmax = e.get("range", [min(vals) * 0.9, max(vals) * 1.1])
    x0, x1, y0, y1 = 0.12 * W, 0.86 * W, 0.84 * H, 0.30 * H
    xs = [x0 + (x1 - x0) * i / max(1, len(pts) - 1) for i in range(len(pts))]
    ys = [y0 - (y0 - y1) * (val - vmin) / max(1e-9, vmax - vmin) for val in vals]
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.line([(x0, y0), (x1, y0)], fill=DARK + (60,), width=max(2, int(0.12 * U)))
    step = max(1, len(pts) // 8)
    for i, (p, x) in enumerate(zip(pts, xs)):
        if i % step == 0 or i == len(pts) - 1:
            im, m = cv.line([(str(p[0]), DARK + (160,))], "body", 2.2 * U)
            base.alpha_composite(im, (int(x - m["w"] / 2 - m["pad"]), int(y0 + 3.0 * U - m["base"])))
    layers.append(Layer(cv, base, 0, 0, 0.0, "fade"))
    T = e.get("draw_seconds", 2.0)
    thick = max(3, int(0.5 * U))
    hl = e.get("highlight_last", True)
    cache = {}

    def draw(dt):
        k = int(round(dt * cv.FPS))
        if k in cache:
            return cache[k]
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im)
        p = (1.0 if NO_MOTION else min(1.0, dt / T)) * (len(pts) - 1)
        line = [(xs[0], ys[0])]
        for i in range(1, len(pts)):
            f = min(1.0, max(0.0, p - (i - 1)))
            if f <= 0:
                break
            line.append((xs[i - 1] + (xs[i] - xs[i - 1]) * f, ys[i - 1] + (ys[i] - ys[i - 1]) * f))
        dd.line(line, fill=DARK + (255,), width=thick, joint="curve")
        r = 0.7 * U
        hx, hy = line[-1]
        dd.ellipse([hx - r, hy - r, hx + r, hy + r], fill=(ACC if hl and p >= len(pts) - 1 else DARK) + (255,))
        cache[k] = im
        return im
    layers.append(Layer(cv, None, 0, 0, 0.0, "none", fn=draw, fn_dur=T + 0.1))
    last = f"{vals[-1]:,}" if isinstance(vals[-1], int) else f"{vals[-1]:g}"
    im, m = cv.line([(e.get("last_text", last), ACC)], "heading", 3.4 * U)
    layers.append(Layer(cv, im, min(xs[-1] - m["w"] / 2, W - m["w"] - 2 * U) - m["pad"], ys[-1] - 2.4 * U - m["base"], T))
    return ("colour", BG), layers, {"title": e.get("title"), "points": pts}


def g_waffle(e):
    groups = e["groups"]
    total = int(e["total"])
    cols = e.get("columns", 18 if total > 60 else 10)
    rows_n = math.ceil(total / cols)
    gx0, gx1, gy0, gy1 = 0.07 * W, 0.60 * W, 0.27 * H, 0.90 * H
    step = min((gx1 - gx0) / cols, (gy1 - gy0) / rows_n)
    side = step * 0.80
    times = [rel(e, g) if g.get("anchor") else 0.6 * i for i, g in enumerate(groups)]
    starts, acc = [], 0
    for g in groups:
        starts.append(acc)
        acc += int(g["n"])
    cache = {}

    def draw(dt):
        k = int(round(dt * cv.FPS))
        if k in cache:
            return cache[k]
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        state = [None] * total
        for g, t0, a in zip(groups, times, starts):
            f = 1.0 if NO_MOTION else min(1.0, max(0.0, (dt - t0) / 0.7))
            for j in range(int(round(int(g["n"]) * ease_out(f)))):
                if a + j < total:
                    state[a + j] = colour_by_name(g.get("color", "dark"))
        for i in range(total):
            r, c = divmod(i, cols)
            x, y = gx0 + c * step, gy0 + r * step
            if state[i] is None:
                d.rounded_rectangle([x, y, x + side, y + side], int(side * 0.18), outline=DARK + (60,), width=max(1, int(0.12 * U)))
            else:
                d.rounded_rectangle([x, y, x + side, y + side], int(side * 0.18), fill=state[i] + (255,))
        cache[k] = im
        return im
    layers = header(e)
    layers.append(Layer(cv, None, 0, 0, 0.0, "none", fn=draw, fn_dur=max(times) + 0.8))
    ly = 0.33 * H
    for g, t0 in zip(groups, times):
        col = colour_by_name(g.get("color", "dark"))
        c, _ = cv.text_layer([(str(g["n"]), col)], "heading", 7.2 * U, x=0.65 * W, cap_cy=ly, t0=t0)
        layers.append(c)
        tpx = cv.fit([g["text"]], "heading", 2.8 * U, 0.30 * W, track=0.04)
        c, _ = cv.text_layer([(g["text"], DARK)], "heading", tpx, x=0.65 * W, cap_cy=ly + 5.6 * U, t0=t0 + 0.1, anim="fade", track=0.04)
        layers.append(c)
        ly += 12.0 * U
    return ("colour", BG), layers, {"title": e.get("title"), "groups": [(g["n"], g["text"]) for g in groups]}


def icon(kind, d_px, n=None):
    im = Image.new("RGBA", (int(d_px), int(d_px)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = NEU if kind == "cross" else ACC
    d.ellipse([0, 0, im.width - 1, im.height - 1], fill=fill + (255,))
    g = max(3, int(d_px * 0.11))
    if kind == "check":
        d.line([(d_px * 0.27, d_px * 0.53), (d_px * 0.44, d_px * 0.69), (d_px * 0.75, d_px * 0.34)], fill=LIGHT + (255,), width=g, joint="curve")
    elif kind == "cross":
        d.line([(d_px * 0.32, d_px * 0.32), (d_px * 0.68, d_px * 0.68)], fill=LIGHT + (255,), width=g)
        d.line([(d_px * 0.68, d_px * 0.32), (d_px * 0.32, d_px * 0.68)], fill=LIGHT + (255,), width=g)
    elif kind == "number" and n is not None:
        t, m = cv.line([(str(n), LIGHT)], "heading", d_px * 0.5)
        im.alpha_composite(t, (int(d_px / 2 - m["w"] / 2 - m["pad"]), int(d_px / 2 + m["cap"] / 2 - m["base"])))
    else:
        r = d_px * 0.16
        d.ellipse([d_px / 2 - r, d_px / 2 - r, d_px / 2 + r, d_px / 2 + r], fill=LIGHT + (255,))
    return im


def g_icons(e):
    items = e["items"]
    layers = header(e, col=LIGHT)
    n = len(items)
    y0, row = 0.30 * H, min(0.17 * H, 0.62 * H / n)
    ipx = cv.fit([it["text"] for it in items], "heading", 5.0 * U, 0.66 * W)
    for i, it in enumerate(items):
        t0 = rel(e, it) if it.get("anchor") else 0.45 * i
        cy = y0 + row * (i + 0.5)
        ic = icon(it.get("icon", "check"), row * 0.62, i + 1)
        layers.append(Layer(cv, ic, 0.07 * W, cy - ic.height / 2, t0))
        x = 0.07 * W + ic.width + 2.4 * U
        dy = -1.6 * U if it.get("detail") else 0.0
        c, _ = cv.text_layer([(it["text"], LIGHT)], "heading", ipx, x=x, cap_cy=cy + dy, t0=t0)
        layers.append(c)
        if it.get("detail"):
            c, _ = cv.text_layer([(it["detail"], ACC)], "body", 2.8 * U, x=x, cap_cy=cy + 3.4 * U, t0=t0 + 0.12, anim="fade")
            layers.append(c)
    return ("colour", DARK), layers, {"title": e.get("title"), "items": [it["text"] for it in items]}


def arrow(length, col):
    g = max(3, int(0.45 * U))
    im = Image.new("RGBA", (int(length), int(3.2 * U)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    cy = im.height / 2
    d.line([(0, cy), (length - 1.8 * U, cy)], fill=col + (255,), width=g)
    d.polygon([(length - 2.2 * U, cy - 1.4 * U), (length, cy), (length - 2.2 * U, cy + 1.4 * U)], fill=col + (255,))
    return im


def g_flow(e):
    steps = e["steps"]
    layers = header(e)
    n = len(steps)
    gap = 5.0 * U
    bw = (0.86 * W - gap * (n - 1)) / n
    bh = 0.40 * H
    y = 0.36 * H
    tpx = min(cv.fit([s["title"]], "heading", 4.0 * U, bw - 4 * U) for s in steps)
    dpx = min(cv.fit([s.get("detail", "") or " "], "heading", 3.2 * U, bw - 4 * U) for s in steps)
    for i, s in enumerate(steps):
        t0 = rel(e, s) if s.get("anchor") else 0.6 * i
        x = 0.07 * W + i * (bw + gap)
        if i:
            layers.append(Layer(cv, arrow(gap * 0.8, DARK), x - gap * 0.9, y + bh / 2 - 1.6 * U, max(0.0, t0 - 0.15), "fade"))
        b = box(bw, bh, DARK, 255, 0.8 * U)
        r = 2.6 * U
        ImageDraw.Draw(b).ellipse([2.0 * U, 2.0 * U, 2.0 * U + 2 * r, 2.0 * U + 2 * r], fill=ACC + (255,))
        im, m = cv.line([(str(s.get("n", i + 1)), LIGHT)], "heading", 3.0 * U)
        b.alpha_composite(im, (int(2.0 * U + r - m["w"] / 2 - m["pad"]), int(2.0 * U + r + m["cap"] / 2 - m["base"])))
        im, m = cv.line([(s["title"], LIGHT)], "heading", tpx)
        b.alpha_composite(im, (int(2.0 * U - m["pad"]), int(bh * 0.55 + m["cap"] / 2 - m["base"])))
        if s.get("detail"):
            im, m = cv.line([(s["detail"], ACC)], "heading", dpx)
            b.alpha_composite(im, (int(2.0 * U - m["pad"]), int(bh * 0.78 + m["cap"] / 2 - m["base"])))
        layers.append(Layer(cv, b, x, y, t0))
    return ("colour", BG), layers, {"title": e.get("title"), "steps": [s["title"] for s in steps]}


def g_venn(e):
    parts = e["parts"]
    layers = header(e)
    r = 0.25 * H
    cx1, cx2, cy = W / 2 - r * 0.62, W / 2 + r * 0.62, 0.58 * H
    for i, (cx, col) in enumerate(((cx1, DARK), (cx2, ACC))):
        im = Image.new("RGBA", (int(2 * r) + 2, int(2 * r) + 2), (0, 0, 0, 0))
        ImageDraw.Draw(im).ellipse([0, 0, 2 * r, 2 * r], fill=col + (70,), outline=col + (255,), width=max(3, int(0.35 * U)))
        p = parts[i] if i < len(parts) else {}
        layers.append(Layer(cv, im, cx - r, cy - r, rel(e, p) if p.get("anchor") else 0.4 * i))
    spots = [(cx1 - r * 0.45, cy), (cx2 + r * 0.45, cy), (W / 2, cy)]
    for i, (p, (x, y)) in enumerate(zip(parts, spots)):
        t0 = rel(e, p) if p.get("anchor") else 0.4 * i + 0.2
        rows = [" ".join(l) for l in cv.wrap(p["text"].split(), "heading", 2.8 * U, r * (0.75 if i < 2 else 0.55))]
        for j, row in enumerate(rows):
            c, _ = cv.text_layer([(row, DARK)], "heading", 2.8 * U, cx=x, cap_cy=y + (j - (len(rows) - 1) / 2) * 3.6 * U, t0=t0)
            layers.append(c)
    return ("colour", BG), layers, {"title": e.get("title"), "parts": [p["text"] for p in parts]}


def g_question(e):
    qs = e["questions"]
    layers = header(e)
    y0, row = 0.32 * H, min(0.27 * H, 0.60 * H / len(qs))
    spx = cv.fit([q["text"] for q in qs], "heading", 5.0 * U, 0.74 * W)
    for i, q in enumerate(qs):
        t0 = rel(e, q) if q.get("anchor") else 0.6 * i
        cy = y0 + row * (i + 0.4)
        ic = icon("number", 6.8 * U, i + 1)
        layers.append(Layer(cv, ic, 0.07 * W, cy - ic.height / 2, t0))
        x = 0.07 * W + ic.width + 2.4 * U
        c, _ = cv.text_layer([(q["text"], DARK)], "heading", spx, x=x, cap_cy=cy - (0.6 * U if q.get("translation") else 0), t0=t0)
        layers.append(c)
        if q.get("translation"):
            c, _ = cv.text_layer([(q["translation"], DARK + (160,))], "body", 2.7 * U, x=x, cap_cy=cy + 5.0 * U, t0=t0 + 0.12, anim="fade")
            layers.append(c)
    return ("colour", BG), layers, {"title": e.get("title"), "questions": [q["text"] for q in qs]}


def g_map(e):
    """Countries from Natural Earth (public domain, assets/maps/), highlighted ones in the accent colour, and arrows
    between the points in order, each entering on its word."""
    geo = json.loads((ROOT / "assets" / "maps" / "ne_110m_admin_0_countries.geojson").read_text(encoding="utf-8"))
    hl = set(e.get("countries", []))
    pts = e.get("points", [])
    # the view frames the points (or, with no points, the highlighted countries' largest piece: no Alaska zoom-out)
    lons, lats = [p["lon"] for p in pts], [p["lat"] for p in pts]
    if not pts:
        for f in geo["features"]:
            if f["properties"].get("ISO_A3") in hl or f["properties"].get("ADM0_A3") in hl:
                biggest = max(_polys(f["geometry"]), key=lambda pl: len(pl[0]))
                lons += [c[0] for c in biggest[0]]
                lats += [c[1] for c in biggest[0]]
    lons, lats = lons or [-180, 180], lats or [-60, 80]
    lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
    pad_lo, pad_la = max(12, (lo1 - lo0) * 0.35), max(8, (la1 - la0) * 0.35)
    lo0, lo1, la0, la1 = lo0 - pad_lo, lo1 + pad_lo, la0 - pad_la, la1 + pad_la
    mx0, mx1, my0, my1 = 0.05 * W, 0.95 * W, 0.20 * H, 0.95 * H
    sc = min((mx1 - mx0) / (lo1 - lo0), (my1 - my0) / (_merc(la1) - _merc(la0)))
    ox = (mx0 + mx1) / 2 - sc * (lo0 + lo1) / 2
    oy = (my0 + my1) / 2 + sc * (_merc(la0) + _merc(la1)) / 2
    proj = lambda lon, lat: (ox + sc * lon, oy - sc * _merc(lat))
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    for f in geo["features"]:
        on = f["properties"].get("ISO_A3") in hl or f["properties"].get("ADM0_A3") in hl
        for poly in _polys(f["geometry"]):
            ring = [proj(*c) for c in poly[0]]
            d.polygon(ring, fill=(ACC if on else NEU) + (255 if on else 90,), outline=BG + (255,))
    layers = header(e)
    layers.insert(0, Layer(cv, base, 0, 0, 0.0, "fade"))
    for i, p in enumerate(pts):
        t0 = rel(e, p) if p.get("anchor") else 0.6 * i
        x, y = proj(p["lon"], p["lat"])
        r = 1.1 * U
        dot = Image.new("RGBA", (int(2 * r) + 2, int(2 * r) + 2), (0, 0, 0, 0))
        ImageDraw.Draw(dot).ellipse([0, 0, 2 * r, 2 * r], fill=DARK + (255,), outline=LIGHT + (255,), width=max(2, int(0.25 * U)))
        layers.append(Layer(cv, dot, x - r, y - r, t0))
        if p.get("label"):
            im, m = cv.line([(p["label"], LIGHT)], "heading", 2.6 * U)
            b = box(m["w"] + 2 * U, m["cap"] + 1.6 * U, DARK, 235, 0.3 * U)
            b.alpha_composite(im, (int(1 * U - m["pad"]), int(0.8 * U + m["cap"] - m["base"])))
            layers.append(Layer(cv, b, min(x + 1.6 * U, W - b.width - U), y - b.height - 1.2 * U, t0 + 0.1))
        if i:
            (ax, ay), (bx, by) = proj(pts[i - 1]["lon"], pts[i - 1]["lat"]), (x, y)

            def fly(dt, ax=ax, ay=ay, bx=bx, by=by):
                f = 1.0 if NO_MOTION else ease_inout(min(1.0, dt / 0.8))
                im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                dd = ImageDraw.Draw(im)
                mx, my = (ax + bx) / 2, (ay + by) / 2 - math.hypot(bx - ax, by - ay) * 0.2
                curve = [((1 - s) ** 2 * ax + 2 * (1 - s) * s * mx + s ** 2 * bx, (1 - s) ** 2 * ay + 2 * (1 - s) * s * my + s ** 2 * by)
                         for s in [k / 40 * f for k in range(41)]]
                dd.line(curve, fill=DARK + (255,), width=max(3, int(0.4 * U)), joint="curve")
                return im
            layers.append(Layer(cv, None, 0, 0, max(0.0, t0 - 0.5), "none", fn=fly, fn_dur=0.85))
    return ("colour", BG), layers, {"title": e.get("title"), "countries": sorted(hl), "points": [p.get("label") for p in pts]}


def _merc(lat):
    lat = max(-85.0, min(85.0, lat))
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def _polys(g):
    return [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []


def people(e):
    """A named person (rules §4): their approved cutout on the left, the name typed in an accent box and the role below."""
    layers = []
    photo = Image.open(v.dir / e["photo"] if (v.dir / e["photo"]).exists() else ROOT / e["photo"]).convert("RGBA")
    col_w = 0.40 * W
    s = min(0.88 * H / photo.height, col_w * 1.05 / photo.width)
    ph = photo.resize((int(photo.width * s), int(photo.height * s)), Image.LANCZOS)
    layers.append(Layer(cv, ph, (col_w - ph.width) / 2 + 0.02 * W, H - ph.height, 0.0, "fade"))
    x0 = col_w + 0.05 * W
    name, role = e["name"].upper(), e.get("role", "").upper()
    npx = cv.fit([name], "heading", 5.6 * U, W - 0.06 * W - x0 - 4.8 * U)
    rpx = cv.fit([role], "heading", 3.6 * U, W - 0.06 * W - x0, track=0.06)
    _, mfull = cv.line([(name, LIGHT)], "heading", npx)
    bh = mfull["cap"] + 2 * U + npx * 0.25
    y = (H - (bh + 1.6 * U + rpx * 0.9)) / 2
    cps = max(len(name) / 0.75, 22)
    cache = {}

    def typing(dt):
        n = len(name) if NO_MOTION else max(1, min(len(name), int(dt * cps) + 1))
        if n not in cache:
            im, m = cv.line([(name[:n], LIGHT)], "heading", npx)
            b = box(m["w"] + 4.8 * U, bh, ACC)
            b.alpha_composite(im, (int(2.4 * U - m["pad"]), int(bh / 2 + m["cap"] / 2 - m["base"])))
            cache[n] = b
        return cache[n]
    layers.append(Layer(cv, None, x0, y, 0.2, "none", fn=typing, fn_dur=len(name) / cps + 0.1))
    c, _ = cv.text_layer([(role, DARK)], "heading", rpx, x=x0, cap_cy=y + bh + 1.6 * U + rpx * 0.36,
                         t0=0.3 + len(name) / cps, anim="fade", track=0.06)
    layers.append(c)
    return ("colour", BG), layers, {"name": e["name"], "role": e.get("role")}


def end_screen(e):
    """The last seconds, for YouTube's end-screen elements: the profile's banner, or a calm card with the channel name."""
    bf = prof.get("banner_file")
    if bf and (ROOT / bf).exists():
        ban = Image.open(ROOT / bf).convert("RGBA")
        s = max(W / ban.width, H / ban.height)
        ban = ban.resize((int(ban.width * s) + 1, int(ban.height * s) + 1), Image.LANCZOS)
        ban = ban.crop(((ban.width - W) // 2, (ban.height - H) // 2, (ban.width - W) // 2 + W, (ban.height - H) // 2 + H))
        return ("colour", DARK), [Layer(cv, ban, 0, 0, 0.0, "fade")], {"banner": bf}
    name = (prof.get("channel_name") or "").upper() or " "
    px = cv.fit([name], "heading", 7 * U, 0.8 * W)
    c, _ = cv.text_layer([(name, LIGHT)], "heading", px, cx=W / 2, cap_cy=0.16 * H, anim="fade")
    bar = box(0.08 * W, 0.5 * U, ACC)
    layers = [c, Layer(cv, bar, W / 2 - 0.04 * W, 0.16 * H + px * 0.7, 0.2, "fade")]
    lf = prof.get("logo_file")
    if lf and (ROOT / lf).exists():
        logo = Image.open(ROOT / lf).convert("RGBA")
        s = 0.10 * H / logo.height
        logo = logo.resize((int(logo.width * s), int(logo.height * s)), Image.LANCZOS)
        layers.append(Layer(cv, logo, W - logo.width - 3 * U, H - logo.height - 3 * U, 0.0, "fade"))
    return ("colour", DARK), layers, {"channel": prof.get("channel_name")}


# ---------------------------------------------------------------- video and photos (full screen)
def burned_box(text, style="accent"):
    _, layers, _ = lower({"type": "LOWER", "text": text, "style": style})
    return layers[0].img, layers[0].x, layers[0].y


def credit(txt):
    px = 1.25 * U
    im, m = cv.line([(txt, LIGHT + (235,))], "body", px)
    padx, pady = px * 0.55, px * 0.42
    b = box(m["w"] + 2 * padx, m["cap"] + 2 * pady, DARK, 115, 0.35 * U)
    b.alpha_composite(im, (int(round(padx - m["pad"])), int(round(pady + m["cap"] - m["base"]))))
    return b, W - b.width - 2.2 * U, H - b.height - 2.2 * U


def full_video(e, n, path):
    """BROLL / WEB at full screen, real speed, no zoom, with the place box and credit burned in."""
    if e.get("clip"):
        src = v.clip_path(e["clip"])
    else:
        src = v.dir / e["file"]
    ss = float(e.get("from", 0.0))
    over = []
    if e.get("place"):
        over.append(burned_box(e["place"], e.get("place_style", "accent")))
    if e.get("credit"):
        over.append(credit(e["credit"]))
    args = ["-y", "-ss", f"{ss:.3f}", "-i", src]
    fil = f"[0:v]fps={FPS_STR},scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1"
    if over:
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for img, x, y in over:
            canvas.alpha_composite(img, (int(round(x)), int(round(y))))
        png = OUT / "_tmp" / f"{e['id']}_over.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(png)
        args += ["-loop", "1", "-i", png]
        fil += "[b];[b][1:v]overlay=0:0:shortest=1"
    fil += ",scale=out_color_matrix=bt709:out_range=tv,format=yuv420p[v]"
    ffmpeg(*args, "-filter_complex", fil, "-map", "[v]", "-frames:v", n, "-an", "-c:v", "libx264", "-preset", "fast",
           "-crf", "16", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-r", FPS_STR, path)
    return {"source": src.name, "from": ss, "place": e.get("place")}


def full_photo(e, n, path):
    """PHOTO at full screen: covers the frame, slow push 100 → 104 %, the place name on its word, small credit.
    A vertical photo sits whole over a blurred copy of itself (rules D16)."""
    im = Image.open(v.dir / e["file"]).convert("RGB")
    if e.get("crop"):
        x0, y0, x1, y1 = e["crop"]
        im = im.crop((int(x0 * im.width), int(y0 * im.height), int(x1 * im.width), int(y1 * im.height)))
    if im.width / im.height < 1.2:
        bgim = im.resize((W, int(W * im.height / im.width)), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40 * SCALE + 4))
        bgim = bgim.crop((0, (bgim.height - H) // 2, W, (bgim.height - H) // 2 + H))
        tall = int(H * 0.92)
        fr = im.resize((int(im.width * tall / im.height), tall), Image.LANCZOS)
        bgim.paste(fr, ((W - fr.width) // 2, (H - tall) // 2))
        im = bgim
    s = max(W / im.width, H / im.height) * 1.04
    big = im.resize((int(im.width * s) + 2, int(im.height * s) + 2), Image.LANCZOS)
    place = burned_box(e["place"], e.get("place_style", "accent")) if e.get("place") else None
    f_place = int(round(e.get("place_t", 0.0) * cv.FPS))
    cred = credit(e["credit"]) if e.get("credit") else None

    def frames():
        for f in range(n):
            z = 1.0 + (0.0 if NO_MOTION else 0.04 * f / max(1, n - 1))
            cw, ch = W * (1.04 / z), H * (1.04 / z)
            x0, y0 = (big.width - cw) / 2, (big.height - ch) / 2
            fr = big.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + cw, y0 + ch))
            if (place and f >= f_place) or cred:
                fr = fr.convert("RGBA")
                if place and f >= f_place:
                    fr.alpha_composite(place[0], (int(round(place[1])), int(round(place[2]))))
                if cred:
                    fr.alpha_composite(cred[0], (int(round(cred[1])), int(round(cred[2]))))
                fr = fr.convert("RGB")
            yield fr
    import subprocess
    p = subprocess.Popen(gfx.ffmpeg_out(cv, path, "mp4", FPS_STR), stdin=subprocess.PIPE)
    last = None
    for fr in frames():
        p.stdin.write(fr.tobytes())
        last = fr
    p.stdin.close()
    p.wait()
    if last is not None:
        last.save(path.with_suffix(".png"))
    return {"source": Path(e["file"]).name, "place": e.get("place"), "credit": e.get("credit")}


TYPES = {"LOWER": lower, "LINK": lower, "SUB": subtitle, "NAME": name_card, "G-TITLE": g_title, "G-LIST": g_list,
         "G-COUNTER": g_counter, "G-COMPARE": g_compare, "G-BARS": g_bars, "G-TIMELINE": g_timeline, "G-LINE": g_line,
         "G-WAFFLE": g_waffle, "G-ICONS": g_icons, "G-FLOW": g_flow, "G-VENN": g_venn, "G-QUESTION": g_question,
         "G-MAP": g_map, "PEOPLE": people, "END": end_screen}
OVERLAYS = {"LOWER", "LINK", "SUB", "NAME"}


def render(e):
    t = e["type"]
    n = max(1, int(round(e["dur"] * cv.FPS)))
    base = OUT / e["id"]
    if t in ("BROLL", "WEB", "PHOTO"):
        if NO_MOTION:              # preview: one frame is enough
            n = 1
        path = base.with_suffix(".mp4")
        meta = full_photo(e, n, path) if t == "PHOTO" else full_video(e, n, path)
        if t != "PHOTO":
            ffmpeg("-y", "-sseof", "-0.1", "-i", path, "-frames:v", 1, "-update", 1, base.with_suffix(".png"))
        files = [path, base.with_suffix(".png")]
    else:
        if t not in TYPES:
            raise SystemExit(f"{e['id']}: unknown type {t}")
        bg, layers, meta = TYPES[t](e)
        if t in OVERLAYS:
            if NO_MOTION:
                gfx.still(cv, bg, layers, n).save(base.with_suffix(".png"))
                files = [base.with_suffix(".png")]
            else:
                last = gfx.compose(cv, bg, layers, n, [("mov", base.with_suffix(".mov"))], FPS_STR)
                last.save(base.with_suffix(".png"))
                files = [base.with_suffix(".mov"), base.with_suffix(".png")]
        else:
            if NO_MOTION:
                gfx.still(cv, bg, layers, n).convert("RGB").save(base.with_suffix(".png"))
                files = [base.with_suffix(".png")]
            else:
                last = gfx.compose(cv, bg, layers, n, [("mp4", base.with_suffix(".mp4"))], FPS_STR)
                last.convert("RGB").save(base.with_suffix(".png"))
                files = [base.with_suffix(".mp4"), base.with_suffix(".png")]
    return {"id": e["id"], "type": t, "t": e["t"], "tc": e["tc"], "dur": round(n / cv.FPS, 3), "frames": n,
            "overlay": t in OVERLAYS, "files": [f.relative_to(OUT).as_posix() for f in files], "content": meta}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    kinds = sys.argv[sys.argv.index("--types") + 1].split(",") if "--types" in sys.argv else None
    reg_p = OUT / "registry.json"
    reg = load(reg_p, {})
    keep = {e["id"] for e in S["elements"]}
    reg = {k: r for k, r in reg.items() if k in keep}          # drop elements no longer in the sheet
    t_all = time.time()
    for e in S["elements"]:
        if e["type"] == "PUNCH" or (only and e["id"] not in only) or (kinds and not any(e["type"].startswith(k) for k in kinds)):
            continue
        t0 = time.time()
        r = render(e)
        r["seconds"] = round(time.time() - t0, 1)
        reg[e["id"]] = r
        save(reg_p, dict(sorted(reg.items())))
        print(f'{e["id"]} {e["type"]:<11} {e["tc"]:>7} {r["frames"]:>5} frames {r["seconds"]:>6.1f} s → {", ".join(r["files"])}', flush=True)
    print(f"done in {time.time() - t_all:.0f} s · {W}x{H} @ {float(FPS_F):g} fps → {OUT.relative_to(v.dir).as_posix()}/")
