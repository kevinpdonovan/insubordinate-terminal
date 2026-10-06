"""Harvesters: each returns (items, health_record).

Only metadata is collected: title, link, date, source, authors, and (for
tagging only) a short summary. No full text is fetched or republished.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit
from typing import Callable

import feedparser
import requests
from dateutil import parser as dparser

from .items import make_item
from .profile import env, load_lock, save_lock

UA = "InsubordinateFinanceTerminal/0.1 (academic research dashboard; +mailto:{mail})"
TIMEOUT = 30


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = UA.format(mail=env("CONTACT_EMAIL", "unset"))
    return s


S = _session()


def _health(name, ok, n, note=""):
    return {"source": name, "ok": ok, "count": n, "note": note[:200]}


def _date(s) -> str:
    if not s:
        return ""
    try:
        return dparser.parse(str(s), fuzzy=True).date().isoformat()
    except Exception:
        return ""


# ---------------------------------------------------------------- RSS
def harvest_rss(src: dict, section: str, since: dt.date):
    name, url = src["name"], src["url"]
    try:
        r = S.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        if feed.bozo and not feed.entries:
            return [], _health(name, False, 0, f"unparseable feed: {feed.bozo_exception}")
    except Exception as ex:  # network, 4xx/5xx
        return [], _health(name, False, 0, str(ex))
    out = []
    for e in feed.entries:
        d = _date(e.get("published") or e.get("updated") or e.get("dc_date"))
        if d and d < since.isoformat():
            continue
        authors = [a.get("name", "") for a in e.get("authors", []) if a.get("name")]
        out.append(make_item(
            section=section, title=e.get("title", ""), url=e.get("link", ""),
            source=name, date=d, authors=authors,
            summary=e.get("summary", ""), origin=f"rss:{name}",
            extra={"filter": src.get("filter", True)},
        ))
    return out, _health(name, True, len(out), "" if feed.entries else "feed returned no entries")


# ---------------------------------------------------------------- polite retries
def get_with_backoff(url: str, params: dict | None = None, tries: int = 4, base_wait: float = 15.0,
                     sleep=None, **kw):
    """GET that waits and retries on 429 / 5xx. Honours Retry-After when given."""
    sleep = sleep or time.sleep
    last = None
    for attempt in range(tries):
        r = S.get(url, params=params, timeout=TIMEOUT, **kw)
        if r.status_code not in (429, 500, 502, 503, 504):
            return r
        last = r
        wait = base_wait * (2 ** attempt)
        try:
            wait = max(wait, float(r.headers.get("Retry-After", 0)))
        except (TypeError, ValueError, AttributeError):
            pass
        sleep(min(wait, 180))
    return last


# ---------------------------------------------------------------- GDELT
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"


def _gdelt_call(query: str, timespan: str, maxrecords: int):
    params = {"query": query, "mode": "ArtList", "format": "json",
              "timespan": timespan, "maxrecords": maxrecords, "sort": "DateDesc"}
    r = get_with_backoff(GDELT, params=params, tries=4, base_wait=20)
    r.raise_for_status()
    txt = r.text.strip()
    if not txt.startswith("{"):
        raise ValueError(txt[:150])  # GDELT returns plain-text errors
    return r.json().get("articles", [])


def gdelt_queries(src: dict, profile: dict) -> list[str]:
    if src.get("mode") == "domain":
        return [f'{src["query"]} domain:{src["domain"]}']
    return profile.get("news_queries", [])


def harvest_gdelt(src: dict, profile: dict, section: str = "news", timespan: str | None = None):
    queries = gdelt_queries(src, profile)
    out, errors, streak = [], [], 0
    for q in queries:
        if streak >= 3:  # GDELT is refusing us today; stop rather than burn the run's time
            errors.append(f"stopped after 3 consecutive refusals; {len(queries) - queries.index(q)} queries skipped")
            break
        try:
            arts = _gdelt_call(q, timespan or src.get("timespan", "7d"), min(250, src.get("max_per_query", 150)))
            streak = 0
        except Exception as ex:
            errors.append(f"{q[:40]}… → {ex}")
            arts = []
            streak += 1
        for a in arts:
            out.append(make_item(
                section=section, title=a.get("title", ""), url=a.get("url", ""),
                source=a.get("domain", ""), date=_date(a.get("seendate", "")),
                origin=f"gdelt:{q[:60]}",
                extra={"filter": True, "language": a.get("language", ""),
                       "source_country": a.get("sourcecountry", "")},
            ))
        time.sleep(src.get("spacing_seconds", 10))  # GDELT asks for ≤1 request / 5 s; we go slower
    ok = len(errors) < max(1, len(queries))
    return out, _health(src["name"], ok, len(out), "; ".join(errors[:3]))


# ---------------------------------------------------------------- OpenAlex
OA = "https://api.openalex.org"


def _oa_params(extra: dict) -> dict:
    p = dict(extra)
    if env("CONTACT_EMAIL"):
        p["mailto"] = env("CONTACT_EMAIL")
    if env("OPENALEX_API_KEY"):
        p["api_key"] = env("OPENALEX_API_KEY")
    return p


def _oa_get(path: str, params: dict) -> dict:
    r = get_with_backoff(f"{OA}{path}", params=_oa_params(params), tries=3, base_wait=10)
    r.raise_for_status()
    return r.json()


def _abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))[:1500]


SELECT = ("id,doi,title,publication_date,publication_year,authorships,primary_location,"
          "abstract_inverted_index,type,referenced_works,language")


def oa_to_item(w: dict, section: str, origin: str, extra=None) -> dict:
    loc = w.get("primary_location") or {}
    src = (loc.get("source") or {})
    venue = src.get("display_name") or ""
    authors = [a["author"]["display_name"] for a in (w.get("authorships") or [])
               if a.get("author", {}).get("display_name")]
    return make_item(
        section=section, title=w.get("title") or "", url=loc.get("landing_page_url") or w.get("id", ""),
        doi=(w.get("doi") or ""), source=venue or "OpenAlex", venue=venue,
        date=w.get("publication_date") or "", authors=authors,
        summary=_abstract(w.get("abstract_inverted_index")), origin=origin,
        extra={"openalex_id": w.get("id", ""), "year": w.get("publication_year"),
               "work_type": w.get("type", ""), "referenced_works": (w.get("referenced_works") or [])[:80],
               "venue_id": (src.get("id") or "").split("/")[-1], "venue_type": src.get("type") or "",
               "publisher": src.get("host_organization_name") or "",
               **(extra or {})},
    )


SOCIAL = {"Social Sciences", "Economics, Econometrics and Finance", "Arts and Humanities",
          "Business, Management and Accounting", "Decision Sciences"}


def _author_fit(a: dict) -> float:
    """Prefer candidates whose publications sit in the social sciences."""
    topics = a.get("topics") or []
    social = sum(t.get("count", 1) for t in topics if (t.get("field") or {}).get("display_name") in SOCIAL)
    total = sum(t.get("count", 1) for t in topics) or 1
    return social / total + min(a.get("works_count", 0), 200) / 2000


def _resolve(kind: str, names: list[str], lock: dict) -> list[str]:
    """Resolve author/journal/series names to OpenAlex IDs once; cache in the lock file.

    Authors: among same-name candidates, the one whose work is mostly in the social
    sciences wins; ambiguous matches are flagged with check: true for a human to confirm.
    """
    table = lock.setdefault(kind, {})
    ids = []
    for name in names:
        stale = (kind == "authors" and isinstance(table.get(name), dict)
                 and "institution" not in table[name] and not table[name].get("manual"))
        if name not in table or stale:
            try:
                if kind == "authors":
                    res = _oa_get("/authors", {"search": name, "per-page": 10,
                                               "select": "id,display_name,works_count,topics,last_known_institutions"})["results"]
                    res.sort(key=_author_fit, reverse=True)
                    close = [r for r in res if _author_fit(r) > 0.5]
                    table[name] = {"id": res[0]["id"].split("/")[-1], "matched": res[0]["display_name"],
                                   "institution": ((res[0].get("last_known_institutions") or [{}])[0] or {}).get("display_name", ""),
                                   "check": len(close) != 1} if res else None
                else:
                    res = _oa_get("/sources", {"search": name, "per-page": 5})["results"]
                    exact = [r for r in res if norm_name(r["display_name"]) == norm_name(name)]
                    pick = (exact or res or [None])[0]
                    table[name] = {"id": pick["id"].split("/")[-1], "matched": pick["display_name"],
                                   "check": not exact} if pick else None
            except Exception:
                continue  # try again next week
        if table.get(name) and table[name].get("id"):
            ids.append(table[name]["id"])
    return ids


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("&", "and"))


def _paged(filter_str: str, search: str | None, cap: int = 200) -> list[dict]:
    out, cursor = [], "*"
    while cursor and len(out) < cap:
        params = {"filter": filter_str, "per-page": min(100, cap), "select": SELECT, "cursor": cursor}
        if search:
            params["search"] = search
        js = _oa_get("/works", params)
        out += js.get("results", [])
        cursor = js.get("meta", {}).get("next_cursor")
        if not js.get("results"):
            break
    return out[:cap]


WORK_TYPES = "type:article|preprint|book|book-chapter|report|review"


def harvest_openalex(src: dict, profile: dict, section: str = "research"):
    mode = src.get("mode")
    since = (dt.date.today() - dt.timedelta(days=src.get("lookback_days", 21))).isoformat()
    base = f"from_publication_date:{since},{WORK_TYPES}"
    out, errors = [], []
    try:
        if mode == "queries":
            for q in profile.get("research_queries", []):
                try:
                    for w in _paged(base, q, cap=src.get("per_query", 25)):
                        out.append(oa_to_item(w, section, f"openalex:query:{q}", {"filter": True}))
                except Exception as ex:
                    errors.append(f"{q}: {ex}")
                time.sleep(0.2)
        elif mode == "reports":
            rbase = f"from_publication_date:{since},type:report"
            for q in profile.get("grey_queries", []) or profile.get("research_queries", []):
                try:
                    for w in _paged(rbase, q, cap=40):
                        out.append(oa_to_item(w, section, f"openalex:reports:{q}", {"filter": True}))
                except Exception as ex:
                    errors.append(f"{q}: {ex}")
                time.sleep(0.2)
        elif mode in ("journals", "authors", "series"):
            lock = load_lock()
            names = {"journals": profile.get("watch_journals", []), "authors": profile.get("watch_authors", []),
                     "series": profile.get("watch_series", [])}[mode]
            ids = _resolve(mode, names, lock)
            save_lock(lock)
            key = "authorships.author.id" if mode == "authors" else "primary_location.source.id"
            base_m = base if mode != "series" else f"from_publication_date:{since}"
            for i in range(0, len(ids), 50):
                chunk = "|".join(ids[i:i + 50])
                for w in _paged(f"{base_m},{key}:{chunk}", None, cap=400):
                    out.append(oa_to_item(w, section, f"openalex:{mode}",
                                          {"filter": mode != "authors", "watched": mode == "authors"}))
    except Exception as ex:
        errors.append(str(ex))
    return out, _health(src["name"], not errors or bool(out), len(out), "; ".join(errors[:3]))


def harvest_citation_trail(src: dict, research_items: list[dict]):
    """Older works cited by this week's strongest research items."""
    cutoff = dt.date.today().year - src.get("older_than_years", 10)
    refs: dict[str, int] = {}
    for it in research_items:
        for ref in it.get("referenced_works", []):
            refs[ref.split("/")[-1]] = refs.get(ref.split("/")[-1], 0) + 1
    if not refs:
        return [], _health(src["name"], True, 0, "no references this week")
    # most-cited-by-this-week first
    ordered = sorted(refs, key=refs.get, reverse=True)[:150]
    out = []
    try:
        for i in range(0, len(ordered), 50):
            chunk = "|".join(ordered[i:i + 50])
            js = _oa_get("/works", {"filter": f"openalex:{chunk},to_publication_date:{cutoff}-12-31",
                                    "per-page": 50, "select": SELECT})
            for w in js.get("results", []):
                wid = w["id"].split("/")[-1]
                out.append(oa_to_item(w, "archive", "openalex:citations",
                                      {"filter": True, "cited_by_this_week": refs.get(wid, 1)}))
    except Exception as ex:
        return out, _health(src["name"], False, len(out), str(ex))
    return out, _health(src["name"], True, len(out))


