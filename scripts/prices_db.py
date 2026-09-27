#!/usr/bin/env python3
"""DuckDB price cache for the miners database.

Single local database file: <repo>/data/prices.duckdb

Tables
------
tickers(ticker TEXT PRIMARY KEY, kind TEXT, name TEXT, currency TEXT)
    kind is 'miner' or 'etf'; ticker is the Yahoo Finance symbol.
prices(ticker TEXT, date DATE, open/high/low/close/adj_close DOUBLE,
       volume BIGINT, PRIMARY KEY (ticker, date))
    Daily OHLCV bars; adj_close is split/dividend adjusted (Yahoo).
"""
import os

try:
    import duckdb
except ImportError:  # pragma: no cover
    raise SystemExit("duckdb is required: pip install duckdb")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO, 'data', 'prices.duckdb')

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickers (
  ticker   TEXT PRIMARY KEY,
  kind     TEXT,
  name     TEXT,
  currency TEXT
);
CREATE TABLE IF NOT EXISTS prices (
  ticker    TEXT,
  date      DATE,
  open      DOUBLE,
  high      DOUBLE,
  low       DOUBLE,
  close     DOUBLE,
  adj_close DOUBLE,
  volume    BIGINT,
  PRIMARY KEY (ticker, date)
);
"""


def connect(path=DB_PATH):
    con = duckdb.connect(path)
    con.execute(SCHEMA)
    return con


def upsert_tickers(con, rows):
    """rows: iterable of (ticker, kind, name, currency)."""
    con.executemany("INSERT OR REPLACE INTO tickers VALUES (?, ?, ?, ?)", rows)


def upsert_prices(con, rows):
    """rows: iterable of (ticker, date, open, high, low, close, adj_close, volume)."""
    con.executemany("INSERT OR REPLACE INTO prices VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)


def replace_ticker_bars(con, df):
    """Upsert bars from a pandas DataFrame.

    Columns: ticker, date, open, high, low, close, adj_close, volume.
    Deletes only the (ticker, date) pairs present in df, then inserts —
    safe for both full backfills and incremental top-ups. One transaction.
    """
    if df is None or len(df) == 0:
        return 0
    con.execute("BEGIN")
    try:
        con.register("_new_bars", df)
        # delete exactly the overlapping (ticker, date) pairs, then insert
        con.execute("""DELETE FROM prices WHERE (ticker, date) IN
                       (SELECT ticker, CAST(date AS DATE) FROM _new_bars)""")
        con.execute("""INSERT INTO prices
                       SELECT ticker, CAST(date AS DATE), open, high, low, close,
                              adj_close, volume FROM _new_bars""")
        con.unregister("_new_bars")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return len(df)


def max_date(con, ticker):
    row = con.execute("SELECT max(date) FROM prices WHERE ticker = ?", [ticker]).fetchone()
    return row[0] if row else None
    row = con.execute("SELECT max(date) FROM prices WHERE ticker = ?", [ticker]).fetchone()
    return row[0] if row else None


def tickers_with_data(con):
    return [r[0] for r in con.execute(
        "SELECT DISTINCT ticker FROM prices ORDER BY ticker").fetchall()]


def history(con, ticker):
    """Return (currency, [(epoch_day, adj_close), ...]) ascending by date."""
    cur = con.execute("SELECT currency FROM tickers WHERE ticker = ?", [ticker]).fetchone()
    rows = con.execute(
        """SELECT CAST(date AS DATE), adj_close FROM prices
           WHERE ticker = ? AND adj_close IS NOT NULL
           ORDER BY date""", [ticker]).fetchall()
    import datetime
    epoch = datetime.date(1970, 1, 1)
    pts = [( (r[0] - epoch).days, round(float(r[1]), 4)) for r in rows]
    return (cur[0] if cur else None), pts
