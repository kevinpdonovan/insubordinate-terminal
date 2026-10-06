# Google Alerts: Insubordinate Finance: The Terminal

Account: insubordinatefinanceterminal@gmail.com · 47 alerts · all delivered by email, "at most once a day".
"all" = *All results*; "best" = *Only the best results*. In Google's syntax, OR groups bind before the implied AND, so `A OR B C OR D` means (A or B) and (C or D).
Alerts reach the dashboard once the `IMAP_USER` / `IMAP_PASSWORD` GitHub secrets are set.

**This file is the source of truth for the alert list.** The README points here rather than
duplicating the table, which is how the earlier 16-alert copy went stale. Alerts are created and
edited by hand at google.com/alerts while signed in as the project account; record changes here.

## Set 1: places and institutions (created 5 Oct 2026)

| Query | Results | Language |
|---|---|---|
| `"Nairobi International Financial Centre"` | all | EN |
| `"Casablanca Finance City"` | all | EN |
| `"Vietnam International Financial Centre" OR "Vietnam International Financial Center"` | all | EN |
| `"GIFT City" IFSC` | all | EN |
| `"Mauritius International Financial Centre" OR "Mauritius financial centre" OR "Mauritius IFC"` | all | EN |
| `"African Credit Rating Agency" OR AfCRA` | all | EN |
| `"African Exchanges Linkage" OR "African Securities Exchanges Association"` | all | EN |
| `"Nairobi Securities Exchange" OR "Capital Markets Authority" Kenya` | all | EN |
| `sukuk Morocco OR Kenya OR Senegal OR Nigeria OR "Ivory Coast" OR Mauritius` | best | EN |
| `"Africa Financial Industry Summit" OR "Africa Financial Summit" OR "Africa CEO Forum" OR "Africa Debt Forum"` (corrected 5 Oct) | all | EN |
| `Eurobond Kenya OR "Ivory Coast" OR Senegal OR Morocco OR Nigeria OR Ghana` | best | EN |
| `site:imf.org Kenya OR Morocco OR "Cote d'Ivoire" OR Mauritius OR "South Africa" OR Vietnam "financial sector"` | all | EN |
| `"frontier market" MSCI OR "FTSE Russell" reclassification OR upgrade` | best | EN |
| `BRVM` | best | any |
| `"place financière" Abidjan OR Casablanca OR Maurice OR Dakar` | all | any |
| `"centro financeiro" OR "mercado de capitais" "Faria Lima" OR "São Paulo" OR B3` | best | any |

## Set 2: concepts from the ERC proposal (created 5 Oct 2026)

Proposal concept in brackets. ➕ = extension beyond the proposal's own wording.

