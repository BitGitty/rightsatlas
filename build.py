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
from urllib.parse import quote

import engine
sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
import seasons  # noqa: E402

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site"
BASE = os.environ.get("BASE_URL", "/").rstrip("/") + "/"
YEAR = date.today().year
CUTOFF = engine.pd_cutoff_year()
NEXT_CLASS = engine.next_pd_class_year()
# lower-case so canonical/sitemap URLs match the Search Console property (bitgitty.github.io) exactly
HOST = os.environ.get("SITE_ORIGIN", "https://example.org").lower()
# Every "entering-public-domain-YYYY" page ever written stays built. The nav links next
# January's class; until that page is written it falls back to the newest one, so the
# Class-of page never 404s on Public Domain Day (it used to vanish on 1 January).
CLASSES = sorted(int(p.stem.rsplit("-", 1)[1])
                 for p in (ROOT / "content").glob("entering-public-domain-*.html"))
CLASS_YEAR = NEXT_CLASS + 96 if (NEXT_CLASS + 96) in CLASSES or not CLASSES else CLASSES[-1]

DISCLAIMER = (
    "RightsAtlas publishes research about the copyright status of works — "
    "it is not legal advice, and it describes <strong>United States</strong> status only; "
    "other countries' terms differ. Verify independently before commercial use."
)

# same Supabase project/key the analytics snippet already uses (publishable anon key —
# safe client-side, same trust level as the existing track_view/stats calls).
SUPABASE_URL = "https://uumiwuvbxzmtxuwmutis.supabase.co"
SUPABASE_KEY = "sb_publishable_E2ECaIgR-2fLWAEeDfVnMA_5_balO9b"

# GitHub issue template — kept as the <noscript> / network-failure fallback now that
# /suggest/ submits straight to Supabase (submit_suggestion RPC) for JS-enabled visitors.
SUGGEST_URL = "https://github.com/BitGitty/rightsatlas/issues/new?template=film-suggestion.yml"

# v3 sticky top nav (owner feature A). "class2027" always points at whichever
# entering-public-domain-YYYY page is actually live (CLASS_YEAR, computed above).
# 2026-11-20 owner redesign: 5 main tabs + "More" + an always-visible search button; phones get a ☰ menu.
NAV = [
    ("films", "Films", f"{BASE}films/"),
    ("songs", "Songs", f"{BASE}songs/"),
    ("tools", "Tools", f"{BASE}tools/"),
    ("blog", "Blog", f"{BASE}blog/"),
    ("about", "About", f"{BASE}about/"),
]
NAV_MORE = [
    ("class2027", f"Free on 1 January {CLASS_YEAR}", f"{BASE}entering-public-domain-{CLASS_YEAR}/"),
    ("collections", "Collections", f"{BASE}collections/"),
    ("how", "How we check", f"{BASE}methodology/"),
    ("corrections", "Corrections", f"{BASE}corrections/"),
    ("suggest", "Suggest a title", f"{BASE}suggest/"),
]

# short tab labels for the collections sub-nav (owner feature B) — real names/order,
# keyed by the slugs data/collections.json actually defines.
COLLECTION_SHORT = {
    "halloween-horror": "Halloween",
    "christmas-classics": "Christmas",
    "thanksgiving": "Thanksgiving",
    "new-years-eve": "New Year's Eve",
    "valentines-romance": "Valentine's",
    "independence-day-americana": "Independence Day",
}

# plain-English risk tag for the "Can I..." panel — derived straight from the
# green/amber/red tier engine.guidance() already computes, not a new claim.
RISK_TAG = {"green": "Lower risk", "amber": "Caution", "red": "Higher risk"}


def e(s):
    return html.escape(str(s), quote=True)


def main_nav(current):
    def links(items):
        return "".join(f'<a href="{href}" class="{"tab current" if key == current else "tab"}"'
                       f'{" aria-current=\"page\"" if key == current else ""}>{e(label)}</a>' for key, label, href in items)
    more_cur = " current" if any(k == current for k, _, _ in NAV_MORE) else ""
    return (f'<nav class="mainnav" aria-label="Main">{links(NAV)}'
            f'<details class="more"><summary class="tab{more_cur}">More ▾</summary><div class="moremenu">{links(NAV_MORE)}</div></details></nav>'
            f'<a class="searchbtn" href="{BASE}search/" aria-label="Search films and songs">🔎<span> Search</span></a>'
            f'<details class="mobmenu"><summary aria-label="Menu">☰</summary><nav aria-label="Menu">{links(NAV + NAV_MORE)}</nav></details>')


def collections_subnav(collections, current_slug=None):
    items = [("All collections", f"{BASE}collections/", current_slug is None)]
    for c in collections:
        items.append((COLLECTION_SHORT.get(c["slug"], c["h1"]),
                      f"{BASE}collections/{c['slug']}/", c["slug"] == current_slug))
    links = ""
    for label, href, cur in items:
        cls = "tab sub current" if cur else "tab sub"
        aria = ' aria-current="page"' if cur else ""
        links += f'<a href="{href}" class="{cls}"{aria}>{e(label)}</a>'
    return f'<div class="subnav-wrap"><nav class="subnav" aria-label="Collections">{links}</nav></div>'


def page(title, desc, body, extra_head="", nav=None, path="", subnav="", card="summary"):
    canon = f"{HOST}{BASE}{path}"
    head = f"""<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800&family=IBM+Plex+Mono:wght@400;500&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="RightsAtlas">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{canon}">
<meta name="twitter:card" content="{card}">
<meta name="robots" content="max-image-preview:large">
<meta name="p:domain_verify" content="0a3a02be80579a322d28fc07d6c05c25">
<link rel="alternate" type="application/rss+xml" title="RightsAtlas blog" href="{BASE}blog/feed.xml">
{extra_head}"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="stylesheet" href="{BASE}assets/style.css">
{head}
</head>
<body>
<header class="top">
  <div class="topin">
    <a class="brand" href="{BASE}">
      <span class="bars" aria-hidden="true"><span class="b1"></span><span class="b2"></span><span class="b3"></span><span class="b4"></span><span class="b5"></span></span>
      <span class="word">RightsAtlas</span>
    </a>
    {main_nav(nav)}
  </div>
{subnav}</header>
<main>
{body}
</main>
<footer>
  <div class="footin">
    <div class="footleft">
      <p class="disclaimer">{DISCLAIMER}</p>
      <p class="copyright">© {YEAR} RightsAtlas · research last-reviewed dates are shown per page.</p>
    </div>
    <nav class="footnav" aria-label="Footer">
      <a href="{BASE}methodology/">How it works</a>
      <a href="{BASE}corrections/">Corrections</a>
      <a href="{BASE}suggest/">Suggestions</a>
      <a href="{BASE}about/">About</a>
    </nav>
  </div>
  <div class="footin follow"><span>Follow us:</span>
    <a href="https://bsky.app/profile/rightsatlas.net" rel="me noopener">Bluesky</a>
    <a href="https://mastodon.social/@rightsatlas" rel="me noopener">Mastodon</a>
    <a href="https://x.com/RightsAtlas" rel="me noopener">X</a>
    <a href="https://www.pinterest.com/rightsatlas/" rel="me noopener">Pinterest</a>
    <a href="{BASE}blog/feed.xml">RSS</a>
  </div>
</footer>
<script>/* first-party analytics */(function(){{try{{fetch("https://uumiwuvbxzmtxuwmutis.supabase.co/rest/v1/rpc/track_view",{{method:"POST",headers:{{"apikey":"sb_publishable_E2ECaIgR-2fLWAEeDfVnMA_5_balO9b","Authorization":"Bearer sb_publishable_E2ECaIgR-2fLWAEeDfVnMA_5_balO9b","Content-Type":"application/json"}},body:JSON.stringify({{p_site:"rightsatlas",p_path:location.pathname,p_ref:document.referrer||null}}),keepalive:true}}).catch(function(){{}})}}catch(e){{}}}})();</script>
</body>
</html>"""


def status_badge(status):
    # public UI shows Clear/Unclear/Active; the precise internal status is the tooltip
    label, cls = engine.public_label(status)
    return f'<span class="badge {cls}" title="{e(engine.STATUSES[status][0])}">{e(label)}</span>'


def evidence_list(evidence):
    if not evidence:
        return '<p class="ev none">No primary evidence on file — treated as unverified.</p>'
    items = []
    for ev in evidence:
        link = f' — <a href="{e(ev["url"])}" rel="nofollow noopener">{e(ev.get("source", "source"))}</a>' if ev.get("url") else ""
        items.append(f'<li><span class="evtype">{e(ev.get("type", "note"))}</span> {e(ev["note"])}{link}</li>')
    return f'<ul class="ev">{"".join(items)}</ul>'


