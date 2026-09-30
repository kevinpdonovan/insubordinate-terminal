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
from .harvesters import HARVESTERS, harvest_citation_trail
from .items import DATA, SECTIONS, SeenStore, iso_week, load_json, make_item, save_json
from .profile import CONFIG, load_profile, load_sources
from .relevance import Scorer
from .review import issue_body, parse_form, parse_review, lines, select_for_review, week_from_body
from .tagger import tag_items, write_digest


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ harvest
def cmd_harvest(args):
    profile, sources = load_profile(), load_sources()
    week = args.week or iso_week()
    since = dt.date.today() - dt.timedelta(days=args.days)
    seen = SeenStore()
    scorer = Scorer(profile)
    raw, health = [], []

    for section in ("research", "news", "grey"):
        for src in sources.get(section) or []:
            fn = HARVESTERS.get(src.get("type"))
            if not fn:
                continue
            log(f"· {section:8} {src['name']}")
            if src["type"] == "rss":
                items, h = fn(src, section, since)
            else:
                items, h = fn(src, profile, section)
            raw += items
            health.append(h)

    # de-duplicate within the week, then against previous weeks
    uniq = {}
    for it in raw:
        uniq.setdefault(it["id"], it)
    fresh = [it for it in uniq.values() if it["id"] not in seen and it["title"]]

    passed = []
    for it in fresh:
        it["kw"] = scorer.assess(it)
        if it["kw"]["pass"]:
            passed.append(it)
    log(f"harvested {len(raw)}, unique {len(uniq)}, new {len(fresh)}, passed gate {len(passed)}")

    # tag research first so the citation trail can use the strongest items
    research = [i for i in passed if i["section"] == "research"]
    research.sort(key=lambda i: i["kw"]["score"], reverse=True)
    research = research[:150]
    others = [i for i in passed if i["section"] != "research"]
    others.sort(key=lambda i: i["kw"]["score"], reverse=True)
    others = others[:300]  # cap tagging cost
    tagged = tag_items(profile, research, log)

    # from the archive: older works cited by this week's best research
    strong = [i for i in research if (i.get("ai") or {}).get("relevance", 0) >= 2] if tagged else research[:25]
    for src in sources.get("archive") or []:
        if src.get("mode") == "citations":
            arch, h = harvest_citation_trail(src, strong)
            health.append(h)
            arch = [a for a in arch if a["id"] not in seen]
            for a in arch:
                a["kw"] = scorer.assess(a)
            arch = [a for a in arch if a["kw"]["pass"]]
            arch.sort(key=lambda a: (a.get("cited_by_this_week", 0), a["kw"]["score"]), reverse=True)
            others += arch[: src.get("max_items", 8) * 2]
    tag_items(profile, others, log)

    candidates = research + others
    chosen = select_for_review(candidates)
    run_dir = DATA / "runs" / week
    save_json(run_dir / "candidates.json", candidates)
    stats = {"harvested": len(raw), "passed": len(passed), "tagged": tagged}
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
        seen.add(it["id"], week)
    seen.save()
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
            it = {k: v for k, v in it.items() if k not in ("summary", "referenced_works")}
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
    s = sub.add_parser("suggest"); s.add_argument("body"); s.add_argument("user")
    f = sub.add_parser("focus"); f.add_argument("body"); f.add_argument("user")
    args = ap.parse_args(argv)
    {"harvest": cmd_harvest, "publish": cmd_publish, "build": cmd_build,
     "suggest": cmd_suggest, "focus": cmd_focus}[args.cmd](args)
