"""research_one.py — the missing research step: queue row -> researched dossier in data/pending/.

Everything else already existed (prefill -> qc -> gate -> drip); nothing filled the evidence,
so the drip pool ran dry and the site froze at 69 dossiers. This shells out to headless
`claude -p` for the judgment part, then verifies the result deterministically: dead or
searchy watch links are dropped, and the candidate must still pass qc_candidate + the
promote gate before it can reach the pending pool.

  python scripts/research_one.py            # research the next queue title -> data/pending/
  python scripts/research_one.py -n 5       # top up the drip pool by 5
  python scripts/research_one.py --id the-crowd-1928
  python scripts/research_one.py --refresh 2  # re-research 2 thin published dossiers in place
  python scripts/research_one.py --check    # self-check (no network, no LLM)

Every candidate that passes the gates then goes to an independent fact-check (a second
`claude -p` that did not write it). Errors found -> revision -> gates + fact-check again, at
most twice; still failing -> blocked, never published. Each title's outcome is appended to
data/research_runs.jsonl, which research_status.py reads to prove the run happened.
"""
import json
import re
import shutil
import subprocess
import tempfile
import time
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import engine                                    # noqa: E402
import cce_prefill                               # noqa: E402
import qc_candidate                              # noqa: E402
import promote_candidate                         # noqa: E402
import seasons                                   # noqa: E402

QUEUE = ROOT / "data" / "queues" / "research_queue_500.json"
FILMS = ROOT / "data" / "films"
PENDING = ROOT / "data" / "pending"
CAND = ROOT / "data" / "candidates"
RUNS = ROOT / "data" / "research_runs.jsonl"
BUDGET_MIN = 100   # stop starting new titles after this; the 10:00 status must see a finished run
MODEL = "sonnet"          # light reasoning over a fixed template — not an Opus job

PROMPT = """You are researching one film for RightsAtlas, a US public-domain rights reference.
Output is consumed by a script, not by a person. Return ONE JSON object and nothing else
(no markdown fence, no commentary). Do not write, move or promote any file — the calling
script verifies your links and runs the gates. Research and answer, nothing more.

QUEUE ROW: {row}
SKELETON (fill it in, keep the id/title/year exactly): {skeleton}
Set "country" to the PRODUCTION country as a 2-letter code (US, DE, FR, UK, SE...). The
queue row's country is often a padded default of "US" and can be wrong (Spione is DE).

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
  renewal DB record page), not a search result. Every cited URL is fetched by the script;
  a dead or invented address blocks the run. Duke CSPD Public Domain Day pages live at
  https://web.law.duke.edu/cspd/publicdomainday/<year>/ (there is no copyright.duke.edu).
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

Every factual detail you write (dates, places, people, composers, archives, restorations,
releases) must come from a page you actually fetched in this session. If you cannot confirm a
detail, leave it out: an independent fact-checker reviews this dossier and any unsupported
detail blocks it. A shorter dossier is better than a wrong one.

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


def _key(slug: str) -> str:
    """Queue ids and dossier filenames slug apostrophes and leading articles differently
    (jaccuse vs j-accuse, the-cabinet-of-dr-caligari vs cabinet-of-dr-caligari)."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^(the|a|an)-", "", slug.lower()))


def recently_blocked(days=14, times=2) -> set:
    """Titles blocked `times`+ in `days`: skipped so two hard titles cannot stall the queue
    (they sort to the top and would be retried, and fail, every single day)."""
    if not RUNS.exists():
        return set()
    since, n = (date.today() - timedelta(days=days)).isoformat(), {}
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["date"] >= since and r["result"] == "blocked":
            n[_key(r["id"])] = n.get(_key(r["id"]), 0) + 1
    return {k for k, c in n.items() if c >= times}


def next_rows(count=1, only_id=None):
    """Queue rows worth researching next: unpublished, not already queued, not stuck;
    in-season titles first, then bright-line US titles, then by demand."""
    rows = _load(QUEUE)
    if only_id:
        return [r for r in rows if r["id"] == only_id][:1]
    done = {_key(p.stem) for p in [*FILMS.glob("*.json"), *PENDING.glob("*.json")]} | recently_blocked()
    season = {_key(i): d for i, d in seasons.deadlines().items()}
    cutoff = engine.pd_cutoff_year()
    todo = [r for r in rows if _key(r["id"]) not in done and r.get("renewal_truth") != "known_renewed"]
    # nearest holiday first, then bright-line US titles (term expiry is arithmetic), then demand
    todo.sort(key=lambda r: (
        season.get(_key(r["id"]), "9999"),
        not ((r.get("country") or "US").upper() in ("US", "USA") and r["year"] <= cutoff),
        -r.get("demand_score", 0)))
    return todo[:count]


