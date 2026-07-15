"""promote_candidate.py (RightsAtlas v4 §3.3) — the hard evidence gate between an AI/human
draft (data/candidates/, gitignored) and a public dossier (data/films/). A human runs this
with --approve; it refuses anything that doesn't meet the symmetric evidence bar, logs the
promotion, and strips draft markers.

  python scripts/promote_candidate.py data/candidates/<id>.json          # dry-run: report gate result
  python scripts/promote_candidate.py data/candidates/<id>.json --approve # promote to data/films/
  python scripts/promote_candidate.py --check                             # self-check
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import engine  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FILMS = ROOT / "data" / "films"
QUEUE = ROOT / "data" / "queues" / "research_queue_500.json"
LOG = ROOT / "data" / "promote_log.jsonl"
HIGH_DEMAND = 80  # queue demand_score at/above which a second citation is required


def _queue_row(fid):
    if not QUEUE.exists():
        return None
    return next((r for r in json.loads(QUEUE.read_text(encoding="utf-8")) if r["id"] == fid), None)


def gate(cand: dict) -> list:
    """Return blocking reasons (empty = promotable). Symmetric bar in both directions."""
    reasons = []
    layers = cand.get("layers", {})
    print_layer = layers.get("print", {})
    country = (cand.get("country") or "US").upper()
    row = _queue_row(cand.get("id"))

    # 0: can't publish a raw/unresearched draft
    if cand.get("_prefill"):
        reasons.append("candidate is still a raw prefill — draft and evidence it first")
    if not any(L.get("evidence") for L in layers.values()):
        reasons.append("no evidence on any layer — nothing researched to publish")

    # 1 + 2: a PD print claim needs PRIMARY evidence (not search/wiki URLs)
    if print_layer.get("status") in ("verified_pd",):
        primary = [ev for ev in print_layer.get("evidence", []) if engine.is_primary(ev)]
        if not primary:
            reasons.append("print verified_pd without a primary-source evidence entry")
        # 7: two citations for high-demand titles
        if row and row.get("demand_score", 0) >= HIGH_DEMAND and len(primary) < 2:
            reasons.append(f"high-demand title needs >=2 primary citations (has {len(primary)})")
    # symmetric: a 'renewed/not_pd' claim also needs a renewal registration
    if print_layer.get("status") in ("not_pd", "likely_restored"):
        if not any(ev.get("type") in engine.PRIMARY_RENEWED_EVIDENCE and engine.is_primary(ev)
                   for ev in print_layer.get("evidence", [])):
            reasons.append("not_pd/restored claim without a renewal-registration citation")

    # 3: foreign works require a URAA analysis or the print stays not_assessed
    if country not in ("US", "USA") and print_layer.get("status") in ("verified_pd", "likely_pd"):
        if not any(ev.get("type") == "uraa_analysis" for ev in print_layer.get("evidence", [])):
            reasons.append("foreign work without uraa_analysis cannot claim PD print")

    # 4: queue rows tagged known_renewed are blocked unless re-tagged with evidence
    if row and row.get("renewal_truth") == "known_renewed":
        if not any(ev.get("type") in engine.PRIMARY_RENEWED_EVIDENCE
                   for L in layers.values() for ev in L.get("evidence", [])):
            reasons.append("queue row is known_renewed — attach a renewal registration to override")

    # 5: watch[] links must not be search URLs
    for w in cand.get("watch", []):
        u = (w.get("url") or "").lower()
        if "/search" in u or "?q=" in u:
            reasons.append(f"watch link looks like a search URL: {w.get('url')}")

    # engine build-gate must also pass
    reasons += engine.validate(cand)
    return reasons


def promote(cand: dict, approver: str = "Bit Git") -> Path:
    cand = dict(cand)
    cand.pop("_prefill", None)
    cand["last_verified"] = date.today().isoformat()
    cand.setdefault("byline", "Bit Git · RightsAtlas research (AI-assisted, human-reviewed)")
    dest = FILMS / f"{cand['id']}.json"
    dest.write_text(json.dumps(cand, ensure_ascii=False, indent=2), encoding="utf-8")
    ev_count = sum(len(L.get("evidence", [])) for L in cand.get("layers", {}).values())
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": cand["id"], "promoted_by": approver,
                             "promoted_at": date.today().isoformat(),
                             "evidence_count": ev_count}) + "\n")
    return dest


def check() -> None:
    base = {"id": "fixture-1935", "title": "Fixture", "year": 1935, "country": "US",
            "layers": {k: {"status": "undetermined", "evidence": []} for k, _ in engine.LAYERS}}
    # unevidenced verified_pd -> blocked
    bad = json.loads(json.dumps(base))
    bad["layers"]["print"] = {"status": "verified_pd", "evidence": []}
    assert any("primary-source" in r for r in gate(bad)), "must block unevidenced verified_pd"
    # search-URL 'primary' -> still blocked (not primary)
    searchy = json.loads(json.dumps(base))
    searchy["layers"]["print"] = {"status": "verified_pd",
        "evidence": [{"type": "registration", "url": "https://x.org/search?q=foo", "note": "n"}]}
    assert any("primary-source" in r for r in gate(searchy)), "search URL must not count as primary"
    # foreign PD without URAA -> blocked
    foreign = json.loads(json.dumps(base))
    foreign["country"] = "DE"
    foreign["layers"]["print"] = {"status": "verified_pd",
        "evidence": [{"type": "term_expiry", "note": "old"}]}
    assert any("uraa" in r for r in gate(foreign)), "foreign PD needs URAA analysis"
    # clean US renewal-absence candidate -> promotable
    good = json.loads(json.dumps(base))
    good["layers"]["print"] = {"status": "verified_pd", "evidence": [
        {"type": "renewal_absence_search", "note": "no renewal 1962-64",
         "url": "https://exhibits.stanford.edu/copyrightrenewals"}]}
    assert gate(good) == [], f"clean candidate should pass, got {gate(good)}"
    print("promote_candidate self-check passed")


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "--check":
        check()
        return 0
    cand = json.loads(Path(args[0]).read_text(encoding="utf-8"))
    reasons = gate(cand)
    if reasons:
        print(f"PROMOTE BLOCKED ({cand.get('id')}):")
        for r in reasons:
            print("  -", r)
        return 1
    if "--approve" in args:
        dest = promote(cand)
        print(f"promoted -> {dest}")
    else:
        print(f"gate OK: {cand.get('id')} (dry-run; pass --approve to promote)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