def film_page(f, post=None):
    g = engine.guidance(f)
    decade = (f["year"] // 10) * 10
    breadcrumb = (f'<nav class="breadcrumb" aria-label="Breadcrumb">'
                  f'<a href="{BASE}films/">Films</a> / <a href="{BASE}films/{decade}s/">{decade}s</a> / '
                  f'<span>{e(f["title"])}</span></nav>')

    rf_rows = "".join(
        f'<div class="rf-row"><span class="rf-label">{e(label)}</span>{status_badge(f["layers"][key]["status"])}</div>'
        for key, label in engine.LAYERS)
    rightsfacts = f"""<div class="rightsfacts" aria-label="Rights Facts for {e(f["title"])}">
  <div class="rf-title">Rights Facts</div>
  <div class="rf-head"><span>Layer</span><span>US status</span></div>
  {rf_rows}
  <p class="rf-note">Verified {e(f.get("last_verified", "—"))} · sources cited per layer · United States only</p>
</div>"""

    canpanel = f"""<div class="canpanel">
  <h2>Can I…</h2>
  <div class="qrow">
    <div class="qhead"><h3>Watch it (stream the archival copy, share the link)?</h3>
      <span class="risktag {g["watch"][0]}">{e(RISK_TAG[g["watch"][0]])}</span></div>
    <p>{e(g["watch"][1])}</p>
  </div>
  <div class="qrow">
    <div class="qhead"><h3>Reuse it (remix, upload, monetize)?</h3>
      <span class="risktag {g["reuse"][0]}">{e(RISK_TAG[g["reuse"][0]])}</span></div>
    <p>{e(g["reuse"][1])}</p>
  </div>
</div>"""

    record_rows = "".join(f"""<details>
  <summary>{e(label)} <span class="rtoggle">{status_badge(f["layers"][key]["status"])} ▾</span></summary>
  <div class="recbody">{evidence_list(f["layers"][key].get("evidence"))}</div>
</details>""" for key, label in engine.LAYERS)

    watch_html = ""
    for w in f.get("watch", []):
        watch_html += (f'<li><a href="{e(w["url"])}" rel="nofollow noopener">'
                       f'{e(w.get("label", "Watch on archive.org"))}</a>'
                       f'{" · " + e(w["quality"]) if w.get("quality") else ""}</li>')
    # 2026-11-20 owner "go": people search "watch <film> free" far more than "is it public domain".
    # Embed the archive.org player, but only when the print is verified public domain (never on
    # unverified pages: that would read as our endorsement of copying it).
    verified = f["layers"]["print"]["status"] == "verified_pd"
    arch = next((w["url"].rsplit("/details/", 1)[1].strip("/") for w in f.get("watch", [])
                 if "archive.org/details/" in w["url"]), None) if verified else None
    player = (f'<section class="embed watchnow" id="watch"><h2>Watch {e(f["title"])} ({f["year"]}) free</h2>'
              f'<iframe loading="lazy" src="https://archive.org/embed/{e(arch)}" title="{e(f["title"])} '
              f'on the Internet Archive" allowfullscreen></iframe>'
              f'<p class="credit">Streamed from the <a href="https://archive.org/details/{e(arch)}" '
              f'rel="nofollow noopener">Internet Archive</a>. The film print is public domain in the US; '
              f'a copy with a newer added score may carry separate music rights.</p></section>') if arch else ""
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
             "countryOfOrigin": f.get("country", "US"), "url": f"{HOST}{BASE}film/{f['id']}/",
             **({"isAccessibleForFree": True} if arch else {})},
            {"@type": "FAQPage", "mainEntity": faq_ld} if faq_ld else {},
        ],
    }
    body = f"""
{breadcrumb}
<article class="dossier">
<h1>{e(f["title"])}</h1>
<p class="lead">Is <em>{e(f["title"])}</em> ({f["year"]}) public domain?</p>
<p class="meta">Country of origin: {e(f.get("country", "US"))} · Last verified:
{e(f.get("last_verified", "—"))} · Researched by RightsAtlas (AI-assisted, with automated evidence and fact checks)</p>

<div class="verdict {engine.public_label(f["layers"]["print"]["status"])[1]}">
  <span class="vhead">Film print:</span> <strong>{e(engine.public_label(f["layers"]["print"]["status"])[0])}</strong>
  <span class="vsub">— this answer is about the film itself only, not its music, story or restorations (see below).</span>
</div>
{player}
{'<p class="whyunclear">Why <b>Unclear</b>, not Clear? This film is widely treated as public domain, but we have not yet attached a primary renewal-search citation — so the verdict stays Unclear until that evidence is on this page. The background and notes below describe the widely-understood status; the label above is the conservative, evidence-gated verdict.</p>' if f["layers"]["print"]["status"] in ("likely_pd", "undetermined") else ''}

<div class="risk">⚠️ <strong>Planning to upload or monetize?</strong> A public-domain film print does
<em>not</em> clear the <a href="#layers">music score, story, or restorations</a> — and the score is
the single most common cause of YouTube Content ID claims. Check every layer, not just the print.{
'  <br><strong>Pre-1972 sound recordings</strong> can be protected under US state law and the Music Modernization Act until 2067 or later — the print being public domain does not free the recorded music.' if f["year"] < 1972 else ''}</div>

<p class="hint">A film is not one copyright — it is several. Each layer below
can be free or protected independently. This is why one-click “public domain”
answers are wrong so often.</p>
<div class="layercols">{rightsfacts}{canpanel}</div>

<p class="packet"><a href="{BASE}packets/{e(f["id"])}.md" rel="nofollow" download>📄 Download the print-layer research packet (Markdown)</a>
<span class="packet-note">— citations you can attach to a dispute. Not legal advice; print layer only.</span>
· <a href="{BASE}suggest/?kind=correction&amp;page={quote(f"{f['title']} ({f['year']})")}">Spotted an error? Send a correction</a></p>

<section class="record"><h2 id="layers">The record behind each answer</h2>{record_rows}</section>
{f'<h2>Automatic rule notes</h2><ul class="notes">{notes}</ul>' if notes else ''}

{f'<h2>Watch it free (archival copies)</h2><ul class="watch">{watch_html}</ul>' if watch_html else ''}

{f'<p class="readpost">Read our article: <a href="{BASE}blog/{post["slug"]}/">{e(post["title"])}</a></p>' if post else ''}
<h2>Background</h2>
{"".join(f"<p>{e(p)}</p>" for p in f.get("editorial", "").split(chr(10) * 2) if p.strip())}

{f'<h2>Common questions</h2>{faq_html}' if faq_html else ''}
{embed}
</article>
<script type="application/ld+json">{json.dumps(ld)}</script>"""
    desc = (f'{f["title"]} ({f["year"]}) US copyright status, layer by layer, '
            f'with primary-source evidence and free legal watch links.')
    title = f'Is {f["title"]} ({f["year"]}) public domain? — RightsAtlas'
    if arch:
        title = f'Is {f["title"]} ({f["year"]}) public domain? Yes: watch it free — RightsAtlas'
        desc = (f'Watch {f["title"]} ({f["year"]}) free and legally. Its US film print is verified public '
                f'domain; here is the evidence, plus the music and story layers to check before reuse.')
    # 2026-11-20: share previews + film<->blog internal links (Google ranks pages that link each other)
    img = f'{HOST}{BASE}blog/img/{post["hero"]}' if post else ""
    head = f'<meta property="og:image" content="{img}">\n<meta name="twitter:image" content="{img}">' if img else ""
    return page(title, desc, body, extra_head=head, card="summary_large_image" if img else "summary",
                nav="films", path=f"film/{f['id']}/")


