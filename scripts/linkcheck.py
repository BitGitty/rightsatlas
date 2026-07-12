"""Nightly link health: verify archive.org items still exist and are not dark.
Writes data/link_status.json; exits 0 always (report, don't break the site)."""

import json
import re
import time
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
status = {"checked": str(date.today()), "items": {}}

for p in sorted((ROOT / "data" / "films").glob("*.json")):
    film = json.loads(p.read_text(encoding="utf-8"))
    for w in film.get("watch", []):
        m = re.search(r"archive\.org/details/([^/?#]+)", w["url"])
        if not m:
            continue
        ident = m.group(1)
        try:
            with urllib.request.urlopen(
                    f"https://archive.org/metadata/{ident}", timeout=30) as r:
                meta = json.load(r)
            ok = bool(meta.get("files")) and not meta.get("is_dark")
        except Exception:
            ok = False
        status["items"][ident] = {"ok": ok, "film": film["id"]}
        time.sleep(1)

out = ROOT / "data" / "link_status.json"
out.write_text(json.dumps(status, indent=1), encoding="utf-8")
bad = [k for k, v in status["items"].items() if not v["ok"]]
print(f"link check: {len(status['items'])} items, {len(bad)} failing: {bad}")
