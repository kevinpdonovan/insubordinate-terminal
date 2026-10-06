# Insubordinate Finance: The Terminal

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
| New research | OpenAlex (open scholarly index): keyword queries in English, French, Portuguese and Spanish, plus watched journals and watched authors; Google Scholar alerts by email |
| From the archive | Works 10+ years old cited by this week's new research (OpenAlex citation graph) |
| News | GDELT global news index, **restricted to an allowlist of quality outlets**; regional outlets' RSS feeds; **your own Bloomberg alerts and Google Alerts by email** |
| Reports & grey literature | World Bank Documents & Reports database; OpenAlex reports and IFI working-paper series (IMF, BIS, World Bank); **watched publication pages** of central banks, regulators and exchanges; think-tank RSS feeds |

**Quality controls:**

- **Duplicates.** Preprint, repository and journal versions of the same work are merged (the journal version is kept). Syndicated copies of a news story are clustered (the best outlet is kept). Nothing shown in an earlier week reappears, even under a new link.
- **Venues.** Journals are graded by OpenAlex h-index. Watched journals are trusted, deny-listed venues and publishers are dropped (edit the lists in `themes.yaml → quality`), and low-signal venues are flagged ⚠ in the review issue and never pre-ticked.
- **Claude** rates relevance 0–3 and, for scholarship, substance 0–2. News is only pre-ticked at relevance 3.

Only metadata is collected: title, link, date, source and authors. Abstracts are used for tagging but never
published, and news text is never stored.

## The website

The site has four pages. **This week** shows the latest issue, with filters. **Past issues** lists every week, each kept permanently. **Search** covers every item ever published, filterable by section, city, theme and date. **Themes & sources** lists everything the sweep looks for.

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

## Email alerts (Bloomberg, Google Scholar, Google Alerts)

Your own alerts are the best-quality inputs, and the sweep can read them from a dedicated inbox. Setup takes about 15 minutes:

1. **Create a Gmail account just for this**, e.g. `insubordinate.terminal@gmail.com`. Don't use your personal inbox: the automation can read everything in it.
2. In that account, turn on **2-Step Verification** (Google Account → Security), then create an **App password** (Security → App passwords). Copy the 16-character password.
3. In GitHub → **Settings → Secrets and variables → Actions** add two **secrets**: `IMAP_USER` (the Gmail address) and `IMAP_PASSWORD` (the app password).
4. Point alerts at that address:
   - **Google Scholar:** scholar.google.com → Alerts → create alerts for key phrases and authors, delivered to the project address.
   - **Google Alerts:** google.com/alerts, signed in as the project account → one alert per query (e.g. `"Nairobi International Financial Centre"`, `"Casablanca Finance City"`, `BRVM`, `"African Credit Rating Agency"`, `sukuk Morocco`) → *How often: at most once a day*, *Deliver to: the project address*.
   - **Bloomberg:** set up saved-search alerts and newsletters in your Bloomberg account, then in your own mail add a filter that **forwards** Bloomberg alert emails to the project address. Only headlines and links are extracted; no article text is stored.

The Source health page shows "not configured" for these until the secrets exist.

## Google Alerts in use

**47 alerts** are live in the project account (insubordinatefinanceterminal@gmail.com), all
delivered at most once a day: 16 for places and institutions, 31 for concepts drawn from the ERC
proposal.

The full list, with each query's settings and the reasoning behind it, is in
**[`docs/google-alerts.md`](docs/google-alerts.md)** — that file is the source of truth. It is not
duplicated here: an earlier copy of the table in this README listed only the first 16 and drifted
out of date.

Alerts only reach the dashboard once the inbox secrets (`IMAP_USER`, `IMAP_PASSWORD`) are set. See
"Email alerts" above. Until then they collect in the Gmail inbox, which is still worth skimming.

To add or edit one, go to google.com/alerts signed in as the project account, then record the
change in `docs/google-alerts.md`.

## GDELT (global news index)

GDELT limits how often any one internet address may query it, and GitHub's servers are shared, so one big weekly burst of about 30 queries got refused. The **Daily news collector** workflow (`.github/workflows/news-daily.yml`) instead asks GDELT about the *past day* every morning, spaced 10 seconds apart. It waits and retries when refused, gives up for the day after three refusals in a row, and saves the results to `data/news_cache/`. The Monday harvest reads the week's cache, and only calls GDELT live if the cache is empty.

## Watched publication pages

`sources.yaml` lists central-bank, regulator and exchange pages under `type: pagewatch`. Each week the sweep notes links that are **new** since last week (the first run only records a baseline). Pages that build their content with JavaScript can't be read this way. They'll show as failing on the Source health page, and it's best to delete them.

## Paywalled sources and logins

- **Don't put university credentials into the automation.** Publisher licences and university IT policy
  forbid systematic automated access. Discovery only needs metadata, which is open.
- **Library proxy:** readers choose their library in the site footer, and scholarly links are rewritten through
  that proxy (Edinburgh is preset; please verify the prefix with the library). Colleagues elsewhere can paste their own proxy prefix.
- **Bloomberg:** don't scrape it (terms of service). Headlines arrive via GDELT, and your own alerts come by email (see above).
  Factiva/Nexis alerts through Edinburgh can use the same route; add a matching `type: email` entry in `sources.yaml`.
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
