"""Optional Claude pass: relevance 0–3, theme/city tags, and a one-line note.

Runs only if ANTHROPIC_API_KEY is set. Without it, keyword scores are used.
The tagger sees titles and short abstracts/summaries only.
"""
from __future__ import annotations

import json
import re

from .profile import env

BATCH = 25

SYSTEM = """You are the research assistant for an academic project. You screen candidate items
for a weekly research dashboard and return strict JSON. Be discriminating: most routine
market news is NOT relevant. Relevance scale:
3 = directly about the project's questions (a case-study city's financial centre, a specific
    financial device and its politics, South–South/North–South financial linkages, the
    history of these centres, or scholarship engaging financial subordination / social
    studies of finance in the Global South);
2 = clearly useful context (regulatory changes, debt/ratings events, major deals or
    institutional moves in the case-study countries; relevant scholarship on adjacent cases);
1 = marginal; 0 = irrelevant (price moves, earnings, tips, unrelated topics).
For scholarly items (section research or archive) also give "quality" 0–2 for scholarly
substance, judged from the title, abstract and venue information supplied: 2 = substantive
peer-reviewed scholarship with a clear argument or evidence; 1 = acceptable (thin abstract,
working paper, review, or modest venue); 0 = poor (generic, formulaic or incoherent abstract,
predatory-looking venue, or not really scholarship). Omit "quality" for news and reports.
The one-line note (max 25 words) says concretely why a researcher on this project would care.
Do not repeat the title. Do not speculate beyond the text given. Write notes in English."""


def _prompt(profile: dict, batch: list[dict]) -> str:
    themes = "\n".join(f"- {t['id']}: {t['label']} — {t.get('description','')}" for t in profile["themes"])
    places = ", ".join(f"{p['id']} ({p['city']})" for p in profile["places"])
    items = "\n".join(
        json.dumps({"id": it["id"], "section": it["section"], "title": it["title"],
                    "source": it.get("source", ""), "text": it.get("summary", "")[:700],
                    **({"venue": it.get("venue", ""),
                        "venue_signals": (it.get("quality_signals") or {}).get("labels") or None,
                        "type": it.get("work_type")}
                       if it["section"] in ("research", "archive") else {})},
                   ensure_ascii=False)
        for it in batch)
    return f"""PROJECT BRIEF
{profile['project']['brief']}

THEME IDS
{themes}

PLACE IDS
{places}

ITEMS (one JSON object per line)
{items}

Return ONLY a JSON array with one object per item, in the same order:
[{{"id": "...", "relevance": 0-3, "quality": 0-2 (scholarly items only), "themes": ["theme_id", ...],
   "places": ["place_id", ...], "note": "one line"}}]"""


def _parse(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text, re.S)
    return json.loads(m.group(0)) if m else []


def tag_items(profile: dict, items: list[dict], log=print) -> bool:
    key = env("ANTHROPIC_API_KEY")
    if not key or not items:
        return False
    import anthropic

    client = anthropic.Anthropic(api_key=key)
    model = env("TAGGER_MODEL", "claude-haiku-4-5")
    valid_t = {t["id"] for t in profile["themes"]}
    valid_p = {p["id"] for p in profile["places"]}
    by_id = {it["id"]: it for it in items}
    for i in range(0, len(items), BATCH):
        batch = items[i:i + BATCH]
        try:
            msg = client.messages.create(
                model=model, max_tokens=4000, system=SYSTEM,
                messages=[{"role": "user", "content": _prompt(profile, batch)}])
            results = _parse("".join(b.text for b in msg.content if b.type == "text"))
        except Exception as ex:
            log(f"  tagger batch {i // BATCH + 1} failed: {ex}")
            continue
        for r in results:
            it = by_id.get(r.get("id"))
            if not it:
                continue
            it["ai"] = {
                "relevance": int(r.get("relevance", 0)),
                "themes": [t for t in r.get("themes", []) if t in valid_t],
                "places": [p for p in r.get("places", []) if p in valid_p],
                "note": (r.get("note") or "").strip()[:240],
            }
            if it["section"] in ("research", "archive") and isinstance(r.get("quality"), (int, float)):
                it["ai"]["quality"] = int(r["quality"])
    return True


DIGEST_SYSTEM = """You write the short editorial opening of a weekly academic research digest.
Tone: dry, precise, collegial; no hype, no adjectives like 'exciting'. 3–5 sentences.
Only mention items in the list; refer to them by outlet/author and topic. No bullet points."""


def write_digest(profile: dict, items: list[dict]) -> str:
    key = env("ANTHROPIC_API_KEY")
    if not key or not items:
        return ""
    import anthropic

    client = anthropic.Anthropic(api_key=key)
    listing = "\n".join(f"- [{it['section']}] {it['title']} ({it.get('source','')}) — {it.get('ai',{}).get('note','')}"
                        for it in items[:60])
    try:
        msg = client.messages.create(
            model=env("DIGEST_MODEL", env("TAGGER_MODEL", "claude-haiku-4-5")), max_tokens=600,
            system=DIGEST_SYSTEM,
            messages=[{"role": "user", "content": f"Project: {profile['project']['brief']}\n\nThis week's approved items:\n{listing}\n\nWrite the opening paragraph."}])
        return "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception:
        return ""
