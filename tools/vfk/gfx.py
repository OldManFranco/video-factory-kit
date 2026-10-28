"""Small motion-graphics engine (Pillow + ffmpeg): text lines measured on real font metrics, layers that pop/fade in at
their own time, and frame-by-frame composition piped into ffmpeg. Fonts and colours come from CHANNEL_PROFILE.md.

Units: U = 1 % of the frame width, so a design scales to any resolution.
"""
import math
import platform
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .kit import ROOT
from .media import tool
from .profile import load_profile, rgb


class Canvas:
    """Frame size, fps, palette and fonts of one render."""

    def __init__(self, w, h, fps, prof=None):
        self.W, self.H, self.FPS = int(w), int(h), fps
        self.U = self.W / 100.0
        p = prof or load_profile()
        c = p["colors"]
        self.BG, self.DARK, self.ACC = rgb(c["background"]), rgb(c["dark"]), rgb(c["accent"])
        self.NEU, self.LIGHT = rgb(c["neutral"]), rgb(c["light"])
        f = p["fonts"]
        bundled = ROOT / "assets" / "fonts"
        self.paths = {
            "heading": _first(ROOT / f.get("heading_file", ""), bundled / "Poppins-ExtraBold.ttf"),
            "body": _first(ROOT / f.get("body_file", ""), bundled / "Poppins-SemiBold.ttf"),
            "light": _first(ROOT / f.get("light_file", ""), bundled / "Poppins-Medium.ttf"),
        }
        self.fallback = [Path(x) for x in _system_fallbacks() if Path(x).exists()]
        self._fonts, self._cmaps = {}, {}

    # ---------------------------------------------------------------- fonts
    def font(self, name, px):
        k = (name, int(round(px)))
        if k not in self._fonts:
            path = self.paths.get(name) or name
            self._fonts[k] = ImageFont.truetype(str(path), max(4, int(round(px))))
        return self._fonts[k]

    def cmap(self, path):
        if path not in self._cmaps:
            try:
                from fontTools.ttLib import TTFont
                self._cmaps[path] = set(TTFont(str(path), fontNumber=0).getBestCmap())
            except Exception:  # noqa: BLE001
                self._cmaps[path] = None
        return self._cmaps[path]

    def runs(self, segs, name):
        """[(text, colour)] → [(text, colour, font_path)]: characters missing from the font use a system fallback."""
        main = self.paths.get(name)
        cm = self.cmap(main)
        out = []
        for txt, col in segs:
            for ch in txt:
                path = main
                if cm is not None and ord(ch) not in cm and ch != " ":
                    path = next((fb for fb in self.fallback if (self.cmap(fb) or set()) and ord(ch) in self.cmap(fb)), main)
                if out and out[-1][1] == col and out[-1][2] == path:
                    out[-1][0] += ch
                else:
                    out.append([ch, col, path])
        return out

    def _f(self, path, px):
        k = (str(path), int(round(px)))
        if k not in self._fonts:
            self._fonts[k] = ImageFont.truetype(str(path), max(4, int(round(px))))
        return self._fonts[k]

    def width(self, segs, name, px, track=0.0):
        if isinstance(segs, str):
            segs = [(segs, self.LIGHT)]
        return sum(self._f(p, px).getlength(t) + track * px * len(t) for t, _, p in self.runs(segs, name))

    def line(self, segs, name, px, track=0.0):
        """One line of text → (RGBA image, metrics {base, cap, w, pad})."""
        if isinstance(segs, str):
            segs = [(segs, self.LIGHT)]
        f = self.font(name, px)
        asc, desc = f.getmetrics()
        pad = int(px * 0.25) + 4
        w = self.width(segs, name, px, track)
        im = Image.new("RGBA", (int(math.ceil(w)) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        x, base = float(pad), pad + asc
        for t, col, path in self.runs(segs, name):
            fn = self._f(path, px)
            fill = col + (255,) if len(col) == 3 else col
            if track:
                for ch in t:
                    d.text((x, base), ch, font=fn, fill=fill, anchor="ls")
                    x += fn.getlength(ch) + track * px
            else:
                d.text((x, base), t, font=fn, fill=fill, anchor="ls")
                x += fn.getlength(t)
        cap = -f.getbbox("H", anchor="ls")[1]
        return im, {"base": base, "cap": cap, "w": w, "pad": pad}

    def fit(self, texts, name, px, max_w, track=0.0):
        """The largest size (≤ px) at which every text fits in max_w."""
        for t in texts:
            a = self.width([(t, self.LIGHT)], name, px, track)
            if a > max_w:
                px = px * max_w / a
        return px

    def wrap(self, words, name, px, max_w):
        f = self.font(name, px)
        lines, cur = [], []
        for w in words:
            test = " ".join([x if isinstance(x, str) else x[0] for x in cur + [w]])
            if cur and f.getlength(test) > max_w:
                lines.append(cur)
                cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(cur)
        return lines

    def text_layer(self, segs, name, px, cx=None, x=None, cap_cy=None, base_y=None, t0=0.0, anim="pop", track=0.0):
        """A one-line layer placed by its centre (cx) or left (x), and by the middle of the capitals or the baseline."""
        im, m = self.line(segs, name, px, track)
        left = (cx - m["w"] / 2) if cx is not None else x
        if cap_cy is not None:
            base_y = cap_cy + m["cap"] / 2
        return Layer(self, im, left - m["pad"], base_y - m["base"], t0, anim), m


def _first(*paths):
    return next((p for p in paths if p and Path(p).is_file()), None)


def _system_fallbacks():
    s = platform.system()
    if s == "Windows":
        return [r"C:\Windows\Fonts\seguisym.ttf", r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\arial.ttf"]
    if s == "Darwin":
        return ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/System/Library/Fonts/Apple Symbols.ttf",
                "/Library/Fonts/Arial Unicode.ttf"]
    return ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_inout(x):
    return 0.5 - 0.5 * math.cos(math.pi * x)


def box(w, h, colour, alpha=255, radius=0):
    im = Image.new("RGBA", (max(1, int(round(w))), max(1, int(round(h)))), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, im.width - 1, im.height - 1], int(radius), fill=tuple(colour[:3]) + (alpha,))
    return im


def with_shadow(im, dy, blur, alpha):
    m = int(blur * 1.2) + 2
    out = Image.new("RGBA", (im.width + 2 * m, im.height + 2 * m + int(dy)), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, int(255 * alpha)))
    sh.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    out.alpha_composite(sh, (m, m + int(dy)))
    out = Image.merge("RGBA", out.split()[:3] + (out.getchannel("A").filter(ImageFilter.GaussianBlur(blur / 2)),))
    out.alpha_composite(im, (m, m))
    return out, (m, m)


