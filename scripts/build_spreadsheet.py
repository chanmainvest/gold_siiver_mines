#!/usr/bin/env python3
"""Build miners-mine-data.xlsx from data/*.json, data/portfolio/*.json,
etf_holdings.csv, etf_methodology.json and company_financials.csv.

Sheets: Cover, Companies, Mines, Reserves & Resources, Cost Structure,
Royalties & Streams, Mine Links, ETF Holdings, ETF Methodology, Company Financials.
All reads use .get() so files with missing/extra keys never break the build.
"""
import json, glob, os, re, csv
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(os.path.expanduser("~"), "workspace", "your_files", "miners-mine-data.xlsx")

# ODV.json is the pre-rename filing of the same company now covered by OGG.json
# (renamed Osisko Development Corp. -> Osisko Gold Group Inc., July 14, 2026).
SKIP = {"ODV.json"}

HDR_FILL = PatternFill("solid", fgColor="1F4E5F")
HDR_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=16, color="1F4E5F")
SUB_FONT = Font(bold=True, size=12, color="1F4E5F")

# ---------------- ETF membership (from etf_holdings.csv) ----------------
ETF_ORDER = ["GDX","GDXJ","SIL","SILJ","GBUG","RING","AUAU","SGDM","SGDJ","GOAU","SLVP","SLJY"]
ETF_INFO = {
 "GDX":  ("VanEck Gold Miners ETF", "MarketVector Global Gold Miners Index",
          "https://www.vaneck.com/us/en/investments/gold-miners-etf-gdx/ (official holdings table)", "09/24/2026",
          "59 equities (65 holdings incl. cash lines)"),
 "GDXJ": ("VanEck Junior Gold Miners ETF", "MVIS Global Junior Gold Miners Index",
          "https://www.vaneck.com/us/en/investments/junior-gold-miners-etf-gdxj/ (official holdings table)", "09/24/2026",
          "156 equity rows"),
 "SIL":  ("Global X Silver Miners ETF", "Solactive Global Silver Miners Total Return Index",
          "https://stockanalysis.com/etf/sil/holdings/ + Global X SIL annual report (schedule of investments, Oct 31, 2025)",
          "09/23/2026", "25 identified (top 25; 42 total per stockanalysis)"),
 "SILJ": ("Amplify Junior Silver Miners ETF", "Nasdaq Junior Silver Miners Index",
          "https://stockanalysis.com/etf/silj/holdings/ + companiesmarketcap.com + cbonds.com",
          "09/22/2026", "57 identified (71 total per stockanalysis)"),
 "GBUG": ("Sprott Active Gold & Silver Miners ETF", "Actively managed (no index)",
          "https://www.marketbeat.com/stocks/NASDAQ/GBUG/holdings/ + Sprott GBUG factsheet",
          "09/24/2026", "38 identified (48 holdings incl. cash per marketbeat)"),
 "RING": ("iShares MSCI Global Gold Miners ETF", "MSCI ACWI Select Gold Miners Investable Market Index",
          "https://companiesmarketcap.com/ishares-msci-global-gold-miners-etf/holdings/ (ishares.com blocked 403)",
          "09/22/2026", "40 equities"),
 "AUAU": ("Global X Gold Miners ETF", "NYSE Arca Gold Miners Index (same index as GDX)",
          "https://stockanalysis.com/etf/auau/holdings/ (top 25)", "09/24/2026",
          "25 identified (117 total; launched 12/09/2025, not a Goldman Sachs product)"),
 "SGDM": ("Sprott Gold Miners ETF", "Solactive Gold Miners Custom Factors Total Return Index",
          "https://companiesmarketcap.com/sprott-gold-miners-etf/holdings/", "09/23/2026",
          "48 equities"),
 "SGDJ": ("Sprott Junior Gold Miners ETF", "Solactive Junior Gold Miners Custom Factors Index",
          "https://companiesmarketcap.com/sprott-junior-gold-miners-etf/holdings/", "09/23/2026",
          "31 equities"),
 "GOAU": ("U.S. Global GO GOLD and Precious Metal Miners ETF", "Actively managed (former: U.S. Global GO GOLD Index)",
          "https://www.usglobaletfs.com/fund/goau/ (official holdings table)", "09/22/2026",
          "28 equities"),
 "SLVP": ("iShares MSCI Global Silver and Metals Miners ETF", "MSCI ACWI Select Silver Miners Investable Market Index",
          "https://stockanalysis.com/etf/slvp/holdings/ (top 25; ishares.com blocked 403)", "09/23/2026",
          "25 identified (38 total)"),
 "SLJY": ("Amplify SILJ Junior Silver Miners Covered Call ETF", "Actively managed covered-call on silver miners",
          "https://stockanalysis.com/etf/sljy/holdings/ (top 25)", "09/23/2026",
          "17 equities + SILJ itself (24.19%) + SLV calls/T-bills/cash"),
}

