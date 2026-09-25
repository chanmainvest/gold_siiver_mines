import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#!/usr/bin/env python3
"""Fetch latest prices from Yahoo Finance v8 chart endpoint for all 205 companies + FX pairs."""
import json, re, time, urllib.request, urllib.parse, sys, os

BASE = os.path.dirname(os.path.abspath(__file__))

def yahoo_symbol(row):
    t = row['Tickers'].split(',')[0].strip()
    ex = row['Exchange']
    m = re.match(r'^(.+)\.([A-Za-z]{1,3})$', t)
    if m and m.group(2).upper() in {'AX','TO','V','L','HK','KS','MX','JK','WA','SI','IS','PS','ST','JO','LM','CL','CN'}:
        return t
    if 'Unlisted' in ex:
        return None
    exu = ex.upper()
    def has(*ws): return any(w in exu for w in ws)
    if has('TSX-V','TSXV','TSX VENTURE'):
        return t + '.V'
    if has('TSX'):
        return t + '.TO'
    if has('CSE'):
        return t + '.CN'
    if has('ASX'):
        return t + '.AX'
    if has('LSE','AIM'):
        return t + '.L'
    if has('HKEX'):
        return t + '.HK'
    if has('IDX'):
        return t + '.JK'
    if has('PSE'):
        return t + '.PS'
    if has('BIST'):
        return t + '.IS'
    if has('KRX'):
        return t + '.KS'
    if has('SGX'):
        return t + '.SI'
    if has('GPW','WARSAW'):
        return t + '.WA'
    if has('BVL'):
        return t + '.LM'
    if has('JSE') and not has('NYSE','NASDAQ'):
        return t + '.JO'
    if has('NGM','STOCKHOLM'):
        return t + '.ST'
    if has('BMV'):
        return t + '.MX'
    if has('NYSE','NASDAQ'):
        return t
    return t  # fallback bare

def fetch(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym, safe='')}" \
          f"?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

def main():
    rows = json.load(open(os.path.join(REPO, 'data', 'webapp', 'companies.json')))['rows']
    syms = []
    for r in rows:
        syms.append((r['Tickers'].split(',')[0].strip(), r['Company'], yahoo_symbol(r)))
    fx = ['CAD','AUD','GBP','EUR','MXN','KRW','IDR','PHP','BRL','CLP','PEN','ZAR','TRY','SEK','PLN','HKD','SGD','CNY','JPY','CHF']
    out = {}
    all_syms = [(t, c, s) for (t, c, s) in syms] + [(f, f'FX {f}/USD', f'{f}USD=X') for f in fx]
    for i, (tick, comp, sym) in enumerate(all_syms):
        if sym is None:
            out[tick] = {'error': 'unlisted/no yahoo symbol'}
            continue
        try:
            j = fetch(sym)
            res = (j.get('chart') or {}).get('result')
            if not res:
                err = (j.get('chart') or {}).get('error') or {}
                out[tick] = {'symbol': sym, 'company': comp, 'error': str(err.get('description') or err.get('code') or 'no result')}
            else:
                meta = res[0]['meta']
                out[tick] = {
                    'symbol': sym, 'company': comp,
                    'price': meta.get('regularMarketPrice'),
                    'currency': meta.get('currency'),
                    'time': meta.get('regularMarketTime'),
                    'exchange': meta.get('exchangeName'),
                    'longName': meta.get('longName'),
                }
        except Exception as e:
            out[tick] = {'symbol': sym, 'company': comp, 'error': f'{type(e).__name__}: {e}'}
            if '429' in str(e):
                json.dump(out, open(os.path.join(REPO, 'data', 'etf', 'prices_raw.json'), 'w'), indent=1)
                print(f'RATE LIMITED at {i}/{len(all_syms)}', flush=True)
                return
        time.sleep(1)
        if (i + 1) % 25 == 0:
            print(f'{i+1}/{len(all_syms)} done', flush=True)
    json.dump(out, open(os.path.join(REPO, 'data', 'etf', 'prices_raw.json'), 'w'), indent=1)
    ok = sum(1 for v in out.values() if 'price' in v and v['price'])
    print(f'DONE: {ok}/{len(out)} with prices', flush=True)

main()
