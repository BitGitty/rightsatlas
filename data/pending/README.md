# data/pending/ — the daily-drip queue

Finished, evidence-backed dossiers **researched in the backend but not yet public** live here
as `<film-id>.json` (same format as `data/films/`).

The nightly CI runs `scripts/drip_publish.py` which moves the **oldest one** into
`data/films/` **once per day**, so the public site grows ~1 dossier/day (steady, YouTube-schedule
style) instead of releasing a whole batch at once. Order is FIFO by file mtime — to jump the
queue, just re-touch a file so it's newest... or drop it straight into `data/films/`.

Research as many as you want in here; the gate controls the public pace. State: `data/drip_state.json`.
