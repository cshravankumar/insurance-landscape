# Insurance Landscape

Five linked, sourced maps of the US property & casualty insurance market — who the participants are, how the work actually flows between them, and where insurtech capital went. Live site: **https://cshravankumar.github.io/insurance-landscape/**

| Page | What it is |
|---|---|
| [Market Map](pc-market-map.html) | Every participant type in the $1.05T US P&C market — carriers, reinsurers, brokers, wholesalers, MGAs, fronting carriers, claims/TPAs, and the periphery — named and sized, audited against canonical censuses (NAIC market share, Business Insurance Top 100, AM Best surplus lines, Conning MGA census, Gallagher Re fronting composite). |
| [Workflow Evidence Map](pc-workflow-map.html) | Six roles × 158 tasks with cited evidence (job postings, audit checklists, regulator handbooks, practitioner accounts), an automation grade per stage, and a ledger of reported AI deployments. |
| [Investor Graph](insurtech-graph.html) | 332 insurance startups × their investors, as a browsable directory with portfolio highlighting. |
| [Capital Flow](capital-flow.html) | Disclosed funding laid along the value chain the workflow map defines, plus investor concentration ("who doubled down"). |
| [Capital Timeline](capital-timeline.html) | The same data by year and tier, cross-filterable by investor, drillable to the company. |

The workflow map is the spine: its participants — retail broker → underwriter/MGA → policy in force → claims adjuster — are the categories every other page rolls up to.

## The data

- **`insurtech-dataset.json`** — one record per company: `name`, `url`, `what`, `workflow_step` (the fine-grained tag; the pages roll these up to value-chain tiers), `buyer`, `stage` (free-text funding history in a fixed format: `$XM Series Y, Mon YYYY (led by Z); $T total`), `investors`, and provenance: `funding_source` (the URL the figure came from), `funding_refreshed` (date it was verified) or `funding_as_of` (date the text was last written, if not yet verified), `status` (acquired / shut_down / public where known), `source` (which census pass added the record).
- **`census/`** — the exhibitor and directory lists the roster was audited against: ITC Vegas 2021–2026 (full floors for 2021, 2023–2026), ITC Asia/Japan/Europe 2026, InsurTech NY's NYC and Boston maps, InsurTech NY competition history, and sister-organization cohorts (InsurTech Hartford, Global Insurance Accelerator, gener8tor). `itc_company_index.json` gives first/last-seen years per company; `itc_attrition.json` lists who exhibited in 2023–24 but not 2025–26.
- **`FRESHNESS.md`** — the queue of funding news newer than each record, produced by the freshness probe (below). Nothing in it is verified until someone checks the primary source.

## Method, and what the numbers are not

**Rosters come from censuses, never from recall.** The market map was built by enumerating canonical rankings and then re-audited when a $1.5B MGA (Novacore) turned out to be missing. The startup dataset began as an investor-portfolio crawl and was then diffed against conference exhibitor lists — which is how ~120 companies the portfolio crawl couldn't see (bootstrapped, non-US, or funded outside the seed set) were found.

**Funding figures are money raised, as stated in public announcements.** The parser (`analysis/capital_parse.py`) excludes valuations, acquisition prices, and credit facilities — the first version didn't, and counted "$108M + $106M Series B1 at $2.6B valuation" as $2.6B; that bug inflated the total by $17.9B before it was caught. £/€ amounts are converted at flat approximate rates. Every figure with a `funding_source` was verified one company at a time against a primary source under a "null unless cited" rule; records without one carry the date their text was last written so staleness is visible. Totals are floors: a company that discloses nothing contributes $0.

**Each company's date is its latest known round**, not a full funding history — the timeline shows when the most recent money arrived, not every round.

**Provenance is on the page, one click down.** Each page uses the same disclosure pattern: the number or bar is always visible; a small "i" mark opens the caveat scoped to that figure; paragraph-length methodology sits in a collapsed note.

## Rebuilding

```bash
python3 analysis/rebuild_pages.py     # regenerates the three data-driven pages from insurtech-dataset.json
python3 analysis/freshness_probe.py   # checks Google News RSS for funding news newer than each record → FRESHNESS.md
```

To update a record: edit its `stage` text in the fixed format, set `funding_source` and `funding_refreshed`, run the rebuild, commit. `analysis/merge_refresh.py` merges structured research results (see the docstring for the schema).

## Limits worth knowing

- Coverage is US-centric and skewed toward companies visible at ITC, InsurTech NY, and in VC portfolios; a bootstrapped vendor that never exhibits can still be missing.
- ~60 records disclose no funding at all and ~40 state a figure without naming the round; both are shown as such rather than guessed.
- Name collisions are the most common error class (two "Covr"s, two "Kyber"s, "Assured" vs "Assured Allies"); each record's `url` is the disambiguator.
- Static pages, hand-maintained. Compiled Sept 2026.
