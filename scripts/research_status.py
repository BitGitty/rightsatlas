"""RightsAtlas daily status — is the pipeline ACTUALLY working, end to end?

Checks what each step really produced, not that a task exited 0 (on 2026-10-04 the old
version said "OK" while research had crashed and been re-researching the same 2 titles
for days):
  1. research ran today and queued NEW titles; the refresh lane upgraded thin pages
     (data/research_runs.jsonl, written per title); 0 output for 2 days is a FAIL
  2. the local repo is not stuck mid-rebase and has nothing left unpushed
  3. the CI drip published within the last 2 days (origin/main, not the local copy)
  4. the newest published film page answers 200 on the live site
  5. the last CI build passed
  6. from 1 Nov, next Public Domain Day's "entering-public-domain-YYYY" page exists
  7. promotion lanes are alive: TBTF Shorts, TBTF comments, hourly Reddit replies (WARN only)
Prints the report and sends it to Telegram (Aurora bot, "RightsAtlas" in the first line).

  python scripts/research_status.py            # report + Telegram
  python scripts/research_status.py --no-send  # report only
  python scripts/research_status.py --check    # self-check of the verdict logic (offline)
"""
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "research_runs.jsonl"
SITE = "https://bitgitty.github.io/rightsatlas"
ENV = Path("D:/Aurora/aurora-twin/.env")


def git(*args) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          encoding="utf-8").stdout.strip()


