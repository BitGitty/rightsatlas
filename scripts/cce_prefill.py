"""cce_prefill.py (RightsAtlas v4 §3.2) — generate an UNDETERMINED candidate draft plus
DIY primary-source links for a queue row. This is the seed an AI agent then drafts into a
full dossier; a human approves it via promote_candidate.py. It is deliberately pessimistic:
every layer starts `undetermined`, never `likely_pd`, so nothing optimistic leaks by default.

Offline by design — no network calls (the dead NYPL /api/search of v2/v3 is gone).

  python scripts/cce_prefill.py "A Star Is Born" 1937 [US]
  python scripts/cce_prefill.py --id a-star-is-born-1937   # look title/year up in the queue
  python scripts/cce_prefill.py --check                     # self-check, writes nothing
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine import LAYERS, film_id  # noqa: E402  (shared slug + layer list)

ROOT = Path(__file__).resolve().parent.parent
CAND = ROOT / "data" / "candidates"
QUEUE = ROOT / "data" / "queues" / "research_queue_500.json"


def diy_links(title: str, renewal_years: list) -> list:
    """Primary-source links a human actually follows — NO search-API scraping, NO Wikipedia."""
    q = title.replace(" ", "+")
    yrs = ", ".join(str(y) for y in renewal_years)
    return [
        {"label": f"Stanford Copyright Renewal DB — search “{title}” (renewals ~{yrs})",
         "url": f"https://exhibits.stanford.edu/copyrightrenewals/catalog?q={q}"},
        {"label": "Catalog of Copyright Entries (archive.org) — browse the Motion Pictures "
                  "renewal-year volume by hand",
         "url": "https://archive.org/search?query=catalog+of+copyright+entries+motion+pictures"},
        {"label": "US Copyright Office public records (1978+ renewals/assignments)",
         "url": "https://publicrecords.copyright.gov/"},
    ]


def prefill(title: str, year: int, country: str = "US") -> dict:
    renewal_years = [year + 27, year + 28, year + 29]  # 1909-Act 28th-year renewal window
    return {
        "id": film_id(title, year),
        "title": title,
        "year": year,
        "country": country,
        "_prefill": True,                       # promote_candidate.py must strip this
        "last_verified": None,
        "byline": None,
        # every layer starts UNDETERMINED — never likely_pd (v4 §3.2)
        "layers": {k: {"status": "undetermined", "evidence": []} for k, _ in LAYERS},
        "renewal_search": {
            "renewal_years": renewal_years,
            "negative_result": None,            # human fills after the CCE pass
            "diy_links": diy_links(title, renewal_years),
        },
        "watch": [],
        "editorial": "",
        "faq": [],
    }


def _from_queue(fid: str) -> tuple:
    rows = json.loads(QUEUE.read_text(encoding="utf-8"))
    row = next((r for r in rows if r["id"] == fid), None)
    if not row:
        sys.exit(f"id '{fid}' not in queue")
    return row["title"], row["year"], row.get("country", "US")


def check() -> None:
    d = prefill("A Star Is Born", 1937, "US")
    assert d["id"] == "a-star-is-born-1937"
    assert all(layer["status"] == "undetermined" for layer in d["layers"].values()), "all layers undetermined"
    assert not any(layer["status"] == "likely_pd" for layer in d["layers"].values()), "never likely_pd"
    assert d["renewal_search"]["renewal_years"] == [1964, 1965, 1966]
    assert set(k for k, _ in LAYERS) <= set(d["layers"]), "all engine layers present"
    assert d["_prefill"] is True
    print("cce_prefill self-check passed")


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "--check":
        check()
        return 0
    if args[0] == "--id":
        title, year, country = _from_queue(args[1])
    else:
        title, year = args[0], int(args[1])
        country = args[2] if len(args) > 2 else "US"
    draft = prefill(title, year, country)
    CAND.mkdir(parents=True, exist_ok=True)
    out = CAND / f"{draft['id']}.json"
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}  ({len(draft['renewal_search']['diy_links'])} DIY links, "
          f"renewal years {draft['renewal_search']['renewal_years']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