# ---------------------------------------------------------------- venue quality
def venue_stats(venue_ids: list[str], cache: dict) -> dict:
    """h-index, type and publisher for journals/series; cached in data/venues.json."""
    todo = [v for v in dict.fromkeys(venue_ids) if v and v not in cache]
    for i in range(0, len(todo), 50):
        chunk = "|".join(todo[i:i + 50])
        try:
            js = _oa_get("/sources", {"filter": f"openalex:{chunk}", "per-page": 50,
                                      "select": "id,display_name,type,summary_stats,host_organization_name,is_in_doaj"})
        except Exception:
            continue
        for s in js.get("results", []):
            cache[s["id"].split("/")[-1]] = {
                "name": s.get("display_name", ""), "type": s.get("type", ""),
                "h_index": (s.get("summary_stats") or {}).get("h_index", 0),
                "mean_citedness": round((s.get("summary_stats") or {}).get("2yr_mean_citedness", 0) or 0, 2),
                "publisher": s.get("host_organization_name") or "", "doaj": bool(s.get("is_in_doaj")),
            }
    return cache


# ---------------------------------------------------------------- World Bank documents
# v2 is frozen: its newest indexed document is 2025-03-12, so any recent-date filter returns
# nothing. v3 is current and takes the same parameters and field names.
WB = "https://search.worldbank.org/api/v3/wds"