def thin_films(count=1) -> list:
    """Published dossiers with 3+ layers never researched (60 of 103 on 2026-10-05: only the
    print layer was done). In-season ones first, then the longest unverified."""
    season = {_key(i) for i in seasons.priority_ids()}
    skip = recently_blocked()
    thin = []
    for p in FILMS.glob("*.json"):
        d = _load(p)
        weak = sum(1 for L in d["layers"].values() if L.get("status") in ("undetermined", "likely_pd"))
        if weak >= 3 and _key(d["id"]) not in skip:
            thin.append(((_key(d["id"]) not in season, d.get("last_verified", ""), d["id"]), d))
    return [d for _, d in sorted(thin, key=lambda t: t[0])][:count]


REVIEW_PROMPT = """You are an independent fact-checker for RightsAtlas, a US public-domain rights reference.
Another model wrote the dossier below. Your job is to catch what it got WRONG before it is published.
Output is consumed by a script: return ONE JSON object and nothing else (no fence, no commentary).
Do not write, move or promote any file.

Check, using WebSearch/WebFetch for anything you are not certain of:
- title, year, production country, director, studio, cast, release dates;
- every factual claim in the evidence notes, editorial and faq: restorations (who made them, when,
  which release), scores and recordings, source works and their dates, lawsuits, survival status
  (a lost or partial film must not be presented as fully watchable);
- that each cited source plausibly supports the claim it is attached to;
- superlatives ("first", "only", "most expensive ever") - wrong ones are common.
Do NOT re-judge the legal rule (95 years from publication; everything published in {cutoff} or
earlier is public domain in the US by term) and do not nitpick style or wording.
Report only problems you are confident are real factual errors. If unsure, leave it out.

DOSSIER: {cand}

Return {{"verdict": "pass" or "fail", "issues": [{{"where": "<field>", "problem": "<what is wrong>", "fix": "<what is right>"}}]}}
"verdict" is "fail" exactly when "issues" is not empty."""

REVISE_PROMPT = """You wrote this RightsAtlas dossier. An independent fact-checker found the problems
below. Fix every one: correct the claim, or remove it if you cannot support the correction. While
you are at it, remove any other detail you cannot confirm from a page you fetch now - the checker
runs again. Keep every key and the same JSON shape. Return ONE JSON object and nothing else.
Do not write, move or promote any file.

PROBLEMS: {issues}
DOSSIER: {cand}"""


