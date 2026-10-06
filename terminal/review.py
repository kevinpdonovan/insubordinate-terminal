"""The weekly review queue lives in a GitHub issue with tick-boxes.

harvest  -> writes candidates.json and an issue body (review.md)
reviewer -> unticks what shouldn't publish, adds ★ to feature, closes the issue
publish  -> reads the closed issue's body and publishes the ticked items
"""
from __future__ import annotations

import re

from .items import SECTION_LABELS, SECTIONS

MAX_PER_SECTION = {"research": 60, "archive": 12, "news": 50, "grey": 45}
MIN_SHOWN = {"news": 2}  # with AI tags, news rated below this isn't even listed
PRETICK = {"research": 2, "archive": 2, "news": 3, "grey": 2}  # AI relevance needed to pre-tick
PRETICK_KEYWORD = 5  # ...or keyword score >= 5 when no AI tags exist
LINE_RX = re.compile(r"^\s*[-*]\s*\[(?P<tick>[ xX])\]\s*(?P<star>★|⭐)?.*?<!--id:(?P<id>[0-9a-f]{10})-->", re.M)


def rank_key(it: dict):
    ai = it.get("ai") or {}
    return (ai.get("relevance", -1), ai.get("quality", 1), it.get("kw", {}).get("score", 0), it.get("date", ""))


def pretick(it: dict) -> bool:
    ai = it.get("ai")
    if ai:
        sec = it.get("section", "news")
        if ai.get("relevance", 0) < PRETICK.get(sec, 2):
            return False
        if sec in ("research", "archive") and not it.get("watched"):
            if (it.get("venue_quality") or {}).get("level") in ("low", "denied"):
                return False
            if ai.get("quality") is not None and ai["quality"] < 1:
                return False
        return True
    if it.get("section") == "archive":
        return it.get("kw", {}).get("score", 0) >= 2
    return it.get("kw", {}).get("score", 0) >= PRETICK_KEYWORD or bool(it.get("watched"))


def select_for_review(items: list[dict]) -> dict[str, list[dict]]:
    out = {}
    for sec in SECTIONS:
        floor = MIN_SHOWN.get(sec, 1)
        pool = [i for i in items if i["section"] == sec
                and (i.get("ai") or {}).get("relevance", floor) >= (floor if i.get("ai") else 1)]
        pool.sort(key=rank_key, reverse=True)
        out[sec] = pool[: MAX_PER_SECTION[sec]]
    return out


def _tags(it: dict) -> str:
    ai = it.get("ai") or {}
    places = ai.get("places") or it.get("kw", {}).get("places", [])
    themes = ai.get("themes") or it.get("kw", {}).get("themes", [])[:2]
    return ", ".join(places + themes)


def issue_body(week: str, chosen: dict[str, list[dict]], stats: dict) -> str:
    L = [f"<!-- terminal:week={week} -->",
         f"**Insubordinate Finance: The Terminal — weekly review for {week}.** Harvested {stats.get('harvested', 0)} items; "
         f"{stats.get('duplicates_removed', 0)} duplicates and {stats.get('repeats_removed', 0)} repeats from earlier weeks were removed; "
         f"{stats.get('passed', 0)} passed the relevance gate; the strongest are listed below. "
         f"News is only pre-ticked when rated 3/3; scholarship in low-signal venues is never pre-ticked.",
         "",
         "**How to review:** untick anything that shouldn't be published. To *feature* an item "
         "(top of the page and the newsletter), edit this issue and add ★ right after its box. "
         "When you're done, **close the issue** and the site updates within a few minutes. "
         "Items you leave unticked won't appear again.",
         ""]
    for sec in SECTIONS:
        items = chosen.get(sec, [])
        L.append(f"### {SECTION_LABELS[sec]} ({len(items)})")
        if not items:
            L.append("_Nothing this week._")
        for it in items:
            tick = "x" if pretick(it) else " "
            rel = (it.get("ai") or {}).get("relevance")
            badge = f"r{rel}" if rel is not None else f"k{it.get('kw', {}).get('score', 0)}"
            note = (it.get("ai") or {}).get("note", "")
            title = it["title"].replace("[", "(").replace("]", ")")[:180]
            vq = (it.get("venue_quality") or {}).get("level", "")
            flag = {"low": "⚠ low-signal venue", "repository": "preprint/repository", "unknown": "venue unknown",
                    "watched": "watched journal"}.get(vq, "")
            also = f"also: {', '.join(it['also_at'][:3])}" if it.get("also_at") else ""
            meta = " · ".join(x for x in [it.get("source", ""), it.get("date", ""), _tags(it), flag, also] if x)
            L.append(f"- [{tick}] [{title}]({it['url']}) · {meta} · `{badge}`"
                     + (f" — {note}" if note else "") + f" <!--id:{it['id']}-->")
        L.append("")
    body = "\n".join(L)
    return body[:65000]


def parse_review(body: str) -> tuple[list[str], list[str]]:
    """Return (approved_ids, featured_ids) from an edited issue body."""
    approved, featured = [], []
    for m in LINE_RX.finditer(body or ""):
        if m.group("tick").lower() == "x":
            approved.append(m.group("id"))
            if m.group("star"):
                featured.append(m.group("id"))
    return approved, featured


def week_from_body(body: str) -> str | None:
    m = re.search(r"terminal:week=(\d{4}-W\d{2})", body or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------- issue forms
def parse_form(body: str) -> dict:
    """Parse a GitHub issue-form body ('### Label\\n\\nvalue') into {label: value}."""
    out, cur = {}, None
    for line in (body or "").splitlines():
        if line.startswith("### "):
            cur = line[4:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    clean = {}
    for k, v in out.items():
        val = "\n".join(v).strip()
        clean[k] = "" if val in ("_No response_", "None") else val
    return clean


def lines(val: str) -> list[str]:
    return [x.strip(" -•\t") for x in re.split(r"[\n;]", val or "") if x.strip(" -•\t")]