def load_etf_holdings():
    """Read etf_holdings.csv -> (membership {stem: [etfs]}, sheet rows)."""
    member = {}
    rows = []
    with open(os.path.join(HERE, "etf_holdings.csv"), newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
            stem = r["company_ticker"]
            # skip the SLJY row that is the SILJ fund itself, not a company
            if stem == "SILJ" and r["etf_ticker"] == "SLJY":
                continue
            member.setdefault(stem, set()).add(r["etf_ticker"])
    return member, rows

ETF_MEMBER, ETF_HOLDING_ROWS = load_etf_holdings()

ROYALTY_FILES = {"RGLD.json", "FNV.json", "WPM.json", "OR.json", "TFPM.json",
                 "SAND.json", "GROY.json", "MTA.json", "VOXR.json", "ELE.json",
                 "EMX.json", "OGN.json", "ALS.TO.json", "VMET.json",
                 "LUNR.json", "FISH.json"}

def load():
    recs = []
    for f in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        base = os.path.basename(f)
        if base in SKIP:
            continue
        with open(f) as fh:
            d = json.load(fh)
        d["_file"] = base
        recs.append(d)
    return recs

def etf_list(rec):
    stem = rec["_file"][:-5]
    return ",".join(e for e in ETF_ORDER if e in ETF_MEMBER.get(stem, ()))

# ---------------- Royalty/streaming portfolio interests ----------------
RS_HEADERS = ["Royalty Company", "Ticker", "Asset / Mine", "Operator", "Country",
              "Commodity", "Interest Type", "Interest Detail",
              "Attributable Production", "Production Unit", "Revenue (USD)",
              "Effective Date", "Notes"]
ML_HEADERS = ["Mine", "Mine Operator (Owner)", "Country", "Royalty/Stream Holder",
              "Holder Ticker", "Interest Summary", "Mine In Database"]

def _norm_name(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())

_SUFFIXES = ("complex", "mine", "mines", "project", "projects", "operation",
             "operations", "deposit", "deposits", "property")

def _core_name(s):
    n = _norm_name(s)
    for suf in _SUFFIXES:
        if n.endswith(suf) and len(n) > len(suf) + 3:
            n = n[: -len(suf)]
    return n

def load_interests():
    """Normalize data/portfolio/*.json (3 schema variants) into canonical dicts."""
    rows = []
    for f in sorted(glob.glob(os.path.join(HERE, "data", "portfolio", "*.json"))):
        with open(f) as fh:
            d = json.load(fh)
        ticker = os.path.basename(f)[:-5]
        company = d.get("company") or d.get("owner") or ticker
        for i in d.get("interests") or []:
            if "asset" in i:  # variant A (task schema) and variant C (worker-2 schema)
                asset = i.get("asset")
                operator = i.get("operator") or i.get("counterparty")
                detail = i.get("interest_detail") or ""
                rate = i.get("interest_rate")
                if rate is not None and not detail:
                    detail = f"{rate}%"
                elif rate is not None and str(rate) not in str(detail):
                    detail = f"{detail} [{rate}%]"
                prod, unit = i.get("attributable_production"), i.get("production_unit")
                notes = i.get("notes") or ""
                stage = i.get("stage")
                if stage:
                    notes = f"[Stage: {stage}] " + notes
                # best-effort GEO extraction from worker-2 notes text
                if prod is None:
                    m = re.search(r"FY2025 GEOs? earned:\s*([\d,]+)", notes)
                    if m:
                        prod, unit = m.group(1), "GEO"
                rows.append({"company": company, "ticker": ticker, "asset": asset,
                             "operator": operator, "country": i.get("country"),
                             "commodity": i.get("commodity"), "type": i.get("interest_type"),
                             "detail": detail, "prod": prod, "unit": unit,
                             "revenue": i.get("revenue_usd"), "eff": i.get("effective_date"),
                             "notes": notes})
            else:  # variant B (mine/rate_text schema)
                comm = i.get("commodities")
                if isinstance(comm, list):
                    comm = ",".join(comm)
                detail = i.get("rate_text") or ""
                rp = i.get("rate_pct")
                if rp is not None and str(rp) not in str(detail):
                    detail = f"{detail} [{rp}%]"
                notes = i.get("notes") or ""
                if i.get("attributable_oz_note"):
                    notes = notes
                rows.append({"company": company, "ticker": ticker, "asset": i.get("mine"),
                             "operator": i.get("operator"), "country": i.get("mine_country"),
                             "commodity": comm, "type": i.get("interest_type"),
                             "detail": detail, "prod": i.get("attributable_oz_note"),
                             "unit": None, "revenue": i.get("fy2025_revenue"),
                             "eff": None, "notes": notes})
    return rows

def build_mine_links(recs, interests):
    """One row per mine <-> royalty/stream holder pair."""
    lookup = {}  # normalized mine name -> [(company, country, is_royalty_file)]
    core_lookup = {}  # core (suffix-stripped) name -> same
    for x in recs:
        is_roy = x["_file"] in ROYALTY_FILES
        for m in x.get("mines") or []:
            k = _norm_name(m.get("mine"))
            if k:
                lookup.setdefault(k, []).append(
                    (x.get("company"), m.get("country"), is_roy))
            kc = _core_name(m.get("mine"))
            if kc:
                core_lookup.setdefault(kc, []).append(
                    (x.get("company"), m.get("country"), is_roy))
    links = []
    for r in interests:
        k = _norm_name(r["asset"])
        cands = lookup.get(k, []) + core_lookup.get(_core_name(r["asset"]), [])
        nonroy = [c for c in cands if not c[2]]
        if nonroy:
            owner, country = nonroy[0][0], nonroy[0][1]
            in_db = "Yes"
        else:
            owner, country = r["operator"], r["country"]
            in_db = "No"
        summary = f"{r['ticker']}: {r['type'] or ''} — {r['detail'] or ''}".strip(" —")
        links.append([r["asset"], owner, country, r["company"], r["ticker"],
                      summary, in_db])
    return links

def add_sheet(wb, title, headers, rows, widths=None):
    ws = wb.create_sheet(title)
    ws.append(headers)
    for c in ws[1]:
        c.fill = HDR_FILL; c.font = HDR_FONT
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for r in rows:
        ws.append(r)
    for i, col in enumerate(ws.columns, 1):
        w = widths[i-1] if widths and i-1 < len(widths) else 18
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws

def main():
    recs = load()
    wb = Workbook()

    # ---------- Cover ----------
    ws = wb.active; ws.title = "Cover"
    ws["A1"] = "Gold & Silver Miners — Mine-Level Database"; ws["A1"].font = TITLE_FONT
    ws["A2"] = f"Built {date.today().isoformat()} — all identifiable equity holdings of 12 precious-metals-mining ETFs, plus full royalty/streaming portfolios, company financials and ETF construction comparison"
    ws["A2"].font = SUB_FONT
    r = 4
    ws[f"A{r}"] = "Scope"; ws[f"A{r}"].font = SUB_FONT; r += 1
    scope = ("Every identifiable equity holding of TWELVE precious-metals-mining ETFs: VanEck Gold Miners (GDX), "
             "VanEck Junior Gold Miners (GDXJ), Global X Silver Miners (SIL), Amplify Junior Silver "
             "Miners (SILJ), Sprott Active Gold & Silver Miners (GBUG), iShares MSCI Global Gold Miners (RING), "
             "Global X Gold Miners (AUAU), Sprott Gold Miners (SGDM), Sprott Junior Gold Miners (SGDJ), "
             "U.S. Global GO GOLD and Precious Metal Miners (GOAU), iShares MSCI Global Silver Miners (SLVP), "
             "and Amplify SILJ Junior Silver Miners Covered Call (SLJY). Includes foreign-listed "
             "holdings (ASX, HKEX, LSE, IDX, JSE, PSE, MOEX, etc.), developers, explorers, royalty/streaming "
             "companies, and a small number of non-miners held by the ETFs (Korea Zinc — smelter; "
             "Valterra Platinum — PGM producer), flagged as such. "
             "Separately, ALL US- and Canada-listed gold & silver royalty/streaming companies are "
             "covered with full portfolio detail (RGLD, FNV, WPM, OR, TFPM, SAND, GROY, MTA, VOXR, "
             "ELE, EMX, OGN, ALS, VMET, LUNR, FISH): see the 'Royalties & Streams' sheet for every "
             "material interest and the 'Mine Links' sheet for the mine-to-holder relationship map. "
             "The 'ETF Holdings' sheet maps every ETF to its miners (with weights); 'ETF Methodology' "
             "compares how the 12 ETFs are constructed from their prospectuses; 'Company Financials' "
             "gives price, market cap, revenue, EBITDA, debt and cash per company.")
    ws[f"A{r}"] = scope; ws[f"A{r}"].alignment = Alignment(wrap_text=True); ws.merge_cells(f"A{r}:H{r}")
    r += 2
    ws[f"A{r}"] = "ETF holdings sources"; ws[f"A{r}"].font = SUB_FONT; r += 1
    hdr = ["ETF", "Fund", "Index", "Holdings source", "Holdings as of", "Size"]
    for i, h in enumerate(hdr, 1):
        c = ws.cell(row=r, column=i, value=h); c.fill = HDR_FILL; c.font = HDR_FONT
    r += 1
    for e in ETF_ORDER:
        name, idx, src, asof, size = ETF_INFO[e]
        for i, v in enumerate([e, name, idx, src, asof, size], 1):
            ws.cell(row=r, column=i, value=v)
        r += 1
    r += 1
    ws[f"A{r}"] = "Coverage totals"; ws[f"A{r}"].font = SUB_FONT; r += 1
    n_mines = sum(len(x.get("mines") or []) for x in recs)
    n_rr = sum(len(x.get("reserves_resources") or []) for x in recs)
    n_prod = sum(1 for x in recs if (x.get("mines") or []) and any(m.get("status") == "Operating" for m in x["mines"]))
    interests = load_interests()
    links = build_mine_links(recs, interests)
    n_linked = sum(1 for L in links if L[6] == "Yes")
    stats = [
        ("Companies in database", len(recs)),
        ("Mine / asset rows", n_mines),
        ("Reserves & resources rows", n_rr),
        ("Companies with ≥1 operating mine", n_prod),
        ("Royalty/stream interests extracted", len(interests)),
        ("Mine↔holder links (mine also in database)", f"{n_linked} of {len(links)}"),
        ("Royalty/streaming companies covered", len(ROYALTY_FILES)),
    ]
    from collections import Counter as _Counter
    _eq = _Counter(r["etf_ticker"] for r in ETF_HOLDING_ROWS
                   if not (r["company_ticker"] == "SILJ" and r["etf_ticker"] == "SLJY"))
    for e in ETF_ORDER:
        stats.append((f"{e} equity holdings in file", _eq.get(e, 0)))
    try:
        _meth = json.load(open(os.path.join(HERE, "etf_methodology.json")))
        stats.append(("ETFs in construction comparison", len(_meth)))
    except Exception:
        pass
    try:
        _fin_n = sum(1 for _ in open(os.path.join(HERE, "company_financials.csv"))) - 1
        stats.append(("Companies with financials rows", _fin_n))
    except Exception:
        pass
    stats.append(("ETF<->miner mapping rows", len(ETF_HOLDING_ROWS) - 1))  # minus SLJY/SILJ fund row
    for label, val in stats:
        ws.cell(row=r, column=1, value=label); ws.cell(row=r, column=2, value=val); r += 1
    r += 1
    ws[f"A{r}"] = "Methodology & caveats"; ws[f"A{r}"].font = SUB_FONT; r += 1
    notes = [
        "Most recent annual report (10-K / 40-F / AIF / annual information form / MD&A) per company; "
        "FY2025 for Dec year-ends, FY2026 for June year-ends (Australian) and other off-cycle filers.",
        "Production is attributable ounces. Costs are USD/oz unless flagged (AUD reporters note the basis in mine notes).",
        "Null = not disclosed by the company; nothing is estimated or fabricated.",
        "Royalty/streaming companies (WPM, FNV, RGLD, OR, TFPM, ELE, GROY, MTA, VOXR, VMET, LUNR, FISH): "
        "Companies-sheet production = attributable GEO/oz sold; revenue split stream vs royalty in file notes. "
        "Mines-sheet rows are the underlying portfolio assets (ownership_pct = stream/royalty interest). "
        "SAND (Sandstorm): Royal Gold acquired it Oct 20, 2025 — delisted, no FY2025 report; filed on FY2024 basis. "
        "EMX: merged into Elemental Altus Nov 2025 — kept as historical FY2024 record. "
        "ALS (Altius): diversified — only precious-metals royalties included, other segments excluded (documented).",
        "Royalties & Streams sheet: one row per material interest (659 total). Long exploration tails of "
        "juniors are grouped with a flag where individually immaterial. Franco-Nevada: 438 assets, 47 rows "
        "(exploration tails grouped). Revenue/attributable oz shown only where the company discloses them — "
        "null = not disclosed, never estimated.",
        "Developers: flagship project shown as development-stage entry with PEA/PFS/FS economics where published; pure explorers list no mine rows.",
        "Partial data_status: DSV, 340.HK, PSAB.JK, EMAS.JK, ARCI.JK (FY2025 annual report unobtainable in English); BYN/DC/HSTR figures flagged verify-before-publish in file notes.",
        "Special cases: VGCX (Victoria Gold) bankrupt — Eagle mine shut; SSMR private — no public report; VALT platinum-group producer; 010130.KS (Korea Zinc) smelter, not a mine operator; OGG renamed from Osisko Development Corp. (ODV filing excluded as duplicate); NIX (NorthX Nickel) was Archer Exploration Corp. until May 2024 — VanEck still shows the old name.",
        "Small-cap tails of SIL (Oct 2025 annual report) and SILJ/GBUG (third-party aggregators) could not be fully verified against current holdings; unidentified names are the only gap.",
    ]
    for n in notes:
        ws[f"A{r}"] = "• " + n; ws[f"A{r}"].alignment = Alignment(wrap_text=True)
        ws.merge_cells(f"A{r}:H{r}"); r += 1
    r += 1
    ws[f"A{r}"] = "How the sheets join (ETF -> miner -> mine -> royalty holder)"; ws[f"A{r}"].font = SUB_FONT; r += 1
    joins = [
        "ETF Holdings.company_ticker = Companies.Tickers / Mines.Company key: every ETF->miner pair (with weight %) joins to the company and its mines.",
        "Mines (Company + Mine + Country) -> Mine Links (Mine + Country): each mine's royalty/stream holders and interest terms.",
        "Mine Links.Holder Ticker -> Royalties & Streams.Ticker: the holder's full portfolio interest behind each link.",
        "Royalties & Streams.Ticker -> Companies.Tickers: royalty/streaming companies' attributable production and revenue.",
        "Company Financials.ticker = Companies.Tickers: price, market cap, revenue, EBITDA, debt, cash per company.",
        "ETF Methodology: one row per ETF — join to ETF Holdings on ETF ticker for holdings + construction in one view.",
    ]
    for j in joins:
        ws[f"A{r}"] = "• " + j; ws[f"A{r}"].alignment = Alignment(wrap_text=True)
        ws.merge_cells(f"A{r}:H{r}"); r += 1
    r += 1
    ws[f"A{r}"] = "ETF construction comparison (summary — detail in 'ETF Methodology' sheet)"; ws[f"A{r}"].font = SUB_FONT; r += 1
    comp = [
        "Index vs active: 9 ETFs track an index (GDX/GDXJ: MarketVector; RING/SLVP: MSCI 25/50; SIL: Solactive silver; SILJ: Nasdaq junior silver (changed Jan 2026); SGDM/SGDJ: Solactive custom-factor; AUAU: NYSE Arca Gold Miners — the same index as GDX); 3 are actively managed (GBUG: Sprott discretionary value/contrarian; GOAU: U.S. Global quant multifactor incl. royalty/streaming companies; SLJY: Amplify covered-call writing on silver miners).",
        "Selection: most require a minimum % of revenue from gold/silver mining (typically 50%) plus market-cap and liquidity screens; juniors (GDXJ, SGDJ, SILJ) target small/mid-cap explorers and developers.",
        "Weighting: mostly modified market-cap with single-stock caps (e.g. GDX caps large names; SGDM single <= 18%, >4.5% names <= 50% aggregate; SGDJ single <= 9%; MSCI 25/50 for RING/SLVP); GOAU uses a multifactor quant score.",
        "Rebalance: quarterly for most (GDX, GDXJ, SILJ, SGDM); semi-annual for RING/SLVP (May/Nov) and SGDJ (Mar/Sep).",
        "Expense ratios range 0.35% (AUAU) to 0.90% (GBUG); AUM ranges from ~$7M (AUAU, launched Dec 2025) to ~$28.4B (GDX).",
        "Corrections applied during research: AUAU is a Global X product (not Goldman Sachs); SLJY is an Amplify (not YieldMax) covered-call fund; GOAU dropped its index and is now actively managed; SILJ switched from MSCI to the Nasdaq index in Jan 2026.",
    ]
    for j in comp:
        ws[f"A{r}"] = "• " + j; ws[f"A{r}"].alignment = Alignment(wrap_text=True)
        ws.merge_cells(f"A{r}:H{r}"); r += 1
    r += 1
    ws[f"A{r}"] = "Company Financials — basis"; ws[f"A{r}"].font = SUB_FONT; r += 1
    fin = [
        "Prices are Yahoo Finance quotes observed 2026-09-25 (PSE:PX from stockanalysis.com; PLZL sanctioned — no quote), converted to USD.",
        "Market cap = price x shares outstanding (computed where both available); fundamentals (revenue, EBITDA/operating income, net income, debt, cash) come from each company's latest annual-report financial statements, converted to USD at statement-date FX. Blank = undisclosed or unobtainable — nothing estimated.",
        "ETF AUM and holdings weights are as of the dates in the ETF table above; holdings change daily.",
    ]
    for j in fin:
        ws[f"A{r}"] = "• " + j; ws[f"A{r}"].alignment = Alignment(wrap_text=True)
        ws.merge_cells(f"A{r}:H{r}"); r += 1
    for col, w in zip("ABCDEFGH", [10, 34, 40, 60, 14, 34, 14, 14]):
        ws.column_dimensions[col].width = w

    # ---------- Companies ----------
    ch = ["Company", "Tickers", "Exchange", "Headquarters", "Fiscal Year", "ETFs",
          "Data Status", "Total Gold Prod (oz)", "Total Silver Prod (oz)", "Report Title",
          "Source URL", "Notes"]
    rows = []
    for x in recs:
        rows.append([x.get("company"), ",".join(x.get("tickers") or []), x.get("exchange"),
                     x.get("headquarters"), x.get("fiscal_year"), etf_list(x),
                     x.get("data_status"), x.get("total_gold_production_oz"),
                     x.get("total_silver_production_oz"), x.get("report_title"),
                     x.get("report_url"), x.get("notes")])
    add_sheet(wb, "Companies", ch, rows, [34, 16, 12, 26, 10, 18, 22, 16, 16, 30, 40, 60])

    # ---------- Mines ----------
    mh = ["Company", "Mine", "Country", "Ownership %", "Status", "Mine Type", "Processing",
          "Gold (oz)", "Silver (oz)", "Byproduct", "Byproduct Qty", "Unit",
          "Head Grade Au (g/t)", "Head Grade Ag (g/t)", "Reserve Tonnes (Mt)",
          "Reserve Au (oz)", "Reserve Ag (oz)", "Notes"]
    mrows = []
    for x in recs:
        for m in x.get("mines") or []:
            mrows.append([x.get("company"), m.get("mine"), m.get("country"),
                          m.get("ownership_pct"), m.get("status"), m.get("mine_type"),
                          m.get("processing"), m.get("gold_oz"), m.get("silver_oz"),
                          m.get("byproduct"), m.get("byproduct_qty"), m.get("byproduct_unit"),
                          m.get("head_grade_au_gpt"), m.get("head_grade_ag_gpt"),
                          m.get("reserve_tonnes_mt"), m.get("reserve_au_oz"),
                          m.get("reserve_ag_oz"), m.get("mine_notes")])
    add_sheet(wb, "Mines", mh, mrows, [28, 28, 12, 10, 12, 16, 24, 14, 14, 14, 14, 10, 14, 14, 16, 16, 16, 60])

    # ---------- Reserves & Resources ----------
    rh = ["Company", "Mine", "Classification", "Tonnes (Mt)", "Au (g/t)", "Ag (g/t)",
          "Contained Au (oz)", "Contained Ag (oz)", "Effective Date", "Notes"]
    rrows = []
    for x in recs:
        for rr in x.get("reserves_resources") or []:
            rrows.append([x.get("company"), rr.get("mine"), rr.get("classification"),
                          rr.get("tonnes_mt"), rr.get("au_gpt"), rr.get("ag_gpt"),
                          rr.get("contained_au_oz"), rr.get("contained_ag_oz"),
                          rr.get("effective_date"), rr.get("notes")])
    add_sheet(wb, "Reserves & Resources", rh, rrows, [28, 28, 26, 12, 10, 10, 16, 16, 14, 40])

    # ---------- Cost Structure ----------
    sh = ["Company", "Mine", "Cash Cost ($/oz)", "AISC ($/oz)", "Sustaining Capex ($M)", "Notes"]
    srows = []
    for x in recs:
        for m in x.get("mines") or []:
            if m.get("cash_cost_usd_per_oz") is None and m.get("aisc_usd_per_oz") is None \
               and m.get("sustaining_capex_usd_m") is None:
                continue
            srows.append([x.get("company"), m.get("mine"), m.get("cash_cost_usd_per_oz"),
                          m.get("aisc_usd_per_oz"), m.get("sustaining_capex_usd_m"),
                          m.get("mine_notes")])
    add_sheet(wb, "Cost Structure", sh, srows, [28, 28, 14, 14, 18, 70])

    # ---------- Royalties & Streams ----------
    rsrows = [[r["company"], r["ticker"], r["asset"], r["operator"], r["country"],
               r["commodity"], r["type"], r["detail"], r["prod"], r["unit"],
               r["revenue"], r["eff"], r["notes"]] for r in interests]
    add_sheet(wb, "Royalties & Streams", RS_HEADERS, rsrows,
              [30, 10, 30, 28, 16, 12, 16, 40, 18, 12, 14, 12, 70])

    # ---------- Mine Links ----------
    add_sheet(wb, "Mine Links", ML_HEADERS, links,
              [30, 30, 16, 30, 12, 50, 14])

    # ---------- ETF Holdings ----------
    ehh = ["ETF", "ETF Name", "Company", "Company Ticker", "Weight %", "As Of", "Holdings Source"]
    ehrows = [[r["etf_ticker"], r["etf_name"], r["company"], r["company_ticker"],
               r["weight_pct"], r["as_of_date"], r["holdings_source"]]
              for r in ETF_HOLDING_ROWS
              if not (r["company_ticker"] == "SILJ" and r["etf_ticker"] == "SLJY")]
    add_sheet(wb, "ETF Holdings", ehh, ehrows, [10, 44, 40, 14, 10, 12, 60])

    # ---------- ETF Methodology ----------
    try:
        meth = json.load(open(os.path.join(HERE, "etf_methodology.json")))
        mcols = ["ETF Ticker", "ETF Name", "Issuer", "Index Tracked", "Selection Criteria",
                 "Weighting Scheme", "Rebalance Frequency", "Expense Ratio", "Inception Date",
                 "AUM (USD)", "AUM As Of", "Num Holdings", "Notes"]
        methrows = [[m.get(c) for c in mcols] for m in meth]
    except Exception as e:
        mcols, methrows = ["Note"], [[f"etf_methodology.json not loaded: {e}"]]
    add_sheet(wb, "ETF Methodology", mcols, methrows,
              [10, 40, 28, 40, 60, 50, 22, 16, 14, 16, 12, 12, 80])

    # ---------- Company Financials ----------
    fcols = ["ticker", "company", "price_usd", "price_as_of", "market_cap_usd",
             "shares_outstanding", "revenue_usd", "ebitda_usd", "net_income_usd",
             "total_debt_usd", "cash_usd", "net_debt_usd", "fiscal_year",
             "financial_source", "notes"]
    frows = []
    with open(os.path.join(HERE, "company_financials.csv"), newline="") as f:
        for r in csv.DictReader(f):
            frows.append([r.get(c) for c in fcols])
    fh = ["Ticker", "Company", "Price (USD)", "Price As Of", "Market Cap (USD)",
          "Shares Outstanding", "Revenue (USD)", "EBITDA (USD)", "Net Income (USD)",
          "Total Debt (USD)", "Cash (USD)", "Net Debt (USD)", "Fiscal Year",
          "Financial Source", "Notes"]
    add_sheet(wb, "Company Financials", fh, frows,
              [12, 34, 12, 12, 16, 18, 16, 16, 16, 16, 14, 14, 10, 40, 70])

    wb.save(OUT)
    print("saved", OUT)
    print("companies:", len(recs), "| mines:", len(mrows), "| R&R:", len(rrows),
          "| cost rows:", len(srows), "| interests:", len(rsrows), "| links:", len(links),
          "| ETF holdings:", len(ehrows), "| methodology:", len(methrows), "| financials:", len(frows))
    # ETF coverage sanity check
    have = {x["_file"][:-5] for x in recs}
    for e in ETF_ORDER:
        want = {r["company_ticker"] for r in ETF_HOLDING_ROWS
                if r["etf_ticker"] == e and not (r["company_ticker"] == "SILJ" and r["etf_ticker"] == "SLJY")}
        missing = sorted(want - have)
        print(e, "missing:", missing if missing else "none")

if __name__ == "__main__":
    main()
