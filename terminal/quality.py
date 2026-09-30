"""Venue-quality signals for scholarship (and a domain allowlist for news).

Venue levels, best to worst:
  watched      a journal on the project's watch list
  established  OpenAlex h-index >= 20
  modest       h-index 5–19
  repository   preprint server / institutional repository (fine, but flagged)
  unknown      no venue information
  low          h-index < 5
  denied       venue or publisher on the deny list (dropped unless by a watched author)
"""
from __future__ import annotations

from .dedupe import domain_of
from .relevance import norm

LEVEL_SCORE = {"watched": 3, "established": 2, "modest": 1, "repository": 0, "unknown": 0, "low": -2, "denied": -10}


def _match(name: str, patterns: list[str]) -> bool:
    n = norm(name)
    return any(norm(p) in n for p in patterns if p)


def venue_level(it: dict, venues: dict, profile: dict) -> str:
    q = profile.get("quality", {})
    name, publisher = it.get("venue") or it.get("source", ""), it.get("publisher", "")
    info = venues.get(it.get("venue_id", ""), {})
    publisher = publisher or info.get("publisher", "")
    if _match(name, q.get("venue_denylist", [])) or _match(publisher, q.get("publisher_denylist", [])):
        return "denied"
    watched = {norm(j) for j in profile.get("watch_journals", []) + q.get("venue_allowlist", [])}
    if norm(name) in watched:
        return "watched"
    vtype = it.get("venue_type") or info.get("type", "")
    if vtype == "repository":
        return "repository"
    if not info:
        return "unknown"
    h = info.get("h_index", 0) or 0
    if h >= q.get("established_h_index", 20):
        return "established"
    if h >= q.get("modest_h_index", 5):
        return "modest"
    return "low"


def apply_venue_quality(items: list[dict], venues: dict, profile: dict) -> int:
    """Annotate scholarly items; drop denied venues (unless by a watched author). Returns n dropped."""
    dropped = 0
    for it in items:
        if it["section"] not in ("research", "archive") or it.get("origin", "").startswith(("email", "suggestion")):
            continue
        lvl = venue_level(it, venues, profile)
        info = venues.get(it.get("venue_id", ""), {})
        it["venue_quality"] = {"level": lvl, "h_index": info.get("h_index")}
        if lvl == "denied" and not it.get("watched"):
            it["drop"] = "venue on deny list"
            dropped += 1
    return dropped


# ------------------------------------------------------------- news outlets
def outlet_rank(profile_sources: dict) -> dict[str, int]:
    """Domain -> rank (0 = best) from sources.yaml > news_outlets."""
    rank = {}
    for i, d in enumerate(profile_sources.get("news_outlets", []) or []):
        rank[d.lower().removeprefix("www.")] = i
    return rank


def outlet_ok(it: dict, rank: dict[str, int]) -> bool:
    d = domain_of(it)
    return any(d == o or d.endswith("." + o) for o in rank)


def rank_for(it: dict, rank: dict[str, int]) -> int:
    d = domain_of(it)
    for o, r in rank.items():
        if d == o or d.endswith("." + o):
            return r
    return 10_000