def index_page(films, backlog_count):
    seasonal = "".join(
        f'<section class="callout seasonal"><h2>{e(c["h1"])}</h2><p>{e(c["intro"][0])}</p>'
        f'<p><a href="{BASE}collections/{c["slug"]}/">See what\'s actually free →</a></p></section>'
        for c in seasons.in_season()
        if len(seasons.published(c, {f["id"] for f in films})) >= seasons.MIN_FILMS)
    cards = ""
    for f in sorted(films, key=lambda x: x["title"]):
        g = engine.guidance(f)
        cards += (f'<a class="card {g["reuse"][0]}" href="{BASE}film/{f["id"]}/">'
                  f'<strong>{e(f["title"])}</strong><span>{f["year"]}'
                  f'{" · <b class=\"watchmini\">▶ Watch free</b>" if watch_id(f) else ""}</span></a>')
    songs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SONGS.glob("*.json"))] if SONGS.exists() else []
    n_songs = len(songs)
    song_cards = "".join(
        f'<a class="card {song_label(s)[1]}" href="{BASE}song/{s["id"]}/"><strong>{e(s["title"])}</strong>'
        f'<span>{s["year"]} · {e(song_label(s)[0])}{" · <b class=\"watchmini\">▶ Listen</b>" if s.get("listen") else ""}</span></a>'
        for s in sorted(songs, key=lambda x: x["title"]))
    # the free player was only visible deep inside film pages (owner 2026-11-20): show it on the front page
    famous = ["nosferatu-1922", "metropolis-1927", "the-general-1926", "the-gold-rush-1925", "steamboat-willie-1928",
              "night-of-the-living-dead-1968", "safety-last-1923", "the-phantom-of-the-opera-1925"]
    by_id = {f["id"]: f for f in films}
    def thumb(i):  # our own public-domain still from the blog when we have one, else archive.org's frame
        return (f"{BASE}blog/img/{i}.jpg" if (BLOG / "img" / f"{i}.jpg").exists()
                else f"https://archive.org/services/img/{watch_id(by_id[i])}")
    watch_cards = "".join(
        f'<a class="watchcard" href="{BASE}film/{i}/#watch"><img src="{e(thumb(i))}" '
        f'alt="" loading="lazy"><span>▶ {e(by_id[i]["title"])} ({by_id[i]["year"]})</span></a>'
        for i in famous if i in by_id and watch_id(by_id[i]))
    n_watch = sum(1 for f in films if watch_id(f))
    # 2026-11-21 owner: "put music players together with the film player ... better design by adding artwork".
    # Each card: public-domain artwork (data/song_art.json, Commons sheet-music covers) + a real player on the home page.
    art = json.loads((ROOT / "data" / "song_art.json").read_text(encoding="utf-8")) \
        if (ROOT / "data" / "song_art.json").exists() else {}
    def music_card(s):
        L, a = s["listen"][0], art.get(s["id"])
        pic = (f'<img src="{BASE}{e(a["img"])}" alt="{e(a.get("what", s["title"]))}" loading="lazy">' if a else
               f'<div class="noart" aria-hidden="true"><span>♪</span><b>{s["year"]}</b></div>')
        return (f'<div class="musiccard">{pic}<div class="mc-body"><a href="{BASE}song/{s["id"]}/"><strong>{e(s["title"])}'
                f'</strong></a><span>{e(L["performer"])}, {L["year"]}</span>'
                f'<audio controls preload="none" src="{e(L["audio"])}"></audio></div></div>')
    listen_cards = "".join(music_card(s) for s in
                           sorted(songs, key=lambda x: x["listen"][0]["year"] if x.get("listen") else 0) if s.get("listen"))
    body = f"""<section class="hero">
<div class="hero-main">
<p class="kicker">Free answers, with sources</p>
<h1>Is it public domain?</h1>
<p class="lead">We check classic films and songs in the US, part by part: the film itself, its music, its story.
Every answer shows where it comes from.</p>
<form class="bigsearch" action="{BASE}search/" method="get" role="search">
<label for="hq" class="sr">Search a film or a song</label>
<input id="hq" name="q" type="search" placeholder="Search a film or a song, e.g. Nosferatu" autocomplete="off">
<button type="submit">🔎 Search</button></form>
<div class="homecards">
<a class="homecard" href="{BASE}films/"><b>{len(films)}</b><span>Films</span><small>Which classic films are free, and why</small></a>
<a class="homecard" href="{BASE}songs/"><b>{n_songs}</b><span>Songs</span><small>Songs and recordings, checked separately</small></a>
<a class="homecard" href="{BASE}tools/"><b>4</b><span>Tools</span><small>Calculator, record finder, free movie picker</small></a>
</div>
<p id="ra-usage">🔎 <strong id="ra-usecount">0</strong> research lookups and counting</p>
<script>fetch("https://uumiwuvbxzmtxuwmutis.supabase.co/rest/v1/rpc/stats",{{method:"POST",headers:{{"apikey":"sb_publishable_E2ECaIgR-2fLWAEeDfVnMA_5_balO9b","Authorization":"Bearer sb_publishable_E2ECaIgR-2fLWAEeDfVnMA_5_balO9b","Content-Type":"application/json"}},body:JSON.stringify({{p_site:"rightsatlas"}})}}).then(function(r){{return r.json()}}).then(function(n){{var el=document.getElementById("ra-usecount"),w=document.getElementById("ra-usage");if(el&&w&&Number(n)>0){{el.textContent=Number(n).toLocaleString();w.style.display="block";}}}}).catch(function(){{}});</script>
<p class="coverage">{len(films)} films checked in full ·
<a href="{BASE}queue/">{backlog_count} more films waiting to be researched</a>
<span class="cov-note">(waiting = no answer yet, not a list of free films)</span></p>
</div>
</section>
<section class="watchfree">
<h2>▶ Watch free classic films</h2>
<p>{n_watch} films on this site are verified public domain in the US, and you can watch them right here, free.</p>
<div class="watchgrid">{watch_cards}</div>
<p><a href="{BASE}films/?watch=1">See all {n_watch} films you can watch free →</a></p>
</section>
<section class="watchfree listenfree" id="listen">
<h2>♪ Listen free: old recordings that are public domain</h2>
<p>US recordings published before {YEAR - 100} are free. Press play right here; tap a title for the full story.</p>
<div class="musicgrid">{listen_cards}</div>
</section>
{seasonal}
<section class="callout tools-callout">
<h2>Free tools</h2>
<ul>
<li><a href="{BASE}tools/#calculator">Public domain calculator</a>: enter a year and country, get the likely US status.</li>
<li><a href="{BASE}tools/#renewal-finder">Renewal record finder</a>: open the exact copyright catalog pages for any 1931-1963 film.</li>
<li><a href="{BASE}tools/#movie-night">Free movie night picker</a>: a random verified public domain film, ready to watch.</li>
<li><a href="{BASE}tools/#by-year">What becomes public domain each year</a>, and <a href="{BASE}blog/">our blog</a>: a new sourced post every day.</li>
<li><a href="{BASE}songs/">Public domain songs</a>: famous songs checked with sources, like the 1931 class that becomes free on 1 January 2027.</li>
</ul>
</section>
<section>
<h2>Films we have checked</h2>
<div class="grid">{cards}</div>
</section>
<section>
<h2>Songs we have checked</h2>
<div class="grid">{song_cards}</div>
</section>
<section class="callout">
<h2>January 1, {NEXT_CLASS + 96}: the next public domain class</h2>
<p>Every film published in {NEXT_CLASS} enters the US public domain on
January 1, {NEXT_CLASS + 96}. <a href="{BASE}entering-public-domain-{CLASS_YEAR}/">See what's coming →</a></p>
</section>
<section class="suggest">
<h2>Missing a film? Spotted something wrong?</h2>
<p>RightsAtlas grows from the community. Suggest a film to research, flag a broken
link or error, or pitch a feature — it goes straight to our research queue.</p>
<a class="suggest-btn" href="{BASE}suggest/">💡 Suggest a film or improvement</a>
</section>"""
    return page("Is it public domain? Free checks of classic films and songs — RightsAtlas",
                "Free, sourced answers: is a classic film or song public domain in the US? We check the film, "
                "its music and its story separately, and link a free copy to watch where the film is free.",
                body, nav=None, path="")


def collection_page(c, by_id, collections):
    fs = sorted((by_id[i] for i in seasons.published(c, set(by_id))), key=lambda f: (f["year"], f["title"]))
    short = {"print": "Film print", "score": "Music", "story": "Story", "trademark": "Trademarks",
             "restorations": "Restorations"}
    head = "".join(f"<th>{short.get(k, lbl)}</th>" for k, lbl in engine.LAYERS)
    rows = "".join(
        f'<tr><td><a href="{BASE}film/{f["id"]}/">{e(f["title"])}</a></td><td>{f["year"]}</td>'
        + "".join(f'<td>{status_badge(f["layers"][k]["status"])}</td>' for k, _ in engine.LAYERS)
        + "</tr>" for f in fs)
    intro = "".join(f"<p>{e(x)}</p>" for x in c["intro"])
    body = f"""<h1>{e(c["h1"])}</h1>
{intro}
<div class="tablewrap"><table class="listing">
<tr><th>Film</th><th>Year</th>{head}</tr>
{rows}</table></div>
<p class="backlink">{len(fs)} films · <a href="{BASE}collections/">all collections</a> ·
<a href="{BASE}films/">all researched films</a></p>"""
    return page(f'{c["title"]} ({YEAR}) — RightsAtlas', c["description"], body,
                nav="collections", path=f'collections/{c["slug"]}/',
                subnav=collections_subnav(collections, c["slug"]))


def collections_index(collections, by_id):
    items = "".join(
        f'<li><a href="{BASE}collections/{c["slug"]}/">{e(c["h1"])}</a> '
        f'({len(seasons.published(c, set(by_id)))} films)</li>' for c in collections)
    body = f"""<h1>Collections</h1>
<p>Classic films grouped by season and theme, each checked layer by layer.</p>
<ul>{items}</ul>"""
    return page("Collections — RightsAtlas", "Seasonal and themed collections of classic films "
                "with their US public-domain status, layer by layer.", body,
                nav="collections", path="collections/",
                subnav=collections_subnav(collections, None))


def watch_id(f):
    """archive.org id of a free copy, only when the film print is verified public domain (else None)."""
    if f["layers"]["print"]["status"] != "verified_pd":
        return None
    return next((w["url"].rsplit("/details/", 1)[1].strip("/") for w in f.get("watch", [])
                 if "archive.org/details/" in w["url"]), None)


