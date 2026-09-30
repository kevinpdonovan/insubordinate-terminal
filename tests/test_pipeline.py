"""Offline end-to-end test: mocks every network call, runs harvest -> review -> publish -> build."""
import datetime as dt, json, os, re, shutil, sys, tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TODAY = dt.date.today().isoformat()

RSS = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Kenya's Capital Markets Authority unveils rules for Nairobi International Financial Centre listings</title>
<link>https://example.org/nifc-rules?utm_source=x</link><pubDate>{dt.date.today().strftime('%a, %d %b %Y')} 08:00:00 GMT</pubDate>
<description>The regulator said the new framework for the financial centre would attract foreign investors.</description></item>
<item><title>Safaricom shares rise 2% in morning trade</title><link>https://example.org/saf</link>
<pubDate>{dt.date.today().strftime('%a, %d %b %Y')} 09:00:00 GMT</pubDate><description>stock</description></item>
<item><title>Recipe: the best chapati</title><link>https://example.org/chapati</link>
<pubDate>{dt.date.today().strftime('%a, %d %b %Y')} 09:00:00 GMT</pubDate><description>food</description></item>
</channel></rss>"""

GDELT = {"articles": [
  {"url": "https://www.bloomberg.com/news/articles/x-brvm", "title": "West African bourse BRVM weighs cross-listing with Nigeria's exchange",
   "seendate": dt.date.today().strftime("%Y%m%dT120000Z"), "domain": "bloomberg.com", "language": "English", "sourcecountry": "United States"},
  {"url": "https://example.fr/abj", "title": "Abidjan: la place financière régionale attire les banques d'investissement",
   "seendate": dt.date.today().strftime("%Y%m%dT100000Z"), "domain": "example.fr", "language": "French", "sourcecountry": "France"}]}

def work(i, title, year, refs=(), src="Review of International Political Economy", abstract="financial subordination in Africa stock exchange"):
    return {"id": f"https://openalex.org/W{i}", "doi": f"https://doi.org/10.1000/test{i}", "title": title,
            "publication_date": f"{year}-06-01" if year < 2026 else TODAY, "publication_year": year,
            "authorships": [{"author": {"display_name": "A. Author"}}, {"author": {"display_name": "B. Author"}}],
            "primary_location": {"source": {"display_name": src}, "landing_page_url": f"https://example.org/w{i}"},
            "abstract_inverted_index": {w: [n] for n, w in enumerate(abstract.split())},
            "type": "article", "referenced_works": [f"https://openalex.org/W{r}" for r in refs]}

NEW = [work(1, "Provincializing the stock exchange: devices of valuation in Casablanca and Abidjan", 2026, refs=(900, 901)),
       work(2, "Monetary sovereignty and the CFA franc: a postcolonial financial history", 2026, refs=(900,))]
OLD = [work(900, "Global and world cities: a view from off the map", 2002, src="IJURR", abstract="financial centre global south cities postcolonial finance"),
       work(901, "Market devices", 2007, src="Blackwell", abstract="financial markets devices valuation")]

class Resp:
    def __init__(self, content=b"", js=None, status=200):
        self.content = content if isinstance(content, bytes) else content.encode()
        self._js = js; self.status_code = status
        self.text = json.dumps(js) if js is not None else self.content.decode()
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(f"HTTP {self.status_code}")
    def json(self): return self._js

def fake_get(url, params=None, timeout=None):
    params = params or {}
    if "gdeltproject" in url: return Resp(js=GDELT)
    if url.endswith("/authors") or url.endswith("/sources"):
        return Resp(js={"results": [{"id": "https://openalex.org/A1", "display_name": params.get("search"), "works_count": 10}]})
    if url.endswith("/works"):
        f = params.get("filter", "")
        if f.startswith("openalex:"): return Resp(js={"results": OLD, "meta": {}})
        return Resp(js={"results": NEW, "meta": {"next_cursor": None}})
    if "broken" in url: return Resp(status=404)
    return Resp(content=RSS)

def test_end_to_end():
    tmp = Path(tempfile.mkdtemp())
    for d in ("config", "templates", "static", "terminal"):
        shutil.copytree(ROOT / d, tmp / d)
    # small sources file incl. one broken feed
    (tmp / "config/sources.yaml").write_text("""
