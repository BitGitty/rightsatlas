"""Mastodon as @rightsatlas@mastodon.social, official API (owner 2026-11-20). Bots are allowed there; the
account is flagged as a bot and its bio discloses AI assistance (mastodon.social rule).

  python scripts/masto.py "text"                     # post, prints the URL
  python scripts/masto.py --reply <status_id> "text" # reply in a thread
  python scripts/masto.py --mentions [since_id]      # mentions/replies (JSON)
  python scripts/masto.py --profile                  # (re)apply name, bio, link, bot flag, avatar

Token lives in ~/.rightsatlas/mastodon.json (never in the repo). Stdlib only.
"""
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

CFG = json.loads((Path.home() / ".rightsatlas" / "mastodon.json").read_text(encoding="utf-8"))
API = f"https://{CFG['instance']}/api/v1"


def call(method, path, fields=None, files=None):
    hdr = {"Authorization": f"Bearer {CFG['access_token']}"}
    data = None
    if files:  # multipart for the avatar
        b = uuid.uuid4().hex
        parts = [f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in (fields or {}).items()]
        for k, (name, blob, ctype) in files.items():
            parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\n'
                         f'Content-Type: {ctype}\r\n\r\n'.encode() + blob + b"\r\n")
        data = b"".join(parts) + f"--{b}--\r\n".encode()
        hdr["Content-Type"] = f"multipart/form-data; boundary={b}"
    elif fields is not None:
        data = json.dumps(fields).encode()
        hdr["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, method=method, headers=hdr)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def post(text, reply_to=None):
    s, d = call("POST", "/statuses", {"status": text, "visibility": "public", "language": "en",
                                      **({"in_reply_to_id": reply_to} if reply_to else {})})
    if s != 200:
        raise SystemExit(f"Mastodon post failed: HTTP {s} {json.dumps(d)[:300]}")
    return d["url"]


def profile():
    fields = {"display_name": "RightsAtlas", "bot": "true",
              "note": "Is that classic film or song really public domain in the US? Free, sourced checks, layer by "
                      "layer. Posts are automated; research is AI-assisted with human-set rules and primary sources. "
                      "Not legal advice.",
              "fields_attributes[0][name]": "Website", "fields_attributes[0][value]": "https://rightsatlas.net",
              "fields_attributes[1][name]": "Blog", "fields_attributes[1][value]": "https://rightsatlas.net/blog/"}
    avatar = Path(r"D:\rightsatlas-private\promo\avatar.png").read_bytes()
    s, d = call("PATCH", "/accounts/update_credentials", fields, {"avatar": ("avatar.png", avatar, "image/png")})
    return s, {k: d.get(k) for k in ("acct", "display_name", "bot", "url")}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "--profile":
        print(profile())
    elif a and a[0] == "--mentions":
        q = "/notifications?types[]=mention&limit=30" + (f"&since_id={a[1]}" if len(a) > 1 else "")
        print(json.dumps(call("GET", q)[1], ensure_ascii=False, indent=1)[:20000])
    elif a and a[0] == "--reply":
        print(post(a[2], reply_to=a[1]))
    elif a:
        print(post(a[0]))
