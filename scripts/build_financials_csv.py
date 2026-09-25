import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#!/usr/bin/env python3
"""Assemble company_financials_partial.csv from prices, FX, and fundamentals."""
import json, os, csv
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
    PT = ZoneInfo('America/Los_Angeles')
except Exception:
    PT = timezone.utc

BASE = 'REPO'
rows = json.load(open(os.path.join(BASE, 'webapp-data/companies.json')))['rows']
prices = json.load(open(os.path.join(BASE, 'prices_raw.json')))
fx = json.load(open(os.path.join(BASE, 'fx_raw.json')))
fund = json.load(open(os.path.join(BASE, 'fundamentals_raw.json')))

def usd_per_unit(cur):
    """USD per 1 unit of cur, using fx_raw (<CUR>USD=X quotes)."""
    if cur == 'USD':
        return 1.0, 'USD'
    f = fx.get(cur)
    if f and f.get('price'):
        return f['price'], f"Yahoo {f.get('symbol')}={f['price']}"
    return None, None

def qdate(ts):
    if not ts:
        return ''
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(PT).strftime('%Y-%m-%d')

PRICE_NOTES = {
    'DV': 'no Yahoo quote (TSX-V:DV not returned by Yahoo)',
    'SLVR': 'no Yahoo quote (TSX-V:SLVR not returned by Yahoo)',
    'EMX': 'no Yahoo quote (EMX.V/EMX not returned by Yahoo)',
    'ELE': 'no Yahoo quote (TSX-V:ELE / NASDAQ:ELEA not returned by Yahoo)',
    'MAG': 'delisted (acquired by Pan American Silver, 2025); no quote',
    'NGD': 'delisted March 2026; no quote',
    'SAND': 'delisted Oct 20, 2025 (acquired by Royal Gold); no quote',
    'ASE': 'no Yahoo coverage (CSE:ASE)',
    'FFX': 'delisted from ASX 2024-06-28; no quote',
    'GTRE': 'CSE listing pending; no quote',
    'MFRISCO': 'no Yahoo quote (BMV: MFRISCOA.MX not returned)',
    'APX': 'no Yahoo quote (PSE:APX.PS not returned)',
    'SSMR': 'unlisted; no quote',
    'HMMC': 'no Yahoo quote (TSX-V:HMMC)',
    'LUNR': 'no Yahoo quote (TSX-V:LUNR)',
}

out_rows = []

# Documented manual corrections (parser misread statement currency or grabbed
# wrong line; values blanked rather than left wrong)
FUND_OVERRIDES = {
    'MUX': {'currency': 'USD',
            'note': 'currency corrected to USD (US 10-K filer; parser picked MXN from risk-factor prose)'},
    'RSG': {'currency': 'AUD', 'net_income': None, 'total_debt': None,
            'note': 'currency corrected to AUD; net income/debt blanked (parser grabbed retained-earnings and lease-note lines)'},
    'BOL': {'currency': 'SEK', 'total_debt': None, 'cash': None,
            'note': 'currency corrected to SEK (Swedish reporter); debt/cash blanked (unreliable line matches)'},
    'HMMC': {'revenue': None, 'ebitda': None, 'net_income': None, 'total_debt': None, 'cash': None,
             'shares_outstanding': None, 'currency': None,
             'note': 'fundamentals blanked: report folder contains MD&A only, no financial statements'},
    'PSAB': {'revenue': None, 'ebitda': None, 'net_income': None, 'total_debt': None, 'cash': None,
             'shares_outstanding': None, 'currency': None,
             'note': 'fundamentals blanked: Indonesian-format statements (dot thousand-separators), unreliable extraction'},
    'SOSI': {'currency': None,
             'note': 'statement currency not identified (parser guessed USD); USD figures blank'},
    'KGH': {'total_debt': None,
            'note': 'total debt blanked (borrowings-line extraction unreliable for KGHM)'},
    'PAF': {'total_debt': None, 'cash': None,
            'note': 'debt/cash blanked (statement units not labeled; figures likely in thousands but unverifiable)'},
}

