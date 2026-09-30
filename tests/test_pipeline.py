"""Offline end-to-end test: every network call is mocked.

Covers harvest (OpenAlex, GDELT, RSS, World Bank, page watcher, email), de-duplication,
venue quality, the review queue, publishing, the issue forms, and the site build.
Run:  python tests/test_pipeline.py
"""
import datetime as dt, json, os, re, shutil, sys, tempfile
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
TODAY = dt.date.today()
RFC = TODAY.strftime("%a, %d %b %Y") + " 08:00:00 GMT"

RSS = f"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>Kenya's Capital Markets Authority unveils listing rules for Nairobi International Financial Centre firms</title>
<link>https://www.businessdailyafrica.com/nifc-rules?utm_source=x</link><pubDate>{RFC}</pubDate>
<description>The regulator said the framework for the financial centre would attract foreign investors.</description></item>
<item><title>Safaricom shares rise 2% in morning trade</title><link>https://example.org/saf</link><pubDate>{RFC}</pubDate><description>stock</description></item>
<item><title>Investment in Bangkok property picks up</title><link>https://example.org/bkk</link><pubDate>{RFC}</pubDate><description>investment Bangkok</description></item>
</channel></rss>"""

SEEN = TODAY.strftime("%Y%m%dT120000Z")
GDELT = {"articles": [
  {"url": "https://www.bloomberg.com/news/articles/x-brvm", "title": "West African bourse BRVM weighs cross-listing with Nigeria's exchange", "seendate": SEEN, "domain": "bloomberg.com"},
  {"url": "https://www.marketscreener-clone.biz/brvm", "title": "West African bourse BRVM weighs cross-listing with Nigeria exchange", "seendate": SEEN, "domain": "marketscreener-clone.biz"},
  {"url": "https://allafrica.com/stories/brvm", "title": "West African Bourse BRVM Weighs Cross-Listing With Nigeria's Exchange", "seendate": SEEN, "domain": "allafrica.com"},
  {"url": "https://www.jeuneafrique.com/abj", "title": "Abidjan : la place financière régionale attire les banques d'investissement et le marché financier", "seendate": SEEN, "domain": "jeuneafrique.com"},
]}

def work(i, title, year, refs=(), src="Review of International Political Economy", sid="S1", stype="journal",
         abstract="financial subordination in Africa stock exchange cross-listing capital market development",
         author="Ilias Alami", doi=True, publisher="Taylor & Francis"):
    return {"id": f"https://openalex.org/W{i}", "doi": f"https://doi.org/10.1000/test{i}" if doi else None, "title": title,
            "publication_date": f"{year}-06-01" if year < TODAY.year else TODAY.isoformat(), "publication_year": year,
            "authorships": [{"author": {"display_name": author}}, {"author": {"display_name": "B. Author"}}],
            "primary_location": {"source": {"id": f"https://openalex.org/{sid}", "display_name": src, "type": stype,
                                            "host_organization_name": publisher},
                                 "landing_page_url": f"https://example.org/w{i}"},
            "abstract_inverted_index": {w: [n] for n, w in enumerate(abstract.split())},
            "type": "article" if stype == "journal" else "preprint", "referenced_works": [f"https://openalex.org/W{r}" for r in refs]}

NEW = [
  work(1, "Provincializing the stock exchange: devices of valuation in Casablanca and Abidjan", TODAY.year, refs=(900, 901)),
  # same work as a preprint on a repository: must merge into W1
  work(11, "Provincializing the Stock Exchange — Devices of Valuation in Casablanca and Abidjan", TODAY.year, src="SSRN", sid="S9", stype="repository", doi=False),
  work(2, "Monetary sovereignty and the CFA franc: a postcolonial financial history of Abidjan's financial centre", TODAY.year, refs=(900,)),
  # predatory venue: must be dropped
  work(3, "Stock exchange and financial centre growth in Nairobi: a financial subordination study", TODAY.year, src="Journal of Economics and Sustainable Development", sid="S7", publisher="IISTE"),
]
OLD = [work(900, "Global and world cities: a view from off the map financial centre", 2002, src="IJURR", sid="S2",
            abstract="financial centre global south cities postcolonial finance cross-listing capital market development")]
SOURCES = {"S1": 120, "S2": 150, "S9": 0, "S7": 3}

WB = {"total": 2, "documents": {
  "D1": {"display_title": "Kenya - Capital Market Development and Financial Sector Deepening Program", "docdt": TODAY.isoformat() + "T00:00:00Z", "docty": "Program Document", "url": "https://documents.worldbank.org/d1", "count": "Kenya"},
  "D2": {"display_title": "Water supply in rural Peru", "docdt": TODAY.isoformat() + "T00:00:00Z", "docty": "Report", "url": "https://documents.worldbank.org/d2", "count": "Peru"},
  "facets": []}}

PAGE_V1 = '<html><body><a href="/press/2026/old-release.pdf">Old press release on monetary policy committee decision</a><a href="/about">About</a></body></html>'
PAGE_V2 = PAGE_V1 + '<a href="/press/2026/nifc-circular.pdf">Circular on Nairobi International Financial Centre capital market development</a>'
PAGE = {"html": PAGE_V1}

class Resp:
    def __init__(self, content=b"", js=None, status=200, url=""):
        self.content = content if isinstance(content, bytes) else content.encode()
        self._js = js; self.status_code = status; self.url = url
        self.text = json.dumps(js) if js is not None else self.content.decode()
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(f"HTTP {self.status_code}")
    def json(self): return self._js
    def close(self): pass

def fake_get(url, params=None, timeout=None, **kw):
    params = params or {}
    if "gdeltproject" in url: return Resp(js=GDELT)
    if "worldbank.org/api" in url: return Resp(js=WB)
    if url.endswith("/authors"):
        return Resp(js={"results": [{"id": "https://openalex.org/A1", "display_name": params.get("search"), "works_count": 10,
                                     "topics": [{"count": 5, "field": {"display_name": "Social Sciences"}}]}]})
    if url.endswith("/sources"):
        f = params.get("filter", "")
        if f.startswith("openalex:"):
            ids = f.split(":", 1)[1].split("|")
            return Resp(js={"results": [{"id": f"https://openalex.org/{i}", "display_name": i, "type": "journal",
                                         "summary_stats": {"h_index": SOURCES.get(i, 0)}} for i in ids]})
        return Resp(js={"results": [{"id": "https://openalex.org/S1", "display_name": params.get("search")}]})
    if url.endswith("/works"):
        f = params.get("filter", "")
        if f.startswith("openalex:"): return Resp(js={"results": OLD, "meta": {}})
        if "type:report" in f: return Resp(js={"results": [], "meta": {}})
        if "authorships.author.id" in f: return Resp(js={"results": [NEW[0]], "meta": {}})
        return Resp(js={"results": NEW, "meta": {"next_cursor": None}})
    if "centralbank" in url: return Resp(content=PAGE["html"], url=url)
    if "broken" in url: return Resp(status=404)
    if "redirect.bloomberg" in url: return Resp(url="https://www.bloomberg.com/news/articles/kenya-eurobond")
    return Resp(content=RSS)

def fake_imap_factory():
    msg = EmailMessage()
    msg["From"] = "Bloomberg <noreply@news.bloomberg.com>"; msg["Date"] = RFC; msg["Subject"] = "Alert"
    msg.set_content('<html><a href="https://redirect.bloomberg.com/c/abc">Kenya plans Eurobond buyback as Nairobi exchange reforms sovereign debt market</a>'
                    '<a href="https://redirect.bloomberg.com/c/unsub">Unsubscribe from these alerts please</a></html>', subtype="html")
    raw = msg.as_bytes()
    class M:
        def __init__(self, host): pass
        def login(self, u, p): pass
        def select(self, f, readonly=True): return ("OK", [b"1"])
        def search(self, charset, crit): return ("OK", [b"1"] if "bloomberg" in crit else [b""])
        def fetch(self, mid, what): return ("OK", [(b"1", raw)])
        def logout(self): pass
    return M

def setup_tmp():
    tmp = Path(tempfile.mkdtemp())
    for d in ("config", "templates", "static", "terminal"):
        shutil.copytree(ROOT / d, tmp / d)
    (tmp / "config/sources.yaml").write_text("""
