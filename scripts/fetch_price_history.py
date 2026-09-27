#!/usr/bin/env python3
"""Fetch daily price history from Yahoo Finance into the local DuckDB cache.

Usage:
    python3 scripts/fetch_price_history.py            # backfill ~5y for all tickers
    python3 scripts/fetch_price_history.py --incremental   # only new bars since max(date)
    python3 scripts/fetch_price_history.py --workers=6        # parallel backfill

Universe: every miner in data/webapp/companies.json (mapped to a Yahoo symbol
with fetch_prices.yahoo_symbol) plus the 12 covered ETFs. Failures are logged
and skipped; on HTTP 429 the run stops early — already-fetched tickers stay in
the DB and the next run resumes incrementally.

Also writes data/ticker_map.json: {company name: yahoo symbol}, used by
scripts/build_website.py to wire charts to the company detail drawer.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_prices import yahoo_symbol  # noqa: E402
import prices_db  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'}
BACKFILL_YEARS = 5
THROTTLE = 0.6

ETF_TICKERS = ['GDX', 'GDXJ', 'SIL', 'SILJ', 'GBUG', 'RING', 'AUAU',
               'SGDM', 'SGDJ', 'GOAU', 'SLVP', 'SLJY']

# Reference metals (spot, USD/oz) — charted in the site header for reference.
METAL_TICKERS = [('GC=F', 'metal', 'Gold (COMEX futures)'),
                 ('SI=F', 'metal', 'Silver (COMEX futures)')]


# Manual corrections where the automatic ticker→Yahoo mapping picks the wrong
# listing (usually the US ticker + a Canadian suffix). Keyed by exact company
# name from companies.json.
SYMBOL_OVERRIDES = {
    "Eldorado Gold Corporation": "ELD.TO",
    "Fortuna Mining Corp.": "FVI.TO",
    "Endeavour Silver Corp.": "EDR.TO",
    "B2Gold Corp.": "BTO.TO",
    "Barrick Mining Corporation": "ABX.TO",
    "Aura Minerals Inc.": "ORA.TO",
    "EMX Royalty Corporation": "EMX",
    "Artemis Gold Inc.": "ARTG.V",
    "Tongguan Gold Group Limited": "0340.HK",
    "Sandstorm Gold Ltd.": "SSL.TO",
    "New Pacific Metals Corp.": "NUAG.TO",
    "Pan American Silver Corp.": "PAAS.TO",
}


def build_universe():
    """Return [(yahoo_symbol, kind, name)]."""
    uni = []
    comps = json.load(open(os.path.join(REPO, 'data', 'webapp', 'companies.json')))
    for r in comps['rows']:
        sym = yahoo_symbol(r)
        sym = SYMBOL_OVERRIDES.get(r['Company'], sym)
        if sym:
            uni.append((sym, 'miner', r['Company']))
    etfs = json.load(open(os.path.join(REPO, 'data', 'webapp', 'etf_methodology.json')))
    ename = {r['ETF Ticker']: r['ETF Name'] for r in etfs['rows']}
    for t in ETF_TICKERS:
        uni.append((t, 'etf', ename.get(t, t)))
    uni.extend(METAL_TICKERS)
    # de-dupe, keep first
    seen, out = set(), []
    for s, k, n in uni:
        if s not in seen:
            seen.add(s)
            out.append((s, k, n))
    return out


def fetch_history(sym, period1, period2):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{urllib.parse.quote(sym, safe='')}?interval=1d"
           f"&period1={period1}&period2={period2}&events=div%2Csplit")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def parse_bars(sym, j):
    res = (j.get('chart') or {}).get('result')
    if not res:
        err = (j.get('chart') or {}).get('error') or {}
        return None, str(err.get('description') or err.get('code') or 'no result'), []
    res = res[0]
    meta = res.get('meta', {})
    ts = res.get('timestamp') or []
    q = ((res.get('indicators') or {}).get('quote') or [{}])[0]
    adj = ((res.get('indicators') or {}).get('adjclose') or [{}])[0].get('adjclose') or []
    bars = []
    for i, t in enumerate(ts):
        d = dt.datetime.fromtimestamp(t, dt.timezone.utc).date()
        def g(k):
            v = (q.get(k) or [])
            return float(v[i]) if i < len(v) and v[i] is not None else None
        av = float(adj[i]) if i < len(adj) and adj[i] is not None else None
        vol = q.get('volume') or []
        v = int(vol[i]) if i < len(vol) and vol[i] is not None else None
        bars.append((d, g('open'), g('high'), g('low'), g('close'), av, v))
    return meta.get('currency'), None, bars


def fetch_one(args):
    """Fetch one ticker. Returns (sym, kind, name, currency, bars, error)."""
    sym, kind, name, p1, p2 = args
    try:
        j = fetch_history(sym, p1, p2)
        ccy, err, bars = parse_bars(sym, j)
        time.sleep(THROTTLE)  # per-request pause: Yahoo soft-blocks (404s) on bursts
        if err:
            return (sym, kind, name, None, [], err)
        return (sym, kind, name, ccy, bars, None)
    except Exception as e:
        time.sleep(THROTTLE)
        return (sym, kind, name, None, [], f"{type(e).__name__}: {e}")


def main():
    incremental = '--incremental' in sys.argv
    workers = 1
    for a in sys.argv:
        if a.startswith('--workers='):
            workers = max(1, int(a.split('=', 1)[1]))
    con = prices_db.connect()
    uni = build_universe()
    print(f"universe: {len(uni)} tickers, workers={workers}", flush=True)

    today = dt.date.today()
    default_p1 = int(dt.datetime(today.year - BACKFILL_YEARS, today.month, today.day,
                                 tzinfo=dt.timezone.utc).timestamp())
    p2 = int(dt.datetime.now(dt.timezone.utc).timestamp()) + 86400

    jobs = []
    for sym, kind, name in uni:
        if incremental:
            md = prices_db.max_date(con, sym)
            p1 = int(dt.datetime(md.year, md.month, md.day,
                                 tzinfo=dt.timezone.utc).timestamp()) if md else default_p1
        else:
            p1 = default_p1
        jobs.append((sym, kind, name, p1, p2))

    ticker_map, done, failed, tick_rows = {}, 0, [], []
    if workers == 1:
        results = []
        for i, job in enumerate(jobs):
            results.append(fetch_one(job))
            if (i + 1) % 10 == 0:
                print(f"{i + 1}/{len(jobs)} tickers fetched", flush=True)
            time.sleep(THROTTLE)
    else:
        from concurrent.futures import ThreadPoolExecutor
        # stagger starts slightly to avoid a thundering herd
        def staggered(job):
            time.sleep(THROTTLE * (hash(job[0]) % 10) / 10)
            return fetch_one(job)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(staggered, jobs))
        print(f"{len(results)}/{len(jobs)} tickers fetched", flush=True)

    # Upsert via pandas DataFrame: DELETE + INSERT in one transaction.
    # (Row-wise INSERT OR REPLACE via executemany is ~1000 rows/sec in
    # duckdb's Python client; the DataFrame path does 32k rows in ~0.1s.)
    import pandas as pd
    bar_rows = []
    for sym, kind, name, ccy, bars, err in results:
        if err:
            failed.append((sym, err))
            continue
        tick_rows.append((sym, kind, name, ccy))
        bar_rows.extend((sym, b[0], b[1], b[2], b[3], b[4], b[5], b[6]) for b in bars)
        if kind == 'miner':
            ticker_map[name] = sym
        done += 1
    prices_db.upsert_tickers(con, tick_rows)
    if bar_rows:
        df = pd.DataFrame(bar_rows, columns=['ticker', 'date', 'open', 'high',
                                             'low', 'close', 'adj_close', 'volume'])
        df['date'] = pd.to_datetime(df['date'])
        df['volume'] = df['volume'].astype('Int64')
        n = prices_db.replace_ticker_bars(con, df)
        print(f"upserted {n} bars for {done} tickers", flush=True)
    con.execute("CHECKPOINT")  # merge WAL into the main file so git commits it all
    # merge with any existing map so incremental runs never lose entries
    mp = os.path.join(REPO, 'data', 'ticker_map.json')
    if os.path.exists(mp):
        old = json.load(open(mp))
        old.update(ticker_map)
        ticker_map = old
    json.dump(ticker_map, open(mp, 'w'), indent=1, sort_keys=True)

    n = con.execute("SELECT count(*), count(DISTINCT ticker) FROM prices").fetchone()
    print(f"DONE: {done} tickers ok, {len(failed)} failed; db holds {n[0]} bars "
          f"for {n[1]} tickers", flush=True)
    for s, e in failed[:15]:
        print(f"  FAIL {s}: {e}")
    con.close()


if __name__ == '__main__':
    main()