def _claude(prompt: str, model: str = MODEL) -> str:
    """One headless claude -p call (web tools only, no file tools); returns its text result."""
    cli = shutil.which("claude") or "claude"      # Windows needs the resolved .cmd
    # Run OUTSIDE the repo: given repo access the researcher writes and "promotes" its own
    # draft instead of answering, skipping the verification this script exists to do.
    # Everything it needs is in the prompt, so an empty cwd costs nothing.
    # prompt goes on stdin, not argv: Windows truncates a ~6KB command line and the
    # researcher then answers a half-prompt ("which film?") instead of failing loudly.
    with tempfile.TemporaryDirectory() as sandbox:
        proc = subprocess.Popen([cli, "-p", "--model", model, "--output-format", "json",
                                 "--allowedTools", "WebSearch,WebFetch",
                                 "--disallowedTools", "Write,Edit,MultiEdit,NotebookEdit,Bash"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", cwd=sandbox)
        try:
            out = proc.communicate(prompt, timeout=1500)[0]   # foreign/URAA titles need >15 min
        except subprocess.TimeoutExpired:
            # killing claude.cmd alone orphans the claude.exe under it: kill the whole tree
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
            proc.communicate()
            raise
    try:                                          # unwrap the CLI result envelope
        return json.loads(out).get("result", out)
    except (json.JSONDecodeError, AttributeError):
        return out


def _json(out: str) -> dict:
    m = re.search(r"\{.*\}", out or "", re.S)
    if not m:
        raise ValueError(f"no JSON in model output: {(out or '')[:300]}")
    return json.loads(m.group(0))


def ask_claude(row: dict, skeleton: dict | None = None) -> dict:
    skeleton = skeleton or cce_prefill.prefill(row["title"], row["year"], row.get("country", "US"))
    return _json(_claude(PROMPT.format(row=json.dumps(row, ensure_ascii=False),
                                       skeleton=json.dumps(skeleton, ensure_ascii=False),
                                       today=date.today().isoformat(),
                                       cutoff=engine.pd_cutoff_year())))


def parse_review(out: str) -> list:
    """Fact-check reply -> list of issue strings (empty = pass). Unparseable raises ValueError."""
    r = _json(out)
    issues = [f"{i.get('where', '?')}: {i.get('problem', '')} -> {i.get('fix', '')}"
              for i in r.get("issues") or [] if isinstance(i, dict)]
    if r.get("verdict") != "pass" and not issues:
        issues = ["fact-check failed without listing issues"]
    return issues


def review(cand: dict) -> list:
    return parse_review(_claude(REVIEW_PROMPT.format(
        cand=json.dumps(cand, ensure_ascii=False), cutoff=engine.pd_cutoff_year())))


def revise(cand: dict, issues: list) -> dict:
    return _json(_claude(REVISE_PROMPT.format(issues=json.dumps(issues, ensure_ascii=False),
                                              cand=json.dumps(cand, ensure_ascii=False))))


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


def link_dead(url: str) -> bool:
    """Dead = the domain does not resolve or the page is 404/410. Bot walls (403/429) and
    timeouts count as alive: the researcher invents addresses, it does not invent firewalls."""
    try:
        urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0"}),
            timeout=30).close()
        return False
    except urllib.error.HTTPError as e:
        return e.code in (404, 410)
    except urllib.error.URLError as e:
        return isinstance(e.reason, OSError) and "getaddrinfo" in str(e.reason)
    except Exception:
        return False


def finish(cand: dict, verify=True):
    """Verify links, run both gates. Returns (candidate, blocking_reasons)."""
    cand.pop("_prefill", None)
    cand["watch"] = [w for w in cand.get("watch", []) if not verify or archive_ok(w.get("url"))]
    reasons = qc_candidate.qc(cand) + promote_candidate.gate(cand)
    if verify:
        cited = {ev["url"] for L in cand.get("layers", {}).values()
                 for ev in L.get("evidence", []) if str(ev.get("url", "")).startswith("http")}
        reasons += [f"dead evidence link {u}" for u in sorted(cited) if link_dead(u)]
    return cand, reasons


def log_run(rid: str, result: str, reasons: list) -> None:
    with RUNS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"date": date.today().isoformat(), "id": rid, "result": result,
                            "reasons": reasons}, ensure_ascii=False) + "\n")


def _evidence(d: dict) -> int:
    return sum(len(L.get("evidence", [])) for L in d.get("layers", {}).values())


