"""Stage 3 · the Gate 1 page: brief + script + chosen takes + borderline takes + named people + facts to check +
audio of the cut + audio flags (rules H25). → gate1.html (Claude publishes it as a private page or the editor opens it).

Reads work/script_resolved.json, audio_flags.md, people_pending.md and, optionally, edit/gate1.json written by Claude:
{
  "brief": "one paragraph: what the video is, the promise, the proposed title",
  "changes": [["what", "what changed"]],                       (for a second version of the page: what was fixed)
  "decisions": [{"title": "...", "detail": "...", "options": ["default", "alternative"]}],   (borderline takes, open calls)
  "facts": [["the host says", "m:ss", "status / source"]],    (rules H3)
  "not_filmed": ["things in the outline that weren't said or filmed"],
  "text_fixes": [["whisper spelling", "correct spelling"]]    (for reading only; the cut is the audio)
}
Usage: python tools/gate1_page.py <video> [<url of the cut audio>]
"""
import sys

from vfk.kit import Video, fmt, load
from vfk.page import E, page

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
G = v.script_resolved()
if not G:
    raise SystemExit("Run build_script.py first.")
D = load(v.edit / "gate1.json", {})
FIX = D.get("text_fixes", [])
audio_url = sys.argv[2] if len(sys.argv) > 2 else f"{v.name} - cut (audio only).mp3"


def blocks():
    out, sec = [], None
    for b in G["blocks"]:
        if b["section"] != sec:
            sec = b["section"]
            out.append(f"<h3>{E(sec or '')}</h3>")
        rows = []
        for p in b["pieces"]:
            txt = p["text"]
            for a, z in FIX:
                txt = txt.replace(a, z)
            lang = f" · {p['lang'].upper()}" if p.get("lang") else ""
            rows.append(f'<div class="piece"><span class="src">{E(v.short(p["clip"]))} · {p["in"]:.1f}–{p["out"]:.1f}s{lang}</span>'
                        f'<div class="txt">{E(txt)}</div></div>')
        note = f'<p class="note">{E(b["note"])}</p>' if b.get("note") else ""
        chk = f'<p class="warn">CHECK: {E(b["check"])}</p>' if b.get("check") else ""
        out.append(f'<section class="block"><div class="head"><span class="t">{fmt(b["start_in_cut"])}</span>'
                   f'<span class="id">{b["id"]}</span><span class="tag">{E(b["role"])}</span><span class="dur">{b["dur"]:.0f}s</span></div>'
                   f'{"".join(rows)}{note}{chk}</section>')
    return "\n".join(out)


def md_items(path):
    if not path.exists():
        return [], []
    unresolved, items, cur = [], [], None
    for l in path.read_text(encoding="utf-8").splitlines():
        if l.startswith("## UNRESOLVED"):
            cur = unresolved
        elif l.startswith("## "):
            cur = items
        elif l.startswith("- ") and cur is not None:
            cur.append(l[2:])
        elif l.startswith("- "):
            items.append(l[2:])
    return unresolved, items


unresolved, flags = md_items(v.dir / "audio_flags.md")
people = (v.dir / "people_pending.md").read_text(encoding="utf-8") if (v.dir / "people_pending.md").exists() else ""
people_rows = [l[2:] for l in people.splitlines() if l.startswith("- ")]
clips_used = len({p["clip"] for b in G["blocks"] for p in b["pieces"]})
body = [f"""<header><h1>{E(G.get('title') or v.name)} · <span>Gate 1</span></h1>
<p class="lede">{E(D.get('brief', 'The script of the cut, block by block, with the takes chosen. Every word is from the footage.'))}</p></header>
<div class="facts"><span>Cut <b>{fmt(G['duration_s'])}</b></span><span><b>{len(G['blocks'])}</b> blocks</span>
<span>Clips used <b>{clips_used}</b> of {len(v.clips())}</span><span>Audio flags <b>{len(flags)}</b></span></div>
<div class="gate"><b>How to approve.</b><p>Listen to the cut ({E(audio_url.split('/')[-1])}), read the flags and the open
choices below (defaults highlighted), and write <b>approved</b> in the chat, with any changes. Nothing is designed or
rendered before that.</p><audio controls preload="none" src="{E(audio_url)}" style="width:100%;margin-top:10px"></audio></div>"""]
if unresolved:
    body.append("<section><h2 class=\"bad\">Not fixed yet</h2><ul>" + "".join(f"<li>{E(x)}</li>" for x in unresolved) + "</ul></section>")
if D.get("changes"):
    body.append("<section><h2>What changed</h2><div class=\"scroll\"><table><tr><th>What</th><th>Change</th></tr>"
                + "".join(f"<tr><td class=\"m\">{E(a)}</td><td>{E(b)}</td></tr>" for a, b in D["changes"]) + "</table></div></section>")
if D.get("decisions"):
    body.append("<section><h2>Your call</h2><div style=\"display:grid;gap:12px\">" + "".join(
        f'<article class="card"><h4>{E(d["title"])}</h4><p>{E(d.get("detail", ""))}</p><div class="opts">'
        + "".join(f'<span class="{"def" if i == 0 else ""}">{E(o)}</span>' for i, o in enumerate(d.get("options", [])))
        + "</div></article>" for d in D["decisions"]) + "</div></section>")
body.append("<section><h2>Joins to listen to</h2><p class=\"lede\" style=\"margin:0 0 8px\">Every join was already checked "
            "by Whisper on the whole cut. These are only the spots with no clean silence to cut in, or set by hand.</p>"
            + ("<ul>" + "".join(f"<li>{E(x)}</li>" for x in flags) + "</ul>" if flags else "<p>None.</p>") + "</section>")
if D.get("facts"):
    body.append("<section><h2>Facts</h2><div class=\"scroll\"><table><tr><th>The host says</th><th>Cut</th><th>Status</th></tr>"
                + "".join(f"<tr><td>{E(a)}</td><td class=\"m\">{E(m)}</td><td>{E(s)}</td></tr>" for a, m, s in D["facts"])
                + "</table></div></section>")
body.append("<section><h2>Named people</h2>" + ("<ul>" + "".join(f"<li>{E(x)}</li>" for x in people_rows) + "</ul>"
            if people_rows else "<p class=\"lede\" style=\"margin:0\">Nobody is introduced by name: no cutouts needed.</p>") + "</section>")
if D.get("not_filmed"):
    body.append("<section><h2>Not filmed or not said</h2><ul>" + "".join(f"<li>{E(x)}</li>" for x in D["not_filmed"]) + "</ul></section>")
body.append("<section><h2>Script and chosen takes</h2><p class=\"lede\" style=\"margin:0 0 6px\">Left: the clip and the "
            "seconds used inside it. The text is Whisper's; the cut is the audio.</p>" + blocks() + "</section>")
html_ = page(f"{G.get('title') or v.name} · Gate 1", "\n".join(body))
(v.dir / "gate1.html").write_text(html_, encoding="utf-8")
print(f"gate1.html ({len(html_) // 1024} KB){' · ' + str(len(unresolved)) + ' UNRESOLVED differences shown at the top' if unresolved else ''}")