| Query | Results |
|---|---|
| `"financial subordination" OR "subordinate financialization" OR "subordinated financialisation"` (subordination) | all |
| `"Wall Street Consensus"` (subordination) | all |
| `"monetary sovereignty" OR "financial sovereignty" Africa OR "Global South"` ➕ | all |
| `"currency hierarchy" OR "monetary hierarchy"` ➕ | all |
| `"sovereign debt" Africa OR "emerging markets" OR "Global South"` (sovereign debt) | best |
| `"debt restructuring" OR "sovereign default" Ghana OR Zambia OR Kenya OR Ethiopia OR Senegal` ➕ | best |
| `"non-resident holdings" OR "foreign holdings" "government securities" OR "local currency bonds"` ➕ (who holds the debt) | all |
| `"domestic debt market" OR "local currency debt" Africa` (sovereign debt) | all |
| `"sovereign credit rating" OR "sovereign rating" Africa OR Kenya OR Nigeria OR Ghana OR Morocco OR Senegal OR "South Africa"` (valuation) | best |
| `"municipal credit rating" OR "subnational credit rating" OR "city credit rating" OR "subnational rating" Africa OR Senegal OR Kenya OR "South Africa" OR Morocco OR India OR Brazil OR Vietnam` (urban politics of ratings) | all |
| `"rating agencies" OR "credit rating agencies" bias OR "African premium" OR "perception premium" Africa` ➕ (rating disputes) | all |
| `"yield curve" Kenya OR Nigeria OR "Cote d'Ivoire" OR Ghana OR Morocco OR UEMOA OR Mauritius` (valuation devices) | all |
| `"index inclusion" OR "bond index" OR "GBI-EM" "local currency" Africa OR India OR Vietnam OR Nigeria OR Kenya OR Egypt OR Brazil` (benchmark indices) | all |
| `"cross-listing" OR "dual listing" OR "cross-listed" Africa OR "emerging markets" OR Nairobi OR Johannesburg OR Casablanca OR BRVM` (integration) | all |
| `"capital market integration" OR "regional capital market" OR "capital markets integration" Africa OR ASEAN OR "Latin America" OR "Pacific Alliance"` (integration) | all |
| `FATF "grey list" OR "gray list" OR greylist Kenya OR Nigeria OR "South Africa" OR Senegal OR Morocco OR Mauritius OR Vietnam` ➕ (regulation) | best |
| `"systemic risk" OR "financial stability report" "central bank" Kenya OR Morocco OR Mauritius OR "South Africa" OR BCEAO OR Thailand OR Vietnam` (regulation) | best |
| `"financial deepening" OR "capital market deepening" OR "financial sector deepening"` (deepening) | all |
| `"capital market development" OR "capital markets development" Africa OR Asia OR "Latin America"` (deepening) | all |
| `"Global Financial Centres Index" OR GFCI` (centres) | all |
| `"international financial centre" OR "international financial center" OR "financial hub" Africa OR "Global South" OR Kigali OR Lagos OR Accra OR "Abu Dhabi" OR Astana` (centres) | best |
| `"offshore financial centre" OR "offshore financial center" OR "offshore finance" Africa OR Mauritius OR Seychelles OR Kenya` (offshore) | all |
| `"decolonising finance" OR "decolonizing finance" OR "decolonial finance" OR "decolonise finance" OR "decolonize finance"` ➕ | all |
| `"popular shareholding" OR "retail investors" OR "retail investor" IPO Nairobi OR BRVM OR Johannesburg OR Casablanca OR Mauritius OR Vietnam` (popular shareholding) | all |
| `"financial independence" OR "economic independence" Africa "stock exchange" OR "capital markets" OR "financial centre"` (independence) | all |
| `"African bankers" OR "African financiers" OR "African asset managers" OR "African investment bankers" OR "African fund managers"` (professionals) | all |
| `"South-South" finance OR investment OR "capital markets" OR "financial centre" OR "financial cooperation"` (South–South networks) | best |
| `"de-risking" OR derisking OR "blended finance" "private capital" OR "private investment" Africa OR "emerging markets"` (Wall Street Consensus) | best |
| `"impact investing" OR "impact investment" Africa OR "emerging markets" "capital markets" OR "stock exchange" OR "pension funds"` (impact investing) | best |
| `"municipal bond" OR "municipal bonds" OR "city bond" Africa OR Senegal OR Dakar OR Kenya OR "South Africa" OR Morocco OR India OR Brazil` (municipal finance) | all |
| `securitisation OR securitization OR "mortgage refinance" housing OR mortgage Africa OR "emerging markets" OR Kenya OR Senegal OR Morocco` (securitisation/housing) | best |

## Still to create: cover for dropped sources (6 Oct)

Nine sources were removed from `sources.yaml` after the W41 run. Four were recovered in code:
ODI, CGD and the AfDB now come through OpenAlex by institution (`themes.yaml → watch_institutions`),
and Eurodad's feed was simply at the wrong URL.

The remaining five cannot be reached from GitHub Actions at all. UNCTAD and the JSE refuse every
request; the WFE and Bank Al-Maghrib answer a home connection but refuse GitHub's servers, which is
a datacentre-address block that no setting on our side changes; Finance in Common renders its
listing in JavaScript, so there is nothing for a page watcher to read. Alerts are the way back in —
create these at google.com/alerts signed in as the project account, then record them above.

| Query | Results | Covers |
|---|---|---|
| `site:unctad.org ("sovereign debt" OR "capital markets" OR "financial centre" OR "debt sustainability")` | all | UNCTAD |
| `"Johannesburg Stock Exchange" (listing OR delisting OR reform OR regulation)` | all | JSE |
| `"World Federation of Exchanges"` | all | WFE |
| `"Bank Al-Maghrib" OR "Banque centrale du Maroc"` | all | Bank Al-Maghrib |
| `"Finance in Common" OR "public development banks"` | best | Finance in Common |

## Tuning

After 2–3 weeks of email, check which alerts produce mostly noise (likely candidates:
"financial independence", "systemic risk", "sovereign debt", "de-risking") and either tighten
them or switch them to "best". Edit them at google.com/alerts while signed in to the project
account.

## Relation to themes.yaml

These alerts reach the dashboard as email, through IMAP — they do not need query entries in
`config/themes.yaml` to work. What they need is the `IMAP_USER` / `IMAP_PASSWORD` secrets.

Two related config notes:

- The Google Alerts email source sets `max_messages: 500` in `config/sources.yaml`. At 47 alerts
  delivered daily, an 8-day harvest window holds roughly 376 alert emails; the default cap of 60
  would read only the most recent day and ignore the rest of the week.
- Nine report-shaped concepts from Set 2 were added to `grey_queries` (6 Oct 2026), which feeds the
  OpenAlex reports query and the World Bank API behind the Reports section. `research_queries` was
  left as it was — the scholarly list already covers these concepts, and the alerts are aimed at
  the news and grey literature sections rather than at scholarship.
