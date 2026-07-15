"""qc_candidate.py (RightsAtlas v4 §3.4) — automated rubric on an AI-drafted candidate
BEFORE a human spends time reviewing it. Cheap gate; catches the obvious slop.

  python scripts/qc_candidate.py data/candidates/<id>.json
  python scripts/qc_candidate.py --check
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import engine  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "data" / "queues" / "research_queue_500.json"
ADAPTED_HINTS = ("based on", "novel", "play", "story by", "adaptation", "adapted from")


def qc(cand: dict) -> list:
    """Return a list of rubric failures (empty = pass)."""
    fails = []
    # title/year/country consistency with the queue row (if present)
    if QUEUE.exists():
        rows = json.loads(QUEUE.read_text(encoding="utf-8"))
        row = next((r for r in rows if r["id"] == cand.get("id")), None)
        if row and (row["title"] != cand.get("title") or row["year"] != cand.get("year")):
            fails.append("title/year does not match the queue row")
    # no likely_pd smuggled into a candidate (v4 §3.2/§3.4)
    for k, layer in cand.get("layers", {}).items():
        if layer.get("status") == "likely_pd":
            fails.append(f"layer '{k}' is likely_pd — not allowed in a candidate")
    # editorial must not state a legal conclusion without an evidence link
    ed = (cand.get("editorial") or "").lower()
    if re.search(r"public domain|not renewed|copyright expired", ed):
        has_ev = any(L.get("evidence") for L in cand.get("layers", {}).values())
        if not has_ev:
            fails.append("editorial asserts a legal conclusion but no layer has evidence")
    # registration-number sanity (loose format check when present)
    for k, layer in cand.get("layers", {}).items():
        for ev in layer.get("evidence", []):
            rn = ev.get("registration_number")
            if rn and not re.match(r"^[A-Z]{1,3}\d{2,7}$", str(rn).replace(" ", "")):
                fails.append(f"layer '{k}': implausible registration number '{rn}'")
    # adapted-work trap: if the title/editorial smells adapted, story must be evidenced
    hay = (cand.get("title", "") + " " + ed).lower()
    if any(h in hay for h in ADAPTED_HINTS):
        story = cand.get("layers", {}).get("story", {})
        if story.get("status") in ("verified_pd", "likely_pd") and not story.get("evidence"):
            fails.append("adapted-work hint present but story layer PD-leaning without evidence")
    return fails


def check() -> None:
    good = {"id": "the-general-1926", "title": "The General", "year": 1926, "country": "US",
            "editorial": "A public domain classic.",
            "layers": {"print": {"status": "verified_pd",
                                 "evidence": [{"type": "term_expiry", "note": "1926 < cutoff"}]},
                       "story": {"status": "undetermined", "evidence": []}}}
    assert qc(good) == [], f"clean candidate should pass, got {qc(good)}"
    bad = {"id": "x-1940", "title": "X", "year": 1940,
           "editorial": "This is public domain.",
           "layers": {"print": {"status": "likely_pd", "evidence": []}}}
    fails = qc(bad)
    assert any("likely_pd" in f for f in fails), "must flag likely_pd in candidate"
    assert any("legal conclusion" in f for f in fails), "must flag unevidenced conclusion"
    print("qc_candidate self-check passed")


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] == "--check":
        check()
        return 0
    cand = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    fails = qc(cand)
    if fails:
        print(f"QC FAIL ({cand.get('id')}):")
        for f in fails:
            print("  -", f)
        return 1
    print(f"QC pass: {cand.get('id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