class Layer:
    """An image (or a function dt → image) at (x, y) top-left; enters at t0 with 'pop', 'fade' or 'none'.
    key(f) says whether the frame changes, so still frames aren't recomposed."""

    def __init__(self, cv, img, x, y, t0=0.0, anim="pop", fn=None, fn_dur=0.0, centre=None, alpha=1.0):
        self.cv, self.img, self.x, self.y, self.t0, self.anim = cv, img, x, y, t0, anim
        self.fn, self.fn_dur, self.centre, self.alpha = fn, fn_dur, centre, alpha

    def key(self, f):
        t = f / self.cv.FPS
        if t < self.t0 - 1e-6:
            return None
        k = int(round((t - self.t0) * self.cv.FPS))
        return (min(k, 6), min(k, int(self.fn_dur * self.cv.FPS) + 1) if self.fn else 0)

    def paste(self, canvas, f):
        fps = self.cv.FPS
        t = f / fps
        if t < self.t0 - 1e-6:
            return
        dt = t - self.t0
        im = self.fn(dt) if self.fn else self.img
        if im is None:
            return
        p = min(1.0, dt / (6 / fps)) if self.anim != "none" else 1.0
        s, a = 1.0, 1.0
        if self.anim == "pop":
            s, a = 0.92 + 0.08 * ease_out(p), min(1.0, p * 2.2)
        elif self.anim == "fade":
            a = ease_out(p)
        a *= self.alpha
        cx, cy = self.centre or (self.x + im.width / 2, self.y + im.height / 2)
        if abs(s - 1) > 1e-3:
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.BICUBIC)
        if a < 0.999:
            im = im.copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
        if self.centre or abs(s - 1) > 1e-3:
            x, y = int(round(cx - (cx - self.x) * s)), int(round(cy - (cy - self.y) * s))
        else:
            x, y = int(round(self.x)), int(round(self.y))
        if x >= 0 and y >= 0:
            canvas.alpha_composite(im, (x, y))
        else:
            x0, y0 = max(0, -x), max(0, -y)
            if x0 < im.width and y0 < im.height:
                canvas.alpha_composite(im.crop((x0, y0, im.width, im.height)), (max(0, x), max(0, y)))


# ---------------------------------------------------------------- output
def ffmpeg_out(cv, path, mode, fps_str):
    base = [tool("ffmpeg"), "-v", "error", "-y", "-f", "rawvideo", "-s", f"{cv.W}x{cv.H}", "-r", fps_str, "-i", "-"]
    colour = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
    if mode == "mp4":
        return base[:6] + ["-pix_fmt", "rgb24"] + base[6:] + [
            "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p", "-c:v", "libx264", "-preset", "fast",
            "-crf", "16", *colour, "-movflags", "+faststart", "-r", fps_str, str(path)]
    if mode == "mov":   # ProRes 4444 with alpha
        return base[:6] + ["-pix_fmt", "rgba"] + base[6:] + [
            "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuva444p10le", "-c:v", "prores_ks",
            "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", *colour, str(path)]
    raise ValueError(mode)


def background(cv, bg):
    kind, val = bg
    if kind == "colour":
        return Image.new("RGBA", (cv.W, cv.H), tuple(val[:3]) + (255,))
    return Image.new("RGBA", (cv.W, cv.H), (0, 0, 0, 0))


def compose(cv, bg, layers, n_frames, outputs, fps_str):
    """Draw every frame once and send it to one or more outputs [(mode, path)]. Returns the last frame (RGBA)."""
    base = background(cv, bg)
    procs = [(mode, subprocess.Popen(ffmpeg_out(cv, path, mode, fps_str), stdin=subprocess.PIPE)) for mode, path in outputs]
    prev_k, data, last = None, None, None
    for f in range(n_frames):
        k = tuple(L.key(f) for L in layers)
        if k != prev_k:
            canvas = base.copy()
            for L in layers:
                L.paste(canvas, f)
            last = canvas
            data = {"rgba": canvas.tobytes()}
            if any(m == "mp4" for m, _ in outputs):
                data["rgb"] = canvas.convert("RGB").tobytes()
            prev_k = k
        for mode, p in procs:
            p.stdin.write(data["rgb"] if mode == "mp4" else data["rgba"])
    for _, p in procs:
        p.stdin.close()
        p.wait()
        if p.returncode:
            raise RuntimeError("ffmpeg failed while writing a graphic")
    return last


def still(cv, bg, layers, n_frames):
    canvas = background(cv, bg)
    for L in layers:
        L.paste(canvas, n_frames - 1)
    return canvas
