"""Build the static site from published weekly issues in data/issues/."""
from __future__ import annotations

import datetime as dt
import glob
import html
import json
import shutil
from email.utils import format_datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .items import DATA, SECTION_LABELS, SECTIONS, load_json, week_range
from .profile import ROOT, load_profile, load_site, load_sources

SITE = ROOT / "site"
TEMPLATES = ROOT / "templates"
STATIC = ROOT / "static"


def load_issues() -> list[dict]:
    issues = [load_json(Path(p), {}) for p in sorted(glob.glob(str(DATA / "issues" / "*.json")))]
    return sorted([i for i in issues if i.get("week")], key=lambda i: i["week"], reverse=True)


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["nicedate"] = lambda d: dt.date.fromisoformat(d).strftime("%-d %b %Y") if d else ""
    return env


def _decorate(issue: dict, profile: dict) -> dict:
    tlabel = {t["id"]: t["label"] for t in profile["themes"]}
    plabel = {p["id"]: p["city"] for p in profile["places"]}
    start, end = week_range(issue["week"])
    issue["range"] = f"{start.strftime('%-d %b')} – {end.strftime('%-d %b %Y')}"
    for it in issue["items"]:
        ai = it.get("ai") or {}
        kw = it.get("kw") or {}
        it["place_ids"] = ai.get("places") or kw.get("places", [])
        it["theme_ids"] = ai.get("themes") or kw.get("themes", [])[:3]
        it["place_labels"] = [plabel.get(p, p) for p in it["place_ids"]]
        it["theme_labels"] = [tlabel.get(t, t) for t in it["theme_ids"]]
        it["note"] = it.get("editor_note") or ai.get("note", "")
        a = it.get("authors") or []
        it["byline"] = (", ".join(a[:3]) + (" et al." if len(a) > 3 else "")) if a else ""
    issue["by_section"] = {s: [i for i in issue["items"] if i["section"] == s] for s in SECTIONS}
    issue["featured_items"] = [i for i in issue["items"] if i.get("featured")]
    issue["counts"] = {s: len(v) for s, v in issue["by_section"].items()}
    used_p = sorted({p for i in issue["items"] for p in i["place_ids"]}, key=lambda p: plabel.get(p, p))
    used_t = sorted({t for i in issue["items"] for t in i["theme_ids"]}, key=lambda t: tlabel.get(t, t))
    issue["filter_places"] = [(p, plabel.get(p, p)) for p in used_p]
    issue["filter_themes"] = [(t, tlabel.get(t, t)) for t in used_t]
    return issue


def _rss(site: dict, issues: list[dict]) -> str:
    base = (site.get("base_url") or "").rstrip("/")
    entries = []
    for iss in issues[:20]:
        link = f"{base}/weeks/{iss['week']}.html"
        parts = []
        if iss.get("digest"):
            parts.append(f"<p>{html.escape(iss['digest'])}</p>")
        for sec in SECTIONS:
            items = iss["by_section"][sec]
            if not items:
                continue
            parts.append(f"<h3>{SECTION_LABELS[sec]}</h3><ul>")
            for it in items[:15]:
                note = f" — {html.escape(it['note'])}" if it.get("note") else ""
                parts.append(f'<li><a href="{html.escape(it["url"])}">{html.escape(it["title"])}</a> '
                             f'<em>({html.escape(it.get("source", ""))})</em>{note}</li>')
            if len(items) > 15:
                parts.append(f'<li><a href="{link}">+ {len(items) - 15} more</a></li>')
            parts.append("</ul>")
        pub = dt.datetime.fromisoformat(iss.get("published_at", dt.datetime.utcnow().isoformat()))
        entries.append(
            f"<item><title>{html.escape(site['title'])} — {iss['week']}</title><link>{link}</link>"
            f"<guid isPermaLink=\"false\">{iss['week']}</guid>"
            f"<pubDate>{format_datetime(pub.replace(tzinfo=dt.timezone.utc))}</pubDate>"
            f"<description>{html.escape(''.join(parts))}</description></item>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
            f"<title>{html.escape(site['title'])}</title><link>{base}/</link>"
            f"<description>{html.escape(site.get('subtitle', ''))}</description>"
            + "".join(entries) + "</channel></rss>\n")


def build(log=print) -> None:
    profile, site, sources = load_profile(), load_site(), load_sources()
    issues = [_decorate(i, profile) for i in load_issues()]
    env = _env()
    if SITE.exists():
        shutil.rmtree(SITE)
    (SITE / "weeks").mkdir(parents=True)
    shutil.copytree(STATIC, SITE / "static")
    common = {"site": site, "profile": profile, "sections": SECTIONS, "labels": SECTION_LABELS,
              "issues": issues, "built": dt.datetime.utcnow().strftime("%-d %b %Y, %H:%M UTC"),
              "proxies_json": json.dumps(site.get("library_proxies", []))}

    def render(tpl, out, **ctx):
        (SITE / out).write_text(env.get_template(tpl).render(**common, **ctx), encoding="utf-8")

    for n, iss in enumerate(issues):
        ctx = {"issue": iss, "prev": issues[n + 1]["week"] if n + 1 < len(issues) else None,
               "next": issues[n - 1]["week"] if n > 0 else None}
        render("week.html", f"weeks/{iss['week']}.html", root="../", page="week", **ctx)
        if n == 0:
            render("week.html", "index.html", root="", page="home", **ctx)
    if not issues:
        render("empty.html", "index.html", root="", page="home")
    render("archive.html", "archive.html", root="", page="archive")
    def js(obj):
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    render("search.html", "search.html", root="", page="search",
           place_labels_json=js({p["id"]: p["city"] for p in profile["places"]}),
           theme_labels_json=js({t["id"]: t["label"] for t in profile["themes"]}),
           section_labels_json=js(SECTION_LABELS))
    render("about.html", "about.html", root="", page="about", sources=sources)
    health = load_json(DATA / "health.json", {})
    render("health.html", "health.html", root="", page="health", health=health)
    (SITE / "feed.xml").write_text(_rss(site, issues), encoding="utf-8")
    (SITE / "items.json").write_text(json.dumps(
        [{k: i.get(k) for k in ("id", "section", "title", "url", "source", "date", "authors",
                                "place_ids", "theme_ids", "note")} | {"week": iss["week"]}
         for iss in issues for i in iss["items"]], ensure_ascii=False), encoding="utf-8")
    robots = "User-agent: *\nAllow: /\n" if site.get("public") else "User-agent: *\nDisallow: /\n"
    (SITE / "robots.txt").write_text(robots)
    (SITE / ".nojekyll").write_text("")
    log(f"built site: {len(issues)} issue(s) -> {SITE}")