def http_status(url: str):
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def gather() -> dict:
    today = date.today()
    runs = [json.loads(l) for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if RUNS.exists() else []
    git("fetch", "-q")
    drip = json.loads(git("show", "origin/main:data/drip_state.json") or "{}")
    last = (drip.get("log") or [{}])[-1].get("film")
    try:
        ci = json.loads(subprocess.run(
            ["gh", "run", "list", "-R", "BitGitty/rightsatlas", "-L", "1", "--json", "conclusion,status"],
            capture_output=True, text=True, timeout=60).stdout)[0]
    except Exception:
        ci = None
    week = (today - timedelta(days=7)).isoformat()
    two_days = (today - timedelta(days=1)).isoformat()
    sys.path.insert(0, str(ROOT / "scripts"))
    import seasons
    next_class = today.year + 1
    return {
        "made_2d": [r["id"] for r in runs if r["date"] >= two_days and r["result"] in ("queued", "refreshed")],
        "refreshed_1d": [r["id"] for r in runs if r["date"] >= two_days and r["result"] == "refreshed"],
        "in_season": [c["slug"] for c in seasons.in_season(today)],
        "class_page_missing": today.month >= 11 and not (
            ROOT / "content" / f"entering-public-domain-{next_class}.html").exists(),
        "next_class": next_class,
        "today": today.isoformat(),
        # latest record per title: a title blocked then fixed on a re-run counts as queued
        "runs_today": list({r["id"]: r for r in runs if r["date"] == today.isoformat()}.values()),
        "queued_week": [r["id"] for r in runs if r["date"] >= week and r["result"] == "queued"],
        "mid_rebase": (ROOT / ".git" / "rebase-merge").exists() or (ROOT / ".git" / "rebase-apply").exists(),
        "unpushed": int(git("rev-list", "--count", "origin/main..HEAD") or 0),
        "last_release": drip.get("last_release"),
        "last_film": last,
        "live_status": http_status(f"{SITE}/film/{last}/") if last else None,
        "films": len([l for l in git("ls-tree", "--name-only", "origin/main", "data/films/").splitlines()
                      if l.endswith(".json")]),
        "pending": len([l for l in git("ls-tree", "--name-only", "origin/main", "data/pending/").splitlines()
                        if l.endswith(".json")]),
        "ci": ci,
        "lanes": lanes(today),
    }


SHORTS = Path("D:/viral-shorts-factory/extras/rightsatlas_shorts")
REDDIT_LOG = Path("D:/rightsatlas-private/logs/reddit_watch.log")


def lanes(today: date) -> dict:
    """Last activity of each promotion lane (dates), read from their own ledgers/logs."""
    def last(path, key, field="date"):
        try:
            rows = json.loads(path.read_text(encoding="utf-8")).get(key, [])
            return max((r.get(field, "") for r in rows), default=None)
        except Exception:
            return None
    try:
        reddit = REDDIT_LOG.read_text(encoding="utf-8").strip().splitlines()[-1][:16]
    except Exception:
        reddit = None
    return {"shorts": last(SHORTS / "ledger.json", "shorts", "made"),
            "comments": last(SHORTS / "comments_ledger.json", "done"),
            "comment_token": (Path("D:/viral-shorts-factory") / "token_tbtf_ssl.json").exists(),
            "reddit": reddit}


def evaluate(f: dict):
    """facts -> (verdict, lines). FAIL beats WARN beats OK; unknown is never OK."""
    fails, warns, lines = [], [], []
    queued = [r["id"] for r in f["runs_today"] if r["result"] == "queued"]
    blocked = [r for r in f["runs_today"] if r["result"] == "blocked"]
    if not f["runs_today"]:
        fails.append("research did not run today (no run record)")
    elif not queued and not any(r["result"] in ("refreshed", "deferred") for r in f["runs_today"]):
        warns.append(f"research ran but all {len(blocked)} title(s) were blocked")
    if not f["made_2d"]:
        fails.append("nothing researched or refreshed in 2 days (check logs/daily_research.log)")
    refreshed = [r["id"] for r in f["runs_today"] if r["result"] == "refreshed"]
    deferred = [r["id"] for r in f["runs_today"] if r["result"] == "deferred"]
    lines.append(f"Research today: {len(queued)} new" + (f" ({', '.join(queued)})" if queued else "")
                 + f", {len(refreshed)} upgraded, {len(blocked)} blocked")
    if deferred:
        warns.append(f"Claude usage limit paused research ({len(deferred)} title(s) deferred, retried next run)")
    for b in blocked:
        lines.append(f"  blocked {b['id']}: {(b['reasons'] or ['?'])[0][:140]}")
    dupes = sorted({i for i in f["queued_week"] if f["queued_week"].count(i) > 1})
    if dupes:
        fails.append(f"same title researched twice this week: {', '.join(dupes)}")
    if f["mid_rebase"]:
        fails.append("local repo stuck mid-rebase (next research run will fail)")
    if f["unpushed"]:
        fails.append(f"{f['unpushed']} research commit(s) never reached GitHub")
    utc_today = datetime.now(timezone.utc).date()
    if not f["last_release"] or f["last_release"] < (utc_today - timedelta(days=2)).isoformat():
        fails.append(f"site has not published since {f['last_release']}")
    lines.append(f"Last published: {f['last_film']} ({f['last_release']}) — "
                 + ("live" if f["live_status"] == 200 else f"NOT live ({f['live_status']})"))
    if f["live_status"] != 200:
        fails.append(f"newest film page not live ({f['live_status']})")
    lines.append(f"Live films: {f['films']} · waiting to publish: {f['pending']}")
    if f["refreshed_1d"]:
        lines.append(f"Thin pages upgraded: {', '.join(f['refreshed_1d'])}")
    if f["in_season"]:
        lines.append(f"In season (prioritised): {', '.join(f['in_season'])}")
    if f["class_page_missing"]:
        warns.append(f"Public Domain Day page for {f['next_class']} not written yet")
    if f["pending"] < 5:
        warns.append(f"only {f['pending']} films waiting to publish")
    ci = f["ci"]
    if ci is None:
        warns.append("site build status unknown (gh unavailable)")
    elif ci.get("status") == "completed" and ci.get("conclusion") in ("failure", "timed_out", "startup_failure"):
        # "cancelled" is normal: a newer push supersedes a running deploy
        fails.append(f"last site build: {ci.get('conclusion')}")
    ln, stale = f.get("lanes") or {}, (date.fromisoformat(f["today"]) - timedelta(days=2)).isoformat()
    if ln:
        lines.append(f"Promotion: Shorts last {ln.get('shorts') or 'never'} · comments last "
                     f"{ln.get('comments') or 'never'} · Reddit check {ln.get('reddit') or 'never'}")
        if not ln.get("shorts") or ln["shorts"] < stale:
            warns.append("no TBTF Short made in 2 days (see rightsatlas_shorts/logs/shorts.log)")
        if not ln.get("comment_token"):
            warns.append("TBTF comments off: needs the owner's one-time passkey approval")
        elif not ln.get("comments") or ln["comments"] < stale:
            warns.append("no TBTF comments posted in 2 days")
        if not ln.get("reddit") or ln["reddit"][:10] < stale:
            warns.append("Reddit reply job has not run in 2 days")
    verdict = "FAIL" if fails else "WARN" if warns else "OK"
    return verdict, [f"FAIL: {x}" for x in fails] + [f"WARN: {x}" for x in warns] + lines


def send_telegram(text: str) -> str:
    env = {}
    if ENV.exists():
        for l in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.lstrip().startswith("#"):
                k, _, v = l.partition("=")
                env[k.strip()] = v.strip().strip('"')
    token, chat = env.get("AURORA_TELEGRAM_BOT_TOKEN"), env.get("AURORA_TELEGRAM_CHAT_ID")
    if not (token and chat):
        return "telegram: not sent (no bot credentials)"
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=30) as r:
            return "telegram: sent" if json.load(r).get("ok") else "telegram: refused"
    except Exception as e:
        return f"telegram: failed ({type(e).__name__})"


