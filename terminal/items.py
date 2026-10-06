"""The common item record, IDs, weeks, and the seen-store."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .profile import ROOT

DATA = ROOT / "data"
SECTIONS = ["research", "news", "grey", "archive"]
SECTION_LABELS = {
    "research": "New research",
    "archive": "From the archive",
    "news": "News",
    "grey": "Reports & grey literature",
}

_TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_cid|mc_eid|cmpid|ref$|src$)")


def clean_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING.match(k)]
    return urlunsplit((parts.scheme or "https", parts.netloc.lower(), parts.path.rstrip("/") or "/", urlencode(q), ""))


def item_id(url: str = "", doi: str = "", title: str = "") -> str:
    key = (doi or "").lower().strip() or clean_url(url) or re.sub(r"\W+", "", (title or "").lower())
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def make_item(*, section, title, url, source, date=None, doi="", authors=None, summary="",
              venue="", origin="", extra=None) -> dict:
    title = re.sub(r"\s+", " ", (title or "")).strip()
    doi = (doi or "").replace("https://doi.org/", "").strip()
    link = f"https://doi.org/{doi}" if doi else clean_url(url)
    return {
        "id": item_id(url, doi, title),
        "section": section,
        "title": title,
        "url": link,
        "doi": doi,
        "source": source,          # outlet / journal / organisation
        "venue": venue,            # journal name for research
        "authors": authors or [],
        "date": (date or "")[:10],
        "summary": re.sub(r"<[^>]+>", " ", summary or "")[:1500].strip(),  # for tagging only; never published
        "origin": origin,          # which harvester found it
        "scholarly": bool(doi) or section in ("research", "archive"),
        **(extra or {}),
    }


def iso_week(d: dt.date | None = None) -> str:
    d = d or dt.date.today()
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_range(week: str) -> tuple[dt.date, dt.date]:
    y, w = week.split("-W")
    start = dt.date.fromisocalendar(int(y), int(w), 1)
    return start, start + dt.timedelta(days=6)


def load_json(path: Path, default):
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


class SeenStore:
    """Remembers item IDs already put in front of a reviewer, so nothing repeats."""

    def __init__(self, path: Path = DATA / "seen.json", keep_weeks: int = 52):
        self.path = path
        self.keep_weeks = keep_weeks
        self.data = load_json(path, {})

    def __contains__(self, iid: str) -> bool:
        return iid in self.data

    def add(self, iid: str, week: str) -> None:
        self.data.setdefault(iid, week)

    def save(self) -> None:
        cutoff = iso_week(dt.date.today() - dt.timedelta(weeks=self.keep_weeks))
        self.data = {k: v for k, v in self.data.items() if v >= cutoff}
        save_json(self.path, self.data)
