"""Shared look for the review pages (gates, storyboard, publishing package): the channel's palette and heading font,
light and dark mode, readable on a phone. Each page: page(title, body_html) → full HTML string."""
import html

from .profile import load_profile

E = html.escape


def _mix(hex_a, hex_b, t):
    a = [int(hex_a.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(hex_b.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def css(prof=None):
    p = prof or load_profile()
    c = p["colors"]
    bg, ink, acc, neu = c["background"], c["dark"], c["accent"], c["neutral"]
    head = p["fonts"]["heading"].split()[0]
    gf = head.replace(" ", "+")
    dark_bg, dark_ink = _mix(ink, "#000000", 0.25), _mix(bg, "#FFFFFF", 0.3)
    return f"""<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={gf}:wght@400;600;800&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{ --bg:{bg}; --paper:{_mix(bg, '#FFFFFF', 0.55)}; --ink:{ink}; --muted:{_mix(ink, bg, 0.45)}; --rule:{_mix(ink, bg, 0.82)};
  --accent:{acc}; --neutral:{neu}; --warn:#B7791F; --bad:#B42318;
  --display:"{head}",system-ui,sans-serif; --body:"{head}",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,monospace; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:{dark_bg}; --paper:{_mix(dark_bg, '#FFFFFF', 0.06)};
  --ink:{dark_ink}; --muted:{_mix(dark_ink, dark_bg, 0.4)}; --rule:{_mix(dark_ink, dark_bg, 0.8)}; --accent:{_mix(acc, '#FFFFFF', 0.15)};
  --warn:#E0A84A; --bad:#F97066; color-scheme:dark }} }}
:root[data-theme="dark"] {{ --bg:{dark_bg}; --paper:{_mix(dark_bg, '#FFFFFF', 0.06)}; --ink:{dark_ink}; --muted:{_mix(dark_ink, dark_bg, 0.4)};
  --rule:{_mix(dark_ink, dark_bg, 0.8)}; --accent:{_mix(acc, '#FFFFFF', 0.15)}; --warn:#E0A84A; --bad:#F97066; color-scheme:dark }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.6 var(--body); }}
.wrap {{ max-width:900px; margin:0 auto; padding:32px 16px 64px; display:grid; gap:28px; }}
h1 {{ font:800 clamp(26px,5vw,38px)/1.1 var(--display); margin:0; text-wrap:balance; }}
h1 span {{ color:var(--accent); }}
h2 {{ font:800 19px/1.2 var(--display); margin:0 0 10px; text-transform:uppercase; letter-spacing:.04em; }}
h3 {{ font:600 13px/1.2 var(--display); text-transform:uppercase; letter-spacing:.08em; color:var(--accent); margin:18px 0 4px; }}
.lede {{ color:var(--muted); margin:6px 0 0; max-width:68ch; }}
.facts {{ display:flex; flex-wrap:wrap; gap:8px 20px; font:500 13px var(--mono); color:var(--muted); }}
.facts b {{ color:var(--ink); }}
.gate {{ background:var(--ink); color:var(--bg); padding:16px 18px; border-radius:6px; }}
.gate p {{ margin:4px 0 0; }} .gate code {{ font:500 13px var(--mono); }}
.card {{ background:var(--paper); border:1px solid var(--rule); border-radius:6px; padding:12px 14px; display:grid; gap:6px; }}
.card h4 {{ margin:0; font:600 15px var(--display); }} .card p {{ margin:0; }}
.opts {{ display:flex; flex-wrap:wrap; gap:8px; font-size:13px; }}
.opts span {{ border:1px solid var(--rule); border-radius:3px; padding:1px 8px; }}
.opts span.def {{ border-color:var(--accent); color:var(--accent); font-weight:600; }}
.block {{ border-top:1px solid var(--rule); padding:10px 0 12px; display:grid; gap:6px; }}
.head {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:10px; font:500 12px var(--mono); }}
.head .t {{ font-size:15px; font-variant-numeric:tabular-nums; }} .head .id {{ color:var(--muted); }}
.head .dur {{ color:var(--muted); margin-left:auto; }}
.tag {{ background:var(--accent); color:#fff; padding:1px 7px; border-radius:3px; letter-spacing:.05em; font:500 12px var(--mono); }}
.piece {{ display:grid; grid-template-columns:150px 1fr; gap:12px; }}
.piece .src {{ font:12px/1.9 var(--mono); color:var(--muted); font-variant-numeric:tabular-nums; }}
.piece .txt {{ min-width:0; }}
.note {{ margin:2px 0 0; font-size:13px; color:var(--muted); }}
.warn {{ margin:2px 0 0; font-size:13px; color:var(--warn); font-weight:600; }}
.bad {{ color:var(--bad); font-weight:600; }}
table {{ border-collapse:collapse; width:100%; font-size:14px; }}
td, th {{ text-align:left; vertical-align:top; padding:8px 8px 8px 0; border-top:1px solid var(--rule); }}
th {{ font:600 12px var(--display); text-transform:uppercase; letter-spacing:.06em; color:var(--muted); }}
td.m {{ font:13px var(--mono); white-space:nowrap; font-variant-numeric:tabular-nums; }}
.scroll {{ overflow-x:auto; }}
ul {{ margin:0; padding-left:20px; display:grid; gap:4px; }} li {{ font-size:14px; }}
img {{ max-width:100%; height:auto; border-radius:4px; display:block; }}
code {{ font:13px var(--mono); }}
.copy {{ font:600 12px var(--body); border:1px solid var(--accent); color:var(--accent); background:transparent; border-radius:4px;
  padding:3px 10px; cursor:pointer; }}
.copy.done {{ background:var(--accent); color:#fff; }}
@media (max-width:560px) {{ .piece {{ grid-template-columns:1fr; gap:0; }} }}
</style>"""


COPY_JS = """<script>
document.querySelectorAll('button.copy').forEach(b => b.addEventListener('click', async () => {
  const t = document.getElementById(b.dataset.target).innerText;
  try { await navigator.clipboard.writeText(t); } catch (e) {
    const r = document.createRange(); r.selectNodeContents(document.getElementById(b.dataset.target));
    const s = getSelection(); s.removeAllRanges(); s.addRange(r); document.execCommand('copy'); }
  b.classList.add('done'); b.textContent = 'Copied'; setTimeout(() => { b.classList.remove('done'); b.textContent = 'Copy'; }, 1500);
}));
</script>"""


def page(title, body, prof=None, script=""):
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" "
            f"content=\"width=device-width,initial-scale=1\"><title>{E(title)}</title>{css(prof)}</head>"
            f"<body><div class=\"wrap\">{body}</div>{script}</body></html>")
