"""export_evidence.py (RightsAtlas v4 §2.2 — the hero feature).

Generates a Markdown "research citation packet" for a verified film. Two tiers:

  Tier A  --tier print   Film-print layer only. ALWAYS available on a dossier.
                         Honestly states the other layers are NOT cleared.
  Tier B  --tier full    Full clearance. Refused unless every layer is resolved
                         (not `undetermined`) AND every layer has evidence.

A packet is citations + facts, NOT legal advice and NOT a DMCA counter-notice
(never auto-generates §512 perjury language). Every packet carries the disclaimer,
its tier scope, a pre-1972 sound-recording warning for old films, a version stamp,
and a footer pointing back to the live dossier.

  python scripts/export_evidence.py <film-id> [--tier print|full]
  python scripts/export_evidence.py --all              # tier-print packet for every film -> packets/
  python scripts/export_evidence.py --check            # self-check (T-05a / T-05b)
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import engine  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FILMS = ROOT / "data" / "films"
PACKETS = ROOT / "packets"
LIVE_URL = "https://bitgitty.github.io/rightsatlas/film/{id}/"


def git_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "local"
    except Exception:
        return "local"


def load(film_id: str) -> dict:
    p = FILMS / f"{film_id}.json"
    if not p.exists():
        sys.exit(f"no dossier: {film_id}")
    return engine.apply_auto_rules(json.loads(p.read_text(encoding="utf-8")))


def full_ready(film: dict) -> tuple:
    """Tier B gate: every layer resolved AND evidenced (T-05b: fail if any undetermined)."""
    for key, _ in engine.LAYERS:
        layer = film["layers"][key]
        if layer["status"] == "undetermined":
            return False, f"layer '{key}' is undetermined"
        if not layer.get("evidence"):
            return False, f"layer '{key}' has no evidence on file"
    return True, ""


def _evidence_md(evidence: list) -> str:
    if not evidence:
        return "- _No primary evidence on file — treat as unverified._\n"
    out = []
    for ev in evidence:
        cite = f" — [{ev.get('source', 'source')}]({ev['url']})" if ev.get("url") else ""
        out.append(f"- **{ev.get('type', 'note')}:** {ev['note']}{cite}")
    return "\n".join(out) + "\n"


def packet(film: dict, tier: str = "print") -> str:
    if tier == "full":
        ok, why = full_ready(film)
        if not ok:
            raise ValueError(f"tier B (full clearance) refused: {why}")

    title, year = film["title"], film["year"]
    ver = f"{film.get('last_verified', 'undated')}-{git_sha()}"
    today = date.today().isoformat()
    print_layer = film["layers"]["print"]
    label = engine.STATUSES[print_layer["status"]][0]

    md = [
        f"# RightsAtlas Research Packet — {title} ({year})",
        "",
        "> ⚠️ **NOT legal advice.** This is a primary-source research packet describing "
        "**United States** copyright status only. It is not a clearance certificate and "
        "not a DMCA counter-notification. Verify independently before any platform dispute.",
        "",
        f"**Scope:** {'Tier B — full clearance (all layers assessed & evidenced).' if tier == 'full' else 'Tier A — **film-print layer only**. Music, story, trademark, and restorations are NOT cleared by this packet.'}",
        f"**Packet version:** `{ver}`  ·  **Generated:** {today}  ·  **Country:** {film.get('country', 'US')}  ·  **Last verified:** {film.get('last_verified', '—')}",
        "",
    ]

    if year < 1972:
        md += [
            "## ⚠️ Sound recordings (pre-1972)",
            "Sound recordings fixed before **15 Feb 1972** can be protected under state law / "
            "the Music Modernization Act until **2067 or later** — the film *print* being public "
            "domain does **not** free the music track. Assume the recorded score is a claim risk.",
            "",
        ]

    md += [
        f"## Film print — {label}",
        _evidence_md(print_layer.get("evidence")),
    ]
    for note in film.get("auto_notes", []):
        md.append(f"> {note}")
    md.append("")

    if tier == "print":
        md += ["## Other layers — NOT cleared by this packet", "",
               "| Layer | Status | Evidence on file |", "|---|---|---|"]
        for key, lbl in engine.LAYERS:
            if key == "print":
                continue
            L = film["layers"][key]
            md.append(f"| {lbl} | {engine.STATUSES[L['status']][0]} | {len(L.get('evidence') or [])} item(s) |")
        md.append("")
    else:
        md += ["## All layers", "", "| Layer | Status | Evidence |", "|---|---|---|"]
        for key, lbl in engine.LAYERS:
            L = film["layers"][key]
            md.append(f"| {lbl} | {engine.STATUSES[L['status']][0]} | {len(L.get('evidence') or [])} item(s) |")
        md.append("")

    g = engine.guidance(film)
    md += ["## What this means", f"- **Watching:** {g['watch'][1]}", f"- **Reusing / monetizing:** {g['reuse'][1]}", ""]

    if film.get("watch"):
        md += ["## Archival copies"] + [
            f"- [{w.get('label', 'archive.org')}]({w['url']})" + (f" · {w['quality']}" if w.get("quality") else "")
            for w in film["watch"]] + [""]

    md += ["---",
           f"_Valid as of {today}. Copyright status can change — check the live dossier before "
           f"relying on this in a dispute:_ {LIVE_URL.format(id=film['id'])}"]
    return "\n".join(md)


def check() -> None:
    # T-05a: print tier succeeds even with an undetermined score
    f = load("his-girl-friday-1940")
    assert f["layers"]["score"]["status"] == "undetermined", "fixture must have undetermined score"
    p = packet(f, "print")
    assert "Tier A" in p and "NOT legal advice" in p and "check the live dossier" in p
    assert "Sound recordings (pre-1972)" in p, "pre-1972 film must carry the warning"
    # T-05b: full tier is refused when a layer is undetermined
    try:
        packet(f, "full")
        raise AssertionError("tier B should have been refused (score undetermined)")
    except ValueError as ex:
        assert "undetermined" in str(ex)
    # a modern-ish film (no pre-1972 banner)
    print("export_evidence self-check passed (T-05a print ok, T-05b full refused)")


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] == "--check":
        check()
        return 0
    if args[0] == "--all":
        PACKETS.mkdir(exist_ok=True)
        n = 0
        for p in sorted(FILMS.glob("*.json")):
            film = load(p.stem)
            (PACKETS / f"{film['id']}.md").write_text(packet(film, "print"), encoding="utf-8")
            n += 1
        print(f"wrote {n} print-tier packets -> {PACKETS}")
        return 0
    tier = "full" if "--tier" in args and args[args.index("--tier") + 1] == "full" else "print"
    film = load(args[0])
    try:
        out = packet(film, tier)
    except ValueError as ex:
        sys.exit(str(ex))
    PACKETS.mkdir(exist_ok=True)
    dest = PACKETS / f"{film['id']}.md"
    dest.write_text(out, encoding="utf-8")
    print(f"wrote {dest} (tier {tier})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
