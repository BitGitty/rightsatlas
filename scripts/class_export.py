"""class_export.py — the machine-readable Public Domain Day dataset the 2027 page promises.

Journalists covering Public Domain Day need the class list before Jan 1, not dossiers after
it. This emits the class of a given publication year as JSON + CSV from the research queue,
with the layer flags that actually trip people up (URAA on foreign works, franchise
trademarks that survive expiry, modern score recordings).

Every field is derived or copied — nothing is invented. Films still under copyright get a
future PD date, never a "clear" status.

  python scripts/class_export.py           # class of 1931 -> static/class-1931.{json,csv}
  python scripts/class_export.py 1932
  python scripts/class_export.py --check
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import engine  # noqa: E402

QUEUE = ROOT / "data" / "queues" / "research_queue_500.json"
STATIC = ROOT / "static"
SITE = "https://bitgitty.github.io/rightsatlas"
FIELDS = ["id", "title", "year", "country", "us_public_domain_date", "print_status",
          "trademark_watch", "uraa_note", "score_note", "dossier_url"]


def row_to_record(row: dict, today: date | None = None) -> dict:
    """One queue row -> one dataset record. Status is computed from the clock, never asserted."""
    year, country = row["year"], (row.get("country") or "US").upper()
    pd_year = year + 96                       # 95-year term; free on Jan 1 of year+96
    free = year <= engine.pd_cutoff_year(today)
    hay = row["title"].lower()
    return {
        "id": row["id"],
        "title": row["title"],
        "year": year,
        "country": country,
        "us_public_domain_date": f"{pd_year}-01-01",
        "print_status": "public_domain_us" if free else f"protected_until_{pd_year}-01-01",
        "trademark_watch": any(f in hay for f in engine.FRANCHISE_TRADEMARK_FLAGS),
        "uraa_note": ("Foreign work: US status also turns on URAA restoration "
                      "(17 U.S.C. 104A; Golan v. Holder). Term expiry still ends it."
                      if country not in ("US", "USA") else ""),
        "score_note": ("Any score you hear on a modern copy is a separately protected "
                       "recording. The images expiring does not free that audio."),
        "dossier_url": f"{SITE}/film/{row['id']}/",
    }


def export(year: int = 1931) -> list:
    rows = [r for r in json.loads(QUEUE.read_text(encoding="utf-8")) if r["year"] == year]
    recs = sorted((row_to_record(r) for r in rows), key=lambda r: -len(r["title"]))
    recs.sort(key=lambda r: r["title"])
    STATIC.mkdir(exist_ok=True)
    (STATIC / f"class-{year}.json").write_text(json.dumps({
        "class": year,
        "us_public_domain_date": f"{year + 96}-01-01",
        "generated": date.today().isoformat(),
        "source": f"{SITE}/entering-public-domain-{year + 96}/",
        "licence": "CC0 — use it, no attribution required (a link back is appreciated)",
        "caveat": ("Term expiry frees the film print only. Score, underlying story, "
                   "trademarks and modern restorations are separate layers."),
        "count": len(recs), "films": recs,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    with (STATIC / f"class-{year}.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(recs)
    return recs


def check() -> None:
    r = row_to_record({"id": "dracula-1931", "title": "Dracula", "year": 1931, "country": "US"},
                      date(2026, 9, 1))
    assert r["us_public_domain_date"] == "2027-01-01", r
    assert r["print_status"] == "protected_until_2027-01-01", "1931 is NOT free in 2026"
    assert r["trademark_watch"] is True, "Dracula carries a live franchise mark"
    assert not r["uraa_note"], "US work needs no URAA note"
    m = row_to_record({"id": "m-1931", "title": "M", "year": 1931, "country": "DE"},
                      date(2026, 9, 1))
    assert m["uraa_note"], "foreign work must carry the URAA note"
    old = row_to_record({"id": "the-general-1926", "title": "The General", "year": 1926,
                         "country": "US"}, date(2026, 9, 1))
    assert old["print_status"] == "public_domain_us", "1926 is free as of 2026"
    print("class_export self-check passed")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--check"]
    if "--check" in sys.argv:
        check()
        raise SystemExit(0)
    y = int(args[0]) if args else 1931
    recs = export(y)
    print(f"class of {y}: {len(recs)} films -> static/class-{y}.json + .csv "
          f"({sum(1 for r in recs if r['trademark_watch'])} carry trademark flags)")
