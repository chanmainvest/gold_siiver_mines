# Web-app data — royalty/streaming expansion (built 2026-09-25)

## New data files
- `royalties_streams.json` — 662 rows. One row per material royalty/stream interest held by the 16 US/Canada-listed royalty & streaming companies. Columns: Royalty Company, Ticker, Asset / Mine, Operator, Country, Commodity, Interest Type, Interest Detail, Attributable Production, Production Unit, Revenue (USD), Effective Date, Notes. Blank = not disclosed by the company (never estimated).
- `mine_links.json` — 662 rows. The mine↔royalty-holder relationship map. Columns: Mine, Mine Operator (Owner), Country, Royalty/Stream Holder, Holder Ticker, Interest Summary, Mine In Database.

All files keep the existing `{"columns": [...], "rows": [...]}` format. The original five files were regenerated from the rebuilt workbook.

## Relationship join keys (for the web-app builder)
1. **Mine detail view → "royalty/stream holders"**: join `mine_links.json` → `Mines` on mine name + country. The `Mine In Database` column = "Yes" for 140 links whose mine also appears in the Mines sheet (140/662); those joins are exact (name spellings were harmonized during extraction). For "No" links, the mine belongs to a non-ETF operator — still show the holder, operator name, country, and interest summary, but there is no Mines-sheet row to link to.
2. **Royalty company view → "portfolio"**: `royalties_streams.json` rows filtered by Ticker; `mine_links.json` rows filtered by Holder Ticker. The 16 holder tickers: RGLD, FNV, WPM, OR, TFPM, SAND, GROY, MTA, VOXR, ELE, EMX, OGN, ALS.TO, VMET, LUNR, FISH.
3. **Company detail pages**: royalty companies already exist in `companies.json` with attributable GEO/oz production and royalty revenue in their notes — reuse the existing company view, and add a "Royalty & Stream Portfolio" section driven by `royalties_streams.json` (per-interest revenue, attributable production, interest terms).

## Suggested UI additions
- On each mine's detail drawer/page: a "Royalty & Stream Holders" section listing holders, interest type/detail (from Mine Links → Interest Summary).
- On each royalty company's page: a full portfolio table (from Royalties & Streams) with columns Asset, Operator, Country, Interest Type/Detail, Attributable Production, Revenue.
- A new top-level "Royalties & Streams" tab: filterable table of all 662 interests (filter by holder, country, commodity, interest type, mine-in-database flag).

## Caveats to surface in the app
- SAND (Sandstorm): acquired by Royal Gold Oct 20, 2025 and delisted — its data is FY2024 (no FY2025 report exists).
- EMX: merged into Elemental Altus (ELE) Nov 2025 — kept as a historical FY2024 record; its assets now live under ELE.
- ALS.TO (Altius): only precious-metals royalties included (company is diversified; other segments excluded by design).
- LUNR's Fruta del Norte silver stream was acquired in 2026 (post FY2025).
- Revenue and attributable ounces are shown only where disclosed; exploration-stage long tails of junior royaltycos are grouped rows flagged in Notes.

---

# Expansion 2 — 12-ETF coverage, ETF↔miner mapping, methodology comparison, company financials (built 2026-09-25)

## New data files
- `etf_holdings.json` — 549 rows. One row per ETF↔company pair: ETF, ETF Name, Company, Company Ticker, Weight %, As Of, Holdings Source. Covers all 12 ETFs: GDX, GDXJ, SIL, SILJ, GBUG, RING, AUAU, SGDM, SGDJ, GOAU, SLVP, SLJY. (The SLJY row that is the SILJ fund itself was excluded — not a company.)
- `etf_methodology.json` — 12 rows. Per-ETF construction comparison from prospectuses (SEC 497K filings + issuer PDFs): ETF Ticker, ETF Name, Issuer, Index Tracked, Selection Criteria, Weighting Scheme, Rebalance Frequency, Expense Ratio, Inception Date, AUM (USD), AUM As Of, Num Holdings, Notes. Includes construction corrections: AUAU is a Global X product (not Goldman Sachs) tracking the NYSE Arca Gold Miners Index (same as GDX); SLJY is an Amplify (not YieldMax) covered-call fund; GOAU is now actively managed (dropped its index); SILJ switched from MSCI to the Nasdaq Junior Silver Miners Index in Jan 2026.
- `company_financials.json` — 209 rows. Per company: Ticker, Company, Price (USD), Price As Of, Market Cap (USD), Shares Outstanding, Revenue (USD), EBITDA (USD), Net Income (USD), Total Debt (USD), Cash (USD), Net Debt (USD), Fiscal Year, Financial Source, Notes. Prices observed 2026-09-25 (Yahoo Finance v8; PSE:PX from stockanalysis.com; PLZL sanctioned — no quote). Market cap = price × shares (computed). Fundamentals from annual-report financial statements, converted to USD. Blank = undisclosed/unobtainable, never estimated. Coverage: 190/209 with price, 40/209 with revenue.

All files keep the existing `{"columns","rows"}` format. The original seven files were regenerated from the rebuilt workbook (10 sheets). Total embedded payload is ~2.3MB.

## Relationship join keys
1. **ETF → Miner → Mine → Royalty holder chain** (the headline new view):
   - `etf_holdings.json` (Company Ticker) → `companies.json` (Tickers) / `mines.json` (Company): every ETF↔miner pair with weight %.
   - `mines.json` (Company + Mine + Country) → `mine_links.json` (Mine + Country): royalty/stream holders per mine.
   - `mine_links.json` (Holder Ticker) → `royalties_streams.json` (Ticker): the holder's portfolio interest behind each link.
2. **ETF detail view**: `etf_holdings.json` filtered by ETF + `etf_methodology.json` row for that ETF (construction, expense, AUM, selection criteria).
3. **Company financials panel**: `company_financials.json` row keyed by Ticker (= `companies.json` Tickers stem).

## Suggested UI additions
- **Clickable sortable column headers on every table** (the user explicitly asked for this): click a header to sort ascending, click again for descending. Apply to all tabs.
- An **ETF detail view**: holdings table (company, weight %) + methodology card (index, selection criteria, weighting, rebalance, expense ratio, inception, AUM).
- A **company financials panel** on each company view: price, market cap, revenue, EBITDA, net income, debt, cash, net debt, with as-of dates and source notes; show "not disclosed" for blanks.
- An **"ETF → Miner → Mine → Royalty holder" chain explorer**: start from an ETF, drill into a holding, see its mines, and each mine's royalty/stream holders.

## Caveats to surface in the app
- Holdings weights and AUM are as of the dates shown per row; holdings change daily.
- AUAU and SLVP: only top-25 holdings identifiable from free sources (tails unavailable); SIL/SILJ/GBUG small-cap tails partially unidentified (pre-existing caveat).
- Financials: fundamentals coverage is thin for juniors (many disclose no usable statements); EBITDA column sometimes holds operating income — flagged per row in Notes.
- PLZL (Polyus): sanctioned — no quote, no accessible report; stub record only.
- SLJY is an option-income fund (~24% SILJ shares + direct equities + SLV calls + T-bills); its "holdings" are not a pure equity portfolio.
