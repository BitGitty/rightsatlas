"""RightsAtlas daily-drip publisher.

Backend research can fill data/pending/ with as many finished dossiers as we produce;
this gate moves the OLDEST ONE into data/films/ per day, so the public site grows
steadily (YouTube-schedule style) instead of dumping everything at once.

Run by the nightly CI *before* build.py; the moved file + state are committed so the
release persists. Idempotent within a day (won't release twice).

  python scripts/drip_publish.py          # release today's one (if any pending)
  python scripts/drip_publish.py --demo    # self-check in a sandbox
"""
import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PENDING = ROOT / "data" / "pending"
FILMS = ROOT / "data" / "films"
STATE = ROOT / "data" / "drip_state.json"


def release_one(today: str, pending: Path, films: Path, state: Path) -> str | None:
    """Move the oldest pending dossier into films/, once per day. Returns its id or None."""
    st = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
    if st.get("last_release") == today:
        return None                                   # already dripped today
    pend = sorted(pending.glob("*.json"), key=lambda p: p.stat().st_mtime)  # FIFO
    if not pend:
        return None
    pick = pend[0]
    shutil.move(str(pick), str(films / pick.name))
    st["last_release"] = today
    st.setdefault("log", []).append({"date": today, "film": pick.stem})
    state.write_text(json.dumps(st, indent=2), encoding="utf-8")
    return pick.stem


def main() -> int:
    PENDING.mkdir(parents=True, exist_ok=True)
    released = release_one(date.today().isoformat(), PENDING, FILMS, STATE)
    n_left = len(list(PENDING.glob("*.json")))
    print(f"drip: released {released} -> data/films/ ({n_left} left)" if released
          else f"drip: nothing today (already dripped or pending empty; {n_left} pending)")
    return 0


def demo():
    import tempfile, time
    with tempfile.TemporaryDirectory() as d:
        d = Path(d); pend, films, state = d / "pending", d / "films", d / "s.json"
        pend.mkdir(); films.mkdir()
        (pend / "a-1920.json").write_text("{}"); time.sleep(0.02)
        (pend / "b-1921.json").write_text("{}")
        assert release_one("2026-07-19", pend, films, state) == "a-1920"   # oldest first
        assert (films / "a-1920.json").exists()
        assert release_one("2026-07-19", pend, films, state) is None       # 1/day gate
        assert release_one("2026-07-20", pend, films, state) == "b-1921"   # next day, next film
        print("OK drip demo: FIFO order + 1/day gate work")


if __name__ == "__main__":
    demo() if "--demo" in sys.argv else sys.exit(main())
