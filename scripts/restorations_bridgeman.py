"""restorations_bridgeman.py - one-time correction (2026-10-05), kept as the record of what changed.

62 dossiers labelled the restorations layer "not_pd" (Protected). In the US a FAITHFUL
restoration of a public-domain film adds no new copyright (Bridgeman Art Library v. Corel, S.D.N.Y.
1999, applying Feist v. Rural, 1991); only genuinely new material is protected. A reader on
r/publicdomain pulled us up on it. This moves those layers to partially_protected and puts the
rule, plus the DMCA ripping caveat, as the first evidence entry. Prose is fixed separately by
restorations_prose.py (it needs judgment per page).

  python scripts/restorations_bridgeman.py           # apply (idempotent)
  python scripts/restorations_bridgeman.py --check   # self-check
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTE = ("A faithful restoration of a public-domain film adds no new US copyright: copying or "
        "restoring public-domain images without original creative additions is not protected "
        "(Bridgeman Art Library v. Corel Corp., S.D.N.Y. 1999, following Feist v. Rural, 1991). "
        "What a restoration ADDS can be protected: a newly composed or newly recorded score, "
        "colorization, newly written or translated titles and subtitles, and other original "
        "additions. Separately, ripping a copy-protected Blu-ray or DVD can break the DMCA's "
        "anti-circumvention rule (17 U.S.C. 1201) even when the film itself is public domain.")
RULE = {"type": "research_note", "note": NOTE, "source": "Bridgeman Art Library v. Corel Corp. (summary)",
        "url": "https://en.wikipedia.org/wiki/Bridgeman_Art_Library_v._Corel_Corp."}
DMCA = {"type": "research_note", "note": "17 U.S.C. 1201 - circumvention of copyright protection systems.",
        "source": "Cornell LII - 17 U.S. Code 1201", "url": "https://www.law.cornell.edu/uscode/text/17/1201"}


def fix(d: dict) -> bool:
    L = d["layers"].get("restorations")
    if not L or L.get("status") != "not_pd" or any(e.get("note") == NOTE for e in L.get("evidence", [])):
        return False
    L["status"] = "partially_protected"
    L["evidence"] = [RULE, DMCA] + L.get("evidence", [])
    return True


def main() -> int:
    if "--check" in sys.argv:
        d = {"layers": {"restorations": {"status": "not_pd", "evidence": [{"note": "x"}]}}}
        assert fix(d) and d["layers"]["restorations"]["status"] == "partially_protected"
        assert d["layers"]["restorations"]["evidence"][0]["note"] == NOTE
        assert not fix(d), "idempotent"
        print("restorations_bridgeman self-check passed")
        return 0
    n = 0
    for f in [*(ROOT / "data" / "films").glob("*.json"), *(ROOT / "data" / "pending").glob("*.json")]:
        d = json.loads(f.read_text(encoding="utf-8"))
        if fix(d):
            f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            n += 1
    print(f"restorations layer corrected on {n} dossiers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