def harvest_worldbank(src: dict, profile: dict, section: str = "grey"):
    since = (dt.date.today() - dt.timedelta(days=src.get("lookback_days", 14))).isoformat()
    out, errors = [], []
    for q in profile.get("grey_queries", []):
        try:
            r = S.get(WB, params={"format": "json", "qterm": q, "rows": src.get("rows", 30), "strdate": since,
                                  "fl": "display_title,docdt,docty,url,pdfurl,count,repnme,majdocty"},
                      timeout=TIMEOUT)
            r.raise_for_status()
            docs = (r.json() or {}).get("documents", {})
        except Exception as ex:
            errors.append(f"{q}: {ex}")
            continue
        for d in docs.values():
            if not isinstance(d, dict) or not d.get("display_title"):
                continue
            country = d.get("count") or ""
            country = ", ".join(country) if isinstance(country, list) else str(country)
            out.append(make_item(
                section=section, title=d["display_title"], url=d.get("url") or d.get("pdfurl", ""),
                source="World Bank" + (f" · {d.get('docty')}" if d.get("docty") else ""),
                date=_date(d.get("docdt")), summary=f"{d.get('docty','')} {country} {d.get('repnme','')}",
                origin=f"worldbank:{q}", extra={"filter": True, "country": country},
            ))
        time.sleep(0.5)
    return out, _health(src["name"], len(errors) < max(1, len(profile.get("grey_queries", []))), len(out),
                        "; ".join(errors[:3]))