for r in rows:
    stem = r['Tickers']
    ticker = stem.split(',')[0].strip()
    company = r['Company']
    p = prices.get(ticker, {})
    f = fund.get(stem, {})
    notes = []

    # ---- price ----
    price, pcur, pdate = p.get('price'), p.get('currency'), qdate(p.get('time'))
    price_usd = None
    if price and pcur:
        if pcur == 'GBp':
            price_usd = price / 100 * fx['GBP']['price']
            notes.append('price quoted in GBp (pence)')
        elif pcur == 'ZAc':
            price_usd = price / 100 * fx['ZAR']['price']
            notes.append('price quoted in ZAc (cents)')
        else:
            rate, _ = usd_per_unit(pcur)
            if rate:
                price_usd = price * rate
                if pcur != 'USD':
                    notes.append(f'price {price} {pcur} converted at {rate} USD/{pcur}')
            else:
                notes.append(f'price {price} {pcur}: no FX rate, left unconverted')
                price_usd = None
    elif ticker in PRICE_NOTES:
        notes.append(PRICE_NOTES[ticker])
    elif p.get('error'):
        notes.append(f'no Yahoo quote: {p.get("error")}'[:120])

    # ---- fundamentals ----
    fcur = f.get('currency')
    ov = FUND_OVERRIDES.get(stem) or FUND_OVERRIDES.get(ticker)
    if ov:
        for k in ('revenue','ebitda','net_income','total_debt','cash','shares_outstanding','currency'):
            if k in ov:
                if k == 'currency':
                    fcur = ov[k]
                else:
                    f[k] = ov[k]
        notes.append(ov['note'])
    frate, frate_src = usd_per_unit(fcur) if fcur else (None, None)
    def conv(v):
        if v is None or frate is None:
            return None
        return v * frate
    revenue_usd = conv(f.get('revenue'))
    ebitda_usd = conv(f.get('ebitda'))
    net_income_usd = conv(f.get('net_income'))
    total_debt_usd = conv(f.get('total_debt'))
    cash_usd = conv(f.get('cash'))
    shares = f.get('shares_outstanding')
    if f.get('error'):
        notes.append(f['error'])
    if fcur and fcur != 'USD' and frate:
        fxdt = qdate(fx[fcur].get('time')) if fx.get(fcur, {}).get('time') else ''
        notes.append(f'statements in {fcur}; FX {frate} USD/{fcur} ({frate_src}, {fxdt})')
    if fcur and not frate and fcur != 'USD':
        notes.append(f'statements in {fcur} but no FX rate; USD figures blank')
    if not fcur and not f.get('error') and any(f.get(k) is not None for k in ('revenue','net_income','cash','total_debt')):
        notes.append('statement currency not identified; USD figures blank')
    ek = f.get('ebitda_kind')
    if ek:
        notes.append(f'EBITDA figure is {ek}')
    evr = (f.get('evidence') or {}).get('revenue')
    if evr and 'guarantor' in str(evr).lower():
        notes.append('revenue from summarized guarantor statements (Reg S-X note), not primary consolidated statements')
    dm = f.get('debt_method')
    if dm:
        notes.append(f'debt: {dm}')

    # ---- market cap / net debt ----
    market_cap_usd = None
    if price_usd and shares:
        market_cap_usd = price_usd * shares
        notes.append('market cap computed as price x shares outstanding')
    elif price_usd and not shares:
        notes.append('market cap not computed: shares outstanding undisclosed')
    net_debt_usd = None
    if total_debt_usd is not None and cash_usd is not None:
        net_debt_usd = total_debt_usd - cash_usd

    fy = f.get('fiscal_year') or r.get('Fiscal Year') or ''
    src = f.get('source') or ''
    interim = 'interim' in src.lower() or 'half-year' in src.lower()
    per = f'{"H1 " if interim else ""}FY{fy}' if fy else ('interim' if interim else '')
    if price and src:
        financial_source = f'Yahoo Finance quote ({pdate}) + {per} {src}'
    elif price:
        financial_source = f'Yahoo Finance quote ({pdate})'
    elif src and not f.get('error'):
        financial_source = f'{per} {src} (no market quote)'
    else:
        financial_source = ''

    def rnd(v, nd=0):
        if v is None:
            return ''
        return round(v, nd)

    out_rows.append({
        'ticker': ticker,
        'company': company,
        'price_usd': rnd(price_usd, 4) if price_usd else '',
        'price_as_of': pdate,
        'market_cap_usd': rnd(market_cap_usd),
        'shares_outstanding': int(shares) if shares else '',
        'revenue_usd': rnd(revenue_usd),
        'ebitda_usd': rnd(ebitda_usd),
        'net_income_usd': rnd(net_income_usd),
        'total_debt_usd': rnd(total_debt_usd),
        'cash_usd': rnd(cash_usd),
        'net_debt_usd': rnd(net_debt_usd),
        'fiscal_year': fy,
        'financial_source': financial_source,
        'notes': '; '.join(notes),
    })

cols = ['ticker','company','price_usd','price_as_of','market_cap_usd','shares_outstanding',
        'revenue_usd','ebitda_usd','net_income_usd','total_debt_usd','cash_usd','net_debt_usd',
        'fiscal_year','financial_source','notes']
with open(os.path.join(BASE, 'company_financials_partial.csv'), 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
    w.writeheader()
    w.writerows(out_rows)

n_price = sum(1 for x in out_rows if x['price_usd'] != '')
n_mc = sum(1 for x in out_rows if x['market_cap_usd'] != '')
n_rev = sum(1 for x in out_rows if x['revenue_usd'] != '')
n_any = sum(1 for x in out_rows if any(x[c] != '' for c in ('revenue_usd','net_income_usd','cash_usd','total_debt_usd')))
print(f'rows: {len(out_rows)}; price: {n_price}; market_cap: {n_mc}; revenue: {n_rev}; any fundamentals: {n_any}')
