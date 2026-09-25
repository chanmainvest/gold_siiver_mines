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
