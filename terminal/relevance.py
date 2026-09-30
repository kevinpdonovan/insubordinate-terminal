"""Keyword relevance gate and scoring (runs before, and without, the AI tagger)."""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower().replace("’", "'").replace("–", "-"))


@lru_cache(maxsize=4096)
def _rx(term: str) -> re.Pattern:
    t = re.escape(norm(term).strip())
    return re.compile(rf"(?<![\w]){t}(?![\w])")


def hits(text: str, terms) -> list[str]:
    return [t for t in terms if t and _rx(t).search(text)]


class Scorer:
    def __init__(self, profile: dict):
        self.p = profile
        self.anchors = profile.get("finance_anchors", [])
        self.neg = profile.get("negative_keywords", [])
        self.themes = {t["id"]: t.get("keywords", []) for t in profile.get("themes", [])}
        self.places = {p["id"]: [p["city"]] + p.get("aliases", []) for p in profile.get("places", [])}
        self.context = profile.get("context_places", [])
        self.extra = profile.get("extra_keywords", [])

    def assess(self, item: dict) -> dict:
        title = norm(item.get("title", ""))
        text = title + " " + norm(item.get("summary", ""))
        if hits(title, self.neg):
            return {"pass": False, "score": 0, "reason": "negative keyword"}
        place_hits = {pid: h for pid, terms in self.places.items() if (h := hits(text, terms))}
        theme_hits = {tid: h for tid, terms in self.themes.items() if (h := hits(text, terms))}
        n_theme_terms = sum(len(h) for h in theme_hits.values())
        extra = hits(text, self.extra)
        anchor = bool(hits(text, self.anchors))
        context = hits(text, self.context)
        watched = bool(item.get("watched"))
        score = (3 * len(place_hits) + n_theme_terms + 2 * len(extra) + (1 if context else 0)
                 + (3 if watched else 0) + (1 if item.get("section") == "research" else 0))
        if watched or item.get("filter") is False:
            ok = True
        else:
            ok = anchor and (bool(place_hits) or n_theme_terms >= 2 or bool(extra))
        return {
            "pass": ok,
            "score": score,
            "places": sorted(place_hits),
            "themes": sorted(theme_hits, key=lambda t: -len(theme_hits[t])),
            "reason": "" if ok else ("no finance anchor" if not anchor else "no place/theme match"),
        }
