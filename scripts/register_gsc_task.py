"""REGISTER-GSCPULL v1.0 — add RightsAtlas-GSC to the shared taskrun manifest (one-off, 2026-11-21)."""
import json
from pathlib import Path

p = Path(r"D:\shared-tools\taskrun\tasks.json")
t = json.loads(p.read_text(encoding="utf-8"))
t["RightsAtlas-GSC"] = {
    "cmdline": r'cmd.exe /c "set PYTHONIOENCODING=utf-8&& C:\Python314\python.exe D:\rightsatlas\scripts\gsc_pull.py >> D:\rightsatlas\logs\gsc_pull.log 2>&1"',
    "cwd": None, "path": "\\", "limit_s": 600}
p.write_text(json.dumps(t, indent=1), encoding="utf-8")
print("ok")
