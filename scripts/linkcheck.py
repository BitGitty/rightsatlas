"""Nightly link health: verify archive.org items still exist and are not dark.

Covers watch links AND evidence citations — both can point at archive.org, and build.py
renders whatever the dossier holds, so a link left dead here is a 404 on the public page.
Self-healing: a dead item is replaced with a verified live copy of the SAME film when one
can be found. A dead watch link is dropped if irreplaceable; a dead citation is flagged for
a human instead, never deleted. Writes data/link_status.json; exits 0 always (report and
repair, never break the site).

  python scripts/linkcheck.py            # check, repair, write status
  python scripts/linkcheck.py --check    # self-check (no network)
"""

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILMS = ROOT / "data" / "films"


def _norm(s: str) -> str:
    """Loose title key: 'The Cabinet of Dr. Caligari' -> 'cabinetofdrcaligari'."""
    s = re.sub(r"[^a-z0-9]+", "", str(s).lower())
    return re.sub(r"^(the|a|an)", "", s)


def item_meta(ident: str):
    with urllib.request.urlopen(f"https://archive.org/metadata/{ident}", timeout=30) as r:
        return json.load(r)


def item_ok(ident: str) -> bool:
    try:
        meta = item_meta(ident)
    except Exception:
        return False
    return bool(meta.get("files")) and not meta.get("is_dark")


VIDEO_HINTS = ("mpeg", "mp4", "ogg", "matroska", "quicktime", "avi", "divx")


def has_video(meta: dict) -> bool:
    """A 'watch it free' link must actually play — many archive.org items are metadata only."""
    return any(any(h in str(f.get("format", "")).lower() for h in VIDEO_HINTS)
               for f in meta.get("files", []))


def is_same_film(meta: dict, title: str, year: int) -> bool:
    """Only accept a replacement whose own metadata says it is this film."""
    md = meta.get("metadata") or {}
    if _norm(title) not in _norm(md.get("title", "")):
        return False
    stamp = str(md.get("year") or md.get("date") or "")
    m = re.search(r"(1[89]\d\d|20\d\d)", stamp)
    return bool(m) and abs(int(m.group(1)) - int(year)) <= 1


def find_replacement(title: str, year: int):
    """A live archive.org item that verifiably IS this film, or None. Never guesses."""
    q = urllib.parse.quote(f'title:("{title}") AND mediatype:movies')
    url = ("https://archive.org/advancedsearch.php?q=" + q +
           "&fl%5B%5D=identifier&rows=12&output=json")
    try:
        with urllib.request.urlopen(url, timeout=45) as r:
            docs = json.load(r)["response"]["docs"]
    except Exception:
        return None
    for d in docs:
        ident = d.get("identifier")
        try:
            meta = item_meta(ident)
        except Exception:
            continue
        if not meta.get("is_dark") and has_video(meta) and is_same_film(meta, title, year):
            return ident
        time.sleep(0.5)
    return None


def sweep() -> dict:
    """Check every archive.org link a dossier carries — watch links AND evidence citations.

    A rotted citation is worse than a rotted watch link: the whole site is the claim that
    the evidence is real. Evidence is repaired or flagged, never deleted — dropping a
    citation silently would weaken a published claim with nobody noticing.
    """
    status = {"checked": str(date.today()), "items": {},
              "repaired": [], "dropped": [], "unrepaired_evidence": []}
    for p in sorted(FILMS.glob("*.json")):
        film = json.loads(p.read_text(encoding="utf-8"))
        evidence = [ev for L in film.get("layers", {}).values() for ev in L.get("evidence", [])]
        changed, dead_watch = False, []
        for holder, is_watch in [(w, True) for w in film.get("watch", [])] + \
                                [(ev, False) for ev in evidence]:
            m = re.search(r"archive\.org/details/([^/?#]+)", holder.get("url") or "")
            if not m:
                continue
            ident = m.group(1)
            ok = item_ok(ident)
            status["items"][ident] = {"ok": ok, "film": film["id"],
                                      "kind": "watch" if is_watch else "evidence"}
            time.sleep(1)
            if ok:
                continue
            changed = True
            repl = find_replacement(film["title"], film["year"])
            if repl:
                holder["url"] = f"https://archive.org/details/{repl}"
                status["repaired"].append({"film": film["id"], "was": ident, "now": repl,
                                           "kind": "watch" if is_watch else "evidence"})
            elif is_watch:
                dead_watch.append(holder)
                status["dropped"].append({"film": film["id"], "was": ident})
            else:
                status["unrepaired_evidence"].append({"film": film["id"], "was": ident})
        if changed:
            film["watch"] = [w for w in film.get("watch", []) if w not in dead_watch]
            p.write_text(json.dumps(film, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


def check() -> None:
    meta = {"metadata": {"title": "The Cabinet of Dr. Caligari (1920)", "year": "1920"}}
    assert is_same_film(meta, "Cabinet of Dr. Caligari", 1920), "same film must match"
    assert not is_same_film(meta, "Nosferatu", 1922), "different film must not match"
    off = {"metadata": {"title": "Nosferatu", "date": "1979-01-01"}}
    assert not is_same_film(off, "Nosferatu", 1922), "wrong year must not match"
    assert _norm("The General") == "general"
    assert has_video({"files": [{"format": "MPEG4"}]}), "a playable item must pass"
    assert not has_video({"files": [{"format": "JPEG Thumb"}]}), "metadata-only item must fail"
    print("linkcheck self-check passed")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
        raise SystemExit(0)
    st = sweep()
    (ROOT / "data" / "link_status.json").write_text(json.dumps(st, indent=1), encoding="utf-8")
    bad = [k for k, v in st["items"].items() if not v["ok"]]
    print(f"link check: {len(st['items'])} items, {len(bad)} dead "
          f"({len(st['repaired'])} repaired, {len(st['dropped'])} watch links dropped, "
          f"{len(st['unrepaired_evidence'])} evidence links need a human): {bad}")
