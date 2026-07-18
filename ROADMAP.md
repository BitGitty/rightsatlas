# RightsAtlas — Roadmap (single source of truth)
*Consolidated 2026-07-15. Strategy + priorities here; task-level status lives in
`D:\progress-ledger\PROGRESS.md`. Supersedes scattered notes in pd-checker/.*

## What it is
Evidence-first, layered public-domain checker for classic films. Every film gets
5 independent verdicts (print / score / story / trademark / restorations), each
requiring a primary-source citation — no "verified" badge without proof.

## Current state (2026-07-15)
- 18 dossiers · layered engine w/ provenance-or-fail build gate · auto-computed
  term cutoff · instant title search (fuse.js) · nightly CI · GSC verified.
- Validated by outside reviews (7/10 and 9/10) and by real corrections from
  r/publicdomain (e.g. the King Kong novelization fix).

## Priorities (ranked — do in this order)
1. **SCALE to 100+ films.** Breadth is the product; 18 is a demo. Build an
   AI-assisted pipeline that drafts skeleton dossiers (from Copyright Office
   catalogs, Stanford renewal DB, court cases) into the research queue → human/
   review-gated before publish. First target: the **Class of 2027** (every 1931
   film, PD on Jan 1 2027). *This is the #1 lever both reviewers named.*
2. **Make search prominent.** We already have instant search — a reviewer missed
   it, which means it's not obvious. Promote it to a hero element + add year/
   status filters on the All-Films page.
3. **Retention hook.** Email capture + "films entering PD in [year]" alert /
   watchlist. Value compounds every Jan 1; remind people instead of waiting.
4. **Territorial split.** Structured US vs EU/UK status per film (Metropolis
   already shows this in prose — make it a field/toggle). Copyright is
   territorial; international creators need it.
5. **Machine-readable API.** Dossiers are already JSON — expose a clean public
   JSON endpoint so editors/archival tools can query status programmatically.
6. **Monetize.** DEFERRED until >100 films + proven repeat traffic. Do not
   build API-paywall/accounts before then (YAGNI).

## Gates
- **G1 — Aug 31:** 500 visitors OR 25 email signups. (Needs #2/#3 shipped + more films.)
- **G2 — Sep 30:** 50+ dossiers, indexing traction.
- **G3 — Jan 12 2027:** Class-of-2027 PR moment — 1931 films live, press to PD community.

## Pending right now (keep-flagging)
- Dossiers requested/queued: Metropolis ✅, Shadow Returns ✅; Gorgo, Babes in
  Toyland, Wizard of Oz (1910/1925), Snow White 1916, Alice 1915/1949 — from
  Pawesome_James's list.
- CCE/renewal-records parser (feeds priority #1) — not started.
- Email capture — not started.
