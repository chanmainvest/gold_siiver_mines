# Annual reports — download your own

The downloaded annual reports (10-K, 40-F, AIF, annual report PDFs) are **not**
committed to this repo. Download them yourself into this folder, one
subdirectory per company ticker:

```
reports/
  NEM/      Newmont 2025 10-K.pdf
  PAAS/     Pan American Silver 2025 annual report.pdf
  ...
```

Where to get them:

- **US-listed companies** — SEC EDGAR: https://www.sec.gov/cgi-bin/browse-edgar
  (10-K filings, free)
- **Canadian companies** — SEDAR+: https://www.sedarplus.ca
  (40-F / AIF filings, free)
- **Australian / UK / other listings** — the company's investor-relations site
  (usually "Investors → Reports & Filings")
- **Royalty/streaming companies** — same sources; their portfolio detail is in
  the MD&A / "Business" section and the Asset Handbook exhibits

Once the reports are in place, run the extraction step documented in
`../skills/miners-database/SKILL.md`, then rebuild with
`../scripts/build_spreadsheet.py`.
