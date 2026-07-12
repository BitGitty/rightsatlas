# RightsAtlas

Evidence-backed public-domain research for creators. Layered per-element
rights reports (film print / score / story / trademark / restorations),
never one-click verdicts.

**Live:** https://bitgitty.github.io/rightsatlas/

## How it works
- `data/films/*.json` — one dossier per film, with per-layer status + evidence
- `engine.py` — status tiers, URAA foreign-restoration gate, PD cutoff computed
  from the clock (never stale on Jan 1), provenance validation (build fails
  if a `verified_pd` claim has no evidence)
- `build.py` — static site generator (stdlib only) → `site/`
- `content/*.html` — methodology, about, the "entering public domain" hub
- `scripts/linkcheck.py` — nightly archive.org health check
- `.github/workflows/site.yml` — build + deploy on push; nightly rebuild
  (keeps cutoff year fresh) + link-check keepalive

## Add a film
Copy an existing `data/films/*.json`, fill every layer with a status from
`engine.STATUSES` and evidence entries, commit. CI rebuilds and deploys.
Rules of the house: no `verified_pd` without a citation; foreign 1930+ works
default to `likely_restored` unless a documented URAA analysis is attached.

## Local build
```
python build.py            # -> site/
python -m http.server --directory site 8321
```

Not legal advice · US status only · see the site's Methodology page.
