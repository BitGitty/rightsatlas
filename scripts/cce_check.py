"""cce_check.py - look a film's renewal up in the printed Catalog of Copyright Entries ourselves.

A model once wrote that it had searched the 1959-60 renewal lists "in their entirety" and found
nothing for The Old Dark House (1932); the 1960 volume lists the renewal (R258433). So a claim of
non-renewal is never taken on the model's word: this reads the archive.org OCR of the volumes for
the film's renewal years (published year + 27 and + 28) and reports any renewal entry it finds.

A hit is strong evidence of renewal. No hit is NOT proof of non-renewal (OCR can garble a title),
so this only ever adds a block, never a pass.

  python scripts/cce_check.py <film-id>      # look one dossier up
  python scripts/cce_check.py --audit        # every live + pending page that claims PD, 1931-1950
  python scripts/cce_check.py --check        # self-check against the real Old Dark House entry
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cce_cache"            # gitignored OCR text, ~1 MB per volume
# Third Series, Parts 12-13 (motion pictures): each year's volume carries that year's renewals
VOLS = {1958: "catalogofcopyrig3121213li", 1959: "catalogofcopyrig3131213li", 1960: "catalogofcopyr3141213libr",
        1961: "catalogofcopyr3151213libr", 1962: "catalogofcopyr3161213libr", 1963: "catalogofcopyr3171213libr",
        1964: "catalogofc19643181213libr", 1965: "catalogofc19653191213libr", 1966: "catalogofc19663201213libr",
        1967: "catalogofc19673211213libr", 1968: "catalogofc19683221213libr", 1969: "catalogofc19693231213libr",
        1970: "catalogofc19703241213libr", 1971: "catalogofc19713251213libr", 1972: "catalogofc19723261213libr",
        1973: "catalogofc19733271213libr", 1974: "catalogofcopyrig3281213li", 1975: "catalogofcopyrig3291213libr",
        1976: "1976motionpictur3301213libr", 1977: "1977motionpictur3311213libr"}
PD_CLAIMS = ("verified_pd", "likely_pd")


def _text(ident: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{ident}.txt"
    if not p.exists():
        meta = json.load(urllib.request.urlopen(f"https://archive.org/metadata/{ident}", timeout=60))
        name = next(f["name"] for f in meta["files"] if f["name"].endswith("_djvu.txt"))
        raw = urllib.request.urlopen(f"https://archive.org/download/{ident}/{urllib.request.quote(name)}",
                                     timeout=300).read().decode("utf-8", "replace")
        p.write_text(raw, encoding="utf-8")
    t = p.read_text(encoding="utf-8").upper()
    return " ".join(re.sub(r"-\s*\n\s*", "", t).split())          # join hyphenated line breaks


def renewal_hits(title: str, year: int) -> list[str]:
    """Renewal entries for `title` published in `year`, from the renewal-year volumes."""
    words = re.sub(r"^(THE|A|AN)\s+", "", re.sub(r"[^A-Z0-9 ]", " ", title.upper()).strip()).split()
    if not words:
        return []
    pat = re.compile(r"\b" + r"\W+".join(map(re.escape, words)) + r"\b")
    yy = str(year)[2:]
    hits = []
    for vy in (year + 27, year + 28):
        ident = VOLS.get(vy)
        if not ident:
            continue
        t = _text(ident)
        for m in pat.finditer(t):
            win = t[m.start():m.start() + 320]
            # an entry for THIS film: (c) date in its publication year, then a renewal number
            if re.search(rf"\d{{1,2}}\s?[A-Z0-9]{{3}}\s?{yy};", win) and re.search(r"\bR\s?\d{5,6}\b", win):
                hits.append(f"{ident}: {win[:200]}")
    return hits


API = "https://api.publicrecords.copyright.gov/search_service_external/simple_search_dsl"
NUM = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight",
       "9": "nine", "10": "ten", "12": "twelve", "13": "thirteen"}


def _norm(t: str) -> str:
    w = re.sub(r"[^a-z0-9 ]", " ", t.lower()).split()
    w = [NUM.get(x, x) for x in w]
    return " ".join(w[1:] if w and w[0] in ("the", "a", "an") else w)


def online_hits(title: str, year: int) -> list[str]:
    """Renewals filed 1978+ (films from 1950 on) live only in the Copyright Office's online records.
    Search by title, both '9' and 'nine' spellings ('Plan nine from outer space', RE0000279707)."""
    want, hits, seen = _norm(title), [], set()
    for q in dict.fromkeys([title, " ".join(NUM.get(x, x) for x in title.split())]):
        url = API + "?" + urllib.parse.urlencode({"page_number": 1, "query": q, "field_type": "keyword",
                                                  "records_per_page": 100, "sort_order": "asc",
                                                  "highlight": "false", "model": ""})
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 RightsAtlas"})
        for h in json.load(urllib.request.urlopen(req, timeout=60)).get("data", []):
            s = h.get("hit") or h
            rn, rd = str(s.get("registration_number", "")), str(s.get("registration_date", ""))[:4]
            if not rn.startswith("RE") or rn in seen or not rd.isdigit():
                continue
            if _norm(str(s.get("title_concatenated", ""))).startswith(want) and year + 25 <= int(rd) <= year + 30:
                seen.add(rn)
                kind = "film" if s.get("type_of_work") == "motion_picture" else "music/other"
                hits.append(f"[{kind}] {rn} ({rd}): {str(s.get('title_concatenated'))[:90]} - {str(s.get('claimants_list'))[:80]}")
    return hits


def reasons(cand: dict) -> list[str]:
    """Gate reasons: a PD print claim for a renewal-era film whose renewal shows up in the records."""
    y = int(cand.get("year") or 0)
    if not (1931 <= y <= 1963) or cand.get("layers", {}).get("print", {}).get("status") not in PD_CLAIMS:
        return []
    try:   # printed CCE carries renewals to 1977 (films to 1950); the online records carry 1978+
        online = online_hits(cand["title"], y) if y >= 1949 else []
        hits = (renewal_hits(cand["title"], y) if y <= 1950 else []) + [h for h in online if h.startswith("[film]")]
    except Exception as e:                     # archive.org / copyright.gov down: say so, never pass silently
        return [f"renewal check could not run ({type(e).__name__}) - retry before publishing"]
    out = [f"copyright records show a renewal of the film: {h}" for h in hits[:2]]
    # a renewed SONG from the film (Charade, McLintock) only matters if we call the music free
    if cand["layers"].get("score", {}).get("status") in PD_CLAIMS:
        out += [f"music layer claims PD but a song from the film was renewed: {h}"
                for h in online if not h.startswith("[film]")][:2]
    return out


def audit() -> list[tuple]:
    out = []
    for d in ("films", "pending"):
        for p in sorted((ROOT / "data" / d).glob("*.json")):
            c = json.loads(p.read_text(encoding="utf-8"))
            r = reasons(c)
            if r:
                out.append((d, c["id"], c["layers"]["print"]["status"], r[0][:260]))
    return out


def check() -> None:
    hits = renewal_hits("The Old Dark House", 1932)
    assert any("R258433" in h.replace(" ", "") for h in hits), f"must find the real 1960 renewal, got {hits}"
    assert reasons({"year": 1932, "title": "The Old Dark House", "layers": {"print": {"status": "verified_pd"}}})
    assert not reasons({"year": 1925, "title": "The Old Dark House", "layers": {"print": {"status": "verified_pd"}}}), \
        "pre-1931 films are free by term: no lookup"
    plan9 = online_hits("Plan 9 from Outer Space", 1957)
    assert any("RE0000279707" in h and h.startswith("[film]") for h in plan9), f"must find the 1986 Plan 9 renewal online, got {plan9}"
    print("cce_check self-check passed (Old Dark House R258433 in print, Plan 9 RE0000279707 online)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:]
    if "--check" in a:
        check()
    elif "--audit" in a:
        rows = audit()
        for r in rows:
            print(" | ".join(map(str, r)))
        print(f"{len(rows)} page(s) claim PD but the CCE shows a renewal")
    else:
        c = json.loads(next((ROOT / "data").glob(f"*/{a[0]}.json")).read_text(encoding="utf-8"))
        print(renewal_hits(c["title"], c["year"]) or "no renewal entry found (not proof of non-renewal)")
