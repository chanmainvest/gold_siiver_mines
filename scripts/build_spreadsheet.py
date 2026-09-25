import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#!/usr/bin/env python3
"""Build miners-mine-data.xlsx from data/*.json and data/portfolio/*.json.

Sheets: Cover, Companies, Mines, Reserves & Resources, Cost Structure,
Royalties & Streams, Mine Links.
All reads use .get() so files with missing/extra keys never break the build.
"""
import json, glob, os, re
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(REPO, "data", "companies")
OUT = os.path.join(REPO, "miners-mine-data.xlsx")

# ODV.json is the pre-rename filing of the same company now covered by OGG.json
# (renamed Osisko Development Corp. -> Osisko Gold Group Inc., July 14, 2026).
SKIP = {"ODV.json"}

HDR_FILL = PatternFill("solid", fgColor="1F4E5F")
HDR_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(bold=True, size=16, color="1F4E5F")
SUB_FONT = Font(bold=True, size=12, color="1F4E5F")

# ---------------- ETF membership (json filename -> ETFs) ----------------
GDX = ["NEM.json","AEM.json","B.json","WPM.json","FNV.json","AU.json","KGC.json","GFI.json",
 "PAAS.json","NST.AX.json","CDE.json","RGLD.json","AGI.json","EQX.json","EVN.AX.json",
 "PENOLES.MX.json","HL.json","EDV.L.json","AG.json","IAG.json","2259.HK.json","FRES.L.json",
 "GMIN.json","DPM.json","LUG.json","EGO.json","BTG.json","BVN.json","SSRM.json","HMY.json",
 "OGC.json","DSV.json","AMMN.JK.json","PRU.AX.json","RMS.AX.json","MAU.json","OR.json",
 "KNT.json","1818.HK.json","ARTG.json","CMM.AX.json","ARIS.json","VAU.AX.json","CGAU.json",
 "GMD.AX.json","AYA.json","TXG.json","WDO.json","BRMS.JK.json","AUGO.json","GGP.AX.json",
 "SKE.json","FSM.json","RRL.AX.json","SA.json","HOC.L.json","WGX.AX.json","EXK.json","SVM.json"]
GDXJ = ["CDE.json","AGI.json","EQX.json","EDV.L.json","IAG.json","PENOLES.MX.json","HL.json",
 "AG.json","GMIN.json","DPM.json","LUG.json","EGO.json","BTG.json","BVN.json","SSRM.json",
 "HMY.json","OGC.json","DSV.json","PRU.AX.json","RMS.AX.json","MAU.json","OR.json","KNT.json",
 "1818.HK.json","ARTG.json","CMM.AX.json","ARIS.json","VAU.AX.json","CGAU.json","GMD.AX.json",
 "AYA.json","TXG.json","WDO.json","BRMS.JK.json","AUGO.json","GGP.AX.json","PAF.L.json",
 "SKE.json","FSM.json","RRL.AX.json","3939.HK.json","SA.json","HOC.L.json","TFPM.json",
 "WGX.AX.json","EXK.json","SVM.json","EMR.AX.json","SXGC.json","AAUC.json","PDI.AX.json",
 "EMAS.JK.json","PPTA.json","NG.json","WAF.AX.json","SGD.json","ALK.AX.json","OBM.AX.json",
 "VZLA.json","USA.json","IAUX.json","RIO.json","GGD.json","ABRA.json","OMG.json","BGL.AX.json",
 "BNZ.json","RSG.AX.json","HMMC.json","MI6.AX.json","ASM.json","CYL.AX.json","TRALT.IS.json",
 "HYMC.json","NCX.json","KCN.AX.json","DRD.json","ELE.json","ORE.json","FF.json","LUNR.json",
 "340.HK.json","MUX.json","HSLV.json","6693.HK.json","DC.json","MSA.json","MTA.json",
 "TLG.json","LGD.json","SBM.AX.json","GROY.json","TCG.AX.json","TAU.json","ASE.json",
 "PNR.AX.json","TRMET.IS.json","BYN.json","CNL.json","TALA.json","OGG.json","NFGC.json",
 "FRS.AX.json","AUXX.json","MKO.json","ITRG.json","AMI.AX.json","BC8.AX.json","CTGO.json",
 "NEWP.json","TRX.json","APX.PS.json","VMET.json","GSKR.json","MNO.json","BTR.AX.json",
 "NMG.AX.json","SSMR.json","IDR.json","SMI.AX.json","MAI.json","GAU.json","VGZ.json",
 "HSTR.json","USL.AX.json","SLVR.json","VOXR.json","ARCI.JK.json","CNMC.SG.json","BRC.json",
 "CMCL.json","AUC.AX.json","NEXG.json","APM.json","SIND.json","JAG.json","GSVR.json",
 "USAU.json","WRLG.json","GLDG.json","ASL.AX.json","FDR.json","MEK.AX.json","LUCA.json",
 "AZY.AX.json","THM.json","8299.HK.json","SVRS.json","DTR.AX.json","VGC.json","FFX.AX.json",
 "PSAB.JK.json","G3GOLDFIELDS.json","FMR.json","NIX.json","VGCX.json"]
