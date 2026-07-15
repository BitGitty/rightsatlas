"""RightsAtlas rules engine.

Red-team hard rules implemented here:
- NO binary verdicts: five-tier status per rights LAYER
  (print / score / story / trademark / restorations)
- URAA gate: foreign works published in the renewal era are treated as
  "likely restored" unless evidence says otherwise (Golan v. Holder)
- Pre-cutoff rule is COMPUTED from the clock so the site can never be stale
  on January 1 (works published before currentYear-95 are US public domain)
- "verified_pd" claims REQUIRE evidence entries — build fails otherwise
"""

import re
from datetime import date


def film_id(title: str, year: int) -> str:
    """Canonical dossier/queue slug — the single source of id truth (v4 §3.2).
    'The General', 1926 -> 'the-general-1926'."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")
    return f"{slug}-{year}"


STATUSES = {
    "verified_pd": ("Verified public domain", "ok"),
    "likely_pd": ("Likely public domain", "prob"),
    "partially_protected": ("Partially protected", "warn"),
    "likely_restored": ("Likely restored (URAA)", "warn"),
    "not_pd": ("Not public domain", "no"),
    "undetermined": ("Undetermined", "unk"),
}

LAYERS = [
    ("print", "Film print (photoplay)"),
    ("score", "Music score"),
    ("story", "Underlying story / screenplay"),
    ("trademark", "Character trademarks"),
    ("restorations", "Restorations / re-releases"),
]

# Public-facing labels (v4 §"Public status labels"): keep the 5-tier internal enums,
# but show visitors only Clear / Unclear / Active — never a bare "likely_pd".
PUBLIC_LABELS = {
    "verified_pd": ("Clear", "ok"),
    "likely_pd": ("Unclear", "prob"),
    "undetermined": ("Unclear", "unk"),
    "partially_protected": ("Active rights", "warn"),
    "likely_restored": ("Active rights", "warn"),
    "not_pd": ("Active rights", "no"),
}


def public_label(status: str) -> tuple:
    return PUBLIC_LABELS.get(status, ("Unclear", "unk"))

FRANCHISE_TRADEMARK_FLAGS = (
    "tarzan", "sherlock", "mickey", "zorro", "conan", "popeye",
    "buck rogers", "dracula", "frankenstein",
)

# Symmetric evidence bar (v4 §2.1): a legal conclusion — in EITHER direction — needs a
# primary source. Search-result URLs and Wikipedia are not primary.
PRIMARY_PD_EVIDENCE = {
    "renewal_absence_search", "registration", "cce_entry",
    "copyright_gov_record", "term_expiry", "notice_failure_doc",
}
PRIMARY_RENEWED_EVIDENCE = {"renewal_registration", "cce_renewal_entry", "copyright_gov_record"}
_NON_PRIMARY_URL_HINTS = ("/search", "?q=", "wikipedia.org", "infodigi")


def is_primary(ev: dict) -> bool:
    """True if this evidence entry is a citable primary source (not a search/wiki link)."""
    url = (ev.get("url") or "").lower()
    if any(h in url for h in _NON_PRIMARY_URL_HINTS):
        return False
    return ev.get("type") in (PRIMARY_PD_EVIDENCE | PRIMARY_RENEWED_EVIDENCE)


def pd_cutoff_year(today: date | None = None) -> int:
    """Last publication year now in US public domain by term expiry.
    Works published before (currentYear - 95) i.e. year <= currentYear - 96."""
    t = today or date.today()
    return t.year - 96


def next_pd_class_year(today: date | None = None) -> int:
    return pd_cutoff_year(today) + 1


# v4 §6.3 names. NB: v4's own §8 T-08 expected values are internally inconsistent with its
# formula; these use the copyright-correct semantics (a work from year Y enters US PD on
# Jan 1 of Y+96): as of 2026, works through 1930 are PD and 1931 is the upcoming class.
def pd_term_expired_through_year(today: date | None = None) -> int:
    """Newest publication year already PD by 95-year term as of `today` (year - 96)."""
    return pd_cutoff_year(today)


def pd_entering_class_year(today: date | None = None) -> int:
    """Publication year of the class entering US PD on the next Jan 1 (year - 95)."""
    return next_pd_class_year(today)


def validate(film: dict) -> list:
    """Return list of provenance errors (build fails if any)."""
    errors = []
    for key, _ in LAYERS:
        layer = film["layers"].get(key)
        if not layer:
            errors.append(f"{film['id']}: missing layer '{key}'")
            continue
        if layer["status"] not in STATUSES:
            errors.append(f"{film['id']}: bad status '{layer['status']}' on {key}")
        if layer["status"] == "verified_pd" and not layer.get("evidence"):
            errors.append(f"{film['id']}: verified_pd on '{key}' WITHOUT evidence")
    return errors


def apply_auto_rules(film: dict, today: date | None = None) -> dict:
    """Rules may only make claims MORE cautious, never more optimistic."""
    cutoff = pd_cutoff_year(today)
    year = film["year"]
    country = (film.get("country") or "US").upper()
    print_layer = film["layers"]["print"]
    notes = film.setdefault("auto_notes", [])

    if year <= cutoff:
        notes.append(
            f"Published {year}: US copyright term (95 years) has expired for "
            f"works published through {cutoff} — the film print is public "
            f"domain in the US by term expiry, regardless of country of origin.")
    elif country not in ("US", "USA") and print_layer["status"] in ("verified_pd", "likely_pd"):
        if not any(e.get("type") == "uraa_analysis" for e in print_layer.get("evidence", [])):
            print_layer["status"] = "likely_restored"
            notes.append(
                "URAA gate: non-US work in the renewal era without a documented "
                "URAA analysis — status downgraded to 'likely restored' "
                "(Uruguay Round Agreements Act; Golan v. Holder, 565 U.S. 302).")

    hay = (film["title"] + " " + film.get("editorial", "")).lower()
    tm = film["layers"]["trademark"]
    if tm["status"] in ("verified_pd", "likely_pd") and any(f in hay for f in FRANCHISE_TRADEMARK_FLAGS):
        tm["status"] = "undetermined"
        notes.append(
            "Franchise-character trademark flag: copyright expiry does not "
            "extinguish trademark rights (see Edgar Rice Burroughs v. Dynamite; "
            "Conan Doyle Estate v. Netflix). Check marks before branded use.")
    return film


def guidance(film: dict) -> dict:
    """Plain-English 'what can you actually do' summary from the layers."""
    s = {k: film["layers"][k]["status"] for k, _ in LAYERS}
    watch_ok = s["print"] in ("verified_pd", "likely_pd")
    reuse_layers = [s["print"], s["score"], s["story"]]
    if all(x == "verified_pd" for x in reuse_layers):
        reuse = ("green", "Strong public-domain case across print, score and story "
                          "— reuse and monetization carry the lowest risk profile.")
    elif any(x in ("not_pd", "likely_restored") for x in reuse_layers):
        reuse = ("red", "One or more rights layers appears protected or restored — "
                        "reusing this film commercially is risky without licensing "
                        "or specific legal advice.")
    elif any(x in ("partially_protected", "undetermined") for x in reuse_layers):
        reuse = ("amber", "The film print may be free, but at least one layer "
                          "(music, story, or restoration) is unresolved — expect "
                          "Content ID claims; keep evidence handy and consider "
                          "removing or replacing the score.")
    else:
        reuse = ("amber", "Public-domain case is probable but not fully verified — "
                          "keep this page's evidence for any dispute.")
    return {
        "watch": ("green" if watch_ok else "amber",
                  "Watching via the linked archival copies is generally the "
                  "lowest-risk activity." if watch_ok else
                  "Status unclear — the linked copies may not be authorized."),
        "reuse": reuse,
    }
