"""watchdog.py — runs on GitHub Actions, independent of the owner's PC.

The PC runs research and the daily status report; if the PC is off or broken, that report
never arrives and silence looks like "all fine". This checks the repo itself: if no research
run was logged, or nothing was published, for 2+ days, it alerts on Telegram and fails.

  python scripts/watchdog.py           # check; alert via TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID env
  python scripts/watchdog.py --check   # self-check (offline)
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def problems(last_run: str | None, last_release: str | None, today: date) -> list:
    stale = (today - timedelta(days=2)).isoformat()
    out = []
    if not last_run or last_run < stale:
        out.append(f"no research run logged since {last_run} — the PC job is not running")
    if not last_release or last_release < stale:
        out.append(f"nothing published since {last_release} — the daily release has stopped")
    return out


def main() -> int:
    if "--check" in sys.argv:
        t = date(2026, 10, 10)
        assert problems("2026-10-09", "2026-10-10", t) == []
        assert len(problems("2026-10-07", "2026-10-10", t)) == 1, "stale research must alert"
        assert len(problems(None, None, t)) == 2
        print("watchdog self-check passed")
        return 0
    runs = (ROOT / "data" / "research_runs.jsonl").read_text(encoding="utf-8").splitlines()
    last_run = max((json.loads(l)["date"] for l in runs if l.strip()), default=None)
    drip = json.loads((ROOT / "data" / "drip_state.json").read_text(encoding="utf-8"))
    found = problems(last_run, drip.get("last_release"), date.today())
    if not found:
        print(f"watchdog OK: last research {last_run}, last release {drip.get('last_release')}")
        return 0
    text = "RightsAtlas WATCHDOG (GitHub) — FAIL\n" + "\n".join(found)
    print(text)
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=30)
    return 1


if __name__ == "__main__":
    sys.exit(main())
