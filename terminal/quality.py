"""Quality signals for scholarship (and a domain allowlist for news).

Items are not judged by citation counts. Each scholarly item collects
*positive* signals; an item with at least one is eligible to be pre-ticked,
and the signals are shown in the review issue so the reason is visible.

  watched venue        a journal on the project's watch list        +2
  watched author       an author on the project's watch list        +2
  team author          a member of the project team                 +2
  reputable publisher  a publisher on the allowlist                 +1
  DOAJ                 journal indexed in the Directory of Open     +1
                       Access Journals (OpenAlex supplies this)
  peer-reviewed        article/review/book, not a preprint          +1
  Claude quality 2     added at pre-tick time, after tagging        +1

Nothing is dropped on bibliometrics. The only items dropped are those on the
predatory venue/publisher deny lists, which is a different judgement from
"this venue is not well cited" — and even then, not if the author is watched.

The h-index is deliberately not used: Kevin considers it a poor measure of
quality, and it biases against new, Southern and non-English venues.
"""
from __future__ import annotations

from .dedupe import domain_of
from .relevance import norm

PEER_REVIEWED_TYPES = {"article", "review", "book", "book-chapter"}


def _match(name: str, patterns: list[str]) -> bool:
    n = norm(name)
    return any(norm(p) in n for p in patterns if p)


def _matched(name: str, patterns: list[str]) -> str:
    n = norm(name)
    for p in patterns:
        if p and norm(p) in n:
            return p
    return ""


def is_denied(it: dict, venues: dict, profile: dict) -> bool:
    q = profile.get("quality", {})
    name = it.get("venue") or it.get("source", "")
    info = venues.get(it.get("venue_id", ""), {})
    publisher = it.get("publisher", "") or info.get("publisher", "")
    return _match(name, q.get("venue_denylist", [])) or _match(publisher, q.get("publisher_denylist", []))


def quality_signals(it: dict, venues: dict, profile: dict) -> tuple[int, list[str]]:
    """Return (score, labels) from venue, author, publisher and type signals."""
    q = profile.get("quality", {})
    name = it.get("venue") or it.get("source", "")
    info = venues.get(it.get("venue_id", ""), {})
    publisher = it.get("publisher", "") or info.get("publisher", "")
    score, labels = 0, []

    watched_venues = {norm(j) for j in profile.get("watch_journals", []) + q.get("venue_allowlist", [])}
    if norm(name) in watched_venues:
        score += 2
        labels.append("watched journal")

    if it.get("watched"):
        score += 2
        labels.append("watched author")

    authors = {norm(a) for a in it.get("authors", [])}
    team = [p.get("name", "") for p in profile.get("participants", []) if p.get("name")]
    if any(norm(t) in authors for t in team):
        score += 2
        labels.append("team author")

    pub = _matched(publisher, q.get("publisher_allowlist", []))
    if pub:
        score += 1
        labels.append(pub)

    if info.get("doaj"):
        score += 1
        labels.append("DOAJ")

    vtype = it.get("venue_type") or info.get("type", "")
    if it.get("work_type") in PEER_REVIEWED_TYPES and vtype != "repository":
        score += 1
        labels.append("peer-reviewed")
    elif vtype == "repository" or it.get("work_type") == "preprint":
        labels.append("preprint/repository")

    return score, labels


def apply_quality_signals(items: list[dict], venues: dict, profile: dict) -> int:
    """Annotate scholarly items; drop deny-listed venues (unless by a watched author).

    Returns the number dropped.
    """
    dropped = 0
    for it in items:
        if it["section"] not in ("research", "archive") or it.get("origin", "").startswith(("email", "suggestion")):
            continue
        if is_denied(it, venues, profile) and not it.get("watched"):
            it["drop"] = "venue on deny list"
            dropped += 1
            continue
        score, labels = quality_signals(it, venues, profile)
        it["quality_signals"] = {"score": score, "labels": labels}
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
