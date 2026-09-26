# AGENTS.md — gold_siiver_mines

Mine-level database of gold & silver miners (and royalty/streaming companies)
held by precious-metals ETFs, extracted from annual reports (10-K / 40-F / AIF).
Ships as a 10-sheet spreadsheet (`miners-mine-data.xlsx`) and a self-contained
website (`index.html`), served by GitHub Pages at
https://chanmainvest.github.io/gold_siiver_mines/.

> The repo name really is `gold_siiver_mines` ("siiver" typo). Do not rename it.

## Quick commands

- Build the spreadsheet: `python3 scripts/build_spreadsheet.py` → `miners-mine-data.xlsx`
  (needs `pip install openpyxl`)
- Flatten sheets for the web: see `docs/BUILD_NOTES.md` → `data/webapp/*.json`
  (`{"columns": [...], "rows": [...]}` per sheet)
- Regenerate the site: rebuild `index.html` from `data/webapp/` as a single
  self-contained file with the data embedded (no backend; GitHub Pages serves it)
- Geocode new/renamed mines: `python3 scripts/geocode_mines.py` (OpenStreetMap
  Nominatim; resumable via `data/geocode_cache.json`; throttled ~1 req/sec per
  Nominatim usage policy) → `python3 scripts/write_coords_csv.py` regenerates
  `data/mine_coordinates.csv` → re-run the spreadsheet build to bake in
  `latitude`/`longitude`

Full rebuild pipeline (ETF holdings → extraction → financials → build → site):
`skills/miners-database/SKILL.md`.

## Hard rules

- **Never fabricate data.** When a figure is undisclosed, leave it blank with a
  note. This is the project's core trust contract — an honest gap beats a
  filled-in estimate.
- `reports/` (annual-report PDFs) is intentionally **not committed**. Anyone
  must be able to download the reports themselves (sources in `reports/README.md`)
  and rebuild the whole thing from this repo.
- All scripts must use **repo-relative paths**
  (`REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))`).
  Never hardcode `/home/...` or any machine-specific path — a past build broke
  on exactly this and had to be repaired.
- `index.html` and `miners-mine-data.xlsx` are build artifacts: change the
  source data or pipeline scripts, then regenerate. Don't hand-edit the outputs.
- Push only to this repo, on `main`. GitHub Pages deploys from `main`.

## Known data gaps (documented, not filled)

- ETF small-cap tails partially unidentifiable from free sources
  (AUAU, SLVP, SIL, SILJ, GBUG).
- Empress Royalty (TSXV: EMPR) is a known omitted royalty company
  (publish-first decision, 2026-09-25).
- Mines with no confident geocode match get blank lat/lon; the map counts them
  instead of plotting them. Confidence levels (high/medium/low/none) live in
  `data/mine_coordinates.csv`.
- Financials: most companies have price/market-cap (Yahoo); only ~40 have full
  fundamentals extracted from reports.

## Verifying a rebuild

- Workbook has 10 sheets: Cover, Companies, Mines, Reserves & Resources,
  Cost Structure, Royalties & Streams, Mine Links, ETF Holdings,
  ETF Methodology, Company Financials.
- Mines sheet carries `latitude`/`longitude` columns; ~880 of ~1,340 mine rows
  have coordinates.
- Row counts should match the previous build within a handful of rows —
  investigate larger diffs before committing.
