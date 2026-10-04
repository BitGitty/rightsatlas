"""seasons.py — holiday collections (Halloween, Christmas, ...) from data/collections.json.

A collection is evergreen (its page is always built), but for `lead_days` before its date
range and during it, the collection is "in season":
  - its page is featured on the home page,
  - its films jump the research queue (research_one) and the release queue (drip_publish),
  - its thin dossiers are refreshed first.
Dates are MM-DD; a range may wrap the year end (12-26 -> 01-02).

  python scripts/seasons.py           # print what is in season today
  python scripts/seasons.py --check   # self-check
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "collections.json"


def load() -> list:
    return json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else []


def _window(c: dict, today: date):
    """(start, end) of this collection's season nearest to `today`, lead time included."""
    fm, fd = map(int, c["from"].split("-"))
    tm, td = map(int, c["to"].split("-"))
    for year in (today.year - 1, today.year, today.year + 1):
        start = date(year, fm, fd)
        end = date(year + (1 if (tm, td) < (fm, fd) else 0), tm, td)
        if start - timedelta(days=c.get("lead_days", 45)) <= today <= end:
            return start - timedelta(days=c.get("lead_days", 45)), end
    return None


def in_season(today: date | None = None, collections: list | None = None) -> list:
    today = today or date.today()
    return [c for c in (load() if collections is None else collections) if _window(c, today)]


def priority_ids(today: date | None = None, collections: list | None = None) -> set:
    """Film ids (published, pending or still to research) of every in-season collection."""
    return {i for c in in_season(today, collections) for i in c.get("films", []) + c.get("research", [])}


def check() -> None:
    hw = {"slug": "h", "from": "10-01", "to": "10-31", "lead_days": 45, "films": ["a"], "research": ["b"]}
    xm = {"slug": "x", "from": "12-01", "to": "12-25", "lead_days": 45, "films": ["c"]}
    ny = {"slug": "n", "from": "12-26", "to": "01-02", "lead_days": 30, "films": ["d"]}
    cs = [hw, xm, ny]
    assert [c["slug"] for c in in_season(date(2026, 10, 5), cs)] == ["h"], "Halloween in season in early Oct"
    assert priority_ids(date(2026, 10, 5), cs) == {"a", "b"}
    assert [c["slug"] for c in in_season(date(2026, 8, 20), cs)] == ["h"], "lead time counts"
    assert in_season(date(2026, 8, 1), cs) == [], "too early"
    assert {c["slug"] for c in in_season(date(2026, 11, 20), cs)} == {"x"}, "Christmas lead time"
    assert {c["slug"] for c in in_season(date(2027, 1, 1), cs)} == {"n"}, "range wraps the year end"
    assert {c["slug"] for c in in_season(date(2026, 12, 20), cs)} == {"x", "n"}
    print("seasons self-check passed")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        for c in in_season():
            print(c["slug"], "-", len(c.get("films", [])), "films,", len(c.get("research", [])), "to research")