SIL = ["WPM.json","PAAS.json","CDE.json","HL.json","PENOLES.MX.json","AG.json","SSRM.json",
 "OR.json","FRES.L.json","BVN.json","DSV.json","AYA.json","010130.KS.json","FSM.json",
 "EXK.json","SVM.json","HOC.L.json","TFPM.json","VZLA.json","ABRA.json","GGD.json",
 "USA.json","MUX.json","HYMC.json","ASM.json","AAG.json","APM.json","ASL.AX.json",
 "BRC.json","DV.json","GSVR.json","ITRG.json","NEWP.json","SCZ.json","SLVR.json",
 "SVL.AX.json","USL.AX.json","KCN.AX.json","TXG.json"]
SILJ = ["CDE.json","AG.json","HL.json","WPM.json","SSRM.json","AYA.json","BOL.ST.json",
 "EXK.json","PPTA.json","BVN.json","HYMC.json","SVM.json","SA.json","PAAS.json","OR.json",
 "TFPM.json","FNV.json","SKE.json","VZLA.json","USA.json","RGLD.json","HOC.L.json",
 "ASM.json","ABRA.json","FRES.L.json","KGH.WA.json","TMQ.json","MUX.json","IAUX.json",
 "NEWP.json","TLG.json","WRN.json","PENOLES.MX.json","GGD.json","OM.json","FF.json",
 "SCZ.json","APM.json","PML.json","SVL.AX.json","SOSI.ST.json","SVRS.json","TUD.json",
 "MFRISCO.MX.json","GSVR.json","PZG.json","VOLCAN.json","AGMR.json","BMC.json","CKG.json",
 "AAG.json","SM.json","MKR.AX.json","CUU.json","FPC.json","BNKR.json","IPT.json"]
GBUG = ["DPM.json","GMIN.json","DSV.json","IAG.json","EGO.json","MAU.json","CDE.json",
 "WDO.json","NEM.json","RMS.AX.json","WPM.json","AEM.json","EQX.json","OGC.json",
 "EMR.AX.json","GMD.AX.json","NST.AX.json","IAUX.json","AU.json","EVN.AX.json","KNT.json",
 "B.json","KGC.json","OBM.AX.json","TXG.json","VZLA.json","VALT.json","WGX.AX.json",
 "LUG.json","PPTA.json","EXK.json","MTA.json","WAF.AX.json","BVN.json","OR.json",
 "SSRM.json","AGI.json"]

ETFS = {"GDX": GDX, "GDXJ": GDXJ, "SIL": SIL, "SILJ": SILJ, "GBUG": GBUG}

# Royalty/streaming companies: their portfolio interests feed the
# "Royalties & Streams" and "Mine Links" sheets. Their mine rows also
# appear on the Mines sheet as underlying assets.
ROYALTY_FILES = {"RGLD.json", "FNV.json", "WPM.json", "OR.json", "TFPM.json",
                 "SAND.json", "GROY.json", "MTA.json", "VOXR.json", "ELE.json",
                 "EMX.json", "OGN.json", "ALS.TO.json", "VMET.json",
                 "LUNR.json", "FISH.json"}
