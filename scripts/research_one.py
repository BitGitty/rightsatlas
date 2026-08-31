"""research_one.py — the missing research step: queue row -> researched dossier in data/pending/.

Everything else already existed (prefill -> qc -> gate -> drip); nothing filled the evidence,
so the drip pool ran dry and the site froze at 69 dossiers. This shells out to headless
`claude -p` for the judgment part, then verifies the result deterministically: dead or
searchy watch links are dropped, and the candidate must still pass qc_candidate + the
promote gate before it can reach the pending pool.

  python scripts/research_one.py            # research the next queue title -> data/pending/
  python scripts/research_one.py -n 5       # top up the drip pool by 5
  python scripts/research_one.py --id the-crowd-1928
  python scripts/research_one.py --check    # self-check (no network, no LLM)
"""
import json
import re
import shutil
import subprocess
import tempfile
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import engine                                    # noqa: E402
import cce_prefill                               # noqa: E402
import qc_candidate                              # noqa: E402
import promote_candidate                         # noqa: E402

QUEUE = ROOT / "data" / "queues" / "research_queue_500.json"
FILMS = ROOT / "data" / "films"
PENDING = ROOT / "data" / "pending"
CAND = ROOT / "data" / "candidates"
MODEL = "sonnet"          # light reasoning over a fixed template — not an Opus job

PROMPT = """You are researching one film for RightsAtlas, a US public-domain rights reference.
Output is consumed by a script, not by a person. Return ONE JSON object and nothing else
(no markdown fence, no commentary). Do not write, move or promote any file — the calling
script verifies your links and runs the gates. Research and answer, nothing more.

QUEUE ROW: {row}
SKELETON (fill it in, keep the id/title/year/country exactly): {skeleton}

Today is {today}. US term expiry: everything published in {cutoff} or earlier is public
domain in the US by term, full stop — that is a bright line, not a judgement call.

Fill every one of the five layers (print, score, story, trademark, restorations) with a
status from: verified_pd, partially_protected, likely_restored, not_pd, undetermined.
NEVER use "likely_pd" — the candidate gate rejects it.

Evidence rules (the gate enforces these, a violation wastes the run):
- "verified_pd" on a layer REQUIRES >=1 evidence entry. For a print published in {cutoff}
  or earlier use {{"type":"term_expiry","note":"<why, with the year>","source":"...","url":"..."}}.
- Evidence types that count as primary: term_expiry, renewal_absence_search, registration,
  cce_entry, copyright_gov_record, notice_failure_doc (PD side); renewal_registration,
  cce_renewal_entry (renewed side). Anything else must use type "research_note".
- A URL containing "/search", "?q=" or "wikipedia.org" does NOT count as primary. Cite the
  record or an authority page (copyright.gov, Duke CSPD, Library of Congress, a Stanford
  renewal DB record page), not a search result.
- A non-US work claiming a PD print also needs an evidence entry of type "uraa_analysis".

Layer guidance, applied honestly rather than by rote:
- score: for a silent film the images are free but any score on a modern copy is a separate
  protected recording -> partially_protected. For a sound film the recorded track normally
  shares the film's own status; say which.
- story: adaptations inherit the source's term — check what it was based on and when that
  source was published.
- trademark: character and franchise marks survive copyright expiry. undetermined unless
  you know of an active mark.
- restorations: not_pd where a modern restoration (Criterion, Kino, Flicker Alley, MoMA,
  Photoplay) exists; undetermined otherwise.

watch[]: 1-2 entries {{"url","label","quality"}}. Only real Internet Archive item pages of
the form https://archive.org/details/<identifier>. VERIFY each identifier resolves and is
the right film by fetching https://archive.org/metadata/<identifier> before you cite it.
Never invent an identifier; an empty watch list is better than a wrong one.

editorial: two short paragraphs of specific, concrete prose about THIS film — what it is,
why a creator would want it, and the one rights trap that actually applies. Use facts
(names, dates, studio, what happened to the copyright). No stock phrases, no sentence you
would write for any other film, no hedging filler.
faq: 2 entries, each ["question","answer"], answering what a reuser actually asks.

Never write that the film is "public domain in full", "completely free" or similar while
any layer above is not verified_pd — the whole point of this site is that a film is not one
copyright, and the QC gate rejects prose that contradicts your own layer table. Say what is
free (usually the print) and name what is not. Do not hardcode a cutoff year as a permanent
rule ("the line is 1930") — the line moves every January.

Also set "last_verified" to {today} and drop the "_prefill" key."""


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def next_rows(count=1, only_id=None):
    """Queue rows worth researching next: unpublished, not already queued, bright-line first."""
    rows = _load(QUEUE)
    if only_id:
        return [r for r in rows if r["id"] == only_id][:1]
    done = {p.stem for p in FILMS.glob("*.json")} | {p.stem for p in PENDING.glob("*.json")}
    cutoff = engine.pd_cutoff_year()
    todo = [r for r in rows if r["id"] not in done and r.get("renewal_truth") != "known_renewed"]
    # bright-line US titles first (term expiry is arithmetic, not research), then by demand
    todo.sort(key=lambda r: (
        not ((r.get("country") or "US").upper() in ("US", "USA") and r["year"] <= cutoff),
        -r.get("demand_score", 0)))
    return todo[:count]


