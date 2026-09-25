# gold_siiver_mines

A mine-level database of publicly traded **gold and silver mining companies**
(plus gold/silver **royalty & streaming** companies) held by precious-metals
ETFs — built entirely from published annual reports.

🌐 **Browse the data:** https://chanmainvest.github.io/gold_siiver_mines/

## What's inside

| Sheet | Contents |
|---|---|
| Companies | 200+ miners: tickers, exchanges, HQ, fiscal year, report source URLs, consolidated production |
| Mines | 1,300+ mine/asset rows: ownership, country, type, status, annual gold/silver production, head grades, reserves, cash costs, AISC |
| Reserves & Resources | Proven/probable reserves and measured/indicated resources by mine |
| Cost Structure | Cash costs, AISC, sustaining/growth capex per mine (basis flagged per row) |
| Royalties & Streams | 660+ royalty/stream interests: asset, operator, interest type (NSR %, stream terms), attributable production |
| Mine Links | Mine ↔ royalty/stream holder relationship map |
| ETF Holdings | ETF-to-miner mapping with weights and as-of dates |
| ETF Holdings | ETF-to-miner mapping (549 rows) with weights and as-of dates |
| ETF Methodology | Prospectus-based comparison: index, selection rules, weighting/capping, rebalance, expense ratio |
| Company Financials | Price, market cap, shares outstanding, revenue, EBITDA, debt, cash |
| Cover | Methodology, sources, and caveats |

Covered ETFs: **GDX, GDXJ, SIL, SILJ, GBUG, RING, AUAU, SGDM, SGDJ, GOAU, SLVP**
(+ SLJY noted as Amplify's covered-call overlay on SILJ). Royalty/streamers:
Royal Gold, Franco-Nevada, Wheaton, Osisko Gold Royalties, Triple Flag,
Sandstorm, Gold Royalty, Metalla, Vox, Elemental Altus, EMX, Orogen, Altius,
Versamet, Sailfish, LunR.

**Nothing is estimated.** Blank = not disclosed by the company. Cost bases
(per Au oz / per Ag oz / per GEO) and currency conversions are flagged per row.

## Rebuild it yourself

Annual reports are **not** committed (download your own — see
[`reports/README.md`](reports/README.md)), but everything derived from them is.
With the reports in `reports/<TICKER>/`:

```bash
pip install openpyxl
python3 scripts/build_spreadsheet.py   # → miners-mine-data.xlsx
```

Then flatten the sheets to `data/webapp/*.json` (`{"columns","rows"}` format,
see [`docs/BUILD_NOTES.md`](docs/BUILD_NOTES.md)) and regenerate `index.html`
with the JSON embedded — the site is a single self-contained file with no
backend, served by GitHub Pages.

The full pipeline (ETF holdings → reports → extraction → financials → build)
is documented as a reusable skill in
[`skills/miners-database/SKILL.md`](skills/miners-database/SKILL.md).

## Data as of

- Mine data: FY2025 annual reports (a few FY2024/FY2026 where noted on Cover)
- ETF holdings: September 2025 (see Cover for per-ETF as-of dates)
- Financials: prices as marked per row in Company Financials

## License

Data is extracted from company public filings (facts, no copyrightable
expression added). Code and site are MIT — see [LICENSE](LICENSE).