news_outlets: [bloomberg.com, jeuneafrique.com, businessdailyafrica.com, allafrica.com]
research: [{name: OA q, type: openalex, mode: queries}, {name: OA authors, type: openalex, mode: authors}]
archive: [{name: trail, type: openalex, mode: citations, older_than_years: 10, max_items: 8}]
news:
  - {name: GDELT, type: gdelt, mode: queries}
  - {name: Regional, type: rss, url: "https://www.businessdailyafrica.com/feed", filter: true}
  - {name: Bloomberg alerts, type: email, from: bloomberg, label: Bloomberg, link_pattern: 'bloomberg\\.com/news/', resolve_redirects: true, filter: false}
grey:
  - {name: World Bank, type: worldbank}
  - {name: CBK, type: pagewatch, url: "https://www.centralbank.go.ke/", link_pattern: '\\.pdf', org: "Central Bank of Kenya"}
  - {name: Broken, type: rss, url: "https://broken.example/feed", filter: true}
""")
    th = (tmp / "config/themes.yaml").read_text()
    th = re.sub(r"news_queries:\n(  - .*\n)+", "news_queries:\n  - '\"test\"'\n", th)
    th = re.sub(r"research_queries:\n(  - .*\n)+", "research_queries:\n  - \"financial subordination\"\n", th)
    th = re.sub(r"grey_queries:\n(  - .*\n)+", "grey_queries:\n  - \"capital market development\"\n", th)
    (tmp / "config/themes.yaml").write_text(th)
    sys.path.insert(0, str(tmp))
    for m in [m for m in sys.modules if m.startswith("terminal")]: del sys.modules[m]
    return tmp

def harvest(tmp, week):
    import terminal.harvesters as H
    from terminal import cli
    import imaplib
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ["IMAP_USER"] = "x"; os.environ["IMAP_PASSWORD"] = "y"
    with mock.patch.object(H.S, "get", side_effect=fake_get), mock.patch.object(H.time, "sleep"), \
         mock.patch.object(imaplib, "IMAP4_SSL", fake_imap_factory()):
        cli.main(["harvest", "--week", week])
    return (tmp / f"data/runs/{week}/review.md").read_text()

def test_end_to_end():
    tmp = setup_tmp()
    from terminal import cli
    body = harvest(tmp, "2026-W40")
    print(body)
    cands = json.loads((tmp / "data/runs/2026-W40/candidates.json").read_text())
    titles = [c["title"] for c in cands]
    # research: preprint merged into the journal version
    prov = [c for c in cands if c["title"].lower().startswith("provincializing")]
    assert len(prov) == 1 and prov[0]["doi"], "preprint should merge into journal version"
    assert "SSRN" in prov[0].get("also_at", []), prov[0].get("also_at")
    # predatory venue dropped
    assert not any("subordination study" in t for t in titles), "deny-listed venue should be dropped"
    # news: syndicated copies clustered, non-allow-listed outlet dropped, Bloomberg copy kept
    brvm = [c for c in cands if "BRVM" in c["title"]]
    assert len(brvm) == 1 and "bloomberg.com" in brvm[0]["url"], brvm
    assert "allafrica.com" in brvm[0].get("also_at", [])
    assert not any("marketscreener" in c["url"] for c in cands)
    # gate: a place name alone is not enough
    assert not any("Bangkok property" in t for t in titles)
    assert not any("shares rise" in t for t in titles)
    # email: redirect resolved to bloomberg.com, unsubscribe link ignored
    em = [c for c in cands if c.get("origin", "").startswith("email")]
    assert len(em) == 1 and em[0]["url"].startswith("https://www.bloomberg.com/news/articles/kenya-eurobond"), em
    # World Bank: relevant document in, irrelevant out
    assert any("Capital Market Development" in t for t in titles) and not any("Peru" in t for t in titles)
    # page watcher: first run is a baseline only
    health = {h["source"]: h for h in json.loads((tmp / "data/health.json").read_text())["sources"]}
    assert "baseline" in health["CBK"]["note"], health["CBK"]
    assert not health["Broken"]["ok"]
    # archive trail
    assert any("Global and world cities" in t for t in titles)

    # ---- publish
    lines = []
    for ln in body.splitlines():
        if "Nairobi International" in ln: ln = re.sub(r"- \[.\]", "- [x] ★", ln)
        lines.append(ln)
    (tmp / "edited.md").write_text("\n".join(lines))
    (tmp / "form.md").write_text("### Link\n\nhttps://example.org/paper\n\n### Title\n\nA suggested paper\n\n### Source / outlet\n\nAfrica\n\n### Section\n\nNew research\n\n### Why it matters (one line)\n\nOn Nairobi.\n")
    cli.main(["suggest", str(tmp / "form.md"), "kevinpdonovan"])
    cli.main(["publish", str(tmp / "edited.md")])
    issue = json.loads((tmp / "data/issues/2026-W40.json").read_text())
    ptitles = [i["title"] for i in issue["items"]]
    assert any(i.get("featured") and "Nairobi" in i["title"] for i in issue["items"])
    assert "A suggested paper" in ptitles
    assert all("summary" not in i and "work_key" not in i for i in issue["items"])

    # ---- week 2: repeats (even with a new URL) must not come back; page watcher reports new link
    PAGE["html"] = PAGE_V2
    GDELT["articles"].append({"url": "https://www.jeuneafrique.com/abj-copy?ref=2", "title": "Abidjan: la place financière régionale attire les banques d'investissement et le marché financier",
                              "seendate": SEEN, "domain": "jeuneafrique.com"})
    for m in [m for m in sys.modules if m.startswith("terminal")]: del sys.modules[m]
    body2 = harvest(tmp, "2026-W41")
    c2 = json.loads((tmp / "data/runs/2026-W41/candidates.json").read_text())
    assert not any("Provincializing" in c["title"] for c in c2), "repeat from last week"
    assert not any("place financière" in c["title"] for c in c2), "fuzzy repeat from last week"
    assert any("Circular on Nairobi" in c["title"] for c in c2), "page watcher should report the new link"

    # ---- site
    from terminal import build
    html = (tmp / "site/index.html").read_text()
    assert "Featured" in html and "A suggested paper" in html
    assert (tmp / "site/search.html").exists() and "IFT_LABELS" in (tmp / "site/search.html").read_text()
    items = json.loads((tmp / "site/items.json").read_text())
    assert items and all("week" in i for i in items)
    about = (tmp / "site/about.html").read_text()
    assert "sukuk" in about and "Casablanca Finance City".lower() in about.lower()
    print("\nOK — published", len(ptitles), "items; site at", tmp / "site")
    return tmp

if __name__ == "__main__":
    test_end_to_end()
