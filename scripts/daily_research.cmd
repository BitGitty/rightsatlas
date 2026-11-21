@echo off
REM RightsAtlas research job. RightsAtlas-Research runs it every 4 h with "auto" (new titles and
REM thin-page refreshes take turns). Older modes, still usable by hand:
REM   RightsAtlas-Research 06:10 (no arg)   -> research 2 NEW titles into data/pending
REM   RightsAtlas-Refresh  14:10 ("refresh") -> re-research 2 thin PUBLISHED dossiers in place
REM Both go through the gates + independent fact-check (scripts/research_one.py).
REM Every step is logged to logs\daily_research.log: on 2026-10-05 a run committed but
REM never pushed and still exited 0, with no trace of why.
cd /d D:\rightsatlas
if not exist logs mkdir logs
set LOG=logs\daily_research.log
set PYTHONIOENCODING=utf-8
set MODE=-n 2
set MSG=research: top up drip pool
if /i "%~1"=="refresh" set MODE=--refresh 2
if /i "%~1"=="refresh" set MSG=research: refresh thin dossiers
rem 11-22 owner: free weekly Claude refresh until 2027-03-01 -> 3 titles per run, every 2 h (was 2 per 4 h)
if /i "%~1"=="auto" set MODE=--auto 3
if /i "%~1"=="auto" set MSG=research: rolling batch
echo ==== %date% %time% start %MODE% >> %LOG%
REM a run that died mid-rebase blocks every later run (2026-10-04): clear it, then start
REM from the latest main so a title the drip just released is not researched again
git rebase --abort >nul 2>&1
REM 2026-11-20: a run committed someone's half-finished hand edits in data/films (it stages the whole
REM folder). While hand edits are pending, skip this run; the daily status flags a whole skipped day.
git status --porcelain data/films data/pending | findstr . >nul && (echo hand edits pending in data/films or data/pending - run skipped >> %LOG% & exit /b 0)
git pull --rebase --autostash -q >> %LOG% 2>&1 || (echo pull failed >> %LOG% & exit /b 1)
python scripts\research_one.py %MODE% >> %LOG% 2>&1
REM 2026-11-21 owner: commit times must not show his time zone in this PUBLIC repo -> git runs in UTC
set TZ=UTC
git add data/pending data/films data/promote_log.jsonl data/research_runs.jsonl
git diff --cached --quiet && (echo nothing to commit >> %LOG% & exit /b 0)
git commit -q -m "%MSG%" >> %LOG% 2>&1 || (echo commit failed >> %LOG% & exit /b 1)
git pull --rebase --autostash -q >> %LOG% 2>&1 || (echo second pull failed >> %LOG% & git rebase --abort & exit /b 1)
git push -q >> %LOG% 2>&1 || (echo push failed >> %LOG% & exit /b 1)
echo ==== %date% %time% pushed >> %LOG%