def check() -> None:
    good = {"today": "2026-10-05", "runs_today": [{"id": "a", "result": "queued", "reasons": []}],
            "made_2d": ["a"], "refreshed_1d": [], "in_season": [], "class_page_missing": False,
            "next_class": 2027,
            "queued_week": ["a", "b"], "mid_rebase": False, "unpushed": 0,
            "last_release": datetime.now(timezone.utc).date().isoformat(), "last_film": "x",
            "live_status": 200, "films": 100, "pending": 20, "ci": {"status": "completed", "conclusion": "success"}}
    assert evaluate(good)[0] == "OK", evaluate(good)
    assert evaluate({**good, "runs_today": []})[0] == "FAIL", "no research run must FAIL"
    assert evaluate({**good, "queued_week": ["a", "a"]})[0] == "FAIL", "re-researching a title must FAIL"
    assert evaluate({**good, "mid_rebase": True})[0] == "FAIL", "stuck rebase must FAIL"
    assert evaluate({**good, "live_status": 404})[0] == "FAIL", "unpublished page must FAIL"
    assert evaluate({**good, "last_release": "2026-01-01"})[0] == "FAIL", "stalled drip must FAIL"
    assert evaluate({**good, "ci": None})[0] == "WARN", "unknown build is never OK"
    assert evaluate({**good, "unpushed": 1})[0] == "FAIL", "an unpushed research commit must FAIL"
    assert evaluate({**good, "made_2d": []})[0] == "FAIL", "2 days without output must FAIL"
    assert evaluate({**good, "class_page_missing": True})[0] == "WARN", "missing class page must WARN"
    lane_ok = {"shorts": "2026-10-05", "comments": "2026-10-05", "comment_token": True, "reddit": "2026-10-05 09:00"}
    assert evaluate({**good, "lanes": lane_ok})[0] == "OK"
    assert evaluate({**good, "lanes": {**lane_ok, "shorts": None}})[0] == "WARN", "a dead Shorts lane must WARN"
    print("research_status self-check passed")


def main() -> int:
    # the 08:30 task redirects stdout to a file (cp1252 on Windows): a model-written reason
    # with a character outside it would crash the report before Telegram is sent
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if "--check" in sys.argv:
        check()
        return 0
    verdict, lines = evaluate(gather())
    report = "\n".join([f"RightsAtlas daily — {verdict}"] + lines)
    print(report)
    if "--no-send" not in sys.argv:
        print(send_telegram(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
