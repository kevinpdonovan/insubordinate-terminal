"""Harvesters: each returns (items, health_record).

Only metadata is collected: title, link, date, source, authors, and (for
tagging only) a short summary. No full text is fetched or republished.
"""
from __future__ import annotations

import datetime as dt
import time
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


# ---------------------------------------------------------------- GDELT
GDELT = "https://api.gdeltproject.org/api/v2/doc/doc"


def _gdelt_call(query: str, timespan: str, maxrecords: int):
    params = {"query": query, "mode": "ArtList", "format": "json",
              "timespan": timespan, "maxrecords": maxrecords, "sort": "DateDesc"}
    r = S.get(GDELT, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    txt = r.text.strip()
    if not txt.startswith("{"):
        raise ValueError(txt[:150])  # GDELT returns plain-text errors
    return r.json().get("articles", [])


def harvest_gdelt(src: dict, profile: dict, section: str = "news"):
    if src.get("mode") == "domain":
        queries = [f'{src["query"]} domain:{src["domain"]}']
    else:
        queries = profile.get("news_queries", [])
    out, errors = [], []
    for q in queries:
        try:
            arts = _gdelt_call(q, src.get("timespan", "7d"), src.get("max_per_query", 50))
        except Exception as ex:
            errors.append(f"{q[:40]}… → {ex}")
            arts = []
        for a in arts:
            out.append(make_item(
                section=section, title=a.get("title", ""), url=a.get("url", ""),
                source=a.get("domain", ""), date=_date(a.get("seendate", "")),
                origin=f"gdelt:{q[:60]}",
                extra={"filter": True, "language": a.get("language", ""),
                       "source_country": a.get("sourcecountry", "")},
            ))
        time.sleep(6)  # GDELT asks for ≤1 request / 5 s
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
    r = S.get(f"{OA}{path}", params=_oa_params(params), timeout=TIMEOUT)
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
               **(extra or {})},
    )


def _resolve(kind: str, names: list[str], lock: dict) -> list[str]:
    """Resolve author/journal names to OpenAlex IDs once; cache in the lock file."""
    table = lock.setdefault(kind, {})
    ids = []
    for name in names:
        if name not in table:
            try:
                res = _oa_get(f"/{'authors' if kind == 'authors' else 'sources'}",
                              {"search": name, "per-page": 5})["results"]
                if kind == "authors":
                    res.sort(key=lambda a: a.get("works_count", 0), reverse=True)
                table[name] = {"id": res[0]["id"].split("/")[-1], "matched": res[0]["display_name"],
                               "check": len(res) > 1} if res else None
            except Exception:
                continue  # try again next week
        if table.get(name) and table[name].get("id"):
            ids.append(table[name]["id"])
    return ids


def _paged(filter_str: str, search: str | None, cap: int = 200) -> list[dict]:
    out, cursor = [], "*"
    while cursor and len(out) < cap:
        params = {"filter": filter_str, "per-page": 100, "select": SELECT, "cursor": cursor}
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
                    for w in _paged(base, q, cap=50):
                        out.append(oa_to_item(w, section, f"openalex:query:{q}", {"filter": True}))
                except Exception as ex:
                    errors.append(f"{q}: {ex}")
                time.sleep(0.2)
        elif mode in ("journals", "authors"):
            lock = load_lock()
            names = profile.get("watch_journals" if mode == "journals" else "watch_authors", [])
            ids = _resolve(mode, names, lock)
            save_lock(lock)
            key = "primary_location.source.id" if mode == "journals" else "authorships.author.id"
            for i in range(0, len(ids), 50):
                chunk = "|".join(ids[i:i + 50])
                for w in _paged(f"{base},{key}:{chunk}", None, cap=400):
                    out.append(oa_to_item(w, section, f"openalex:{mode}",
                                          {"filter": mode == "journals", "watched": mode == "authors"}))
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


HARVESTERS: dict[str, Callable] = {
    "rss": harvest_rss,
    "gdelt": harvest_gdelt,
    "openalex": harvest_openalex,
}
