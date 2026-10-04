@echo off
REM Daily: research 2 titles (gates + independent fact-check) into data/pending and push,
REM so the CI drip has stock to release. Net +1/day (CI releases 1/day).
REM Everything is logged to logs\daily_research.log: on 2026-10-05 a run committed but
REM never pushed and still exited 0, with no trace of why.
cd /d D:\rightsatlas
if not exist logs mkdir logs
set LOG=logs\daily_research.log
set PYTHONIOENCODING=utf-8
echo ==== %date% %time% start >> %LOG%
REM a run that died mid-rebase blocks every later run (2026-10-04): clear it, then start
REM from the latest main so a title the drip just released is not researched again
git rebase --abort >nul 2>&1
git pull --rebase --autostash -q >> %LOG% 2>&1 || (echo pull failed >> %LOG% & exit /b 1)
python scripts\research_one.py -n 2 >> %LOG% 2>&1
git add data/pending data/promote_log.jsonl data/research_runs.jsonl
git diff --cached --quiet && (echo nothing to commit >> %LOG% & exit /b 0)
git commit -q -m "research: top up drip pool" >> %LOG% 2>&1
git pull --rebase --autostash -q >> %LOG% 2>&1 || (echo second pull failed >> %LOG% & git rebase --abort & exit /b 1)
git push -q >> %LOG% 2>&1 || (echo push failed >> %LOG% & exit /b 1)
echo ==== %date% %time% pushed >> %LOG%
