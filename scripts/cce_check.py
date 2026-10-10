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


def reasons(cand: dict) -> list[str]:
    """Gate reasons: a PD print claim for a renewal-era film whose renewal shows up in the CCE."""
    y = int(cand.get("year") or 0)
    if not (1931 <= y <= 1950) or cand.get("layers", {}).get("print", {}).get("status") not in PD_CLAIMS:
        return []
    try:
        hits = renewal_hits(cand["title"], y)
    except Exception as e:                     # archive.org down: say so, never pass silently
        return [f"CCE renewal check could not run ({type(e).__name__}) - retry before publishing"]
    return [f"CCE renewal list shows a renewal: {h}" for h in hits[:2]]


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
    print("cce_check self-check passed (Old Dark House renewal R258433 found)")


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
