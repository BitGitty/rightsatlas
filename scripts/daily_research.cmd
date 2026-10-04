@echo off
REM Daily: research 2 titles (gates + independent fact-check) into data/pending and push,
REM so the CI drip has stock to release. Net +1/day (CI releases 1/day).
cd /d D:\rightsatlas
REM a run that died mid-rebase blocks every later run (2026-10-04): clear it, then start
REM from the latest main so a title the drip just released is not researched again
git rebase --abort >nul 2>&1
git pull --rebase --autostash -q || exit /b 1
python scripts\research_one.py -n 2
git add data/pending data/promote_log.jsonl data/research_runs.jsonl
git diff --cached --quiet && exit /b 0
git commit -q -m "research: top up drip pool"
git pull --rebase --autostash -q || (git rebase --abort & exit /b 1)
git push -q
