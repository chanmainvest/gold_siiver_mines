import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#!/usr/bin/env python3
"""Re-fetch prices with corrected symbols; move FX to separate file."""
import json, time, urllib.request, urllib.parse, os

BASE = 'REPO'
d = json.load(open(os.path.join(REPO, 'data', 'etf', 'prices_raw.json')))

# separate FX entries (keys are 3-letter currency codes) from company entries
fx_keys = ['CAD','AUD','GBP','EUR','MXN','KRW','IDR','PHP','BRL','CLP','PEN','ZAR','TRY','SEK','PLN','HKD','SGD','CNY','JPY','CHF']
fx = {}
for k in fx_keys:
    if k in d and d[k].get('symbol', '').endswith('USD=X'):
        fx[k] = d.pop(k)
json.dump(fx, open(os.path.join(BASE, 'fx_raw.json'), 'w'), indent=1)
print('fx saved:', {k: v.get('price') for k, v in fx.items() if v.get('price')})

REFETCH = {
    'AG': 'AG', 'AGI': 'AGI', 'AUGO': 'AUGO', 'B': 'B', 'BTG': 'BTG', 'BVN': 'BVN',
    'CG': 'CG', 'EGO': 'EGO', 'ELE': 'ELEA', 'EMX': 'EMX', 'EQX': 'EQX',
    'EXK': 'EXK', 'FNV': 'FNV', 'FSM': 'FSM', 'IAG': 'IAG', 'IDR': 'IDR',
    'MAG': 'MAG', 'MTA': 'MTA', 'NEWP': 'NEWP', 'NGD': 'NGD', 'OR': 'OR',
    'PAAS': 'PAAS', 'SAND': 'SAND', 'SKE': 'SKE', 'SSRM': 'SSRM', 'SVM': 'SVM',
    'VMET': 'VMET', 'VOXR': 'VOXR', 'WPM': 'WPM', 'WRN': 'WRN',
    'ARTG': 'ARTG.V', '340': '0340.HK', 'BNKR': 'BNKR.CN', 'DV': 'DV.V',
    'SLVR': 'SLVR.V', 'MFRISCO': 'MFRISCOA.MX',
}

def fetch(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym, safe='')}" \
          f"?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

for tick, sym in REFETCH.items():
    try:
        j = fetch(sym)
        res = (j.get('chart') or {}).get('result')
        old = d.get(tick, {})
        if not res:
            err = (j.get('chart') or {}).get('error') or {}
            d[tick] = {**old, 'symbol': sym,
                       'error': str(err.get('description') or err.get('code') or 'no result')}
        else:
            meta = res[0]['meta']
            d[tick] = {'symbol': sym, 'company': old.get('company'),
                       'price': meta.get('regularMarketPrice'), 'currency': meta.get('currency'),
                       'time': meta.get('regularMarketTime'), 'exchange': meta.get('exchangeName'),
                       'longName': meta.get('longName')}
        print(tick, sym, '->', d[tick].get('price'), d[tick].get('currency'),
              str(d[tick].get('error', ''))[:60])
    except Exception as e:
        print(tick, sym, 'EXC', str(e)[:80])
        if '429' in str(e):
            print('RATE LIMITED - stopping')
            break
    time.sleep(1)

json.dump(d, open(os.path.join(REPO, 'data', 'etf', 'prices_raw.json'), 'w'), indent=1)
ok = sum(1 for v in d.values() if v.get('price'))
print(f'DONE: {ok}/{len(d)} with prices')
