"""RightsAtlas heartbeat (2026-11-15): watches the watchers, from the shared task-exit log, not from their own logs.
Alerts on Telegram when RightsAtlas-Research or RightsAtlas-ResearchStatus has not run, or did not exit 0,
within its window. Silent when healthy. Run every 6 h by its own scheduled task.
Usage: python heartbeat.py [--test]   (--test prints the verdict for sample logs and sends nothing)"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
EXITS = Path(r"D:\shared-tools\taskrun\exits.jsonl")
WINDOWS = {"RightsAtlas-Research": 9, "RightsAtlas-ResearchStatus": 26, "RightsAtlas-Shorts": 26,
           "RightsAtlas-RedditWeekly": 8 * 24 + 6}  # max hours since last run (weekly post: 8 days)


def problems(lines, now):
    last = {}
    for l in lines:
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if r.get("task") in WINDOWS:
            last[r["task"]] = r
    out = []
    for task, hours in WINDOWS.items():
        r = last.get(task)
        if not r:
            out.append(f"{task}: no run on record")
            continue
        end = datetime.fromisoformat(r.get("end") or r["start"])
        if now - end > timedelta(hours=hours):
            out.append(f"{task}: last run {end:%Y-%m-%d %H:%M} UTC, older than {hours} h")
        elif r.get("exit") != 0:
            out.append(f"{task}: last run exited {r.get('exit')} {r.get('note') or ''}".strip())
    return out


def demo():
    now = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    ok = [json.dumps({"task": t, "start": "2026-11-15T10:00:00+00:00", "end": "2026-11-15T10:05:00+00:00", "exit": 0})
          for t in WINDOWS]
    assert problems(ok, now) == []
    assert any("exited 1" in p for p in problems(ok + [json.dumps({"task": "RightsAtlas-Shorts", "start": "2026-11-15T11:00:00+00:00",
                                                                     "end": "2026-11-15T11:01:00+00:00", "exit": 1})], now))
    assert any("older than 9 h" in p for p in problems(ok, now + timedelta(hours=10)))
    assert len(problems([], now)) == len(WINDOWS)
    print("heartbeat self-test: OK")


if __name__ == "__main__":
    if "--test" in sys.argv:
        demo()
        sys.exit(0)
    found = problems(EXITS.read_text(encoding="utf-8", errors="replace").splitlines()[-3000:], datetime.now(timezone.utc))
    if found:
        from research_status import send_telegram
        print(send_telegram("RightsAtlas HEARTBEAT FAIL\n" + "\n".join(found)))
    print("heartbeat:", "FAIL " + "; ".join(found) if found else "OK")
    sys.exit(1 if found else 0)
