"""RightsAtlas acceptance tests (v4 Part 8). Stdlib asserts, no framework.

  python tests/test_acceptance.py     # runs all; exits non-zero on first failure

Covers the gates this codebase actually enforces (T-01, T-02, T-05, T-06, T-07,
T-08, T-10, T-12, T-13). Publish/CI runs this on every push.
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import engine  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
import promote_candidate as pc  # noqa: E402

FILMS = ROOT / "data" / "films"


def _base(**over):
    f = {"id": "fixture-1935", "title": "Fixture", "year": 1935, "country": "US",
         "layers": {k: {"status": "undetermined", "evidence": []} for k, _ in engine.LAYERS}}
    f.update(over)
    return f


def t01_verified_pd_without_evidence_fails_validate():
    f = _base()
    f["layers"]["print"] = {"status": "verified_pd", "evidence": []}
    assert engine.validate(f), "verified_pd without evidence must produce a validate error"


def t02_likely_pd_is_warn_not_build_fail():
    # phase 1: likely_pd is allowed by validate() (only a build WARNING), not an error
    f = _base()
    f["layers"]["print"] = {"status": "likely_pd", "evidence": []}
    assert engine.validate(f) == [], "likely_pd must NOT be a validate/build error in phase 1"


def t05a_print_export_ok_with_undetermined_score():
    sys.path.insert(0, str(ROOT / "scripts"))
    import export_evidence as ex
    f = ex.load("his-girl-friday-1940")
    assert f["layers"]["score"]["status"] == "undetermined"
    p = ex.packet(f, "print")
    assert "Tier A" in p and "NOT legal advice" in p


def t05b_full_export_refused_when_undetermined():
    import export_evidence as ex
    f = ex.load("his-girl-friday-1940")
    try:
        ex.packet(f, "full")
        raise AssertionError("tier B must be refused when a layer is undetermined")
    except ValueError:
        pass


def t06_promote_rejects_search_url_evidence():
    f = _base()
    f["layers"]["print"] = {"status": "verified_pd",
        "evidence": [{"type": "registration", "url": "https://x.org/search?q=a", "note": "n"}]}
    assert any("primary-source" in r for r in pc.gate(f)), "search-URL evidence must be rejected"


def t07_foreign_without_uraa_cannot_be_pd():
    f = _base(country="DE")
    f["layers"]["print"] = {"status": "verified_pd", "evidence": [{"type": "term_expiry", "note": "old"}]}
    assert any("uraa" in r for r in pc.gate(f)), "foreign PD needs uraa_analysis"


def t08_jan1_cutoff_semantics():
    d = date(2026, 7, 15)
    assert engine.pd_term_expired_through_year(d) == 1930, "through 1930 as of 2026"
    assert engine.pd_entering_class_year(d) == 1931, "1931 is the upcoming class as of 2026"
    assert engine.pd_term_expired_through_year(date(2027, 1, 1)) == 1931, "through 1931 on 2027"


def t10_known_renewed_blocked_without_renewal_evidence():
    # queue tags stagecoach known_renewed; a candidate with no renewal cite must be blocked
    f = _base(id="stagecoach-1939", title="Stagecoach", year=1939)
    f["layers"]["print"] = {"status": "verified_pd",
        "evidence": [{"type": "renewal_absence_search", "note": "x", "url": "https://exhibits.stanford.edu/copyrightrenewals"}]}
    reasons = pc.gate(f)
    assert any("known_renewed" in r for r in reasons), f"known_renewed row must be blocked, got {reasons}"


def t12_no_internal_signals_in_public_html():
    site = ROOT / "site"
    if not (site / "queue" / "index.html").exists():
        return  # site not built; skipped
    html = (site / "queue" / "index.html").read_text(encoding="utf-8")
    for leak in ("demand_score", "archetype", "renewal_truth", "priority_rank"):
        assert leak not in html, f"public /queue/ must not leak '{leak}'"


def t13_candidates_are_gitignored():
    r = subprocess.run(["git", "check-ignore", "data/candidates/x.json"], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0, "data/candidates/ must be gitignored"


def t_all_live_films_validate():
    errs = []
    for p in sorted(FILMS.glob("*.json")):
        errs += engine.validate(json.loads(p.read_text(encoding="utf-8")))
    assert not errs, f"live dossiers failed validate: {errs}"


TESTS = [v for k, v in sorted(globals().items()) if k.startswith(("t0", "t1", "t_"))]


def main() -> int:
    passed = 0
    for fn in TESTS:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"{passed}/{len(TESTS)} acceptance tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
