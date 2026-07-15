"""M0 quarantine pass (RightsAtlas v4 Part 4.1).

Tags every research-queue row with provenance / renewal_truth / promotable, dedupes
id collisions, and reports the Phase-0 promote set. Idempotent — re-running recomputes
the same tags from source signals (the generator encoded provenance in `notes`).

  python scripts/quarantine_queue.py           # tag + write back + summary
  python scripts/quarantine_queue.py --check    # assert invariants (CI/self-check), no write
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "data" / "queues" / "research_queue_500.json"

# v4 §2.1 — titles asserted "known_renewed" in v3 WITHOUT a citation. Symmetric evidence
# bar: blocked from promotion until re-tagged with an actual renewal registration number.
KNOWN_RENEWED = {"mr. smith goes to washington", "stagecoach", "gunga din", "hell's angels"}
# v4 flips this: famously PD via Selznick non-renewal — promote as a research candidate,
# do NOT exclude it (correcting v3's overconfident mislabel).
LIKELY_PD_RESEARCH = {"a star is born"}          # the 1937 Selznick film
# v4 §2.1 — work-identity error (1934 Laurel & Hardy film vs later reissue title).
IDENTITY_ERROR = {"march of the wooden soldiers"}

# archetype -> the renewal basis it implies
ARCHETYPE_TRUTH = {
    "term_expiry": "term_expiry",              # pre-cutoff: PD by 95-yr term, no renewal question
    "renewal_absence": "renewal_absent_likely",  # claims PD by non-renewal — needs a CCE pass
    "notice_failure": "notice_failure",        # PD by defective/absent notice
    "franchise_complex": "unknown",            # trademark review required first
    "uraa_foreign": "unknown",                 # URAA analysis required first
    "underlying_work_trap": "contested",
}
_PROV_RANK = {"curated": 2, "wikipedia": 1, "padded": 0}


def provenance(note: str) -> str:
    n = (note or "").lower()
    if "padded catalog" in n:
        return "padded"
    if "wikipedia" in n:
        return "wikipedia"
    return "curated"


def renewal_truth(row: dict) -> str:
    t = row["title"].lower()
    if t in KNOWN_RENEWED:
        return "known_renewed"
    if t in IDENTITY_ERROR:
        return "contested"
    if t in LIKELY_PD_RESEARCH:
        return "renewal_absent_likely"
    return ARCHETYPE_TRUTH.get(row.get("archetype"), "unknown")


def promotable(row: dict) -> bool:
    if row["provenance"] in ("padded", "wikipedia"):
        return False
    if row["renewal_truth"] in ("known_renewed", "contested"):
        return False
    if row.get("archetype") in ("franchise_complex", "uraa_foreign"):
        return False  # needs trademark / URAA review before it can be a PD candidate
    return True


def _rank(row: dict) -> tuple:
    """For dedup: prefer curated provenance, then an already-published row."""
    return (_PROV_RANK.get(row["provenance"], 0), row.get("queue_status") == "published")


def tag_and_dedupe(rows: list) -> tuple:
    for r in rows:
        # a title v4 explicitly re-audited and vetted beats its generic bulk-list origin
        r["provenance"] = ("curated" if r["title"].lower() in LIKELY_PD_RESEARCH
                           else provenance(r.get("notes")))
    kept, dropped = {}, []
    for r in rows:
        rid = r["id"]
        if rid in kept:
            winner, loser = (kept[rid], r) if _rank(kept[rid]) >= _rank(r) else (r, kept[rid])
            kept[rid] = winner
            dropped.append(loser)
        else:
            kept[rid] = r
    out = list(kept.values())
    for r in out:
        r["renewal_truth"] = renewal_truth(r)
        r["promotable"] = promotable(r)
    return out, dropped


def phase0(rows: list) -> list:
    return [r for r in rows
            if r["provenance"] == "curated" and r["promotable"]
            and r["renewal_truth"] != "known_renewed"]


def summarize(rows: list, dropped: list) -> None:
    print(f"rows: {len(rows)}  (deduped {len(dropped)}: "
          f"{', '.join(d['id'] for d in dropped) or 'none'})")
    print("provenance:", dict(Counter(r["provenance"] for r in rows)))
    print("renewal_truth:", dict(Counter(r["renewal_truth"] for r in rows)))
    print("promotable:", dict(Counter(r["promotable"] for r in rows)))
    print(f"Phase-0 promote set: {len(phase0(rows))} rows "
          f"(curated & promotable & not known_renewed)")


def check(rows: list, dropped: list) -> None:
    # final-state invariants — hold no matter how many times the pass has run (idempotent)
    weak = [r for r in rows if r["provenance"] in ("padded", "wikipedia")]
    assert 150 <= len(weak) <= 185, f"weak-provenance count out of range: {len(weak)}"
    assert all(not r["promotable"] for r in weak), "weak-provenance rows must be non-promotable"
    kr = [r for r in rows if r["title"].lower() in KNOWN_RENEWED]
    assert kr and all(not r["promotable"] for r in kr), "known_renewed titles must be blocked"
    asib = [r for r in rows if r["title"].lower() == "a star is born"]
    assert asib and all(r["promotable"] for r in asib), "A Star Is Born (1937) must be promotable"
    assert sum(r["id"] == "cabinet-of-dr-caligari-1920" for r in rows) == 1, \
        "Caligari id must be deduped to exactly one row"
    p0 = phase0(rows)
    assert p0 and all(r["provenance"] == "curated" and r["promotable"] for r in p0), \
        "Phase-0 set must be non-empty and all curated+promotable"
    print("quarantine self-check passed")


def main() -> int:
    rows = json.loads(QUEUE.read_text(encoding="utf-8"))
    tagged, dropped = tag_and_dedupe(rows)
    if "--check" in sys.argv:
        check(tagged, dropped)
        return 0
    QUEUE.write_text(json.dumps(tagged, ensure_ascii=False, indent=2), encoding="utf-8")
    summarize(tagged, dropped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
