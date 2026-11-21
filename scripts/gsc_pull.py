"""GSC-PULL v1.0 (2026-11-21). Owner: "add Google Search Console data" (RightsAtlas Studio).
Daily: pull Search Console rows (date x query x page: clicks, impressions, position) for sc-domain:rightsatlas.net and
upsert them into the Supabase table gsc_rows (read only via studio_gsc() with the owner's key).
Read-only token: ~/.rightsatlas/gsc_token.json (scope webmasters.readonly, account bitgitcode, client of project
gamegroove-monitor). Search Console data lags 2-3 days, so every run re-pulls the last 10 days.
    python gsc_pull.py            # last 10 days
    python gsc_pull.py --days 480 # backfill (Search Console keeps 16 months)"""
import json, os, subprocess, sys, tempfile, urllib.parse, urllib.request
from datetime import date, timedelta

# both properties: the domain one (from 2026-11-18) and the old github.io one (history before the domain move)
SITES = ["sc-domain:rightsatlas.net", "https://bitgitty.github.io/rightsatlas/"]
TOKEN = os.path.expanduser(r"~/.rightsatlas/gsc_token.json")
CLIENT = r"D:\gamegroove-monitor\client_secret.json"
RUN_SQL = r"D:\roomkaki\backend\run_sql.py"


def access_token():
    tok, cs = json.load(open(TOKEN)), json.load(open(CLIENT))["installed"]
    data = urllib.parse.urlencode({"client_id": cs["client_id"], "client_secret": cs["client_secret"],
                                   "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"}).encode()
    return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token", data, timeout=60))["access_token"]


def rows(at, start, end, site):
    url = f"https://www.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(site, safe='')}/searchAnalytics/query"
    out, first = [], 0
    while True:
        body = json.dumps({"startDate": start, "endDate": end, "dimensions": ["date", "query", "page"],
                           "rowLimit": 25000, "startRow": first}).encode()
        req = urllib.request.Request(url, body, {"Authorization": "Bearer " + at, "Content-Type": "application/json"})
        got = json.load(urllib.request.urlopen(req, timeout=120)).get("rows", [])
        out += got
        if len(got) < 25000:
            return out
        first += 25000


def q(s):
    return "'" + str(s).replace("'", "''") + "'"


def main():
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 10
    end, start = date.today() - timedelta(days=1), date.today() - timedelta(days=days)
    at = access_token()
    data = [r for s in SITES for r in rows(at, start.isoformat(), end.isoformat(), s)]
    print(f"{len(data)} rows {start}..{end}")
    if not data:
        return 0
    vals = ",\n".join(f"({q(r['keys'][0])},{q(r['keys'][1][:300])},{q(r['keys'][2][:400])},{int(r['clicks'])},"
                      f"{int(r['impressions'])},{float(r['position']):.2f})" for r in data)
    sql = ("insert into gsc_rows (day, query, page, clicks, impressions, position) values\n" + vals +
           "\non conflict (day, query, page) do update set clicks=excluded.clicks, impressions=excluded.impressions, "
           "position=excluded.position;")
    with tempfile.NamedTemporaryFile("w", suffix=".sql", delete=False, encoding="utf-8") as f:
        f.write(sql)
    try:
        r = subprocess.run([sys.executable, RUN_SQL, f.name], capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:])
        return r.returncode
    finally:
        os.unlink(f.name)


if __name__ == "__main__":
    sys.exit(main())