# ---------------------------------------------------------------- page watcher
class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self._href, self._text = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, re.sub(r"\s+", " ", "".join(self._text)).strip()))
            self._href = None


def extract_links(html_text: str, base: str) -> list[tuple[str, str]]:
    p = _Links()
    try:
        p.feed(html_text)
    except Exception:
        pass
    return [(urljoin(base, h), t) for h, t in p.links if h and not h.startswith(("#", "mailto:", "javascript:"))]


def harvest_pagewatch(src: dict, section: str, state_dir: Path):
    """Report links that newly appeared on a publications/news listing page.

    The first run records a baseline and reports nothing, to avoid a flood.
    """
    name, url = src["name"], src["url"]
    pattern = re.compile(src.get("link_pattern", r"."), re.I)
    min_len = src.get("min_title_len", 25)
    state_path = state_dir / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".json")
    try:
        r = S.get(url, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as ex:
        return [], _health(name, False, 0, str(ex))
    links = [(h, t) for h, t in extract_links(r.text, url) if pattern.search(h) and len(t) >= min_len]
    if not links:
        return [], _health(name, False, 0, "no matching links: the page may need JavaScript or the pattern is wrong")
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    current = sorted({h for h, _ in links})
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"links": current[-2000:], "checked": dt.date.today().isoformat()}))
    if state is None:
        return [], _health(name, True, 0, f"baseline recorded ({len(current)} links)")
    before = set(state.get("links", []))
    out, seen = [], set()
    for h, t in links:
        if h in before or h in seen:
            continue
        seen.add(h)
        out.append(make_item(section=section, title=t, url=h, source=src.get("org", name),
                             date=dt.date.today().isoformat(), origin=f"page:{name}",
                             extra={"filter": src.get("filter", True)}))
    return out, _health(name, True, len(out))


