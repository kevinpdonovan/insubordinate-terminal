"""Command line for the weekly pipeline.

  python -m terminal harvest            # sweep sources, tag, write review queue
  python -m terminal publish BODY.md    # publish ticked items from the review issue
  python -m terminal build              # rebuild the site from published issues
  python -m terminal suggest FORM.md USER   # add a hand-suggested item (issue form)
  python -m terminal focus FORM.md USER     # add/update a participant focus file (issue form)
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import yaml

from . import build as site_build
from .dedupe import cluster_news, keys_for, merge_versions, work_key
from .harvesters import (HARVESTERS, harvest_citation_trail, harvest_email, harvest_gdelt, harvest_pagewatch,
                         harvest_rss, venue_stats)
from .quality import LEVEL_SCORE, apply_venue_quality, outlet_ok, outlet_rank
from .items import DATA, SECTIONS, SeenStore, iso_week, load_json, make_item, save_json
from .profile import CONFIG, load_profile, load_sources
from .relevance import Scorer
from .review import issue_body, parse_form, parse_review, lines, select_for_review, week_from_body
from .tagger import tag_items, write_digest


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ GDELT daily cache
NEWS_CACHE = DATA / "news_cache"


def _gdelt_cache_days(since):
    return sorted(p for p in NEWS_CACHE.glob("*.json") if p.stem >= since.isoformat()) if NEWS_CACHE.exists() else []


def _from_gdelt_cache(src, since):
    """Read what the daily collector gathered for this source over the past week."""
    items, notes, days = [], [], 0
    for p in _gdelt_cache_days(since):
        day = load_json(p, {})
        rec = day.get(src["name"])
        if not rec:
            continue
        days += 1
        items += rec.get("items", [])
        if rec.get("note"):
            notes.append(f"{p.stem}: {rec['note'][:60]}")
    ok = days > 0
    return items, {"source": src["name"], "ok": ok, "count": len(items),
                   "note": f"from daily collector ({days} day(s))" + (f"; {'; '.join(notes[:2])}" if notes else "")}


def cmd_collect_news(args):
    """Daily: query GDELT for the last day and add results to data/news_cache/<date>.json.

    Spreading GDELT calls over seven small daily runs (instead of one big weekly burst)
    keeps us under GDELT's rate limit; the weekly harvest then reads the cache.
    """
    profile, sources = load_profile(), load_sources()
    today = dt.date.today().isoformat()
    path = NEWS_CACHE / f"{today}.json"
    day = load_json(path, {})
    for src in sources.get("news") or []:
        if src.get("type") != "gdelt":
            continue
        items, h = harvest_gdelt(src, profile, "news", timespan=args.timespan)
        prev = day.get(src["name"], {}).get("items", [])
        seen_ids = {i["id"] for i in prev}
        day[src["name"]] = {"items": prev + [i for i in items if i["id"] not in seen_ids],
                            "note": h.get("note", ""), "ok": h["ok"]}
        log(f"· {src['name']}: {len(items)} items{'' if h['ok'] else ' (errors: ' + h['note'][:80] + ')'}")
    save_json(path, day)
    # keep five weeks of cache
    cutoff = (dt.date.today() - dt.timedelta(days=35)).isoformat()
    for p in NEWS_CACHE.glob("*.json"):
        if p.stem < cutoff:
            p.unlink()


# ------------------------------------------------------------------ harvest
def _run_sources(sources, profile, since, health, log):
    raw = []
    for section in ("research", "news", "grey"):
        for src in sources.get(section) or []:
            t = src.get("type")
            try:
                if t == "rss":
                    items, h = harvest_rss(src, section, since)
                elif t == "pagewatch":
                    items, h = harvest_pagewatch(src, section, DATA / "pagewatch")
                elif t == "email":
                    items, h = harvest_email(src, section, since)
                elif t == "gdelt" and _gdelt_cache_days(since):
                    items, h = _from_gdelt_cache(src, since)
                elif t in HARVESTERS:
                    items, h = HARVESTERS[t](src, profile, section)
                else:
                    continue
            except Exception as ex:  # one broken source must never sink the run
                items, h = [], {"source": src.get("name", "?"), "ok": False, "count": 0, "note": str(ex)[:200]}
            log(f"· {section:8} {src.get('name')}: {h['count']}{'' if h['ok'] else '  (FAILED)'}")
            raw += items
            health.append(h)
    return raw


def cmd_harvest(args):
    profile, sources = load_profile(), load_sources()
    week = args.week or iso_week()
    since = dt.date.today() - dt.timedelta(days=args.days)
    seen = SeenStore()
    scorer = Scorer(profile)
    health, stats = [], {}

    raw = _run_sources(sources, profile, since, health, log)
    stats["harvested"] = len(raw)

    # --- news: keep only allow-listed outlets for broad index searches (GDELT)
    ranks = outlet_rank(sources)
    if ranks:
        before = len(raw)
        raw = [it for it in raw if not it.get("origin", "").startswith("gdelt") or outlet_ok(it, ranks)]
        stats["dropped_outlet"] = before - len(raw)

    # --- duplicates: exact ids, then versions of the same work, then syndicated news
    uniq = {}
    for it in raw:
        if not it["title"]:
            continue
        if it["section"] in ("research", "archive", "grey"):
            it["work_key"] = work_key(it)
        if it["id"] in uniq:  # same DOI/URL from two harvesters: keep the richer record
            if len(it.get("summary", "")) > len(uniq[it["id"]].get("summary", "")):
                it["watched"] = it.get("watched") or uniq[it["id"]].get("watched")
                uniq[it["id"]] = it
            else:
                uniq[it["id"]]["watched"] = uniq[it["id"]].get("watched") or it.get("watched")
            continue
        uniq[it["id"]] = it
    items, n_versions = merge_versions(list(uniq.values()))
    items, n_syndicated = cluster_news(items, {d: r for d, r in ranks.items()})
    stats["duplicates_removed"] = (len(raw) - len(uniq)) + n_versions + n_syndicated

    # --- against previous weeks (by id AND fuzzy key)
    fresh = [it for it in items if not any(k in seen for k in keys_for(it))]
    stats["repeats_removed"] = len(items) - len(fresh)

    # --- venue quality for scholarship
    venues = load_json(DATA / "venues.json", {})
    venue_stats([it.get("venue_id", "") for it in fresh if it["section"] == "research"], venues)
    save_json(DATA / "venues.json", venues)
    stats["dropped_venue"] = apply_venue_quality(fresh, venues, profile)

    passed = []
    for it in fresh:
        if it.get("drop"):
            continue
        it["kw"] = scorer.assess(it)
        if it["kw"]["pass"]:
            if it.get("venue_quality"):
                it["kw"]["score"] += LEVEL_SCORE.get(it["venue_quality"]["level"], 0)
            passed.append(it)
    stats["passed"] = len(passed)
    log(f"harvested {len(raw)}; new after de-duplication {len(fresh)}; passed gate {len(passed)}")

    # tag research first so the citation trail can use the strongest items
    research = sorted([i for i in passed if i["section"] == "research"], key=lambda i: i["kw"]["score"], reverse=True)[:150]
    others = sorted([i for i in passed if i["section"] != "research"], key=lambda i: i["kw"]["score"], reverse=True)[:300]
    tagged = tag_items(profile, research, log)

    # from the archive: older works cited by this week's best research
    strong = [i for i in research if (i.get("ai") or {}).get("relevance", 0) >= 2] if tagged else research[:25]
    for src in sources.get("archive") or []:
        if src.get("mode") == "citations":
            arch, h = harvest_citation_trail(src, strong)
            health.append(h)
            for a in arch:
                a["work_key"] = work_key(a)
            arch = [a for a in arch if not any(k in seen for k in keys_for(a))]
            venue_stats([a.get("venue_id", "") for a in arch], venues)
            apply_venue_quality(arch, venues, profile)
            for a in arch:
                a["kw"] = scorer.assess(a)
                if a.get("venue_quality"):
                    a["kw"]["score"] += LEVEL_SCORE.get(a["venue_quality"]["level"], 0)
            arch = [a for a in arch if a["kw"]["pass"] and not a.get("drop")]
            arch.sort(key=lambda a: (a.get("cited_by_this_week", 0), a["kw"]["score"]), reverse=True)
            others += arch[: src.get("max_items", 8) * 2]
    save_json(DATA / "venues.json", venues)
    tag_items(profile, others, log)
    stats["tagged"] = tagged

    candidates = research + others
    chosen = select_for_review(candidates)
    run_dir = DATA / "runs" / week
    save_json(run_dir / "candidates.json", candidates)
    body = issue_body(week, chosen, stats)
    (run_dir / "review.md").write_text(body, encoding="utf-8")

    # health with failure streaks
    prev = {h["source"]: h for h in load_json(DATA / "health.json", {}).get("sources", [])}
    for h in health:
        streak = prev.get(h["source"], {}).get("fail_streak", 0)
        h["fail_streak"] = 0 if h["ok"] else streak + 1
    save_json(DATA / "health.json", {"week": week, "run_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
                                     "sources": health, "stats": stats})
    for it in fresh:
        for k in keys_for(it):
            seen.add(k, week)
    seen.save()
    log(f"stats: {stats}")
    log(f"review queue: {run_dir / 'review.md'}")
    print(run_dir / "review.md")


# ------------------------------------------------------------------ publish
def cmd_publish(args):
    body = Path(args.body).read_text(encoding="utf-8")
    week = week_from_body(body) or args.week
    if not week:
        sys.exit("could not find the week marker in the review body")
    cands = {c["id"]: c for c in load_json(DATA / "runs" / week / "candidates.json", [])}
    approved, featured = parse_review(body)
    items = []
    for iid in approved:
        it = cands.get(iid)
        if it:
            it = {k: v for k, v in it.items() if k not in ("summary", "referenced_works", "work_key", "filter")}
            it["featured"] = iid in featured
            items.append(it)
    # hand-suggested items waiting in data/suggestions
    for p in sorted((DATA / "suggestions").glob("*.json")):
        s = load_json(p, None)
        if s and not s.get("published_in"):
            items.append({k: v for k, v in s.items() if k != "summary"})
            s["published_in"] = week
            save_json(p, s)
    order = {s: n for n, s in enumerate(SECTIONS)}
    items.sort(key=lambda i: i.get("date", ""), reverse=True)          # newest first...
    items.sort(key=lambda i: (order.get(i["section"], 9),              # ...within section & relevance
                              not i.get("featured"), -((i.get("ai") or {}).get("relevance", 0))))
    profile = load_profile()
    issue = {"week": week, "published_at": dt.datetime.utcnow().isoformat(timespec="seconds"),
             "items": items, "digest": write_digest(profile, [i for i in items if i.get("featured")] + items)}
    save_json(DATA / "issues" / f"{week}.json", issue)
    log(f"published {week}: {len(items)} items ({len(featured)} featured)")
    site_build.build(log)


def cmd_build(args):
    site_build.build(log)


# ------------------------------------------------------------------ forms
def cmd_suggest(args):
    f = parse_form(Path(args.body).read_text(encoding="utf-8"))
    url = f.get("Link", "").strip()
    if not url.startswith("http"):
        sys.exit("suggestion has no valid link")
    sec_map = {"new research": "research", "older work": "archive", "news": "news",
               "report / grey literature": "grey"}
    section = sec_map.get(f.get("Section", "").lower(), "news")
    it = make_item(section=section, title=f.get("Title", "") or url, url=url,
                   source=f.get("Source / outlet", ""), date=dt.date.today().isoformat(),
                   origin="suggestion", extra={"suggested_by": args.user})
    it["editor_note"] = f.get("Why it matters (one line)", "")[:240]
    it["ai"] = {"relevance": 3, "themes": [], "places": [], "note": it["editor_note"]}
    save_json(DATA / "suggestions" / f"{it['id']}.json", it)
    log(f"saved suggestion {it['id']}")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "participant"


def cmd_focus(args):
    f = parse_form(Path(args.body).read_text(encoding="utf-8"))
    name = f.get("Your name (as it appears on publications)", "").strip()
    if not name:
        sys.exit("focus form has no name")
    card = {
        "name": name,
        "role": f.get("Role on the project", ""),
        "orcid": f.get("ORCID (optional)", ""),
        "focus": lines(f.get("Current focus (cities, devices, topics — one per line)", "")),
        "keywords": lines(f.get("Keywords the sweep should watch for (one per line)", "")),
        "research_queries": lines(f.get("Scholarly search phrases (one per line)", "")),
        "news_queries": lines(f.get("News search phrases (one per line)", "")),
        "watch_authors": lines(f.get("Authors to follow (one per line)", "")),
        "updated": dt.date.today().isoformat(),
        "updated_by": args.user,
    }
    card = {k: v for k, v in card.items() if v}
    path = CONFIG / "participants" / f"{_slug(name)}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Participant focus — merged into the sweep profile each week.\n")
        yaml.safe_dump(card, fh, allow_unicode=True, sort_keys=False)
    log(f"wrote {path}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="terminal")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("harvest"); h.add_argument("--week"); h.add_argument("--days", type=int, default=8)
    p = sub.add_parser("publish"); p.add_argument("body"); p.add_argument("--week")
    sub.add_parser("build")
    c = sub.add_parser("collect-news"); c.add_argument("--timespan", default="1d")
    s = sub.add_parser("suggest"); s.add_argument("body"); s.add_argument("user")
    f = sub.add_parser("focus"); f.add_argument("body"); f.add_argument("user")
    args = ap.parse_args(argv)
    {"harvest": cmd_harvest, "publish": cmd_publish, "build": cmd_build,
     "suggest": cmd_suggest, "focus": cmd_focus, "collect-news": cmd_collect_news}[args.cmd](args)
