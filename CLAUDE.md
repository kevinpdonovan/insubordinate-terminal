# CLAUDE.md: Insubordinate Finance: The Terminal

Context for Claude when working in this repository. Read it first.

## What this is
A weekly research dashboard for the ERC project **InsubordinateFINANCE** (PI J. Christopher Mizes, IRD; Kevin Donovan, University of Edinburgh, is AR1 for Nairobi and runs this dashboard). The project asks whether financial centres in the Global South are vectors of financial subordination or offer independence from Northern financial dominance. It covers 11 case-study cities: São Paulo, Santiago, Montevideo, Casablanca, Abidjan, Nairobi, Johannesburg, Port Louis, Mumbai, Bangkok and Ho Chi Minh City.

Every Monday a GitHub Action sweeps sources, filters and de-duplicates them, has Claude (Haiku) tag them, and opens a **review issue** with tick-boxes. Kevin ticks or stars items and closes the issue, which publishes a static site to GitHub Pages and an RSS feed (the future newsletter source).

Write for a researcher, not a developer: explain changes and their trade-offs in plain language, naming the mechanism rather than the code. Honest disagreement and academic rigour are wanted; agreement for its own sake is not.

## Layout
- `config/themes.yaml`: **the sweep profile**. Themes and keywords, cities and aliases, `countries` (count as places for news and grey literature only), finance anchors, negative keywords, research, news and grey queries, watched authors, journals and series, `quality` rules, team.
- `config/sources.yaml`: `news_outlets` allowlist (ranked) plus sources by section: openalex, gdelt, rss, worldbank, pagewatch, email.
- `config/site.yaml`: title and base_url (Kevin edits this one; never overwrite it wholesale).
- `config/participants/*.yaml`: written by the "Update my research focus" issue form.
- `terminal/`:
  - `harvesters.py`: all fetching, with `get_with_backoff` for 429s
  - `dedupe.py`: work keys, news clustering
  - `quality.py`: venue levels, outlet allowlist
  - `relevance.py`: the keyword gate
  - `tagger.py`: Claude relevance 0–3, quality 0–2, note, digest
  - `review.py`: issue body, pre-tick rules, parse ticks
  - `build.py`: static site
  - `cli.py`: commands `harvest`, `publish`, `build`, `suggest`, `focus`, `collect-news`
- `templates/`, `static/`: site (pages: this week, past issues, search, themes & sources, source health).
- `.github/workflows/`:
  - `weekly-harvest.yml`: Mon 05:17 UTC
  - `publish.yml`: on review-issue close
  - `pages.yml`: rebuild on push
  - `forms.yml`: issue forms
  - `news-daily.yml`: daily GDELT collector into `data/news_cache/`
- `data/`: run outputs, committed by the bot. Includes `runs/<week>/candidates.json` and `review.md`, `issues/<week>.json` (published), `health.json` (per-source status, **read this first when diagnosing**), `seen.json`, `venues.json`, `pagewatch/`, `news_cache/`.
- `tests/test_pipeline.py`: offline end-to-end test with every network call mocked. **Run `python tests/test_pipeline.py` after any change.**

## Rules and decisions
- No university credentials in automation. Link only, never republish text. Respect robots.txt (hence no Google News RSS).
- **No paid add-ons** (no Claude web-search pass, no Overton). The free OpenAlex key (`OPENALEX_API_KEY`) is set.
- **The h-index must not be a hard gate.** Kevin considers it a poor measure; it also biases against Southern and non-English venues.
- Don't re-run the weekly harvest mid-week. It marks items as seen, so they vanish from the next Monday issue. `collect-news` is safe to run any time.
- Pushes made by the bot (GITHUB_TOKEN) don't trigger other workflows, so `publish.yml` deploys Pages itself.
- Secrets: `ANTHROPIC_API_KEY`, `OPENALEX_API_KEY`, `IMAP_USER` / `IMAP_PASSWORD` (alerts inbox insubordinatefinanceterminal@gmail.com; may not be set yet). Variables: `REVIEWER` (kevinpdonovan), `CONTACT_EMAIL`, `TAGGER_MODEL`.

## Status (5 Oct 2026)
- Update 1 is live. **Update 2a is applied** (5 Oct, via GitHub Desktop): news gate rebalanced with country names, daily GDELT collector (`.github/workflows/news-daily.yml`), OpenAlex backoff and cap 25, looser archive gate, 6 dead news feeds removed, World Bank lookback 45 days.
- **Caveat on 2a's test coverage.** `tests/test_pipeline.py` passes, but it contains only `test_end_to_end`, and 2a's change to it was limited to loosening one news-gate assertion. The 429 backoff (`get_with_backoff`), the `data/news_cache/` read/write and the `collect-news` command have **no offline coverage**. Treat the first scheduled runs as the real test: check `data/health.json` and whether `data/news_cache/` is filling.
- **47 Google Alerts** exist in the project Gmail (16 places and institutions, 31 concepts from
  the ERC proposal). They are listed with their settings in `docs/google-alerts.md`, which is the
  source of truth; the README points there rather than repeating the table. They reach the
  dashboard only once `IMAP_USER` / `IMAP_PASSWORD` are set. The email source reads `INBOX` only,
  so do not add a Gmail filter that archives the alerts or skips the inbox.

## To do (Update 2b)
1. Move "From the archive" to the right-hand column (left: New research; right: News, Reports, From the archive; confirm the order with Kevin).
2. Finish the rebrand to "Insubordinate Finance: The Terminal": README, `themes.yaml → project.name`, review-issue wording (`site.yaml` is already done).
3. Replace h-index gating with multi-signal "likely quality" pre-ticking:
   - Positive signals: trusted/watched venues; reputable publishers including francophone and lusophone presses; curated indexes (SciELO, OpenEdition, Cairn, Érudit, Redalyc, AJOL, ERIH PLUS, DOAJ Seal); Claude quality 2; watched or team authors; peer-reviewed type.
   - Never drop on bibliometrics; flag and leave unticked instead. Show the reasons in the review issue.
4. Grey literature: fix the 404 feed URLs (BIS, ODI, Finance in Common, AfDB); drop sources that return 403 to GitHub (IMF, UNCTAD, CGD, Eurodad, JSE, WFE, Bank Al-Maghrib); fix or remove the failing page watchers (CMA Kenya, VIFC, CMF Chile, Long Finance, FSD Africa); debug the World Bank API if it is still 0.
5. Once the inbox is live, check the email sources (the Bloomberg link pattern is a guess).
6. Later: newsletter via Buttondown RSS-to-email; Zotero group library for the archive section; decide whether Bloomberg headlines stay team-only once the site is public.
