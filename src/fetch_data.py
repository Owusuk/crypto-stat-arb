"""
fetch_data.py
-------------
Download live market data for the project from free public APIs (no key needed).

  1. Daily OHLCV for a universe of liquid USD-quoted crypto assets from the
     Coinbase Exchange public market-data API  -> data/crypto_raw_data.csv
  2. Hourly OHLCV for the same universe (used for the day/night and
     institutional-hours seasonality tests)      -> data/crypto_hourly.csv
  3. Deribit DVOL (30-day implied volatility index) for BTC and ETH, used as
     the implied-vol macro indicator              -> data/dvol.csv

Coinbase is used because, from many jurisdictions, Binance returns HTTP 451
(geo-restricted) while Coinbase serves full daily history back to 2021 and
allows paginated candle requests (max 300 candles/request).

The end date is always "now", so re-running this script refreshes the project
to the latest available data.

Run:  python3 src/fetch_data.py            (daily + DVOL + hourly)
      python3 src/fetch_data.py --no-hourly
"""
import os
import sys
import time
import datetime as dt

import pandas as pd
import requests

BASE = "https://api.exchange.coinbase.com"
HEADERS = {"User-Agent": "wsq-stat-arb-research/2.0"}

UNIVERSE = [
    "BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "AVAX", "LINK",
    "LTC", "DOT", "ATOM", "UNI", "BCH", "XLM", "ALGO", "AAVE", "MKR", "COMP",
]
HOURLY_UNIVERSE = [a for a in UNIVERSE if a not in ("XRP", "MKR")]

START = dt.datetime(2021, 1, 1)
HOURLY_START = dt.datetime(2022, 1, 1)
END = dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)


def get(url, params, tries=5):
    for k in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 429:
                time.sleep(2 + 2 * k); continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if k == tries - 1:
                raise
            time.sleep(2 + 2 * k)


def fetch_product(asset, start, end, gran):
    """Paginate Coinbase candles for one product across [start, end]."""
    product = f"{asset}-USD"
    rows = []
    step = dt.timedelta(seconds=gran * 290)   # max 300 candles/request
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + step, end)
        data = get(f"{BASE}/products/{product}/candles",
                   {"granularity": gran, "start": cursor.isoformat(),
                    "end": chunk_end.isoformat()})
        # Each row: [time, low, high, open, close, volume]
        for t, low, high, op, close, vol in data:
            rows.append({"asset": asset,
                         "date": dt.datetime.utcfromtimestamp(t),
                         "open": op, "high": high, "low": low,
                         "close": close, "volume": vol})
        cursor = chunk_end
        time.sleep(0.2)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.drop_duplicates(subset=["date"]).sort_values("date")


def fetch_daily():
    frames = []
    for asset in UNIVERSE:
        try:
            df = fetch_product(asset, START, END, 86400)
            df["date"] = df["date"].dt.normalize()
            # drop today's still-forming candle so every bar is complete
            df = df[df["date"] < pd.Timestamp(END.date())]
            frames.append(df)
            print(f"{asset:5s} {len(df):5d} daily rows  "
                  f"{df['date'].min().date()} -> {df['date'].max().date()}")
        except Exception as e:
            print(f"{asset:5s} FAILED: {str(e)[:80]}")
    full = pd.concat(frames, ignore_index=True)
    full["date"] = full["date"].dt.strftime("%Y-%m-%d")
    full = full.set_index(["asset", "date"]).sort_index()
    full.to_csv("data/crypto_raw_data.csv")
    print(f"Saved data/crypto_raw_data.csv ({full.shape[0]} rows)")


def fetch_hourly():
    frames = []
    for asset in HOURLY_UNIVERSE:
        try:
            df = fetch_product(asset, HOURLY_START, END, 3600)
            frames.append(df[["asset", "date", "close", "volume"]])
            print(f"{asset:5s} {len(df):6d} hourly rows", flush=True)
        except Exception as e:
            print(f"{asset:5s} hourly FAILED: {str(e)[:80]}", flush=True)
    full = pd.concat(frames, ignore_index=True)
    full.to_csv("data/crypto_hourly.csv", index=False)
    print(f"Saved data/crypto_hourly.csv ({full.shape[0]} rows)")


def fetch_dvol():
    out = []
    url = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
    for ccy in ("BTC", "ETH"):
        rows = []
        end_ms = int(END.timestamp() * 1000)
        start_ms = int(START.timestamp() * 1000)
        while True:
            js = get(url, {"currency": ccy, "start_timestamp": start_ms,
                           "end_timestamp": end_ms, "resolution": "1D"})
            data = js["result"]["data"]
            rows += data
            cont = js["result"].get("continuation")
            if not cont or not data or cont <= start_ms:
                break
            end_ms = cont
            time.sleep(0.2)
        d = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
        d["date"] = pd.to_datetime(d.ts, unit="ms").dt.normalize()
        d = d.drop_duplicates("date").set_index("date").sort_index()["close"]
        out.append(d.rename(f"DVOL_{ccy}"))
        print(f"DVOL {ccy}: {len(d)} days {d.index.min().date()} -> {d.index.max().date()}")
    pd.concat(out, axis=1).to_csv("data/dvol.csv")


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    print(f"Fetching through {END:%Y-%m-%d %H:%M} UTC")
    fetch_daily()
    fetch_dvol()
    if "--no-hourly" not in sys.argv:
        fetch_hourly()