def research(row: dict, old: dict | None = None):
    """Queue row -> fact-checked dossier in data/pending/. With `old` (a published thin
    dossier) it is a refresh: same pipeline, result replaces data/films/<id>.json."""
    print(f"{'refreshing' if old else 'researching'} {row['id']} ...")
    cand = None
    try:  # one bad title must not sink the batch; recently_blocked() skips repeat failures
        skeleton = None
        if old:
            row = {**row, "refresh_note": "Already published, but most layers were never researched "
                   "(status undetermined). Research every layer now; keep existing evidence that is correct."}
            skeleton = {k: v for k, v in old.items() if not k.startswith("_")}
        cand, reasons = finish(ask_claude(row, skeleton))
        for rnd in range(3):                     # fact-check; up to 2 revisions; 3rd fail blocks
            if reasons:
                break
            issues = review(cand)
            if not issues:
                break
            if rnd == 2:
                reasons = [f"fact-check: {i}" for i in issues]
                break
            print(f"  fact-check round {rnd + 1}: {len(issues)} issue(s), revising")
            cand, reasons = finish(revise(cand, issues))
    except (subprocess.TimeoutExpired, ValueError) as e:  # JSONDecodeError is a ValueError
        reasons = [f"{type(e).__name__}: {str(e)[:200]}"]
    if old and not reasons:
        if old["layers"]["print"]["status"] == "verified_pd" and cand["layers"]["print"]["status"] != "verified_pd":
            reasons = ["refresh would downgrade a verified print verdict"]
        elif _evidence(cand) < _evidence(old):
            reasons = [f"refresh has less evidence ({_evidence(cand)}) than the live page ({_evidence(old)})"]
    if reasons:
        if cand and cand.get("id"):
            CAND.mkdir(parents=True, exist_ok=True)
            (CAND / f"{cand['id']}.json").write_text(json.dumps(
                {**cand, "_blocked": reasons}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  BLOCKED {row['id']}: " + "; ".join(reasons))
        log_run(row["id"], "blocked", reasons)
        return None
    if old:
        dest = promote_candidate.promote(cand, dest_dir=FILMS)
        print(f"  refreshed -> {dest.relative_to(ROOT)} (evidence {_evidence(old)} -> {_evidence(cand)})")
        log_run(row["id"], "refreshed", [])
        return dest
    PENDING.mkdir(parents=True, exist_ok=True)
    dest = promote_candidate.promote(cand, dest_dir=PENDING)
    print(f"  queued -> {dest.relative_to(ROOT)} ({len(cand['watch'])} watch links, fact-checked)")
    log_run(row["id"], "queued", [])
    return dest


def check() -> None:
    done = {_key(p.stem) for p in [*FILMS.glob("*.json"), *PENDING.glob("*.json")]}
    rows = next_rows(40)
    assert rows and all(_key(r["id"]) not in done for r in rows), \
        "selection must skip already-published or already-queued titles"
    assert _key("jaccuse-1919") == _key("j-accuse-1919"), "slug variants must match"
    assert _key("the-cabinet-of-dr-caligari-1920") == _key("cabinet-of-dr-caligari-1920"), "leading 'the'"
    cutoff = engine.pd_cutoff_year()
    season = {_key(i) for i in seasons.priority_ids()}
    rest = [r for r in rows if _key(r["id"]) not in season]
    assert all(_key(r["id"]) in season for r in rows[:len(rows) - len(rest)]), "in-season titles first"
    assert not rest or rest[0]["year"] <= cutoff, "then bright-line titles"
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
    assert link_dead("https://copyright.duke.invalid/publicdomainday/2024/"), "invented domain must be dead"
    # the fact-check verdict is parsed strictly: pass needs an explicit pass with no issues
    assert parse_review('{"verdict": "pass", "issues": []}') == [], "clean review must pass"
    assert parse_review('x {"verdict": "fail", "issues": [{"where": "year", "problem": "p", "fix": "f"}]} y') \
        == ["year: p -> f"], "issues must be reported"
    assert parse_review('{"verdict": "fail", "issues": []}'), "a bare fail must still block"
    try:
        parse_review("I could not check this film.")
        raise AssertionError("unparseable review must raise, not pass")
    except ValueError:
        pass
    assert all(sum(1 for L in d["layers"].values() if L.get("status") in ("undetermined", "likely_pd")) >= 3
               for d in thin_films(5)), "refresh lane must only pick thin dossiers"
    print(f"research_one self-check passed (next up: {', '.join(r['id'] for r in rows)})")


def main() -> int:
    args = sys.argv[1:]
    if "--check" in args:
        check()
        return 0
    only = args[args.index("--id") + 1] if "--id" in args else None
    n = int(args[args.index("-n") + 1]) if "-n" in args else 1
    if "--refresh" in args:
        jobs = [({"id": d["id"], "title": d["title"], "year": d["year"],
                  "country": d.get("country", "US")}, d)
                for d in thin_films(int(args[args.index("--refresh") + 1]))]
    else:
        jobs = [(r, None) for r in next_rows(n, only)]
    if not jobs:
        print("nothing left to research")
        return 0
    start, made = time.time(), []
    for row, old in jobs:
        if made and time.time() - start > BUDGET_MIN * 60:
            print(f"time budget ({BUDGET_MIN} min) used: {row['id']} left for the next run")
            break
        made.append(research(row, old))
    print(f"done: {sum(1 for m in made if m)}/{len(jobs)} succeeded; "
          f"pending pool = {len(list(PENDING.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
