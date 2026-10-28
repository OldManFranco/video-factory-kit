"""Stage 8 · the publishing package: ONE copy-paste page (publish/copy_paste.html) with a Copy button per field, in
YouTube Studio order, plus the same texts as files in publish/ and 3 real reference frames for the thumbnails.

edit/package.json (written by Claude, rules §7):
{
  "final_title": "…", "alternatives": ["…", "…"], "titles": ["12 options, ★ on the best 3"],
  "blurb": "1–2 sentences: what the viewer gets",
  "summary": ["paragraph", "paragraph"],
  "chapters": [["B01", "Chapter name"], ["B03", "…"]],          (times come from the blocks in the final render)
  "sources": ["where the numbers on screen come from"], "credits": ["image credits (rights records)"],
  "disclaimer": "…", "hashtags": ["#…"], "tags": ["…"],
  "pinned_comment": "optional; default = the profile's links marked 'pinned'",
  "thumbnails": [{"id": "A", "text": "≤ 3 WORDS", "main": true, "frame_t": 12.3,
                  "prop": "…", "composition": "host on the left third", "expression": "…", "background": "…", "colour": "…"}],
  "end_screen": "optional note"
}
The description starts with the profile's links block (rules H16). Thumbnail prompts are for the profile's image tool.
Usage: py-render tools/build_package.py <video>
"""
import json
import sys

import numpy as np

from vfk.kit import Video, load, save
from vfk.media import ffmpeg
from vfk.page import COPY_JS, E, page
from vfk.profile import load_profile

v = Video(sys.argv[1]) if len(sys.argv) > 1 else None
if v is None:
    raise SystemExit(__doc__)
P = load(v.edit / "package.json")
if not P:
    raise SystemExit("Missing edit/package.json (rules §7).")
prof = load_profile()
G = v.script_resolved()
S = load(v.work / "sheet_resolved.json", {})
START = {b["id"]: b["start_in_cut"] for b in G["blocks"]}
PUB = v.publish
PUB.mkdir(parents=True, exist_ok=True)
finals = sorted(v.final_dir.glob("*.mp4"))
video_file = finals[-1] if finals else None
links = prof.get("links") or []


