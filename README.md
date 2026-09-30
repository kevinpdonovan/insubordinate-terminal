# Insubordinate Finance Terminal

A weekly sweep of new research, older scholarship, news and grey literature for the ERC project
**InsubordinateFINANCE** (the postcolonial politics of financial centres in the Global South).
It publishes a static website that links to the originals, plus an RSS feed that will drive the newsletter.

## How it works

```
 Monday 06:17 (UK)             You (≈15 min)                     Minutes later
┌──────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
│ Weekly harvest       │      │ Review issue on GitHub  │      │ Publish                 │
│ OpenAlex · GDELT ·   │ ───▶ │ untick the noise,       │ ───▶ │ site + RSS feed update; │
│ RSS feeds → gate →   │      │ add ★ to feature,       │      │ newsletter reads RSS    │
│ Claude tags + notes  │      │ close the issue         │      │ (phase 2)               │
└──────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
```

| Section | Where it comes from |
|---|---|
| New research | OpenAlex (open scholarly index): keyword queries, watched journals, watched authors; RePEc NEP feeds |
| From the archive | Works 10+ years old cited by this week's new research (OpenAlex citation graph); Zotero group library in phase 2 |
| News | GDELT global news index (65+ languages), regional outlets' RSS feeds, Bloomberg via GDELT and public feeds, and Google Alerts (RSS) |
| Reports & grey literature | IMF, BIS, World Bank, UNCTAD, AfDB, FSD Africa, CGD, ODI, Bretton Woods Project, Eurodad, OMFIF and others, via RSS |

Only metadata is collected: title, link, date, source and authors. Abstracts are used for tagging but never
published, and news text is never stored.

## The files you edit

| File | What it controls |
|---|---|
| `config/themes.yaml` | **The sweep profile**: project brief, themes and keywords, the 11 cities and their institutions, finance anchors, negative keywords, research and news queries, watched authors and journals, team |
| `config/sources.yaml` | Which feeds and indexes are swept, by section |
| `config/site.yaml` | Site title, public/unlisted, library proxy prefixes, newsletter link |
| `config/participants/*.yaml` | One file per team member, written by the *Update my research focus* form. It **adds** keywords, queries and authors to the profile |

To change what's swept, edit a YAML file on GitHub (pencil icon → *Commit changes*). The change applies at the next Monday run.
You can also ask Claude to make the edit.

## Team workflows (GitHub → Issues → New issue)

- **Suggest an item**: paste a link. It appears in the next published issue, credited to the suggester.
- **Update my research focus**: cities, keywords, search phrases, authors. These are merged into the sweep from the following Monday.

## One-time setup (about 30 minutes)

1. **GitHub account.** Create one at github.com. Academics can get GitHub Pro free via *GitHub Education*
   (Teacher benefits), which lets the site be served from a *private* repository. Without Pro, the
   repository must be public; the site is still hidden from search engines while `public: false`.
2. **Create the repository** `insubordinate-terminal`, and upload these files. Claude can push them for you
   if you create a fine-grained access token with *Contents*, *Issues*, *Workflows* and *Pages* permissions on that repository.
3. **Turn on Pages:** *Settings → Pages → Build and deployment → Source: GitHub Actions*.
4. **Add the key and settings:** *Settings → Secrets and variables → Actions*
   - Secret `ANTHROPIC_API_KEY`: create one at console.anthropic.com. Set a monthly spend limit (e.g. $10);
     expected use is roughly $1–3/month.
   - Variable `REVIEWER`: your GitHub username, so the review issue is assigned to you and you get an email.
   - Variable `CONTACT_EMAIL`: a project email, sent politely to OpenAlex and GDELT.
   - Optional secret `OPENALEX_API_KEY`: only if OpenAlex asks for one.
5. **First run:** *Actions → Weekly harvest → Run workflow*. When the review issue appears, tick or untick items and close it.
   Then set `base_url` in `config/site.yaml` to the Pages address GitHub shows you.
6. **Check `config/openalex_lock.yaml`** after the first run. Each watched author was matched automatically;
   fix any that point to the wrong person.
7. **Check the Source health page.** Feeds marked `# check` in `sources.yaml` couldn't be tested before launch.
   Fix or delete any that fail.

## Paywalled sources and logins

- **Don't put university credentials into the automation.** Publisher licences and university IT policy
  forbid systematic automated access. Discovery only needs metadata, which is open.
- **Library proxy:** readers choose their library in the site footer, and scholarly links are rewritten through
  that proxy (Edinburgh is preset; please verify the prefix with the library). Colleagues elsewhere can paste their own proxy prefix.
- **Bloomberg:** don't scrape it (terms of service). Bloomberg headlines arrive via GDELT and Bloomberg's public
  feeds. For saved searches, set up email alerts to a dedicated inbox; ingesting that inbox is a phase-2 add-on.
  Factiva/Nexis alerts through Edinburgh can use the same route.
- **Google Alerts** can be delivered as RSS (google.com/alerts → *Deliver to: RSS feed*). Paste those URLs into `sources.yaml`.

## Newsletter (phase 2)

`site/feed.xml` has one entry per weekly issue: the digest plus up to 15 links per section.
An RSS-to-email service (e.g. Buttondown) can send each new issue automatically. After that, set `newsletter_url` in `site.yaml`.

## Porting to another project

Use *Use this template* on GitHub to copy the repository. Then rewrite `themes.yaml` (Claude can draft it from the
new project's proposal) and `sources.yaml`. No code changes are needed.

## For developers

```
pip install -r requirements.txt
python -m terminal harvest        # writes data/runs/<week>/review.md
python -m terminal publish FILE   # publishes ticked items from an edited review body
python -m terminal build          # rebuilds site/
python tests/test_pipeline.py     # offline end-to-end test (mocked network)
```