def ask_claude(row: dict) -> dict:
    skeleton = cce_prefill.prefill(row["title"], row["year"], row.get("country", "US"))
    prompt = PROMPT.format(row=json.dumps(row, ensure_ascii=False),
                           skeleton=json.dumps(skeleton, ensure_ascii=False),
                           today=date.today().isoformat(), cutoff=engine.pd_cutoff_year())
    cli = shutil.which("claude") or "claude"      # Windows needs the resolved .cmd
    # Run OUTSIDE the repo: given repo access the researcher writes and "promotes" its own
    # draft instead of answering, skipping the verification this script exists to do.
    # Everything it needs is in the prompt, so an empty cwd costs nothing.
    # prompt goes on stdin, not argv: Windows truncates a ~6KB command line and the
    # researcher then answers a half-prompt ("which film?") instead of failing loudly.
    with tempfile.TemporaryDirectory() as sandbox:
        out = subprocess.run([cli, "-p", "--model", MODEL, "--output-format", "json",
                              "--allowedTools", "WebSearch,WebFetch",
                              "--disallowedTools", "Write,Edit,MultiEdit,NotebookEdit,Bash"],
                             input=prompt, capture_output=True, text=True,
                             timeout=900, cwd=sandbox).stdout
    try:                                          # unwrap the CLI result envelope
        out = json.loads(out).get("result", out)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        raise ValueError(f"no JSON in researcher output: {out[:300]}")
    return json.loads(m.group(0))


def archive_ok(url: str) -> bool:
    """A watch link is kept only if it is a live, non-dark archive.org item page."""
    m = re.search(r"archive\.org/details/([^/?#]+)", url or "")
    if not m:
        return False
    try:
        with urllib.request.urlopen(f"https://archive.org/metadata/{m.group(1)}", timeout=30) as r:
            meta = json.load(r)
        return bool(meta.get("files")) and not meta.get("is_dark")
    except Exception:
        return False


def finish(cand: dict, verify=True):
    """Verify links, run both gates. Returns (candidate, blocking_reasons)."""
    cand.pop("_prefill", None)
    cand["watch"] = [w for w in cand.get("watch", []) if not verify or archive_ok(w.get("url"))]
    reasons = qc_candidate.qc(cand) + promote_candidate.gate(cand)
    return cand, reasons


def research(row: dict):
    print(f"researching {row['id']} ...")
    cand, reasons = finish(ask_claude(row))
    if reasons:
        CAND.mkdir(parents=True, exist_ok=True)
        (CAND / f"{cand['id']}.json").write_text(
            json.dumps(cand, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  BLOCKED {cand['id']}: " + "; ".join(reasons))
        return None
    PENDING.mkdir(parents=True, exist_ok=True)
    dest = promote_candidate.promote(cand, dest_dir=PENDING)
    print(f"  queued -> {dest.relative_to(ROOT)} ({len(cand['watch'])} watch links)")
    return dest


def check() -> None:
    published = {p.stem for p in FILMS.glob("*.json")}
    rows = next_rows(3)
    assert rows and all(r["id"] not in published for r in rows), \
        "selection must skip already-published titles"
    cutoff = engine.pd_cutoff_year()
    assert rows[0]["year"] <= cutoff, "bright-line titles must sort first"
    # a well-formed researched candidate passes both gates
    good = {"id": "fixture-1928", "title": "Fixture", "year": 1928, "country": "US",
            "editorial": "x", "watch": [], "faq": [],
            "layers": {k: {"status": "undetermined", "evidence": []} for k, _ in engine.LAYERS}}
    good["layers"]["print"] = {"status": "verified_pd", "evidence": [
        {"type": "term_expiry", "note": f"1928 is on or before {cutoff}",
         "url": "https://copyright.gov/"}]}
    assert finish(json.loads(json.dumps(good)), verify=False)[1] == [], "clean candidate must pass"
    # the researcher's likeliest mistakes must still be caught
    bad = json.loads(json.dumps(good))
    bad["layers"]["story"] = {"status": "likely_pd", "evidence": []}
    assert finish(bad, verify=False)[1], "likely_pd must be blocked"
    searchy = json.loads(json.dumps(good))
    searchy["layers"]["print"]["evidence"] = [
        {"type": "registration", "url": "https://x.org/search?q=a", "note": "n"}]
    assert finish(searchy, verify=False)[1], "search-URL evidence must be blocked"
    assert not archive_ok("https://archive.org/search?query=foo"), "search URL is not a watch link"
    print(f"research_one self-check passed (next up: {', '.join(r['id'] for r in rows)})")


def main() -> int:
    args = sys.argv[1:]
    if "--check" in args:
        check()
        return 0
    only = args[args.index("--id") + 1] if "--id" in args else None
    n = int(args[args.index("-n") + 1]) if "-n" in args else 1
    rows = next_rows(n, only)
    if not rows:
        print("nothing left to research")
        return 0
    made = [research(r) for r in rows]
    print(f"done: {sum(1 for m in made if m)}/{len(rows)} queued; "
          f"pending pool = {len(list(PENDING.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