ETF_INFO = {
 "GDX":  ("VanEck Gold Miners ETF", "MarketVector Global Gold Miners Index",
          "https://www.vaneck.com/us/en/investments/gold-miners-etf-gdx/", "09/24/2026",
          "59 equities (65 holdings incl. cash lines)"),
 "GDXJ": ("VanEck Junior Gold Miners ETF", "MVIS Global Junior Gold Miners Index",
          "https://www.vaneck.com/us/en/investments/junior-gold-miners-etf-gdxj/", "09/24/2026",
          "154 equities (161 holdings incl. cash lines)"),
 "SIL":  ("Global X Silver Miners ETF", "Solactive Global Silver Miners Total Return Index",
          "https://stockanalysis.com/etf/sil/holdings/ + Global X SIL annual report (schedule of investments, Oct 31, 2025)",
          "09/23/2026", "42 total per stockanalysis (top 25 listed); small-cap tail from Oct 2025 annual report"),
 "SILJ": ("Amplify Junior Silver Miners ETF", "Nasdaq Junior Silver Miners Index",
          "https://stockanalysis.com/etf/silj/holdings/ + https://companiesmarketcap.com/amplify-junior-silver-miners-etf/holdings/ + https://cbonds.com/etf/10435/",
          "09/22/2026", "71 total per stockanalysis (top 25 listed); full tail from cbonds/companiesmarketcap"),
 "GBUG": ("Sprott Active Gold & Silver Miners ETF", "Actively managed (no index)",
          "https://www.marketbeat.com/stocks/NASDAQ/GBUG/holdings/ + Sprott GBUG factsheet",
          "09/24/2026", "48 holdings incl. cash per marketbeat (top 25 listed); factsheet as of 12/31/2025"),
}

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
    return ",".join(e for e, lst in ETFS.items() if rec["_file"] in lst)

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
    for f in sorted(glob.glob(os.path.join(REPO, "data", "portfolio", "*.json"))):
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
    ws["A2"] = f"Built {date.today().isoformat()} — all equity holdings of GDX, GDXJ, SIL, SILJ and GBUG"
    ws["A2"].font = SUB_FONT
    r = 4
    ws[f"A{r}"] = "Scope"; ws[f"A{r}"].font = SUB_FONT; r += 1
    scope = ("Every equity holding of five precious-metals-mining ETFs: VanEck Gold Miners (GDX), "
             "VanEck Junior Gold Miners (GDXJ), Global X Silver Miners (SIL), Amplify Junior Silver "
             "Miners (SILJ), and Sprott Active Gold & Silver Miners (GBUG). Includes foreign-listed "
             "holdings (ASX, HKEX, LSE, IDX, JSE, etc.), developers, explorers, royalty/streaming "
             "companies, and a small number of non-miners held by the ETFs (Korea Zinc — smelter; "
             "Valterra Platinum — PGM producer), flagged as such. "
             "Separately, ALL US- and Canada-listed gold & silver royalty/streaming companies are "
             "covered with full portfolio detail (RGLD, FNV, WPM, OR, TFPM, SAND, GROY, MTA, VOXR, "
             "ELE, EMX, OGN, ALS, VMET, LUNR, FISH): see the 'Royalties & Streams' sheet for every "
             "material interest and the 'Mine Links' sheet for the mine-to-holder relationship map.")
    ws[f"A{r}"] = scope; ws[f"A{r}"].alignment = Alignment(wrap_text=True); ws.merge_cells(f"A{r}:H{r}")
    r += 2
    ws[f"A{r}"] = "ETF holdings sources"; ws[f"A{r}"].font = SUB_FONT; r += 1
    hdr = ["ETF", "Fund", "Index", "Holdings source", "Holdings as of", "Size"]
    for i, h in enumerate(hdr, 1):
        c = ws.cell(row=r, column=i, value=h); c.fill = HDR_FILL; c.font = HDR_FONT
    r += 1
    for e in ["GDX", "GDXJ", "SIL", "SILJ", "GBUG"]:
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
        ("GDX holdings covered", f"{len(GDX)} / 59 equities"),
        ("GDXJ holdings covered", f"{len(GDXJ)} / 154 equities"),
        ("SIL holdings covered", f"{len(SIL)} identified of 42 total"),
        ("SILJ holdings covered", f"{len(SILJ)} identified of 71 total"),
        ("GBUG holdings covered", f"{len(GBUG)} identified equities (48 holdings incl. cash)"),
    ]
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

    wb.save(OUT)
    print("saved", OUT)
    print("companies:", len(recs), "| mines:", len(mrows), "| R&R:", len(rrows),
          "| cost rows:", len(srows), "| interests:", len(rsrows), "| links:", len(links))
    # ETF coverage sanity check
    have = {x["_file"] for x in recs}
    for e, lst in ETFS.items():
        missing = [t for t in lst if t not in have]
        print(e, "missing:", missing if missing else "none")

if __name__ == "__main__":
    main()
