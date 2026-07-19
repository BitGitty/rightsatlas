"""RightsAtlas research status — is auto-research working, and how many done?
Prints a daily-report block: published dossiers, pending-drip pool, today's release,
recent growth, and backlog. Run by a daily task; also read by Claude each session.
"""
import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILMS = ROOT / "data" / "films"
PENDING = ROOT / "data" / "pending"
STATE = ROOT / "data" / "drip_state.json"
QUEUE = ROOT / "data" / "queues" / "research_queue_500.json"


def git_recent_dossiers(days=7):
    """How many dossier files were added to data/films in the last N days (git)."""
    try:
        since = f"--since={days}.days.ago"
        out = subprocess.run(["git", "-C", str(ROOT), "log", since, "--diff-filter=A",
                              "--name-only", "--pretty=format:"], capture_output=True, text=True).stdout
        return len({l for l in out.splitlines() if l.startswith("data/films/") and l.endswith(".json")})
    except Exception:
        return None


def main():
    published = len(list(FILMS.glob("*.json")))
    pending = sorted(PENDING.glob("*.json"), key=lambda p: p.stat().st_mtime)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    log = state.get("log", [])
    today = date.today().isoformat()
    dripped_today = state.get("last_release") == today
    try:
        backlog = len(json.loads(QUEUE.read_text(encoding="utf-8"))) if QUEUE.exists() else 0
    except Exception:
        backlog = "?"
    added7 = git_recent_dossiers(7)

    print("=" * 46)
    print(f"RIGHTSATLAS RESEARCH STATUS — {datetime.now(timezone.utc):%Y-%m-%d}")
    print("=" * 46)
    print(f"Published dossiers (live):   {published}")
    print(f"Pending drip pool (waiting): {len(pending)}" +
          (f"  next: {pending[0].stem}" if pending else "  (EMPTY — no new research queued)"))
    print(f"Released today:              {'yes — ' + log[-1]['film'] if dripped_today and log else 'not yet'}")
    print(f"Added last 7 days (git):     {added7 if added7 is not None else '?'}")
    print(f"Research backlog (queue):    {backlog} titles catalogued, not yet researched")
    if log:
        print("Recent drip releases:")
        for e in log[-5:]:
            print(f"   {e['date']}  {e['film']}")
    # verdict
    if len(pending) == 0 and (added7 == 0):
        print("\nVERDICT: auto-research is NOT producing new dossiers — pool empty + 0 added this week.")
    elif len(pending) > 0:
        print(f"\nVERDICT: OK — {len(pending)} researched dossiers queued; drip releases 1/day.")
    else:
        print("\nVERDICT: publishing from research batches; keep the pending pool fed to sustain 1/day.")


if __name__ == "__main__":
    main()
