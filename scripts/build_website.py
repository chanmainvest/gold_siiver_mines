#!/usr/bin/env python3
"""Rebuild the static site (index.html) from data/webapp/*.json + the DuckDB price cache.

index.html is its own template: this script surgically replaces two embedded
blobs and leaves all app code untouched:

  const DATA = {...};            <- rebuilt from data/webapp/*.json
  const PRICE_HISTORY = {...};   <- rebuilt from data/prices.duckdb
  const YAHOO_TICKER = {...};    <- rebuilt from data/ticker_map.json

If PRICE_HISTORY / YAHOO_TICKER consts don't exist yet (older template), they
are inserted right after the DATA statement.

Usage:
    python3 scripts/build_website.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices_db  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(REPO, 'index.html')

# data/webapp/<file> -> DATA key used by the app
DATA_FILES = [
    ('cover.json', 'cover'),
    ('companies.json', 'companies'),
    ('mines.json', 'mines'),
    ('reserves_resources.json', 'reserves'),
    ('cost_structure.json', 'costs'),
    ('royalties_streams.json', 'royalties'),
    ('mine_links.json', 'links'),
    ('etf_holdings.json', 'etfHoldings'),
    ('etf_methodology.json', 'etfMethodology'),
    ('company_financials.json', 'financials'),
]


def find_blob_end(s, start):
    """Given index of '{' starting a JSON blob, return index just past its '}'.

    Brace-matches while respecting JSON strings/escapes.
    """
    assert s[start] == '{'
    depth, instr, esc = 0, False, False
    j = start
    while True:
        c = s[j]
        if instr:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return j + 1
        j += 1


def replace_const(s, name, new_json):
    """Replace `const NAME = {...};` blob with new_json. Returns (new_s, found)."""
    marker = f'const {name}='
    i = s.find(marker)
    if i == -1:
        marker = f'const {name} ='
        i = s.find(marker)
    if i == -1:
        return s, False
    brace = s.find('{', i)
    end = find_blob_end(s, brace)
    assert s[end] == ';', f"expected ';' after const {name} blob"
    return s[:brace] + new_json + s[end:], True


def build_data():
    data = {}
    for fname, key in DATA_FILES:
        with open(os.path.join(REPO, 'data', 'webapp', fname)) as f:
            data[key] = json.load(f)
    return data


def build_price_history():
    con = prices_db.connect()
    try:
        out = {}
        for t in con.execute("SELECT ticker FROM tickers ORDER BY ticker").fetchall():
            sym = t[0]
            ccy, pts = prices_db.history(con, sym)
            if pts:
                out[sym] = {'ccy': ccy, 'p': pts}
        return out
    finally:
        con.close()


def main():
    s = open(HTML, encoding='utf-8').read()

    data_json = json.dumps(build_data(), ensure_ascii=False, separators=(',', ':'))
    s, found = replace_const(s, 'DATA', data_json)
    assert found, 'const DATA not found in index.html'

    ph = build_price_history()
    ph_json = json.dumps(ph, ensure_ascii=False, separators=(',', ':'))
    s, found = replace_const(s, 'PRICE_HISTORY', ph_json)
    if not found:
        # insert after the DATA statement
        i = s.find('const DATA=')
        brace = s.find('{', i)
        end = find_blob_end(s, brace)
        assert s[end] == ';'
        s = s[:end + 1] + '\nconst PRICE_HISTORY=' + ph_json + ';' + s[end + 1:]

    tm_path = os.path.join(REPO, 'data', 'ticker_map.json')
    tm = json.load(open(tm_path)) if os.path.exists(tm_path) else {}
    tm_json = json.dumps(tm, ensure_ascii=False, separators=(',', ':'))
    s, found = replace_const(s, 'YAHOO_TICKER', tm_json)
    if not found:
        i = s.find('const PRICE_HISTORY=')
        brace = s.find('{', i)
        end = find_blob_end(s, brace)
        assert s[end] == ';'
        s = s[:end + 1] + '\nconst YAHOO_TICKER=' + tm_json + ';' + s[end + 1:]

    open(HTML, 'w', encoding='utf-8').write(s)
    print(f"rebuilt {HTML}: {len(ph)} tickers with price history, "
          f"{len(tm)} company ticker mappings, {len(s) / 1e6:.1f} MB")


if __name__ == '__main__':
    main()
