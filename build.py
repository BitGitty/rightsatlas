"""RightsAtlas static site generator. Python stdlib only.

  python build.py            -> site/ (BASE_URL env for subpath hosting)
Build FAILS on provenance errors (engine.validate) — by design.
"""

import html
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

import engine

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site"
BASE = os.environ.get("BASE_URL", "/").rstrip("/") + "/"
YEAR = date.today().year
CUTOFF = engine.pd_cutoff_year()
NEXT_CLASS = engine.next_pd_class_year()

DISCLAIMER = (
    "RightsAtlas publishes research about the copyright status of works — "
    "it is not legal advice, and it describes <strong>United States</strong> status only; "
    "other countries' terms differ. Verify independently before commercial use."
)


def e(s):
    return html.escape(str(s), quote=True)


def page(title, desc, body, extra_head=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="stylesheet" href="{BASE}assets/style.css">
{extra_head}
</head>
<body>
<header class="top">
  <a class="brand" href="{BASE}">Rights<span>Atlas</span></a>
  <nav>
    <a href="{BASE}films/">Films</a>
    <a href="{BASE}entering-public-domain-{NEXT_CLASS + 96}/">Class of {NEXT_CLASS + 96}</a>
    <a href="{BASE}methodology/">Methodology</a>
    <a href="{BASE}corrections/">Corrections</a>
    <a href="{BASE}about/">About</a>
    <a class="nav-cta" href="https://github.com/BitGitty/rightsatlas/issues/new?template=film-suggestion.yml"
       rel="nofollow">💡 Suggest</a>
  </nav>
</header>
<main>
{body}
</main>
<footer>
  <p class="disclaimer">{DISCLAIMER}</p>
  <p>© {YEAR} RightsAtlas · research last reviewed dates shown per page ·
     <a href="{BASE}methodology/">how verdicts work</a> ·
     <a href="https://github.com/BitGitty/rightsatlas/issues/new?template=film-suggestion.yml"
        rel="nofollow">💡 Suggest a film or improvement</a></p>
</footer>
</body>
</html>"""


def status_badge(status):
    label, cls = engine.STATUSES[status]
    return f'<span class="badge {cls}">{e(label)}</span>'


def evidence_list(evidence):
    if not evidence:
        return '<p class="ev none">No primary evidence on file — treated as unverified.</p>'
    items = []
    for ev in evidence:
        link = f' — <a href="{e(ev["url"])}" rel="nofollow noopener">{e(ev.get("source", "source"))}</a>' if ev.get("url") else ""
        items.append(f'<li><span class="evtype">{e(ev.get("type", "note"))}</span> {e(ev["note"])}{link}</li>')
    return f'<ul class="ev">{"".join(items)}</ul>'


def film_page(f):
    g = engine.guidance(f)
    layers_html = ""
    for key, label in engine.LAYERS:
        layer = f["layers"][key]
        layers_html += f"""
<tr>
  <th>{e(label)}</th>
  <td>{status_badge(layer["status"])}</td>
  <td>{evidence_list(layer.get("evidence"))}</td>
</tr>"""
    watch_html = ""
    for w in f.get("watch", []):
        watch_html += (f'<li><a href="{e(w["url"])}" rel="nofollow noopener">'
                       f'{e(w.get("label", "Watch on archive.org"))}</a>'
                       f'{" · " + e(w["quality"]) if w.get("quality") else ""}</li>')
    faq_html, faq_ld = "", []
    for q, a in f.get("faq", []):
        faq_html += f"<h3>{e(q)}</h3><p>{e(a)}</p>"
        faq_ld.append({"@type": "Question", "name": q,
                       "acceptedAnswer": {"@type": "Answer", "text": a}})
    notes = "".join(f'<li>{e(n)}</li>' for n in f.get("auto_notes", []))
    embed = ""
    if f.get("youtube_recap"):
        embed = (f'<div class="embed"><h2>Our video on this film</h2>'
                 f'<iframe loading="lazy" src="https://www.youtube-nocookie.com/embed/{e(f["youtube_recap"])}" '
                 f'title="Video recap" allowfullscreen></iframe></div>')
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Movie", "name": f["title"], "datePublished": str(f["year"]),
             "countryOfOrigin": f.get("country", "US")},
            {"@type": "FAQPage", "mainEntity": faq_ld} if faq_ld else {},
        ],
    }
    body = f"""
<article class="dossier">
<h1>Is <em>{e(f["title"])}</em> ({f["year"]}) public domain?</h1>
<p class="meta">Country of origin: {e(f.get("country", "US"))} · Last verified:
{e(f.get("last_verified", "—"))} · Researched by {e(f.get("byline", "RightsAtlas"))}</p>

<div class="guidance">
  <div class="g {g["watch"][0]}"><strong>Watching:</strong> {e(g["watch"][1])}</div>
  <div class="g {g["reuse"][0]}"><strong>Reusing / monetizing:</strong> {e(g["reuse"][1])}</div>
</div>

<p class="packet"><a href="{BASE}packets/{e(f["id"])}.md" rel="nofollow" download>📄 Download the print-layer research packet (Markdown)</a>
<span class="packet-note">— citations you can attach to a dispute. Not legal advice; print layer only.</span></p>

<h2>Rights, layer by layer</h2>
<p class="hint">A film is not one copyright — it is several. Each layer below
can be free or protected independently. This is why one-click “public domain”
answers are wrong so often.</p>
<table class="layers">{layers_html}</table>
{f'<h2>Automatic rule notes</h2><ul class="notes">{notes}</ul>' if notes else ''}

{f'<h2>Watch it free (archival copies)</h2><ul class="watch">{watch_html}</ul>' if watch_html else ''}

<h2>Background</h2>
{"".join(f"<p>{e(p)}</p>" for p in f.get("editorial", "").split(chr(10) * 2) if p.strip())}

{f'<h2>Common questions</h2>{faq_html}' if faq_html else ''}
{embed}
</article>
<script type="application/ld+json">{json.dumps(ld)}</script>"""
    desc = (f'{f["title"]} ({f["year"]}) US copyright status, layer by layer, '
            f'with primary-source evidence and free legal watch links.')
    return page(f'Is {f["title"]} ({f["year"]}) public domain? — RightsAtlas', desc, body)


def index_page(films, backlog_count):
    cards = ""
    for f in sorted(films, key=lambda x: x["title"]):
        g = engine.guidance(f)
        cards += (f'<a class="card {g["reuse"][0]}" href="{BASE}film/{f["id"]}/">'
                  f'<strong>{e(f["title"])}</strong><span>{f["year"]}</span></a>')
    body = f"""
<section class="hero">
<h1>Can you legally use that film?</h1>
<p>Evidence-backed public-domain research for creators — every verdict shows
its receipts: renewal records, case law, and working archival links.
No green checkmarks without proof.</p>
<p class="coverage"><strong>{len(films)} fully-researched dossiers</strong> ·
<a href="{BASE}queue/">{backlog_count} titles in the research backlog</a>
<span class="cov-note">(backlog = not yet researched — not a public-domain list)</span></p>
<input id="q" type="search" placeholder="Search a film title…" autocomplete="off">
<label class="inclq"><input type="checkbox" id="inclq"> also search the unresearched backlog</label>
<div id="results"></div>
</section>
<section>
<h2>Researched films</h2>
<div class="grid">{cards}</div>
</section>
<section class="callout">
<h2>January 1, {NEXT_CLASS + 96}: the next public domain class</h2>
<p>Every film published in {NEXT_CLASS} enters the US public domain on
January 1, {NEXT_CLASS + 96}. <a href="{BASE}entering-public-domain-{NEXT_CLASS + 96}/">See what's coming →</a></p>
</section>
<section class="suggest">
<h2>Missing a film? Spotted something wrong?</h2>
<p>RightsAtlas grows from the community. Suggest a film to research, flag a broken
link or error, or pitch a feature — it goes straight to our research queue.</p>
<a class="suggest-btn" href="https://github.com/BitGitty/rightsatlas/issues/new?template=film-suggestion.yml"
   rel="nofollow">💡 Suggest a film or improvement</a>
</section>"""
    extra = (f'<script src="{BASE}assets/fuse.min.js"></script>'
             f'<script src="{BASE}assets/search.js" defer></script>')
    return page("RightsAtlas — evidence-backed public domain checker for films",
                "Layered US copyright status for classic films with primary-source "
                "evidence, renewal records, and free legal watch links. Suggest a film "
                "or improvement — the research queue is community-driven.", body, extra)


def films_index(films):
    rows = ""
    for f in sorted(films, key=lambda x: (x["year"], x["title"])):
        p = f["layers"]["print"]["status"]
        rows += (f'<tr><td><a href="{BASE}film/{f["id"]}/">{e(f["title"])}</a></td>'
                 f'<td>{f["year"]}</td><td>{e(f.get("country", "US"))}</td>'
                 f'<td>{status_badge(p)}</td></tr>')
    body = f"""<h1>All researched films</h1>
<p class="sorthint">Click a column heading to sort.</p>
<table class="listing" id="filmtable">
<tr><th data-s="text">Title ↕</th><th data-s="num">Year ↕</th><th data-s="text">Origin ↕</th><th data-s="text">Film print status ↕</th></tr>
{rows}</table>
<script>
(function() {{
  var t = document.getElementById('filmtable'), asc = {{}};
  t.rows[0].querySelectorAll('th').forEach(function(th, i) {{
    th.style.cursor = 'pointer';
    th.onclick = function() {{
      asc[i] = !asc[i];
      var rows = Array.prototype.slice.call(t.rows, 1);
      rows.sort(function(a, b) {{
        var x = a.cells[i].textContent.trim(), y = b.cells[i].textContent.trim();
        if (th.dataset.s === 'num') {{ x = +x; y = +y; return asc[i] ? x - y : y - x; }}
        return asc[i] ? x.localeCompare(y) : y.localeCompare(x);
      }});
      rows.forEach(function(r) {{ t.appendChild(r); }});
    }};
  }});
}})();
</script>"""
    return page("All films — RightsAtlas", "Every film researched by RightsAtlas.", body)


def queue_page(backlog):
    # public backlog view: Title / Year / Status only — NO archetype, demand, or renewal_truth.
    rows = ""
    for r in sorted(backlog, key=lambda x: (x["year"], x["title"])):
        rows += (f'<tr id="{e(r["id"])}"><td>{e(r["title"])}</td>'
                 f'<td>{r["year"]}</td><td class="unr">not researched</td></tr>')
    body = f"""<h1>Research backlog — <em>not</em> a public-domain list</h1>
<p class="hint">These are titles queued for future research. <strong>A row here means
nothing about a film's copyright status</strong> — we have not verified it. Only the
<a href="{BASE}films/">researched dossiers</a> carry evidence-backed conclusions.
Want one prioritised? <a href="https://github.com/BitGitty/rightsatlas/issues/new?template=film-suggestion.yml" rel="nofollow">Suggest it →</a></p>
<table class="listing queue" id="queuetable">
<tr><th>Title</th><th>Year</th><th>Status</th></tr>
{rows}</table>
<button id="qmore" type="button">Show more</button>
<script>
(function() {{
  var rows = Array.prototype.slice.call(document.querySelectorAll('#queuetable tr')).slice(1);
  var shown = 0, STEP = 50, btn = document.getElementById('qmore');
  function render() {{
    rows.forEach(function(r, i) {{ r.style.display = i < shown ? '' : 'none'; }});
    btn.style.display = shown >= rows.length ? 'none' : '';
    btn.textContent = 'Show more (' + (rows.length - shown) + ' left)';
  }}
  function more() {{ shown = Math.min(shown + STEP, rows.length); render(); }}
  btn.addEventListener('click', more);
  more();
  // if the URL targets a specific row, reveal up to it and scroll
  if (location.hash) {{
    var idx = rows.findIndex(function(r) {{ return '#' + r.id === location.hash; }});
    if (idx >= 0) {{ shown = Math.min(rows.length, Math.max(shown, idx + 1)); render();
      var el = document.getElementById(location.hash.slice(1)); if (el) el.scrollIntoView(); }}
  }}
}})();
</script>"""
    return page("Research backlog — RightsAtlas",
                "Titles queued for future copyright research. Not a public-domain list — "
                "no conclusions here, only researched dossiers carry verdicts.", body,
                extra_head='<meta name="robots" content="noindex">')


def corrections_page(corrections):
    if corrections:
        rows = ""
        for c in sorted(corrections, key=lambda x: x["date"], reverse=True):
            fid = c.get("film_id")
            title = (f'<a href="{BASE}film/{e(fid)}/">{e(c.get("title", fid))}</a>'
                     if fid else e(c.get("title", "—")))
            rows += (f'<tr><td>{e(c["date"])}</td><td>{title}</td>'
                     f'<td>{e(c.get("layer", "—"))}</td>'
                     f'<td>{e(c["change"])}<div class="why">{e(c["why"])}</div></td></tr>')
        table = (f'<table class="listing corrections"><tr><th>Date</th><th>Film</th>'
                 f'<th>Layer</th><th>What changed &amp; why</th></tr>{rows}</table>')
    else:
        table = "<p>No corrections issued yet.</p>"
    body = f"""<h1>Corrections</h1>
<p class="hint">When we get something wrong, we fix it in the open and log it here.
A public correction is a health signal, not an embarrassment — it is how an
evidence-first project earns trust. Spotted an error?
<a href="https://github.com/BitGitty/rightsatlas/issues/new?template=film-suggestion.yml" rel="nofollow">Tell us →</a></p>
{table}"""
    return page("Corrections — RightsAtlas",
                "Every correction RightsAtlas has issued, with what changed and why.", body)


def build():
    films = []
    errors = []
    for p in sorted((ROOT / "data" / "films").glob("*.json")):
        f = json.loads(p.read_text(encoding="utf-8"))
        errors += engine.validate(f)
        films.append(engine.apply_auto_rules(f))
    if errors:
        print("PROVENANCE ERRORS — build refused:")
        for err in errors:
            print("  -", err)
        sys.exit(1)

    # T-02 phase 1 (v4): warn (do not fail) on likely_pd print layers still in data/films.
    # Phase 3 flips this to a hard error once all films are migrated to evidenced statuses.
    likely = [f["id"] for f in films if f["layers"]["print"]["status"] == "likely_pd"]
    if likely:
        print(f"T-02 WARNING: {len(likely)} film(s) still have a likely_pd print layer "
              f"(migrate to evidenced verified_pd or downgrade): {', '.join(likely)}")

    # research backlog = queue rows not yet promoted to a verified dossier (M3, v4 §4.2)
    verified_ids = {f["id"] for f in films}
    queue_file = ROOT / "data" / "queues" / "research_queue_500.json"
    queue = json.loads(queue_file.read_text(encoding="utf-8")) if queue_file.exists() else []
    backlog = [r for r in queue if r["id"] not in verified_ids]

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    for a in (ROOT / "assets").iterdir():
        shutil.copy(a, OUT / "assets" / a.name)
    static = ROOT / "static"
    if static.exists():
        for a in static.iterdir():
            shutil.copy(a, OUT / a.name)

    (OUT / "index.html").write_text(index_page(films, len(backlog)), encoding="utf-8")
    (OUT / "queue").mkdir()
    (OUT / "queue" / "index.html").write_text(queue_page(backlog), encoding="utf-8")
    (OUT / "films").mkdir()
    (OUT / "films" / "index.html").write_text(films_index(films), encoding="utf-8")
    for f in films:
        d = OUT / "film" / f["id"]
        d.mkdir(parents=True)
        (d / "index.html").write_text(film_page(f), encoding="utf-8")

    for extra in ("methodology", "about", f"entering-public-domain-{NEXT_CLASS + 96}"):
        src = ROOT / "content" / f"{extra}.html"
        if src.exists():
            d = OUT / extra
            d.mkdir(parents=True)
            title, _, rest = src.read_text(encoding="utf-8").partition("\n")
            (d / "index.html").write_text(
                page(title.strip(), title.strip(), rest), encoding="utf-8")

    # research packets (generated by scripts/export_evidence.py --all) — served for download
    packets = ROOT / "packets"
    if packets.exists():
        (OUT / "packets").mkdir(parents=True, exist_ok=True)
        for mdf in packets.glob("*.md"):
            shutil.copy(mdf, OUT / "packets" / mdf.name)

    # corrections page (v4 §6.4) — public trust signal
    corr_file = ROOT / "data" / "corrections.jsonl"
    corrections = [json.loads(ln) for ln in corr_file.read_text(encoding="utf-8").splitlines()
                   if ln.strip()] if corr_file.exists() else []
    (OUT / "corrections").mkdir(parents=True, exist_ok=True)
    (OUT / "corrections" / "index.html").write_text(corrections_page(corrections), encoding="utf-8")

    # unified search index: verified dossiers + backlog rows (kind tags the section)
    search_idx = ([{"id": f["id"], "title": f["title"], "year": f["year"], "kind": "verified"} for f in films]
                  + [{"id": r["id"], "title": r["title"], "year": r["year"], "kind": "queue"} for r in backlog])
    (OUT / "assets" / "index.json").write_text(json.dumps(search_idx), encoding="utf-8")

    urls = [f"{BASE}"] + [f"{BASE}film/{f['id']}/" for f in films]
    host = os.environ.get("SITE_ORIGIN", "https://example.org")
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{host}{u}</loc></url>" for u in urls)
        + "</urlset>", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {host}{BASE}sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {len(films)} dossiers -> {OUT} (cutoff year: {CUTOFF})")


if __name__ == "__main__":
    build()
