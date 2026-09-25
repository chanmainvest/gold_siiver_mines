---
name: miners-database
description: Rebuild the gold/silver miners mine-level database (spreadsheet + website) from company annual reports. Use when asked to update, rebuild, or extend the miners database, add a company or ETF, refresh financials, or regenerate the website.
---

# Miners Database — rebuild skill

This repo holds a mine-level database of gold & silver miners (and royalty/streaming
companies) held by precious-metals ETFs: per-mine ownership, grades, reserves,
production, cost structure, royalty/stream interests, ETF holdings, and company
financials. Everything is derived from published annual reports — no estimates.

## Repo layout

- `index.html` — the website (served by GitHub Pages). Fully self-contained,
  data embedded, no backend.
- `miners-mine-data.xlsx` — the built spreadsheet (10 sheets).
- `scripts/` — build & data-fetch scripts (run with `python3`).
- `data/companies/` — one `<TICKER>.json` per company: mine-level extraction.
- `data/portfolio/` — one `<TICKER>.json` per royalty/streaming company:
  full royalty/stream portfolio.
- `data/webapp/` — flattened `{"columns","rows"}` JSON per sheet; this is what
  `index.html` embeds.
- `data/etf/` — ETF holdings CSVs, methodology JSON, price snapshots
  (work-in-progress area for the ETF-expansion pass).
- `reports/` — **not committed**. Download annual reports yourself here,
  one folder per ticker (see `reports/README.md`).
- `docs/BUILD_NOTES.md` — sheet schemas, join keys, UI wiring notes.

## Full rebuild pipeline

1. **ETF holdings.** Download the current holdings list for each covered ETF
   (GDX, GDXJ, SIL, SILJ, GBUG, RING, AUAU, SGDM, SGDJ, GOAU, SLVP) from the
   issuer site (vaneck.com, ishares.com, globalxetfs.com, amplifyetfs.com,
   sprottetfs.com, usglobaletfs.com) or stockanalysis.com/etf as fallback.
   Save to `data/etf/holdings/<ETF>.csv`. Record source URL + as-of date.
2. **Diff tickers** against `data/companies/` to find new companies.
3. **Download annual reports** into `reports/<TICKER>/` (latest 10-K / 40-F /
   AIF; FY2025 preferred). See `reports/README.md` for sources.
4. **Extract** each report into `data/companies/<TICKER>.json` following the
   existing schema (copy the closest existing file as a template). Fields per
   mine: name, country, ownership %, type, status, annual gold/silver oz, head
   grades (g/t), reserve tonnes & oz, cash cost $/oz, AISC $/oz, capex, notes,
   report URL, fiscal year. **Never fabricate** — blank + note when undisclosed.
   For royalty/streamers also write `data/portfolio/<TICKER>.json` with every
   material interest: asset, operator, country, commodity, interest type
   (e.g. `2% NSR`, `25% silver stream`), attributable production, revenue.
5. **Financials.** `scripts/fetch_prices.py` pulls price/market-cap/shares-out
   (Yahoo Finance); `scripts/extract_fundamentals.py` reads revenue/EBITDA/debt/
   cash from the reports in `reports/`; `scripts/qa_fundamentals.py` sanity-checks.
6. **Build the spreadsheet:** `python3 scripts/build_spreadsheet.py`
   → writes `miners-mine-data.xlsx` (needs `pip install openpyxl`).
7. **Flatten for the web:** convert each sheet to `data/webapp/<sheet>.json`
   as `{"columns": [...], "rows": [...]}` (see `docs/BUILD_NOTES.md`).
8. **Rebuild the site:** regenerate `index.html` from `data/webapp/`
   (the page embeds the JSON; keep it a single self-contained file so GitHub
   Pages serves it with no backend). Then `git add -A && git commit`.

## Sheet join keys (for the ETF → miner → mine → royalty chain)

- `ETF Holdings.company_ticker` → `Companies` / `Mines` (by company)
- `Mines`: mine name + country → `Mine Links` → `Royalties & Streams`
- `Mine Links.mine_in_database` = No → royalty asset on a non-ETF operator's mine

## Conventions

- Units: oz (troy), g/t, USD. Flag any conversion (e.g. AUD costs, ZAR→USD).
- `null`/blank = not disclosed by the company. Note the basis of every cost
  figure (per Au oz / per Ag oz / per GEO).
- Every sheet row carries its source: report URL + fiscal year + extraction date.