def films_index(films):
    rows = ""
    for f in sorted(films, key=lambda x: (x["year"], x["title"])):
        p = f["layers"]["print"]["status"]
        w = watch_id(f)
        rows += (f'<tr{" class=\"canwatch\"" if w else ""}><td><a href="{BASE}film/{f["id"]}/">{e(f["title"])}</a></td>'
                 f'<td>{f["year"]}</td><td>{e(f.get("country", "US"))}</td>'
                 f'<td>{status_badge(p)}</td><td>{f"<a class=\"watchtag\" href=\"{BASE}film/{f["id"]}/#watch\">▶ Watch free</a>" if w else ""}</td></tr>')
    n_watch = sum(1 for f in films if watch_id(f))
    decades = sorted({(f["year"] // 10) * 10 for f in films})
    dec_links = " · ".join(f'<a href="{BASE}films/{d}s/">{d}s</a>' for d in decades)
    body = f"""<h1>All films we have checked</h1>
<p class="decnav">Browse by decade: {dec_links}</p>
<p><label class="inclq"><input type="checkbox" id="onlywatch"> Show only the {n_watch} films you can watch free here</label></p>
<p class="sorthint">Click a column heading to sort.</p>
<div class="tablewrap"><table class="listing" id="filmtable">
<tr><th data-s="text">Title ↕</th><th data-s="num">Year ↕</th><th data-s="text">Origin ↕</th><th data-s="text">Is the film free? ↕</th><th data-s="text">Watch ↕</th></tr>
{rows}</table></div>
<script>document.getElementById('onlywatch').onchange=function(){{var on=this.checked;
document.querySelectorAll('#filmtable tr:not(:first-child)').forEach(function(r){{r.hidden=on&&!r.classList.contains('canwatch');}});}};
if(/watch=1/.test(location.search)){{var c=document.getElementById('onlywatch');c.checked=true;c.onchange();}}</script>
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
    return page("All films we have checked — RightsAtlas",
                f"Every classic film RightsAtlas has checked, with its US public domain status. {n_watch} can be "
                f"watched free.", body, nav="films", path="films/")


def decade_hub(decade, films):
    fs = sorted(films, key=lambda x: x["title"])
    cards = ""
    for f in fs:
        pl, cls = engine.public_label(f["layers"]["print"]["status"])
        cards += (f'<a class="card {cls}" href="{BASE}film/{f["id"]}/">'
                  f'<strong>{e(f["title"])}</strong><span>{f["year"]} · {e(pl)}</span></a>')
    breadcrumb = (f'<nav class="breadcrumb" aria-label="Breadcrumb">'
                  f'<a href="{BASE}films/">Films</a> / <span>{decade}s</span></nav>')
    body = f"""{breadcrumb}
<h1>{decade}s films — US copyright status</h1>
<p>Evidence-backed US copyright status for {len(fs)} researched film{'s' if len(fs)!=1 else ''}
from the {decade}s — each with sources and a part-by-part answer. This is a
research list, <strong>not</strong> a public-domain list: “Clear” means the film print is public
domain in the US, “Unclear” means researched-but-not-yet-evidenced, “Active rights” means
protected. Always check the music and story layers before reuse.</p>
<div class="grid">{cards}</div>
<p class="backlink"><a href="{BASE}films/">← all researched films</a></p>"""
    return page(f"{decade}s Films — US Copyright Status · RightsAtlas",
                f"US copyright status of {decade}s films — layer-by-layer, evidence-backed, "
                f"with renewal records and watch links. A research list, not a PD list.", body,
                nav="films", path=f"films/{decade}s/")


def queue_page(backlog):
    # public backlog view: Title / Year / Status only — NO archetype, demand, or renewal_truth.
    rows = ""
    for r in sorted(backlog, key=lambda x: (x["year"], x["title"])):
        rows += (f'<tr id="{e(r["id"])}"><td>{e(r["title"])}</td>'
                 f'<td>{r["year"]}</td><td class="unr">not researched</td></tr>')
    body = f"""<h1>Films waiting to be researched (<em>not</em> a list of free films)</h1>
<p class="hint">These are titles queued for future research. <strong>A row here means
nothing about a film's copyright status</strong> — we have not verified it. Only the
Only <a href="{BASE}films/">films we have checked</a> have answers, with sources.
Want one prioritised? <a href="{BASE}suggest/?kind=film">Suggest it →</a></p>
<div class="tablewrap"><table class="listing queue" id="queuetable">
<tr><th>Title</th><th>Year</th><th>Status</th></tr>
{rows}</table></div>
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
    return page("Films waiting to be researched — RightsAtlas",
                "Titles queued for future copyright research. Not a public-domain list — "
                "no answers here yet; only checked films have answers.", body,
                extra_head='<meta name="robots" content="noindex">', nav="films", path="queue/")


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
        table = (f'<div class="tablewrap"><table class="listing corrections"><tr><th>Date</th><th>Film</th>'
                 f'<th>Layer</th><th>What changed &amp; why</th></tr>{rows}</table></div>')
    else:
        table = "<p>No corrections issued yet.</p>"
    body = f"""<h1>Corrections</h1>
<p class="hint">When we get something wrong, we fix it in the open and log it here.
A public correction is a health signal, not an embarrassment — it is how an
evidence-first project earns trust. Spotted an error?
<a href="{BASE}suggest/?kind=correction">Tell us →</a></p>
{table}"""
    return page("Corrections — RightsAtlas",
                "Every correction RightsAtlas has issued, with what changed and why.", body,
                nav="corrections", path="corrections/")


# (value, tile title, tile hint, message label, message placeholder) — one definition
# shared by the radio tiles and the per-kind message copy, so the two can't drift apart.
SUGGEST_KINDS = [
    ("film", "A film to research", "A title you want checked, layer by layer.",
     "Why this film? (optional)", "e.g. I perform live scores to it and need to know what is safe to use."),
    ("correction", "A correction", "Something on a page is wrong, outdated, or a link is dead.",
     "What is wrong?", "Tell us what the page says and what you believe is right. A source helps."),
    ("idea", "An idea for the site", "A tool, or a better way to show the evidence.",
     "Your idea", "What would make RightsAtlas more useful to you?"),
    ("other", "Something else", "Questions, partnerships, anything at all.",
     "Your message", "Anything you want to tell us."),
]

# message label/placeholder per kind, generated from SUGGEST_KINDS above so the JS and the
# server-rendered defaults can never drift apart.
_LABELS_JS = json.dumps({v: [lbl, ph] for v, _, _, lbl, ph in SUGGEST_KINDS})

# Plain vanilla JS — no framework. Submits straight to the submit_suggestion Supabase RPC
# (same project/key as the analytics snippet above); falls back to the GitHub issue link on
# a network/server error so the suggestion is never a dead end.
SUGGEST_JS = ("""
(function () {
  var SUPA = "%s/rest/v1/rpc/submit_suggestion";
  var KEY = "%s";
  var LABELS = %s;
  var form = document.getElementById("sform");
  var done = document.getElementById("sdone");
  var err = document.getElementById("serr");
  var fallback = document.getElementById("sfallback");
  var msgLabel = document.getElementById("msglabel");
  var msgInput = document.getElementById("msg");
  var filmGroup = document.getElementById("filmgroup");
  var whereGroup = document.getElementById("wheregroup");
  var tiles = form.querySelectorAll(".skind");

  function kind() {
    var r = form.querySelector('input[name="kind"]:checked');
    return r ? r.value : "film";
  }
  function sync() {
    var k = kind();
    filmGroup.hidden = k !== "film";
    whereGroup.hidden = k !== "correction";
    var lab = LABELS[k] || LABELS.other;
    msgLabel.textContent = lab[0];
    msgInput.placeholder = lab[1];
    msgInput.required = k !== "film";
    Array.prototype.forEach.call(tiles, function (t) {
      var on = t.querySelector("input").checked;
      t.classList.toggle("on", on);
    });
  }
  Array.prototype.forEach.call(form.querySelectorAll('input[name="kind"]'), function (r) {
    r.addEventListener("change", sync);
  });

  // prefill from ?kind=correction&page=... or ?kind=film&film=...
  var qs = new URLSearchParams(location.search);
  var qkind = qs.get("kind");
  if (qkind && LABELS[qkind]) {
    var radio = form.querySelector('input[name="kind"][value="' + qkind + '"]');
    if (radio) radio.checked = true;
  }
  if (qs.get("film")) document.getElementById("film").value = qs.get("film");
  if (qs.get("page")) document.getElementById("where").value = qs.get("page");
  sync();

  function showError(text) {
    err.textContent = text;
    err.hidden = false;
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    err.hidden = true;
    fallback.hidden = true;
    var k = kind();
    var film = document.getElementById("film").value.trim();
    var year = document.getElementById("year").value.trim();
    var where = document.getElementById("where").value.trim();
    var msg = msgInput.value.trim();
    var email = document.getElementById("email").value.trim();
    var hp = document.getElementById("website").value;
    if (k === "film" && !film) { showError("Please add the film title."); return; }
    if (k !== "film" && !msg) { showError("Please write a few words first."); return; }
    var btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = "Sending\\u2026";
    fetch(SUPA, {
      method: "POST",
      headers: { apikey: KEY, Authorization: "Bearer " + KEY, "Content-Type": "application/json" },
      body: JSON.stringify({
        p_site: "rightsatlas", p_kind: k, p_film: film || null, p_year: year || null,
        p_page: where || null, p_message: msg || null, p_email: email || null, p_hp: hp
      })
    }).then(function (r) { return r.json(); }).then(function (result) {
      btn.disabled = false;
      btn.textContent = "Send suggestion";
      if (result === "ok") {
        form.hidden = true;
        done.hidden = false;
        done.focus();
      } else {
        showError(typeof result === "string" ? result : "Something went wrong \\u2014 please try again.");
      }
    }).catch(function () {
      btn.disabled = false;
      btn.textContent = "Send suggestion";
      fallback.hidden = false;
    });
  });

  document.getElementById("sagain").addEventListener("click", function () {
    form.reset();
    form.hidden = false;
    done.hidden = true;
    err.hidden = true;
    fallback.hidden = true;
    sync();
    form.querySelector('input[name="kind"]:checked').focus();
  });
})();
""") % (SUPABASE_URL, SUPABASE_KEY, _LABELS_JS)


TOOLS_JS = r"""
(function(){
var BASE=%BASE%, Y=new Date().getFullYear(), FILMS=[];
var VOLS=%VOLS%;
function $(id){return document.getElementById(id);}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function norm(s){return String(s).toLowerCase().replace(/^(the|a|an)\s+/,'').replace(/[^a-z0-9]/g,'');}
function match(t,y){var n=norm(t);return FILMS.filter(function(f){return n&&norm(f.t)===n&&(!y||Math.abs(f.y-y)<=1);});}
function href(f){return BASE+(f.k==='song'?'song/':'film/')+f.id+'/';}
function dbLine(t,y){var m=match(t,y);return m.length?'<p class="tool-db">We have checked this: '+m.map(function(f){return '<a href="'+href(f)+'">'+esc(f.t)+' ('+f.y+(f.k==='song'?', song':'')+')</a> &rarr; '+esc(f.l);}).join(', ')+'</p>':'';}
// US sound recordings (Music Modernization Act 2018 for pre-1972 recordings): a different clock from songs/films
function recording(y){
  if(y<1923) return '<strong>Public domain in the US.</strong> Sound recordings published before 1923 are free.';
  if(y<=1946) return (y+100<Y)?'<strong>Public domain in the US.</strong> Recordings published 1923-1946 are protected for 100 years; this one was freed on 1 January '+(y+101)+'.':'<strong>Protected</strong> until 1 January '+(y+101)+' (recordings published 1923-1946 get 100 years).';
  if(y<=1956) return (y+110<Y)?'<strong>Public domain in the US</strong> (110-year term for 1947-1956 recordings).':'<strong>Protected</strong> until 1 January '+(y+111)+' (recordings published 1947-1956 get 110 years).';
  if(y<1972) return '<strong>Protected</strong> until 15 February 2067: all recordings from 1957 to 15 February 1972 stay protected until then.';
  if(y===1972) return '<strong>Protected.</strong> If it was recorded before 15 February 1972 it is protected until 15 February 2067; if later in 1972, it has federal copyright (95 years from publication).';
  return '<strong>Protected.</strong> Recordings from 1972 on have federal copyright, generally 95 years from publication or longer.';
}
var free=Y-96;  // works published in or before this year are public domain by age
// 1. calculator
function calc(){
  var y=parseInt($('cy').value,10), foreign=$('cc').value==='foreign', r=$('cr').value, n=$('cn').value, out, kind=$('ck').value;
  if(!y||y<1800||y>Y){$('cout').innerHTML='<p>Enter the year it was first published.</p>';return;}
  if(kind==='recording'){ $('crw').hidden=true; $('cnw').hidden=true;
    $('cout').innerHTML='<p>'+recording(y)+'</p><p class="tool-note">This is the recording only. The song itself (music and lyrics) has its own term: choose "Song" to check it. US only; not legal advice.</p>'+dbLine($('ct').value,y); return; }
  // 2026-11-21 (Crucible): a missing notice freed a work at publication in ANY year up to 1977, renewal or not
  $('crw').hidden=!(y>free&&y<=1963); $('cnw').hidden=!(y>free&&y<=1977);
  var until='protected until 1 January '+(y+96);
  if(y<=free) out='<strong>Public domain in the US.</strong> Works published in '+free+' or earlier have finished their copyright term.';
  else if(foreign&&y<=1977) out='<strong>Probably still protected in the US.</strong> Most foreign works from these years had their US copyright restored on 1 January 1996 (URAA), even without a renewal or notice. If so, it is '+until+'.';
  else if(y<=1963){
    if(n==='no') out='<strong>Public domain in the US</strong>, if it was really published without a copyright notice: it lost protection on publication.';
    else if(r==='no') out='<strong>Public domain in the US</strong>, if the copyright was really not renewed: it lapsed at the end of '+(y+28)+'.';
    else if(r==='yes') out='<strong>Protected</strong>, if it carried a copyright notice. A renewed work from '+y+' is '+until+'.';
    else out='<strong>It depends on the renewal.</strong> Not renewed: public domain since '+(y+29)+'. Renewed: '+until+'. Use the renewal record finder below.';
  } else if(y<=1977){
    if(n==='no') out='<strong>Public domain in the US</strong>, if it was published without a valid copyright notice.';
    else if(n==='yes') out='<strong>Protected.</strong> Renewal was automatic for works from 1964 on, so it is '+until+'.';
    else out='<strong>It depends on the copyright notice.</strong> Renewal was automatic from 1964, so only a missing notice can make it free.';
  } else if(y<1989) out='<strong>Most likely protected.</strong> A missing notice could still be fixed by registering within five years, so few works from these years are free.';
  else out='<strong>Protected.</strong> Works published from March 1989 on need no notice.';
  var note=kind==='song'?'This covers the song (music and lyrics) only. Every recording of it is a separate right: choose "Sound recording" to check one.':'This covers the main work only. Music, the underlying story, restorations and trademarks are separate.';
  $('cout').innerHTML='<p>'+out+'</p><p class="tool-note">'+note+' US only; not legal advice.</p>'+dbLine($('ct').value,y);
}
// 2. renewal record finder
function renew(){
  var t=$('rt').value.trim(), y=parseInt($('ry').value,10), h='';
  if(!t||!y){$('rout').innerHTML='<p>Enter the title and the year it was published.</p>';return;}
  if(y<=free) h='<p>No renewal needed: works from '+y+' are already public domain by age.</p>';
  else if(y>=1964) h='<p>Renewal became automatic for works from 1964 on, so there is nothing to look up. Check the copyright notice instead.</p>';
  else {
    h='<p>The renewal had to be filed in '+(y+27)+' or '+(y+28)+'. Look for "'+esc(t)+'" in these records:</p><ul>';
    if($('rk').value==='song') [y+27,y+28].forEach(function(v){ if(v<1978) h+='<li><a href="https://archive.org/search?query='+encodeURIComponent('"catalog of copyright entries" music '+v)+'" rel="nofollow noopener" target="_blank">Catalog of Copyright Entries, '+v+', music volumes (renewals)</a>: open the '+v+' volume and search "'+esc(t)+'"</li>'; });
    else [y+27,y+28].forEach(function(v){ if(VOLS[v]) h+='<li><a href="https://archive.org/details/'+VOLS[v]+'?q='+encodeURIComponent(t)+'" rel="nofollow noopener" target="_blank">Catalog of Copyright Entries, '+v+', motion pictures (renewals section)</a></li>'; });
    if(y+28>=1978) h+='<li><a href="https://publicrecords.copyright.gov/" rel="nofollow noopener" target="_blank">US Copyright Office public records</a>: search "'+esc(t)+'" (renewals filed from 1978 on are here)</li>';
    h+='</ul><p class="tool-note">An entry starting with "R" and a number is a renewal. No entry for the film in either year usually means it was not renewed; also check the music and story.</p>';
  }
  $('rout').innerHTML=h+dbLine(t,y);
}
// 3. movie night picker
function pick(){
  var w=FILMS.filter(function(f){return f.a&&f.k!=='song';}); if(!w.length) return;
  var f=w[Math.floor(Math.random()*w.length)];
  $('pout').innerHTML='<h3>'+esc(f.t)+' ('+f.y+')</h3><div class="embed"><iframe loading="lazy" src="https://archive.org/embed/'+encodeURIComponent(f.a)+'" title="'+esc(f.t)+'" allowfullscreen></iframe></div><p><a href="'+BASE+'film/'+f.id+'/">Why it is public domain, with the evidence</a></p>';
}
// which US recordings become free on 1 January x (Music Modernization Act bands)
function recYear(x){
  if(x<2022) return 'no US recordings were federally public domain before 1 January 2022.';
  if(x===2022) return 'on 1 January 2022 all US recordings published before 1923 became free.';
  if(x===2023) return 'no new recordings became free on 1 January 2023.';
  if(x<=2047) return 'on 1 January '+x+', US recordings published in '+(x-101)+' become free.';
  if(x<=2057) return 'no new recordings become free on 1 January '+x+' (recordings from 1947-1956 get 110 years).';
  if(x<=2067) return 'on 1 January '+x+', US recordings published in '+(x-111)+' become free; the rest fixed before 15 February 1972 follow on 15 February 2067.';
  return 'recordings from after 15 February 1972 follow the normal federal term.';
}
// 4. free in year X
function year(){
  var x=parseInt($('xy').value,10); if(!x||x<1978){$('xout').innerHTML='<p>Enter a year from 1978 on. (Before 1978 the term was 28 or 56 years, so it depended on renewal.)</p>';return;}
  // 2026-11-21 (Crucible): 1978-1998 -> renewed works from x-76 (75-year term); 1999-2018 -> nothing new (1998 term extension); 2019 on -> x-96
  if(x>=1999&&x<=2018){$('xout').innerHTML='<p>Nothing new entered the US public domain on 1 January '+x+'. The 1998 term extension added 20 years, so the next class (works from 1923) only became free on 1 January 2019.</p>';return;}
  var c=x>=2019?x-96:x-76, list=FILMS.filter(function(f){return f.y===c;});
  var h='<p>On 1 January '+x+', US works published in <strong>'+c+'</strong> '+(x<=Y?'entered':'enter')+' the public domain'+(x<2019?' (the ones still protected that long; most older works had already lapsed)':'')+'.</p>';
  h+=list.length?'<p>Films and songs from '+c+' we have checked:</p><ul>'+list.map(function(f){return '<li><a href="'+href(f)+'">'+esc(f.t)+'</a>'+(f.k==='song'?' (song)':'')+'</li>';}).join('')+'</ul>':'<p>We have no films or songs from '+c+' in our database yet. <a href="'+BASE+'suggest/">Suggest one</a>.</p>';
  h+='<p class="tool-note">Sound recordings follow a different clock: '+recYear(x)+'</p>';
  $('xout').innerHTML=h;
}
fetch(BASE+'assets/tools.json').then(function(r){return r.json();}).then(function(d){FILMS=d;}).catch(function(){});
['cy','cc','cr','cn','ct','ck'].forEach(function(i){$(i).addEventListener('input',calc);});
$('rgo').addEventListener('click',renew); $('pgo').addEventListener('click',pick); $('xgo').addEventListener('click',year);
$('xy').value=Y+1;
})();
"""


def tools_page():
    from cce_check import VOLS
    js = TOOLS_JS.replace("%VOLS%", json.dumps(VOLS)).replace("%BASE%", json.dumps(BASE))
    sel = lambda i, opts: f'<select id="{i}">' + "".join(f'<option value="{v}">{e(t)}</option>' for v, t in opts) + "</select>"
    ld = {"@context": "https://schema.org", "@type": "WebApplication", "name": "RightsAtlas public domain tools",
          "url": f"{HOST}{BASE}tools/", "applicationCategory": "ReferenceApplication", "operatingSystem": "Any",
          "isAccessibleForFree": True, "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
          "description": "Free public domain calculator, copyright renewal record finder, free movie picker and "
                         "a public-domain-by-year lookup for films, songs and sound recordings."}
    body = f"""<article class="dossier tools">
<h1>Free public domain tools</h1>
<p class="lead">Four free tools for checking whether a film, a song or a sound recording is public domain in the US,
finding the copyright renewal records yourself, and watching verified free films.</p>

<section class="tool" id="calculator"><h2>1. Public domain calculator</h2>
<p>Answer a few questions about a film, a song, a sound recording or any published work, and get its likely US status.
Songs and recordings are checked separately, because they follow different rules.</p>
<div class="toolform">
<label>What is it? {sel("ck", [("film", "Film, book or other work"), ("song", "Song (music and lyrics)"), ("recording", "Sound recording")])}</label>
<label>Title (optional) <input id="ct" type="text" autocomplete="off"></label>
<label>Year first published <input id="cy" type="number" min="1800" max="2100" inputmode="numeric"></label>
<label>Country {sel("cc", [("us", "United States"), ("foreign", "Outside the US")])}</label>
<label id="crw" hidden>Was the copyright renewed in its 28th year? {sel("cr", [("unknown", "I don't know"), ("no", "No"), ("yes", "Yes")])}</label>
<label id="cnw" hidden>Did it carry a copyright notice? {sel("cn", [("unknown", "I don't know"), ("yes", "Yes"), ("no", "No")])}</label>
</div><div id="cout" class="toolout" aria-live="polite"></div></section>

<section class="tool" id="renewal-finder"><h2>2. Renewal record finder</h2>
<p>For films and songs published 1931 to 1963, the copyright had to be renewed in its 28th year. Enter the title and
year, and we open the right catalog volumes to search.</p>
<div class="toolform"><label>Type {sel("rk", [("film", "Film"), ("song", "Song")])}</label>
<label>Title <input id="rt" type="text" autocomplete="off"></label>
<label>Year published <input id="ry" type="number" min="1900" max="2100" inputmode="numeric"></label>
<button id="rgo" type="button">Find the records</button></div>
<div id="rout" class="toolout" aria-live="polite"></div></section>

<section class="tool" id="movie-night"><h2>3. Free movie night picker</h2>
<p>One click picks a film whose US print we have verified as public domain, with a free copy to watch.</p>
<div class="toolform"><button id="pgo" type="button">Pick a free film</button></div>
<div id="pout" class="toolout" aria-live="polite"></div></section>

<section class="tool" id="by-year"><h2>4. What becomes public domain in a given year?</h2>
<p>Pick a year to see which works enter the US public domain on 1 January, and the films from that class we cover.</p>
<div class="toolform"><label>Year <input id="xy" type="number" min="1978" max="2200" inputmode="numeric"></label>
<button id="xgo" type="button">Show</button></div>
<div id="xout" class="toolout" aria-live="polite"></div></section>

<p class="tool-note">These tools apply the US rules explained in <a href="{BASE}methodology/">how it works</a>.
They are research aids, not legal advice.</p>
</article>
<script type="application/ld+json">{json.dumps(ld)}</script>
<script>{js}</script>"""
    return page("Free public domain calculator and film tools — RightsAtlas",
                "Free tools: a public domain calculator, a copyright renewal record finder, a free movie picker, "
                "and what enters the US public domain each year.", body, nav="tools", path="tools/")


def suggest_page(backlog_count):
    tiles = "".join(
        f'<label class="skind"><input type="radio" name="kind" value="{v}"{" checked" if v == "film" else ""}>'
        f'<span><b>{e(title)}</b><small>{e(hint)}</small></span></label>'
        for v, title, hint, _, _ in SUGGEST_KINDS)

    body = f"""<h1>Suggestions</h1>
<p class="lead">A film to research, a mistake to fix, or an idea for the site — tell us directly.
No account needed.</p>

<form id="sform" novalidate>
  <fieldset class="skindset">
    <legend>What kind of suggestion?</legend>
    <div class="suggestkinds">{tiles}</div>
  </fieldset>

  <div class="field" id="filmgroup">
    <label for="film">Film title</label>
    <input id="film" type="text" placeholder="e.g. The Phantom Carriage">
    <label for="year" class="sub">Year <span>(if known)</span></label>
    <input id="year" type="text" inputmode="numeric" placeholder="1921">
  </div>

  <div class="field" id="wheregroup" hidden>
    <label for="where">Which film or page?</label>
    <input id="where" type="text" placeholder="e.g. Nosferatu (1922), music score layer">
  </div>

  <div class="field">
    <label for="msg" id="msglabel">Why this film? (optional)</label>
    <textarea id="msg" rows="6" placeholder="e.g. I perform live scores to it and need to know what is safe to use."></textarea>
  </div>

  <div class="field">
    <label for="email">Email <span>(optional — only if you want a reply; never shown on the site)</span></label>
    <input id="email" type="email" placeholder="you@example.com">
  </div>

  <span class="hp" aria-hidden="true"><input type="text" id="website" name="website" tabindex="-1" autocomplete="off"></span>

  <p id="serr" class="formerr" role="alert" hidden></p>

  <div class="field-row">
    <button type="submit" class="suggest-btn">Send suggestion</button>
    <span class="suggest-note">Takes under a minute.</span>
  </div>
  <p id="sfallback" class="formerr" hidden>Couldn't reach the server. <a href="{SUGGEST_URL}" rel="nofollow">Send it on GitHub instead →</a></p>
</form>

<div id="sdone" role="status" tabindex="-1" hidden>
  <span class="received">Received</span>
  <h2>Thank you — got it.</h2>
  <p>We read every suggestion and act on it — see what happens next below.</p>
  <button type="button" id="sagain" class="suggest-btn ghost">Send another suggestion</button>
</div>

<noscript><p class="suggest-note">JavaScript is off, so this form can't submit here —
<a href="{SUGGEST_URL}" rel="nofollow">send your suggestion on GitHub instead →</a></p></noscript>

<h2>What happens next</h2>
<ol class="nextsteps">
<li><b>1</b><span>We read every suggestion.</span></li>
<li><b>2</b><span>Film requests join the <a href="{BASE}queue/">waiting list</a>
({backlog_count} titles currently waiting) and get a full part-by-part check before the
page goes live.</span></li>
<li><b>3</b><span>Corrections are fixed and logged on the <a href="{BASE}corrections/">Corrections</a> page.</span></li>
</ol>
<script>{SUGGEST_JS}</script>"""
    return page("Suggestions — RightsAtlas",
                "Suggest a film to research, flag a correction, or pitch a feature for RightsAtlas. "
                "No account needed.",
                body, nav="suggest", path="suggest/")


SONGS = ROOT / "data" / "songs"
SONG_LABEL = {"verified_pd": ("Public domain (US)", "ok"), "not_pd": ("Still protected", "no"),
              "undetermined": ("Not verified", "unk")}


def song_label(s):
    st = s["composition"]["status"]
    if st.startswith("enters_pd_"):
        y = int(st.rsplit("_", 1)[1])
        # an unrenewed song lapsed decades earlier, so the term date is the LATEST it becomes free
        return (f"Public domain since 1 January {y} (at the latest)", "ok") if date.today().year >= y else \
               (f"Public domain from 1 January {y} (at the latest)", "warn")
    return SONG_LABEL.get(st, ("Not verified", "unk"))


_ART = None


def song_art(sid):
    """Public-domain cover for a song (data/song_art.json, Commons sheet-music covers, checked per file 11-21)."""
    global _ART
    if _ART is None:
        p = ROOT / "data" / "song_art.json"
        _ART = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _ART.get(sid)


def listen_block(s):
    """2026-11-20 owner: 'play for music like films'. Only recordings that are themselves public domain in the US
    (published before 1926, Music Modernization Act), from Wikimedia Commons, with the year quoted from the file page.
    11-21 owner: 'why music player doesn't have thumbnails?' -> the song's cover sits next to the player."""
    items = [x for x in s.get("listen", []) if int(x.get("year", 9999)) <= YEAR - 101]
    if not items:
        return ""
    a = song_art(s["id"])
    cover = (f'<figure class="listen-art"><img src="{BASE}{e(a["img"])}" alt="{e(a.get("what", s["title"]))}">'
             f'<figcaption class="credit">{e(a.get("what", "Cover"))}, public domain, via '
             f'<a href="{e(a["page"])}" rel="nofollow noopener">Wikimedia Commons</a></figcaption></figure>') if a else ""
    players = cover + "".join(
        f'<figure class="listen"><figcaption>{e(x["performer"])} ({x["year"]})</figcaption>'
        f'<audio controls preload="none" src="{e(x["audio"])}"></audio>'
        f'<p class="credit">Public domain recording, via <a href="{e(x["page"])}" rel="nofollow noopener">Wikimedia Commons</a>.'
        f' US sound recordings published in {YEAR - 101} or earlier are free.</p></figure>' for x in items)
    return f'<section id="listen"><h2>▶ Listen free</h2>{players}</section>'


def mm_block(s):
    """Burmese songs (owner 2026-11-20): Myanmar status (life + 50 under the Copyright Law 2019 / Act 1914) next to
    the US one, which can differ because of the 1996 URAA restoration. English + Burmese, Unicode only."""
    m = s.get("mm")
    if not m:
        return ""
    ev = "".join(f'<li>{e(x["note"])} <a href="{e(x["url"])}" rel="nofollow noopener">{e(x["source"])}</a></li>'
                 for x in m.get("evidence", []))
    return (f'<h2>In Myanmar</h2><div class="verdict"><span class="vhead">Myanmar status:</span> '
            f'<strong>{e(m["label_en"])}</strong></div><p lang="my">{e(m["label_my"])}</p>'
            f'<p>{e(m["note_en"])}</p><p lang="my">{e(m["note_my"])}</p><ul class="evidence">{ev}</ul>')


def song_page(s):
    """2026-11-20 owner 'go music': song (composition) dossiers, same evidence-first idea as films."""
    label, cls = song_label(s)
    ev = "".join(f'<li>{e(x["note"])} <a href="{e(x["url"])}" rel="nofollow noopener">{e(x["source"])}</a></li>'
                 for x in s["composition"].get("evidence", []))
    rec_year = YEAR - 101  # US sound recordings: published 100+ years ago are free (Music Modernization Act)
    body = f"""<article class="dossier">
<p class="backlink"><a href="{BASE}songs/">← All songs</a></p>
<h1>{e(s["title"])}</h1>
{f'<p class="lead" lang="my">{e(s["title_my"])}</p>' if s.get("title_my") else ""}
<p class="lead">Is <em>{e(s["title"])}</em> ({s["year"]}) public domain?</p>
<p class="meta">Written by {e(s.get("writers", "unknown"))} · first published {s["year"]} · last verified {e(s.get("last_verified", "—"))}</p>
<div class="verdict {cls}"><span class="vhead">The song (music and lyrics):</span> <strong>{e(label)}</strong>
<span class="vsub">— this covers the composition only, not any recording of it.</span></div>
{listen_block(s)}
<h2>The evidence</h2><ul class="evidence">{ev}</ul>
<h2>Recordings are a separate right</h2>
<p>A song and a recording of it are two different copyrights. In the US, sound recordings follow the Music
Modernization Act: recordings published in {rec_year} or earlier are public domain, and each later year frees one more
year of recordings. A modern recording of a public domain song is still protected, so to use the song freely, record
or perform it yourself, or use a recording that is itself public domain.</p>
{mm_block(s)}
{f'<h2>Where you have heard it</h2><p>{e(s["famous_use"])} (<a href="{e(s["use_source"])}" rel="nofollow noopener">source</a>)</p>' if s.get("famous_use") else ""}
<p class="tool-note">Research, not legal advice. US status only; other countries differ. Spotted an error?
<a href="{BASE}suggest/">Send a correction</a>.</p>
</article>"""
    return page(f'Is {s["title"]} ({s["year"]}) public domain? — RightsAtlas',
                f'{s["title"]} ({s["year"]}), by {s.get("writers", "")}: US public domain status of the song, with '
                f'sources, and why recordings are separate.', body, nav="songs", path=f'song/{s["id"]}/')


def songs_index(songs):
    """Same table design as /films/ (owner 2026-11-20: 'why songs page design is different from films?')."""
    def badge(s):
        label, cls = song_label(s)
        return f'<span class="badge {cls}">{e(label)}</span>'
    rows = "".join(
        f'<tr><td>' + (f'<img class="songthumb" src="{BASE}{e(song_art(s["id"])["img"])}" alt="" loading="lazy">'
                         if song_art(s["id"]) else "") + f'<a href="{BASE}song/{s["id"]}/">{e(s["title"])}</a>'
        + (f' <span lang="my">{e(s["title_my"])}</span>' if s.get("title_my") and s["title_my"] not in s["title"] else "")
        + (f' <a class="watchtag" href="{BASE}song/{s["id"]}/#listen">▶ Listen</a>' if s.get("listen") else "")
        + f'</td><td>{s["year"]}</td><td>{e(s.get("writers", ""))}</td><td>{badge(s)}</td>'
        f'<td>{e(s["mm"]["label_en"]) if s.get("mm") else "—"}</td></tr>'
        for s in sorted(songs, key=lambda x: (x["year"], x["title"])))
    body = f"""<h1>All songs we have checked</h1>
<p class="lead">Is a song free to use in the US? We check the song itself (music and lyrics), with sources. Every
recording of a song is a separate right, explained on each page. For Burmese songs we also show the Myanmar status.</p>
<p class="sorthint">Click a column heading to sort.</p>
<div class="tablewrap"><table class="listing" id="songtable">
<tr><th data-s="text">Song ↕</th><th data-s="num">Year ↕</th><th data-s="text">Written by ↕</th><th data-s="text">Is the song free? (US) ↕</th><th data-s="text">In Myanmar ↕</th></tr>
{rows}</table></div>
<script>
(function() {{
  var t = document.getElementById('songtable'), asc = {{}};
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
    return page("Public domain songs — RightsAtlas", "Which famous songs are public domain in the US, with sources: "
                "the song and its recordings checked separately.", body, nav="songs", path="songs/")


BLOG = ROOT / "content" / "blog"


def blog_posts(today=None):
    """Published blog posts, newest first. File: content/blog/YYYY-MM-DD-slug.html with
    line 1 = title, line 2 = description, line 3 = "hero.jpg | alt text" (file in
    content/blog/img/, or blank), rest = body HTML ({{BASE}} is replaced). A post dated in the future stays
    hidden until the nightly build on/after that date: that is the scheduler (owner 2026-11-18)."""
    today = today or date.today()
    posts = []
    for src in sorted(BLOG.glob("????-??-??-*.html")):
        day = date.fromisoformat(src.name[:10])
        if day > today:
            continue
        title, desc, hero, body = (src.read_text(encoding="utf-8").split("\n", 3) + ["", "", ""])[:4]
        hero, _, alt = hero.partition("|")
        posts.append({"slug": src.stem[11:], "date": day, "title": title.strip(), "desc": desc.strip(),
                      "hero": hero.strip(), "alt": alt.strip(), "body": body.replace("{{BASE}}", BASE)})
    return sorted(posts, key=lambda p: p["date"], reverse=True)


def blog_post_page(p):
    path = f"blog/{p['slug']}/"
    img = f"{HOST}{BASE}blog/img/{p['hero']}" if p["hero"] else ""
    ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"],
          "description": p["desc"], "datePublished": p["date"].isoformat(),
          "author": {"@type": "Organization", "name": "RightsAtlas"},
          "mainEntityOfPage": f"{HOST}{BASE}{path}", **({"image": img} if img else {})}
    head = (f'<meta property="article:published_time" content="{p["date"].isoformat()}">\n'
            + (f'<meta property="og:image" content="{img}">\n<meta name="twitter:image" content="{img}">\n' if img else "")
            + f'<script type="application/ld+json">{json.dumps(ld)}</script>')
    hero = (f'<img class="blog-hero" src="{BASE}blog/img/{e(p["hero"])}" alt="{e(p["alt"])}" loading="eager">'
            if p["hero"] else "")
    body = (f'<article class="blog"><p class="backlink"><a href="{BASE}blog/">← All posts</a> · '
            f'<time datetime="{p["date"].isoformat()}">{p["date"].strftime("%d %B %Y").lstrip("0")}</time></p>'
            f'<h1>{e(p["title"])}</h1>{hero}{p["body"]}</article>')
    return page(f'{p["title"]} — RightsAtlas', p["desc"], body, extra_head=head, nav="blog", path=path,
                card="summary_large_image" if img else "summary")


def blog_index(posts):
    items = "".join(
        f'<li class="blog-item"><a href="{BASE}blog/{p["slug"]}/">'
        + (f'<img src="{BASE}blog/img/{e(p["hero"])}" alt="" loading="lazy">' if p["hero"] else "")
        + f'<span><strong>{e(p["title"])}</strong><br><small>{p["date"].strftime("%d %B %Y").lstrip("0")}'
        f'</small><br>{e(p["desc"])}</span></a></li>' for p in posts)
    body = ('<h1>Blog</h1><p>Short, sourced notes on classic films and US public domain: what is really '
            f'free, what is a trap, and how to check it yourself.</p><ul class="blog-list">{items}</ul>')
    return page("Blog — RightsAtlas", "Sourced notes on classic films and the US public domain.",
                body, nav="blog", path="blog/")


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
    for a in (ROOT / "assets").iterdir():  # 11-21: assets/art/ (song artwork) is a folder
        (shutil.copytree(a, OUT / "assets" / a.name, dirs_exist_ok=True) if a.is_dir()
         else shutil.copy(a, OUT / "assets" / a.name))
    static = ROOT / "static"
    if static.exists():
        for a in static.iterdir():
            shutil.copy(a, OUT / a.name)

    (OUT / "index.html").write_text(index_page(films, len(backlog)), encoding="utf-8")
    (OUT / "queue").mkdir()
    (OUT / "queue" / "index.html").write_text(queue_page(backlog), encoding="utf-8")
    (OUT / "films").mkdir()
    (OUT / "films" / "index.html").write_text(films_index(films), encoding="utf-8")
    # SEO decade hubs (indexed): /films/1930s/ etc.
    decades = {}
    for f in films:
        decades.setdefault((f["year"] // 10) * 10, []).append(f)
    for dec, fs in decades.items():
        d = OUT / "films" / f"{dec}s"
        d.mkdir(parents=True)
        (d / "index.html").write_text(decade_hub(dec, fs), encoding="utf-8")
    # a film spotlight post's hero image is "<film-id>.jpg": only LIVE posts are linked from film pages
    post_by_film = {p["hero"][:-4]: p for p in reversed(blog_posts()) if p["hero"].endswith(".jpg")}
    for f in films:
        d = OUT / "film" / f["id"]
        d.mkdir(parents=True)
        (d / "index.html").write_text(film_page(f, post_by_film.get(f["id"])), encoding="utf-8")

    by_id = {f["id"]: f for f in films}
    collections = [c for c in seasons.load() if len(seasons.published(c, set(by_id))) >= seasons.MIN_FILMS]
    (OUT / "collections").mkdir()
    (OUT / "collections" / "index.html").write_text(collections_index(collections, by_id), encoding="utf-8")
    for c in collections:
        (OUT / "collections" / c["slug"]).mkdir()
        (OUT / "collections" / c["slug"] / "index.html").write_text(
            collection_page(c, by_id, collections), encoding="utf-8")

    extras = []
    extra_nav = {"methodology": "how", "about": "about"}
    for extra in ("methodology", "about", *(f"entering-public-domain-{y}" for y in CLASSES)):
        src = ROOT / "content" / f"{extra}.html"
        if src.exists():
            extras.append(extra)
            nav_key = extra_nav.get(extra, "class2027" if extra.startswith("entering-public-domain-") else None)
            d = OUT / extra
            d.mkdir(parents=True)
            title, _, rest = src.read_text(encoding="utf-8").partition("\n")
            (d / "index.html").write_text(
                page(title.strip(), title.strip(), rest, nav=nav_key, path=f"{extra}/"), encoding="utf-8")

    songs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SONGS.glob("*.json"))] if SONGS.exists() else []
    if songs:
        (OUT / "songs").mkdir()
        (OUT / "songs" / "index.html").write_text(songs_index(songs), encoding="utf-8")
        for s in songs:
            (OUT / "song" / s["id"]).mkdir(parents=True)
            (OUT / "song" / s["id"] / "index.html").write_text(song_page(s), encoding="utf-8")

    posts = blog_posts()
    (OUT / "blog").mkdir()
    if (BLOG / "img").exists():
        shutil.copytree(BLOG / "img", OUT / "blog" / "img")
    (OUT / "blog" / "index.html").write_text(blog_index(posts), encoding="utf-8")
    # RSS (2026-11-20): Pinterest business accounts auto-pin from a feed (their API needs weeks of review and
    # browser automation breaks their rules); feed readers and Bing use it too. Image = the post's hero.
    items = "".join(
        f'<item><title>{e(p["title"])}</title><link>{HOST}{BASE}blog/{p["slug"]}/</link>'
        f'<guid isPermaLink="true">{HOST}{BASE}blog/{p["slug"]}/</guid>'
        f'<pubDate>{p["date"].strftime("%a, %d %b %Y")} 02:17:00 +0000</pubDate><description>{e(p["desc"])}</description>'
        + (f'<enclosure url="{HOST}{BASE}blog/img/{e(p["hero"])}" type="image/jpeg" length="0"/>'
           f'<media:content url="{HOST}{BASE}blog/img/{e(p["hero"])}" medium="image"/>' if p["hero"] else "")
        + "</item>" for p in posts[:30])
    (OUT / "blog" / "feed.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">'
        f'<channel><title>RightsAtlas blog</title><link>{HOST}{BASE}blog/</link>'
        '<description>Sourced notes on classic films and the US public domain.</description><language>en</language>'
        f'{items}</channel></rss>', encoding="utf-8")
    for p in posts:
        (OUT / "blog" / p["slug"]).mkdir()
        (OUT / "blog" / p["slug"] / "index.html").write_text(blog_post_page(p), encoding="utf-8")

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

    # on-site Suggestions page (v3 nav feature) — real explanation + the one real
    # submission mechanism the site has (SUGGEST_URL), not a fabricated backend.
    (OUT / "suggest").mkdir(parents=True, exist_ok=True)
    (OUT / "suggest" / "index.html").write_text(suggest_page(len(backlog)), encoding="utf-8")

    # unified search index: verified dossiers + backlog rows (kind tags the section)
    search_idx = ([{"id": f["id"], "title": f["title"], "year": f["year"], "kind": "verified"} for f in films]
                  + [{"id": s["id"], "title": s["title"], "year": s["year"], "kind": "song",
                      "alt": s.get("title_my", "")} for s in songs]
                  + [{"id": r["id"], "title": r["title"], "year": r["year"], "kind": "queue"} for r in backlog])
    # /search/ (2026-11-20 redesign): the header 🔎 button lands here; ?q= comes from the home-page search form
    (OUT / "search").mkdir(parents=True, exist_ok=True)
    (OUT / "search" / "index.html").write_text(page(
        "Search films and songs — RightsAtlas", "Search every film and song RightsAtlas has checked.",
        f'<h1>Search</h1><div class="searchwrap"><label for="q">Search a film or a song</label>'
        f'<div class="searchbox"><input id="q" type="search" placeholder="Type a title…" autocomplete="off" autofocus></div>'
        f'<label class="inclq"><input type="checkbox" id="inclq"> also show films we have not researched yet</label>'
        f'<div id="results"></div><p class="asksuggest">Not here yet? <a href="{BASE}suggest/">Ask us to check it</a>.</p></div>',
        extra_head=f'<script src="{BASE}assets/fuse.min.js"></script><script src="{BASE}assets/search.js" defer></script>',
        path="search/"), encoding="utf-8")
    (OUT / "assets" / "index.json").write_text(json.dumps(search_idx), encoding="utf-8")

    # /tools/ (owner 2026-11-20 "go tools"): calculator, renewal finder, movie picker, by-year lookup.
    # tools.json = our films with their print verdict label and (verified + watchable only) archive id
    def arch_id(f):
        if f["layers"]["print"]["status"] != "verified_pd":
            return None
        return next((w["url"].rsplit("/details/", 1)[1].strip("/") for w in f.get("watch", [])
                     if "archive.org/details/" in w["url"]), None)
    tools_idx = [{"id": f["id"], "t": f["title"], "y": f["year"], "k": "film",
                  "l": engine.public_label(f["layers"]["print"]["status"])[0], "a": arch_id(f)} for f in films]
    tools_idx += [{"id": s["id"], "t": s["title"], "y": s["year"], "k": "song", "l": song_label(s)[0]}
                  for s in (json.loads(p.read_text(encoding="utf-8")) for p in sorted(SONGS.glob("*.json")))]
    (OUT / "assets" / "tools.json").write_text(json.dumps(tools_idx), encoding="utf-8")
    (OUT / "tools").mkdir(parents=True, exist_ok=True)
    (OUT / "tools" / "index.html").write_text(tools_page(), encoding="utf-8")

    urls = ([f"{BASE}", f"{BASE}films/", f"{BASE}suggest/"]
            + [f"{BASE}films/{d}s/" for d in sorted(decades)]
            + [f"{BASE}film/{f['id']}/" for f in films]
            + [f"{BASE}{x}/" for x in extras + ["corrections", "collections", "tools"]]
            + [f"{BASE}collections/{c['slug']}/" for c in collections]
            + [f"{BASE}blog/"] + [f"{BASE}blog/{p['slug']}/" for p in posts]
            + ([f"{BASE}songs/"] + [f"{BASE}song/{s['id']}/" for s in songs] if songs else []))
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{HOST}{u}</loc></url>" for u in urls)
        + "</urlset>", encoding="utf-8")
    # plain-text twin: Search Console has shown the XML one as "Couldn't fetch" since July; a new
    # URL in the simplest format Google accepts forces a fresh fetch
    (OUT / "sitemap.txt").write_text("".join(f"{HOST}{u}\n" for u in urls), encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {HOST}{BASE}sitemap.xml\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"built {len(films)} dossiers -> {OUT} (cutoff year: {CUTOFF})")


if __name__ == "__main__":
    build()
