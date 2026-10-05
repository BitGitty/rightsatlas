"""restorations_prose.py - rewrite ONLY the restoration sentences in editorial/faq (2026-10-05).

Companion to restorations_bridgeman.py: the layer labels were corrected in one pass, but 46
pages still SAY "the restoration carries its own copyright" in their prose. A claude -p pass
edits just those sentences to the corrected rule; anything else changing (other fields, big
length swings, new years/numbers) rejects the edit. Stops on a Claude usage limit (Aurora shares
the allowance and comes first). Progress is kept, so re-running continues where it stopped.

  python scripts/restorations_prose.py      # run (background)
  python scripts/restorations_prose.py --check
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
DONE = ROOT / "data" / "restorations_prose_done.json"
PAT = re.compile(r"restor[a-z]*[^.]{0,140}(own copyright|protected|separately|copyrighted|not free|not public domain)"
                 r"|(protected|own copyright|copyrighted)[^.]{0,90}restor", re.I)
PROMPT = """Edit this film page's prose. Change ONLY the sentences that talk about restorations (restored
versions, restored Blu-rays/DVDs, foundation or studio restorations), so they match this rule:

- A faithful restoration of a public-domain film adds no new US copyright (Bridgeman v. Corel;
  Feist v. Rural): the restored images of a public-domain film are as free as the original.
- What a restoration ADDS can be protected: a newly composed or recorded score, colorization,
  newly written or translated titles/subtitles, other original additions.
- Ripping a copy-protected Blu-ray/DVD can break the DMCA anti-circumvention rule even when the
  film is public domain.

Keep every other sentence exactly as it is. Keep the same tone and roughly the same length. Do not
add new facts, names, dates or numbers. Return ONE JSON object and nothing else:
{{"editorial": "...", "faq": [["question", "answer"], ...]}}

EDITORIAL: {editorial}
FAQ: {faq}"""


def needs(d: dict) -> bool:
    return bool(PAT.search(" ".join([d.get("editorial", "")] + [str(x[-1]) for x in d.get("faq", []) if x])))


def acceptable(old: dict, new: dict) -> str | None:
    """Reason to reject an edit, or None."""
    if not isinstance(new.get("editorial"), str) or not isinstance(new.get("faq"), list):
        return "bad shape"
    if len(new["faq"]) != len(old.get("faq", [])):
        return "faq count changed"
    a, b = len(old.get("editorial", "")), len(new["editorial"])
    if not 0.7 * a <= b <= 1.4 * a:
        return f"editorial length {a} -> {b}"
    nums = lambda t: set(re.findall(r"\b\d{3,4}\b", t))
    if nums(new["editorial"]) - nums(old.get("editorial", "")):
        return "new numbers/years appeared"
    return None


def main() -> int:
    if "--check" in sys.argv:
        old = {"editorial": "The 1926 film is free. Its restoration has its own copyright.", "faq": [["q", "a"]]}
        assert needs(old)
        assert acceptable(old, {"editorial": "The 1926 film is free. A faithful restoration adds no new copyright.",
                                "faq": [["q", "a"]]}) is None
        assert acceptable(old, {"editorial": "The 1926 film is free. Restored in 2015.", "faq": [["q", "a"]]})
        assert acceptable(old, {"editorial": old["editorial"], "faq": []}) == "faq count changed"
        print("restorations_prose self-check passed")
        return 0
    from research_one import _claude, _json, UsageLimit
    done = set(json.loads(DONE.read_text(encoding="utf-8"))) if DONE.exists() else set()
    changed, rejected = [], []
    for f in sorted([*(ROOT / "data" / "films").glob("*.json"), *(ROOT / "data" / "pending").glob("*.json")]):
        d = json.loads(f.read_text(encoding="utf-8"))
        if f.stem in done or not needs(d):
            continue
        try:
            new = _json(_claude(PROMPT.format(editorial=json.dumps(d.get("editorial", ""), ensure_ascii=False),
                                              faq=json.dumps(d.get("faq", []), ensure_ascii=False)),
                                timeout=600))
        except UsageLimit:
            print("Claude usage limit: stopping, re-run continues later")
            break
        except Exception as e:
            rejected.append(f"{f.stem}: {type(e).__name__}")
            continue
        why = acceptable(d, new)
        if why:
            rejected.append(f"{f.stem}: {why}")
            continue
        d["editorial"], d["faq"] = new["editorial"], new["faq"]
        f.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        done.add(f.stem)
        DONE.write_text(json.dumps(sorted(done)), encoding="utf-8")
        changed.append(f.stem)
        print("rewrote", f.stem)
    print(f"done: {len(changed)} rewritten, {len(rejected)} rejected: {rejected}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
