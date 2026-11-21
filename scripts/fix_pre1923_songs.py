"""FIX-PRE1923 v1.0 (one-off, 2026-11-21). Songs published before 1923 had status enters_pd_<Y+96>; the correct US
rule is: published before 1923 -> public domain by 1 January Y+76 at the latest (28 + 47-year max term; all were free
by 1998). Rewrites the status and the old year in the song file and its scheduled post(s). Prints every change.
Run with --apply to write; without it, dry run."""
import glob, json, re, sys
from pathlib import Path

APPLY = "--apply" in sys.argv
ROOT = Path(__file__).resolve().parent.parent


def rewrite(p: Path, old: str, new: str, pattern: str):
    raw = p.read_bytes()
    text = raw.decode("utf-8")
    hits = re.findall(pattern, text)
    out = re.sub(pattern, lambda m: m.group(0).replace(old, new), text)
    if APPLY and out != text:
        p.write_bytes(out.encode("utf-8"))
    return len(hits)


for f in sorted(glob.glob(str(ROOT / "data/songs/*.json"))):
    d = json.loads(Path(f).read_text(encoding="utf-8"))
    st = d["composition"].get("status", "")
    if d["year"] >= 1923 or not st.startswith("enters_pd_"):
        continue
    old, new = st.rsplit("_", 1)[1], str(d["year"] + 76)
    if old == new:
        continue
    # in the song file: the status value + the year where it is stated as the free-from year
    n_song = rewrite(Path(f), old, new, rf'"enters_pd_{old}"|(?:since|from|on|in|by) (?:1 January )?{old}\b')
    n_post = 0
    for post in glob.glob(str(ROOT / f"content/blog/*-song-{d['id']}.html")):
        n_post += rewrite(Path(post), old, new, rf"\b{old}\b")
    print(f"{d['id']:45} {d['year']}  {old} -> {new}  song:{n_song} post:{n_post}")
print("APPLIED" if APPLY else "DRY RUN (add --apply)")