# ---------------------------------------------------------------- email alerts
def _unwrap(url: str) -> str:
    """Unwrap redirectors that carry the target in a query parameter (e.g. Google Scholar)."""
    q = parse_qs(urlsplit(url).query)
    for key in ("url", "u", "q", "target"):
        v = q.get(key, [""])[0]
        if v.startswith("http"):
            return v
    return url


def _resolve_redirect(url: str) -> str:
    try:
        r = S.get(url, timeout=15, allow_redirects=True, stream=True)
        r.close()
        return r.url
    except Exception:
        return url


def _email_html(msg) -> str:
    parts = []
    for part in msg.walk():
        if part.get_content_type() in ("text/html", "text/plain") and not part.get_filename():
            try:
                parts.append(part.get_content())
            except Exception:
                payload = part.get_payload(decode=True) or b""
                parts.append(payload.decode("utf-8", "replace"))
    return "\n".join(parts)


def harvest_email(src: dict, section: str, since: dt.date):
    """Headlines + links from alert emails (Bloomberg, Google Scholar, newsletters) in a dedicated inbox.

    Needs IMAP_HOST, IMAP_USER, IMAP_PASSWORD (a Gmail 'app password' works).
    Each rule matches senders and keeps links to the listed domains.
    """
    import email
    import imaplib
    from email import policy

    host, user, pwd = env("IMAP_HOST", "imap.gmail.com"), env("IMAP_USER"), env("IMAP_PASSWORD")
    if not (user and pwd):
        return [], _health(src["name"], True, 0, "not configured (no IMAP_USER / IMAP_PASSWORD secrets)")
    out, notes = [], []
    try:
        M = imaplib.IMAP4_SSL(host)
        M.login(user, pwd)
        M.select(src.get("folder", "INBOX"), readonly=True)
        crit = f'(SINCE "{since.strftime("%d-%b-%Y")}" FROM "{src["from"]}")'
        typ, data = M.search(None, crit)
        ids = (data[0] or b"").split()[-src.get("max_messages", 60):]
        resolved = 0
        for mid in ids:
            typ, msgdata = M.fetch(mid, "(RFC822)")
            msg = email.message_from_bytes(msgdata[0][1], policy=policy.default)
            d = _date(msg.get("Date"))
            body = _email_html(msg)
            pattern = src.get("link_pattern") or "|".join(re.escape(dm) for dm in src.get("link_domains", []))
            wanted = re.compile(pattern, re.I) if pattern else None
            for href, text in extract_links(body, ""):
                if len(text) < src.get("min_title_len", 30) or re.search(r"unsubscribe|view (it )?in|browser|privacy|manage|preferences", text, re.I):
                    continue
                target = _unwrap(href)
                if wanted and not wanted.search(target) and src.get("resolve_redirects") and resolved < 80:
                    target = _unwrap(_resolve_redirect(target))
                    resolved += 1
                if wanted and not wanted.search(target):
                    continue
                out.append(make_item(section=src.get("section", section), title=text, url=target,
                                     source=src.get("label", src["name"]), date=d, origin=f"email:{src['name']}",
                                     extra={"filter": src.get("filter", True)}))
        M.logout()
    except Exception as ex:
        return out, _health(src["name"], False, len(out), str(ex))
    return out, _health(src["name"], True, len(out), "; ".join(notes))


HARVESTERS: dict[str, Callable] = {
    "rss": harvest_rss,
    "gdelt": harvest_gdelt,
    "openalex": harvest_openalex,
    "worldbank": harvest_worldbank,
}
