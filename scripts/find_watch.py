"""Find a free Internet Archive copy for verified-PD films that have no watch link yet.

  python scripts/find_watch.py            # dry run: prints the proposed matches
  python scripts/find_watch.py --apply    # writes them into data/films/<id>.json "watch"

Strict match: archive.org mediatype "movies", the item title contains the film title, the year
appears in its title or date, no trailer/clip/excerpt, and at least 200 downloads (popular copies
are the full film far more often). Prints every decision so a human can spot-check.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "RightsAtlasBot/1.0 (https://rightsatlas.net)"}
BAD = re.compile(r"trailer|clip|excerpt|scene|preview|teaser|remake|review|documentary|making of|colori[sz]ed",
                 re.I)


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("&", "and")).strip()


def search(title, year):
    q = f'title:("{title}") AND mediatype:(movies)'
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        {"q": q, "fl[]": ["identifier", "title", "date", "year", "downloads"], "sort[]": "downloads desc",
         "rows": 15, "output": "json"}, doseq=True)
    docs = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))["response"]["docs"]
    for d in docs:
        t = d.get("title") if isinstance(d.get("title"), str) else " ".join(d.get("title") or [])
        when = f'{t} {d.get("date", "")} {d.get("year", "")}'
        if (norm(title) in norm(t) and str(year) in when and not BAD.search(t)
                and int(d.get("downloads") or 0) >= 200):
            return d["identifier"], t, int(d.get("downloads") or 0)
    return None


def main(apply):
    found = 0
    for p in sorted((ROOT / "data" / "films").glob("*.json")):
        f = json.loads(p.read_text(encoding="utf-8"))
        if f["layers"]["print"]["status"] != "verified_pd" or f.get("watch"):
            continue
        hit = search(f["title"], f["year"])
        time.sleep(1.5)
        print(f'{f["id"]:45} ->', f"{hit[0]}  ({hit[2]} downloads)  {hit[1][:60]}" if hit else "no safe match")
        if hit and apply:
            f["watch"] = [{"url": f"https://archive.org/details/{hit[0]}",
                           "label": f'{f["title"]} ({f["year"]}) on the Internet Archive'}]
            p.write_text(json.dumps(f, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        found += bool(hit)
    print("matches:", found)


if __name__ == "__main__":
    main("--apply" in sys.argv)