def mmss(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def where(l, place):
    w = str(l.get("where", "description")).lower()
    return place in w or (place == "description" and not w)


chapters = [f"{mmss(START[b] if i else 0)} {txt}" for i, (b, txt) in enumerate(P.get("chapters", [])) if b in START]
top = [f"{l['label']}: {l['url']}" if l.get("label") else l["url"] for l in links if where(l, "description")]
desc_lines = top + ([""] if top else []) + [P.get("blurb", "")] + [""] + [x for s in P.get("summary", []) for x in (s, "")]
if chapters:
    desc_lines += ["Chapters:", *chapters, ""]
if P.get("sources"):
    desc_lines += ["Sources:", *[f"- {s}" for s in P["sources"]], ""]
if P.get("credits"):
    desc_lines += ["Credits:", *[f"- {s}" for s in P["credits"]], ""]
if P.get("disclaimer"):
    desc_lines += [P["disclaimer"], ""]
if P.get("hashtags"):
    desc_lines += [" ".join(P["hashtags"][:3])]
desc = "\n".join(desc_lines).strip() + "\n"
pinned = P.get("pinned_comment") or "\n".join(f"{l['label']}: {l['url']}" if l.get("label") else l["url"]
                                              for l in links if where(l, "pinned"))
tags = ", ".join(P.get("tags", []))
end_at = max((e["t"] for e in S.get("elements", []) if e["type"] == "END"), default=G["duration_s"])
end_note = P.get("end_screen") or (f"Last {prof['output']['end_screen_seconds']} s (from {mmss(end_at)} to the end): "
                                   "add the subscribe button and 2 videos (latest upload + best for viewer).")

# reference frames: the sharpest frame within ±1 s of each thumbnail's moment, from the final render (or the cut)
src = video_file
(PUB / "reference_frames").mkdir(exist_ok=True)
frames = {}
for th in P.get("thumbnails", []):
    t0 = float(th.get("frame_t", 0))
    best = None
    for k, dt in enumerate(np.linspace(-1.0, 1.0, 9)):
        out = PUB / "reference_frames" / f"_try{k}.jpg"
        try:
            if src:
                ffmpeg("-y", "-ss", f"{max(0.0, t0 + dt):.3f}", "-i", src, "-frames:v", 1, "-q:v", 2, out)
            else:
                from vfk import cutreader
                args, skip = cutreader.input_args(v, max(0.0, t0 + dt), 0.3)
                ffmpeg("-y", *args, "-frames:v", 1, "-vf", cutreader.skip_filter(skip), "-q:v", 2, out)
        except Exception:  # noqa: BLE001
            continue
        import cv2
        img = cv2.imread(str(out), cv2.IMREAD_GRAYSCALE)
        sharp = float(cv2.Laplacian(img, cv2.CV_64F).var()) if img is not None else 0
        if best is None or sharp > best[0]:
            best = (sharp, out.read_bytes())
    for f in (PUB / "reference_frames").glob("_try*.jpg"):
        f.unlink()
    if best:
        dst = PUB / "reference_frames" / f"{th['id']}.jpg"
        dst.write_bytes(best[1])
        frames[th["id"]] = dst

host = prof.get("host_name") or "the host"
PROMPT = ("Use the attached video frame of {host}. Create a polished YouTube thumbnail, 16:9 (1280x720). Keep their identity, "
          "face, hair and clothes exactly as they are. {prop} {composition}, head and shoulders, face about 45-50% of the image "
          "height, looking into the camera, {expression}. Crisp detail and flattering natural light on the face. Natural skin "
          "and natural eye size. Background: {background}, slightly out of focus but recognizable. {colour} Keep the bottom "
          "third calm and a little darker, with no important details, because text will be added there later. No text, no "
          "letters, no numbers, no logos, no panels, no icons, no arrows. Photorealistic.")
prompts = {th["id"]: PROMPT.format(host=host, prop=th.get("prop", ""), composition=th.get("composition", "The host centred"),
                                   expression=th.get("expression", "a strong but natural expression"),
                                   background=th.get("background", "the place where the video was filmed"),
                                   colour=th.get("colour", "")).replace("  ", " ") for th in P.get("thumbnails", [])}

title = P["final_title"]
title_words = {w.strip(".,!?:").lower() for w in title.split()}
qa = {"links_first": all(desc.startswith(x) for x in top[:1]) if top else None,
      "chapters_ok": (not chapters) or (chapters[0].startswith("0:00") and len(chapters) >= 3),
      "description_chars": len(desc), "description_under_5000": len(desc) < 5000,
      "title_chars": len(title), "title_under_limit": len(title) <= int(prof.get("title_max_chars", 60)),
      "tags_under_500": len(tags) <= 500,
      "thumbnail_text_ok": all(len(th["text"].split()) <= int(prof["thumbnail"]["max_words"]) for th in P.get("thumbnails", [])),
      "thumbnail_text_not_in_title": all(not ({w.strip(".,!?").lower() for w in th["text"].split()} & title_words)
                                         for th in P.get("thumbnails", []))}
made = sorted((PUB / "thumbnails").glob("*.*")) if (PUB / "thumbnails").exists() else []
if made:
    from PIL import Image
    qa["thumbnails_made"] = [{"file": f.name, "size": Image.open(f).size, "mb": round(f.stat().st_size / 1e6, 2),
                              "ok": Image.open(f).size == (1280, 720) and f.stat().st_size < 2e6} for f in made]
save(PUB / "package_qa.json", qa)
for name, txt in (("title.txt", title), ("titles.txt", "\n".join(P.get("titles", []))), ("description.txt", desc),
                  ("tags.txt", tags), ("pinned_comment.txt", pinned)):
    (PUB / name).write_text(txt, encoding="utf-8")
(PUB / "thumbnail_prompts.md").write_text("\n\n".join(f"## Thumbnail {th['id']} · «{th['text']}»{' (main)' if th.get('main') else ''}\n"
                                                    f"Reference frame: reference_frames/{th['id']}.jpg\n\n{prompts[th['id']]}"
                                                    for th in P.get("thumbnails", [])), encoding="utf-8")

n = [0]


def field(label, txt, note=""):
    n[0] += 1
    return (f'<section class="card"><div class="head" style="justify-content:space-between"><h4>{E(label)}</h4>'
            f'<button class="copy" data-target="f{n[0]}">Copy</button></div>{note}'
            f'<pre id="f{n[0]}" style="white-space:pre-wrap;margin:0;font:13px/1.5 var(--mono)">{E(txt)}</pre></section>')


import base64  # noqa: E402
thumbs = ""
for th in P.get("thumbnails", []):
    img = ""
    if th["id"] in frames:
        img = f'<img src="data:image/jpeg;base64,{base64.b64encode(frames[th["id"]].read_bytes()).decode()}" alt="Reference frame {E(th["id"])}">'
    thumbs += (f'<div style="display:grid;gap:8px"><h3>{E(th["id"])} · «{E(th["text"])}»{" · main" if th.get("main") else ""}</h3>{img}'
               f'<p class="note">Reference frame on disk: publish/reference_frames/{E(th["id"])}.jpg</p>'
               + field(f"Prompt {th['id']}", prompts[th["id"]]) + "</div>")
tool = prof.get("thumbnail_image_tool") or "your image tool"
body = f"""<header><h1>{E(title)}</h1><p class="lede">Copy-paste page for YouTube Studio, in Studio order.</p></header>
<section class="card"><h4>Before you publish</h4><ul>
<li>Video file: <code>{E(video_file.relative_to(v.dir).as_posix() if video_file else 'render/final/ (not rendered yet)')}</code></li>
<li>Chapters come from this render. If you change the length in your own editor, ask Claude to re-time them.</li>
<li>Thumbnails: give each reference frame + its prompt to {E(tool)}. Save the results in <code>publish/thumbnails/</code> and Claude checks them and can add the text.</li></ul></section>
{field("Title", title)}
{field("Alternative titles (Test & compare)", chr(10).join(P.get("alternatives", [])))}
{field("Description", desc)}
<section><h2>Thumbnails</h2><p class="lede" style="margin:0 0 8px">Only the short text goes on the image (max {prof['thumbnail']['max_words']} words). No panels, arrows or extra text.</p>
<div style="display:grid;gap:18px">{thumbs}</div></section>
{field("Tags", tags)}
{field("Pinned comment", pinned)}
{field("End screen", end_note)}"""
(PUB / "copy_paste.html").write_text(page(f"{title} · upload", body, prof, COPY_JS), encoding="utf-8")
print(json.dumps(qa, ensure_ascii=False))
print("publish/copy_paste.html")
