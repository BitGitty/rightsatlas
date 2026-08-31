@echo off
REM Daily: research 2 titles into data/pending and push, so the CI drip has stock to release.
REM Net +1/day (CI releases 1/day) — the pool grows instead of running dry again.
cd /d D:\rightsatlas
python scripts\research_one.py -n 2
git add data/pending data/promote_log.jsonl data/candidates 2>nul
git diff --cached --quiet && exit /b 0
git commit -q -m "research: top up drip pool"
git pull --rebase --autostash -q
git push -q
