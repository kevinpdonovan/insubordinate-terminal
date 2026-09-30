"""Load the sweep profile (themes.yaml) and merge participant files.

Participants can add their own focus via config/participants/<slug>.yaml
(written automatically from the "Update my research focus" issue form, or by
hand). Those files ADD keywords, queries, authors and news queries to the
shared profile; they never remove anything.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


def _read(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_profile() -> dict:
    prof = _read(CONFIG / "themes.yaml")
    prof.setdefault("participants", [])
    prof.setdefault("extra_keywords", [])
    for path in sorted(glob.glob(str(CONFIG / "participants" / "*.yaml"))):
        p = _read(Path(path))
        if not p or p.get("active") is False:
            continue
        # participant card (replace an existing card with the same name)
        card = {k: p.get(k) for k in ("name", "role", "focus", "orcid") if p.get(k)}
        prof["participants"] = [c for c in prof["participants"] if c.get("name") != card.get("name")]
        prof["participants"].append(card)
        for key, target in (
            ("keywords", "extra_keywords"),
            ("research_queries", "research_queries"),
            ("news_queries", "news_queries"),
            ("watch_authors", "watch_authors"),
        ):
            vals = p.get(key) or []
            prof.setdefault(target, [])
            for v in vals:
                if v and v not in prof[target]:
                    prof[target].append(v)
        if p.get("name") and p.get("name") not in prof.get("watch_authors", []):
            prof.setdefault("watch_authors", []).append(p["name"])
    return prof


def load_sources() -> dict:
    return _read(CONFIG / "sources.yaml")


def load_site() -> dict:
    path = CONFIG / "site.yaml"
    return _read(path) if path.exists() else {}


def lock_path() -> Path:
    return CONFIG / "openalex_lock.yaml"


def load_lock() -> dict:
    p = lock_path()
    return _read(p) if p.exists() else {"authors": {}, "journals": {}}


def save_lock(lock: dict) -> None:
    header = (
        "# Resolved OpenAlex IDs for watched authors/journals.\n"
        "# Written automatically. If an author resolved to the wrong person,\n"
        "# replace the ID by hand (search https://openalex.org) or set it to null to skip.\n"
    )
    with open(lock_path(), "w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump(lock, f, allow_unicode=True, sort_keys=True)


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v else default
