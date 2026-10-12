# Backlog: things to improve in later iterations

Running list, newest section first. Each item says what was observed and what would settle it, so
a later session can act without re-deriving the context. Tick things off here rather than in
CLAUDE.md, which should stay a description of how the system works now.

Last updated: 12 Oct 2026 (after the 2026-W42 run, the first with alerts and the quality rewrite live).

## Known broken, in priority order

1. **Eurodad returns 403 to GitHub.** `https://www.eurodad.org/news?format=rss` was restored on
   6 Oct after it returned 20 current items from a home connection, but GitHub's servers are
   refused. This is the same residential-versus-datacentre distinction that applies to the WFE and
   Bank Al-Maghrib, applied one source too late. Fix: add a Google Alert for Eurodad and drop the
   feed, as was done for the other five blocked sources.

2. **GDELT returns nothing.** Reduced on 12 Oct from 39 requests a day to 8, with no retry on a
   429 — but unverified, because this address was refused while testing. **Check the collector run
   after 13 Oct.** If still refused, the next move is Kevin emailing kalev.leetaru5@gmail.com, which
   GDELT's own refusal text invites, explaining the ERC project and asking for a larger allowance.
   Their official alternative is the bulk web-ngrams dataset, which is a disproportionate build for
   a weekly dashboard and should be a last resort.

3. **Email sources other than Google Alerts return zero.** With IMAP live, "Bloomberg alerts &
   newsletters" and "Google Scholar alerts" both returned 0 in W42. Either no such mail is arriving
   in the project inbox, or the Bloomberg `link_pattern` is wrong — CLAUDE.md has always flagged it
   as a guess. Settle it by looking in the inbox for a Bloomberg or Scholar email and comparing its
   links against the pattern. This is 2b item 5, still open.

4. **Sources that returned zero without failing** in W42: South African Reserve Bank, FSC Mauritius,
   Boston University GDP Center, AfronomicsLaw, Developing Economics. A quiet week is plausible for
   all five, so check across two or three runs before touching them — a zero that is not a failure
   is not yet evidence of a fault.

## Worth improving

5. **Zenodo items show as "Zenodo (CERN European Organization for Nuclear Research)"**, which reads
   as though CERN published them. They are self-deposits with no journal version anywhere — checked
   against OpenAlex, where every location is Zenodo — so there is no truer source to show. Shorten
   the display to "Zenodo". Separately, decide whether repository-only items belong under New
   research at all, or should be routed to grey literature. They already carry no quality signal
   and are not pre-ticked, so this is presentation, not filtering.

6. **A Facebook link reached the news list** in W42 (unticked). Consider excluding social-media
   domains from news outright.

7. **Google Alerts bypass the keyword gate** (`filter: false` in sources.yaml). W42 numbers: 56 alert
   items reached Claude, 22% of the tagging load; 23 rated >=2 and 33 rated 0 or 1. So roughly 59%
   of alert tagging is spent on items that are then discarded — about 33 Haiku items a week, which
   is small in absolute terms. Kevin has no strong view and asked to be shown this again. Revisit if
   alert volume grows materially, and prefer evidence from a later run over a single week.

8. **Scheduled runs land about seven hours late.** The Monday harvest is set for 05:17 UTC and ran at
   12:14 on 5 Oct and 13:06 on 12 Oct; the daily collector is set for 04:41 and lands around 11:00.
   Nothing is broken, but the review issue arrives mid-afternoon UK time rather than first thing.
   If that matters, move the cron earlier rather than treating a missing morning run as a fault.

9. **Test coverage gaps.** The offline suite now covers the GDELT backoff, the refusal breaker and
   the empty-cache fallback. Still uncovered: IMAP email parsing, the quality-signal scoring, and the
   OpenAlex `institutions` mode. The quality model in particular changed how every scholarly item is
   judged and has no test.

10. **Only three of the blocked organisations are reachable through OpenAlex** (ODI, CGD, AfDB).
    UNCTAD and Eurodad have nothing indexed there, so alerts are their only route.

## Watch, no action yet

11. **The quality threshold.** Scholarship needs 2 signal points to pre-tick. In W42 this gave 13 of
    35 research pre-ticked and the "no quality signal" flag never appeared, which may mean the
    listing cap hides the weakest items rather than that none were weak. Worth confirming the flag
    can actually appear.

12. **News balance.** The W41 complaint was zero news; W42 gave 28 listed and 13 published. Watch
    whether the looser gate now over-corrects. The levers are unchanged: `themes.yaml > countries`
    and `finance_anchors`, `MIN_SHOWN` and `PRETICK` in `review.py`.

13. **World Bank is on API v3.** v2 is frozen — its newest indexed document is 2025-03-12 — so if
    results stop again, check whether v3 has been superseded rather than assuming the lookback.

14. **`max_messages: 500`** on the Google Alerts email source covers 52 alerts a day across an
    8-day window (~416 messages). If the alert count grows past about 60 a day, raise it.
