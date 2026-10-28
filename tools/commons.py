"""Wikimedia Commons: find and download REAL images (public people, places, works) with the licence read from Commons'
official API (nothing is guessed). For lines that name something concrete (rules §3, level 1).

Usage:
  python tools/commons.py search "<query>" [--n 12]
      lists files with licence, author, required attribution and whether a deletion request exists. Only free licences
      (public domain, CC0, CC BY, CC BY-SA) with no deletion request are marked USABLE; under 1280 px wide = framed card only.
  python tools/commons.py get "<File:Name.jpg>" <destination.jpg> [--width 1920]
      downloads the file (or a version of that width) and writes <destination>.json, the rights record (rules H9):
      source, URL, licence, licence URL, author, attribution ready for the description, download date, query.

Policy: Wikimedia's public API, no account or login, a User-Agent naming the tool (a contact can be set in the
WIKIMEDIA_CONTACT environment variable; nothing personal is sent by default). Few queries, one download at a time.
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = "VideoFactoryKit/1.0 (video editing tool; " + os.environ.get("WIKIMEDIA_CONTACT", "no contact configured") + ")"
FREE = re.compile(r"^(public domain|pd|cc0|cc by(-sa)? ?\d|cc-by(-sa)?-\d|cc by-sa|cc by)", re.I)


def get(params):
    url = API + "?" + urllib.parse.urlencode(dict(params, format="json", formatversion="2"))
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def record(p):
    ii = (p.get("imageinfo") or [{}])[0]
    md = ii.get("extmetadata", {})
    val = lambda k: clean((md.get(k) or {}).get("value", ""))
    cats = [c.get("title", "") for c in p.get("categories", [])]
    deletion = any(re.search(r"deletion requests|copyright violations|speedy deletion|possibly unfree", c, re.I) for c in cats)
    lic = val("LicenseShortName")
    author = val("Artist") or val("Credit")
    return {"source": "Wikimedia Commons", "title": p.get("title"), "source_url": ii.get("descriptionurl"),
            "file_url": ii.get("url"), "sized_url": ii.get("thumburl"), "width": ii.get("width"), "height": ii.get("height"),
            "mime": ii.get("mime"), "licence": lic, "licence_url": val("LicenseUrl"), "author": author,
            "attribution_required": val("AttributionRequired").lower() == "true",
            "attribution": val("Attribution") or (f"{author} / {lic} / Wikimedia Commons" if author else f"{lic} / Wikimedia Commons"),
            "terms": val("UsageTerms"), "restrictions": val("Restrictions"), "description": val("ImageDescription")[:300],
            "deletion_request": deletion, "usable": bool(FREE.search(lic or "")) and not deletion and not val("Restrictions")}


def search(q, n=12, width=1920):
    d = get({"action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": q, "gsrlimit": n,
             "prop": "imageinfo|categories", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": width, "cllimit": 50})
    return [record(p) for p in sorted(d.get("query", {}).get("pages", []), key=lambda p: p.get("index", 0))]


def download(title, dest, width=1920, query=None):
    p = get({"action": "query", "titles": title, "prop": "imageinfo|categories", "iiprop": "url|size|mime|extmetadata",
             "iiurlwidth": width, "cllimit": 50})["query"]["pages"][0]
    f = record(p)
    if not f["usable"]:
        raise SystemExit(f"NOT downloaded: licence «{f['licence']}», deletion request={f['deletion_request']}, "
                         f"restrictions={f['restrictions'] or 'none'}")
    url = f["sized_url"] if (f.get("width") or 0) > width and f.get("sized_url") else f["file_url"]
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120) as r, open(dest, "wb") as out:
        out.write(r.read())
    f.update({"file": os.path.basename(dest), "downloaded_url": url, "downloaded": time.strftime("%Y-%m-%d"), "query": query,
              "modifications": "crop / scale / slow push in the video"})
    with open(os.path.splitext(dest)[0] + ".json", "w", encoding="utf-8") as fh:
        json.dump(f, fh, ensure_ascii=False, indent=1)
    return f


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "search":
        n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 12
        for f in search(sys.argv[2], n):
            if not str(f.get("mime", "")).startswith("image/"):
                continue
            if f["usable"] and (f.get("width") or 0) < 1280:
                f["usable"] = False
                f["licence"] = f"{f['licence']} · small: framed card only, never full screen"
            print(f"[{'USABLE' if f['usable'] else 'no    '}] {f['title']} · {f['width']}×{f['height']} · {f['licence'] or 'no licence'}"
                  f"{' · DELETION REQUEST' if f['deletion_request'] else ''} · {f['author'][:60]}")
            print(f"         {f['source_url']}")
    elif sys.argv[1] == "get":
        w = int(sys.argv[sys.argv.index("--width") + 1]) if "--width" in sys.argv else 1920
        f = download(sys.argv[2], sys.argv[3], w)
        print("OK", sys.argv[3], "·", f["licence"], "·", f["attribution"])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