research: [{name: OA q, type: openalex, mode: queries}, {name: OA authors, type: openalex, mode: authors}]
archive: [{name: trail, type: openalex, mode: citations, older_than_years: 10, max_items: 8}]
news: [{name: GDELT, type: gdelt, mode: queries}, {name: Regional, type: rss, url: "https://example.org/feed", filter: true}]
grey: [{name: Broken, type: rss, url: "https://broken.example/feed", filter: true}]
""")
    th = (tmp / "config/themes.yaml").read_text()
    th = re.sub(r"news_queries:\n(  - .*\n)+", "news_queries:\n  - '\"test\"'\n", th)
    th = re.sub(r"research_queries:\n(  - .*\n)+", "research_queries:\n  - \"financial subordination\"\n", th)
    (tmp / "config/themes.yaml").write_text(th)
    sys.path.insert(0, str(tmp))
    for m in [m for m in sys.modules if m.startswith("terminal")]: del sys.modules[m]
    import terminal.harvesters as H
    from terminal import cli
    os.environ.pop("ANTHROPIC_API_KEY", None)
    with mock.patch.object(H.S, "get", side_effect=fake_get), mock.patch.object(H.time, "sleep"):
        cli.main(["harvest", "--week", "2026-W40"])
    body = (tmp / "data/runs/2026-W40/review.md").read_text()
    print(body)
    assert "Nairobi International Financial Centre" in body
    assert "shares rise" not in body, "negative keyword should drop market chatter"
    assert "chapati" not in body, "off-topic item should fail the gate"
    assert "Global and world cities" in body, "citation trail should surface older work"
    health = json.loads((tmp / "data/health.json").read_text())
    assert any(not h["ok"] and h["source"] == "Broken" for h in health["sources"])
    # reviewer: untick the Bloomberg item, feature the NIFC item
    lines = []
    for ln in body.splitlines():
        if "bloomberg.com" in ln: ln = ln.replace("- [x]", "- [ ]")
        if "Nairobi International" in ln: ln = ln.replace("- [x]", "- [x] ★").replace("- [ ]", "- [x] ★")
        lines.append(ln)
    (tmp / "edited.md").write_text("\n".join(lines))
    # a hand suggestion via the issue form
    (tmp / "form.md").write_text("### Link\n\nhttps://example.org/paper\n\n### Title\n\nA suggested paper\n\n### Source / outlet\n\nAfrica\n\n### Section\n\nNew research\n\n### Why it matters (one line)\n\nDirectly on Nairobi's financial centre.\n")
    cli.main(["suggest", str(tmp / "form.md"), "kdonovan"])
    (tmp / "focus.md").write_text("### Your name (as it appears on publications)\n\nKevin P. Donovan\n\n### Role on the project\n\nAR1\n\n### ORCID (optional)\n\n_No response_\n\n### Current focus (cities, devices, topics — one per line)\n\nNairobi\nparastatal finance\n\n### Keywords the sweep should watch for (one per line)\n\nparastatal\nSafaricom privatisation\n\n### Scholarly search phrases (one per line)\n\nparastatal governance Kenya\n\n### News search phrases (one per line)\n\n_No response_\n\n### Authors to follow (one per line)\n\n_No response_\n")
    cli.main(["focus", str(tmp / "focus.md"), "kdonovan"])
    from terminal.profile import load_profile
    p = load_profile()
    assert "parastatal" in p["extra_keywords"] and "parastatal governance Kenya" in p["research_queries"]
    cli.main(["publish", str(tmp / "edited.md")])
    issue = json.loads((tmp / "data/issues/2026-W40.json").read_text())
    titles = [i["title"] for i in issue["items"]]
    assert not any("BRVM weighs" in t for t in titles), "unticked item must not publish"
    assert any(i.get("featured") and "Nairobi" in i["title"] for i in issue["items"])
    assert "A suggested paper" in titles
    assert all("summary" not in i for i in issue["items"]), "abstracts/summaries must not be published"
    html = (tmp / "site/index.html").read_text()
    assert "Featured" in html and "A suggested paper" in html
    assert 'name="robots" content="noindex' in html
    feed = (tmp / "site/feed.xml").read_text()
    assert "<rss" in feed and "2026-W40" in feed
    print("\nPUBLISHED:", len(titles), "items;", "site at", tmp / "site")
    return tmp

if __name__ == "__main__":
    t = test_end_to_end()
    print("OK", t)
