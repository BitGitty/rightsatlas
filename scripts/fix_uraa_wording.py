"""FIX-URAA-WORDING v1.0 (one-off, 2026-11-21, Crucible R2). Burmese song posts/dossiers stated a one-condition URAA
rule and a firm US date. URAA restoration (17 U.S.C. 104A) needs ALL conditions; rewrite to list them and make the
date conditional. Dry run unless --apply."""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD = re.compile(r"Myanmar works still protected in Myanmar on 1 January 1996 had their US copyright restored for 95 years "
                 r"from first publication; if this song was first published in (\d{4}), it is protected in the US until "
                 r"31 December (\d{4})\.")
NEW = (r"a Myanmar work got its US copyright back on 1 January 1996 (the URAA) only if ALL of these hold: it was still "
       r"protected in Myanmar on that date, at least one author was a Myanmar national or resident, it was first published "
       r"outside the US, and it was not published in the US within 30 days. If they all hold and the song was first "
       r"published in \1, it is protected in the US until 31 December \2.")
files = list((ROOT / "content/blog").glob("*burmese-song*.html")) + list((ROOT / "data/songs").glob("*.json"))
total = 0
for p in files:
    t = p.read_bytes().decode("utf-8")
    n = len(OLD.findall(t))
    if n:
        total += n
        print(p.name, n)
        if "--apply" in sys.argv:
            p.write_bytes(OLD.sub(NEW, t).encode("utf-8"))
print("matches", total, "APPLIED" if "--apply" in sys.argv else "DRY RUN")
