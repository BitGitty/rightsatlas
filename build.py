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


def index_page(films):
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
<input id="q" type="search" placeholder="Search a film title…" autocomplete="off">
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

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    for a in (ROOT / "assets").iterdir():
        shutil.copy(a, OUT / "assets" / a.name)
    static = ROOT / "static"
    if static.exists():
        for a in static.iterdir():
            shutil.copy(a, OUT / a.name)

    (OUT / "index.html").write_text(index_page(films), encoding="utf-8")
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

    search_idx = [{"id": f["id"], "title": f["title"], "year": f["year"]} for f in films]
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
