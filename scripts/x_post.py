"""Post to X as @RightsAtlas through the official API (owner 2026-11-18: "X yes").

  python scripts/x_post.py "text"          # posts, prints the post URL
  python scripts/x_post.py --check         # verifies the keys (GET /2/users/me, one paid read)
  python scripts/x_post.py --selftest      # signs a known request offline (no network, no cost)

Keys live in ~/.rightsatlas/x.json (never in the repo). Pay-per-use: about $0.015 per post,
$0.20 when the post has a link, so callers keep it to the weekly post. Stdlib only.
"""
import base64
import hashlib
import hmac
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.x.com/2"
q = lambda s: urllib.parse.quote(str(s), safe="~-._")  # noqa: E731  RFC 3986, as OAuth 1.0a needs


def keys():
    return json.loads((Path.home() / ".rightsatlas" / "x.json").read_text(encoding="utf-8"))


def oauth_header(method, url, k, nonce=None, ts=None, params=None):
    oa = {"oauth_consumer_key": k["api_key"], "oauth_nonce": nonce or secrets.token_hex(16),
          "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": str(ts or int(time.time())),
          "oauth_token": k["access_token"], "oauth_version": "1.0"}
    allp = {**oa, **(params or {})}  # JSON bodies are not signed; query params are
    base = "&".join([method.upper(), q(url), q("&".join(f"{q(a)}={q(b)}" for a, b in sorted(allp.items())))])
    key = f"{q(k['api_secret'])}&{q(k['access_secret'])}"
    oa["oauth_signature"] = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{q(a)}="{q(b)}"' for a, b in sorted(oa.items()))


def call(method, path, body=None):
    url = API + path
    k = keys()
    base, _, query = url.partition("?")  # OAuth 1.0a signs query params, over the URL without them
    params = dict(urllib.parse.parse_qsl(query, keep_blank_values=True))
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": oauth_header(method, base, k, params=params),
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def post(text):
    status, data = call("POST", "/tweets", {"text": text})
    if status != 201:
        raise SystemExit(f"X post failed: HTTP {status} {json.dumps(data)[:300]}")
    return f"https://x.com/{keys().get('handle', 'RightsAtlas')}/status/{data['data']['id']}"


def selftest():
    # Twitter's documented OAuth 1.0a example (developer docs "Creating a signature")
    k = {"api_key": "xvz1evFS4wEEPTGEFPHBog", "api_secret": "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
         "access_token": "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb",
         "access_secret": "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE"}
    h = oauth_header("POST", "https://api.twitter.com/1.1/statuses/update.json", k,
                     nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg", ts=1318622958,
                     params={"include_entities": "true",
                             "status": "Hello Ladies + Gentlemen, a signed OAuth request!"})
    assert 'oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"' in h, h
    print("selftest ok: signature matches the documented example")


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "--selftest"
    if arg == "--selftest":
        selftest()
    elif arg == "--check":
        print(call("GET", "/users/me"))
    else:
        print(post(arg))
