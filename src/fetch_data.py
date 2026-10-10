"""
fetch_data.py  (V2)
-------------------
Builds a survivorship-free universe and downloads its prices.

Universe rule (fixed at the start of the sample, no look-ahead)
---------------------------------------------------------------
Take the CoinMarketCap historical snapshot of 2021-01-03 (the first weekly
snapshot of 2021), drop stablecoins and wrapped / pegged tokens, and keep the
40 largest remaining coins by market capitalisation.  Every coin stays in the
universe for the whole sample - including coins that later collapsed or were
delisted (e.g. Celsius CEL, FTX Token FTT) - until its price history ends.
A coin is dropped only if no free data source has its price at the start of
2021; those drops are recorded in data/universe.csv with the reason.

Prices
------
For every coin, daily candles are requested from three free public APIs:
Coinbase Exchange (USD), KuCoin (USDT) and Bitfinex (USD).  The source with the
earliest start (and then the longest history, then the highest dollar volume)
is chosen, and the same source is used for that coin's hourly candles.
USDT is treated as USD (it traded within a few tenths of a percent of $1).

Outputs
-------
data/universe.csv        rank, market cap, chosen source, coverage, status
data/crypto_raw_data.csv daily OHLCV (long format)
data/crypto_hourly.csv.gz hourly close / volume, 2022 onward
data/dvol.csv            Deribit DVOL implied-volatility index (BTC, ETH)

Run:  python3 src/fetch_data.py [--no-hourly]
"""
import os
import sys
import time
import datetime as dt

import numpy as np
import pandas as pd
import requests

HEADERS = {"User-Agent": "wsq-stat-arb-research/2.0"}
UTC = dt.timezone.utc
START = dt.datetime(2021, 1, 1, tzinfo=UTC)
HOURLY_START = dt.datetime(2022, 1, 1, tzinfo=UTC)
END = dt.datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
LAST_START = pd.Timestamp("2021-07-01")   # must have prices before the first trade date
N_UNIVERSE = 40

# CoinMarketCap historical snapshot, 2021-01-03: (rank, symbol, name, market cap USD).
# Ranks 1-20 carry the published market cap; ranks 21+ are listed in rank order.
CMC_20210103 = [
    (1, "BTC", "Bitcoin", 609409213147), (2, "ETH", "Ethereum", 111309985611),
    (3, "USDT", "Tether", 21340101768), (4, "LTC", "Litecoin", 10610100157),
    (5, "XRP", "XRP", 10254417777), (6, "DOT", "Polkadot", 8995148461),
    (7, "BCH", "Bitcoin Cash", 7845655333), (8, "ADA", "Cardano", 6377915102),
    (9, "BNB", "Binance Coin", 5942182741), (10, "LINK", "Chainlink", 5453374285),
    (11, "USDC", "USD Coin", 4208024428), (12, "WBTC", "Wrapped Bitcoin", 3819401683),
    (13, "BSV", "Bitcoin SV", 3190473984), (14, "XLM", "Stellar", 2989656211),
    (15, "EOS", "EOS", 2625024379), (16, "XMR", "Monero", 2458046205),
    (17, "THETA", "THETA", 2121383112), (18, "TRX", "TRON", 2113567007),
    (19, "XEM", "NEM", 1894334538), (20, "VET", "VeChain", 1667128429),
    (21, "XTZ", "Tezos", None), (22, "CEL", "Celsius", None), (23, "UNI", "Uniswap", None),
    (24, "LEO", "UNUS SED LEO", None), (25, "CRO", "Crypto.com Coin", None),
    (26, "DOGE", "Dogecoin", None), (27, "ATOM", "Cosmos", None), (28, "DAI", "Dai", None),
    (29, "BUSD", "Binance USD", None), (30, "NEO", "Neo", None), (31, "AAVE", "Aave", None),
    (32, "SNX", "Synthetix", None), (33, "REV", "Revain", None), (34, "HT", "Huobi Token", None),
    (35, "FIL", "Filecoin", None), (36, "DASH", "Dash", None), (37, "IOTA", "IOTA", None),
    (38, "ETC", "Ethereum Classic", None), (39, "ZIL", "Zilliqa", None),
    (40, "YFI", "yearn.finance", None), (41, "MKR", "Maker", None), (42, "FTT", "FTX Token", None),
    (43, "COMP", "Compound", None), (44, "ZEC", "Zcash", None), (45, "SUSHI", "SushiSwap", None),
    (46, "KSM", "Kusama", None), (47, "DCR", "Decred", None), (48, "WAVES", "Waves", None),
    (49, "ALGO", "Algorand", None), (50, "UMA", "UMA", None),
]
EXCLUDE = {"USDT": "stablecoin", "USDC": "stablecoin", "DAI": "stablecoin",
           "BUSD": "stablecoin", "WBTC": "wrapped token"}

# venue-specific tickers
BITFINEX_SYM = {"IOTA": "IOT", "DASH": "DSH", "ATOM": "ATO", "VET": "VEE", "BCH": "BCHN",
                "XEM": "XEM", "SNX": "SNX", "CEL": "CEL"}
KUCOIN_SYM = {}


def get(url, params=None, tries=5):
    for k in range(tries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            if r.status_code == 429:
                time.sleep(3 + 3 * k); continue
            if r.status_code >= 400:
                return None
            return r.json()
        except requests.RequestException:
            time.sleep(2 + 2 * k)
    return None


# --------------------------------------------------------------------------- #
# Venue adapters -> DataFrame[date, open, high, low, close, volume]
# --------------------------------------------------------------------------- #
def coinbase(asset, start, end, gran):
    rows, step, cur = [], dt.timedelta(seconds=gran * 290), start
    while cur < end:
        ce = min(cur + step, end)
        js = get(f"https://api.exchange.coinbase.com/products/{asset}-USD/candles",
                 {"granularity": gran, "start": cur.isoformat(), "end": ce.isoformat()})
        if js is None or isinstance(js, dict):
            if not rows and cur == start:
                return pd.DataFrame()
        else:
            rows += [(t, o, h, l, c, v) for t, l, h, o, c, v in js]
        cur = ce
        time.sleep(0.15)
    return _frame(rows, unit="s")


def kucoin(asset, start, end, gran):
    typ = {86400: "1day", 3600: "1hour"}[gran]
    sym = f"{KUCOIN_SYM.get(asset, asset)}-USDT"
    rows, step, cur = [], dt.timedelta(seconds=gran * 1400), start
    while cur < end:
        ce = min(cur + step, end)
        js = get("https://api.kucoin.com/api/v1/market/candles",
                 {"type": typ, "symbol": sym, "startAt": int(cur.timestamp()), "endAt": int(ce.timestamp())})
        if js is None or js.get("code") != "200000":
            if cur == start:
                return pd.DataFrame()
        else:
            rows += [(int(t), float(o), float(h), float(l), float(c), float(v))
                     for t, o, c, h, l, v, _ in js["data"]]
        cur = ce
        time.sleep(0.25)
    return _frame(rows, unit="s")


def bitfinex(asset, start, end, gran):
    tf = {86400: "1D", 3600: "1h"}[gran]
    b = BITFINEX_SYM.get(asset, asset)
    syms = [f"t{b}USD"] if len(b) == 3 else [f"t{b}:USD"]
    rows = []
    for sym in syms:
        cur = int(start.timestamp() * 1000)
        endm = int(end.timestamp() * 1000)
        while cur < endm:
            js = get(f"https://api-pub.bitfinex.com/v2/candles/trade:{tf}:{sym}/hist",
                     {"start": cur, "end": endm, "limit": 10000, "sort": 1})
            if not js or not isinstance(js, list) or (js and not isinstance(js[0], list)):
                break
            rows += [(m // 1000, o, h, l, c, v) for m, o, c, h, l, v in js]
            nxt = js[-1][0] + gran * 1000
            if nxt <= cur or len(js) < 2:
                break
            cur = nxt
            time.sleep(1.2)          # Bitfinex public limit ~ 30-60 req/min
        if rows:
            break
    return _frame(rows, unit="s")


def gate(asset, start, end, gran):
    iv = {86400: "1d", 3600: "1h"}[gran]
    rows, step, cur = [], dt.timedelta(seconds=gran * 900), start
    while cur < end:
        ce = min(cur + step, end)
        js = get("https://api.gateio.ws/api/v4/spot/candlesticks",
                 {"currency_pair": f"{asset}_USDT", "interval": iv,
                  "from": int(cur.timestamp()), "to": int(ce.timestamp())})
        if isinstance(js, list):
            # [t, quote_volume, close, high, low, open, base_volume, closed]
            rows += [(int(r[0]), float(r[5]), float(r[3]), float(r[4]), float(r[2]), float(r[6]))
                     for r in js]
        elif cur == start and gran == 86400:
            return pd.DataFrame()
        cur = ce
        time.sleep(0.25)
    return _frame(rows, unit="s")


def _frame(rows, unit):
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["t", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df.t, unit=unit)
    df = df.drop(columns="t").drop_duplicates("date").sort_values("date")
    return df[df.close > 0]


VENUES = {"coinbase": coinbase, "kucoin": kucoin, "gate": gate, "bitfinex": bitfinex}


def choose_source(asset):
    best = None
    for name, fn in VENUES.items():
        try:
            df = fn(asset, START, END, 86400)
        except Exception as e:                     # noqa: BLE001
            print(f"   {asset} {name} error {str(e)[:60]}")
            continue
        if df.empty:
            continue
        df["date"] = df["date"].dt.normalize()
        df = df[df["date"] < pd.Timestamp(END.date())]
        first, last = df.date.min(), df.date.max()
        dvol = float((df.close * df.volume).median())
        score = (first > pd.Timestamp("2021-01-07"), -len(df), -dvol)
        print(f"   {asset:6s} {name:9s} {first.date()} -> {last.date()}  {len(df):5d} days  med $vol {dvol:,.0f}")
        if best is None or score < best[0]:
            best = (score, name, df)
    return best


def build_universe():
    rows, frames = [], []
    elig = [(r, s, n, m) for r, s, n, m in CMC_20210103 if s not in EXCLUDE]
    for r, s, n, m in CMC_20210103:
        if s in EXCLUDE:
            rows.append({"cmc_rank": r, "asset": s, "name": n, "mcap_usd": m, "status": "excluded",
                         "reason": EXCLUDE[s]})
    for r, s, n, m in elig[:N_UNIVERSE]:
        best = choose_source(s)
        rec = {"cmc_rank": r, "asset": s, "name": n, "mcap_usd": m}
        if best is None:
            rec.update(status="dropped", reason="no free price history found")
        else:
            _, src, df = best
            first, last = df.date.min(), df.date.max()
            if first >= LAST_START:
                rec.update(status="dropped", reason=f"history starts {first.date()} (after first trade date)",
                           source=src, first=first.date(), last=last.date())
            else:
                active = last >= pd.Timestamp(END.date()) - pd.Timedelta(days=5)
                rec.update(status="in universe", reason="" if active else "history ends (delisted / collapsed)",
                           source=src, first=first.date(), last=last.date(), days=len(df),
                           median_dollar_volume=float((df.close * df.volume).median()))
                df = df.assign(asset=s)
                frames.append(df)
        rows.append(rec)
    uni = pd.DataFrame(rows).sort_values("cmc_rank")
    uni.to_csv("data/universe.csv", index=False)
    full = pd.concat(frames, ignore_index=True)
    full["date"] = full["date"].dt.strftime("%Y-%m-%d")
    full[["asset", "date", "open", "high", "low", "close", "volume"]].sort_values(["asset", "date"]) \
        .to_csv("data/crypto_raw_data.csv", index=False)
    n_in = (uni.status == "in universe").sum()
    print(f"\nUniverse: {n_in} coins in, {(uni.status == 'dropped').sum()} dropped, "
          f"{(uni.status == 'excluded').sum()} excluded -> data/universe.csv")
    return uni


def _hourly_best(asset, first_choice):
    """Hourly candles from the coin's daily source; if that venue's hourly
    history is short (Gate.io keeps ~10,000 bars), use the longest venue."""
    df = VENUES[first_choice](asset, HOURLY_START, END, 3600)
    expected = (END - HOURLY_START).total_seconds() / 3600
    src = first_choice
    if len(df) < 0.7 * expected:
        for name, fn in VENUES.items():
            if name == first_choice:
                continue
            alt = fn(asset, HOURLY_START, END, 3600)
            if len(alt) > len(df):
                df, src = alt, name
    return df, src


def fetch_hourly(uni=None, only=None):
    uni = uni if uni is not None else pd.read_csv("data/universe.csv")
    uni = uni[uni.status == "in universe"]
    if only is not None:
        uni = uni[uni.asset.isin(only)]
    frames = []
    for _, r in uni.iterrows():
        df, src = _hourly_best(r.asset, r.source)
        if df.empty:
            print(f"   {r.asset} hourly: none"); continue
        frames.append(df.assign(asset=r.asset)[["asset", "date", "close", "volume"]])
        print(f"   {r.asset:6s} {src:9s} {len(df):6d} hourly rows", flush=True)
    out = pd.concat(frames, ignore_index=True)
    if only is not None and os.path.exists("data/crypto_hourly.csv.gz"):
        old = pd.read_csv("data/crypto_hourly.csv.gz", parse_dates=["date"])
        out = pd.concat([old[~old.asset.isin(only)], out], ignore_index=True)
    out.to_csv("data/crypto_hourly.csv.gz", index=False)


def fetch_dvol():
    out = []
    url = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
    for ccy in ("BTC", "ETH"):
        rows, end_ms, start_ms = [], int(END.timestamp() * 1000), int(START.timestamp() * 1000)
        while True:
            js = get(url, {"currency": ccy, "start_timestamp": start_ms,
                           "end_timestamp": end_ms, "resolution": "1D"})
            data = js["result"]["data"]
            rows += data
            cont = js["result"].get("continuation")
            if not cont or not data or cont <= start_ms:
                break
            end_ms = cont
        d = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
        d["date"] = pd.to_datetime(d.ts, unit="ms").dt.normalize()
        out.append(d.drop_duplicates("date").set_index("date").sort_index()["close"].rename(f"DVOL_{ccy}"))
    pd.concat(out, axis=1).to_csv("data/dvol.csv")


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    print(f"Fetching through {END:%Y-%m-%d %H:%M} UTC")
    u = build_universe()
    fetch_dvol()
    if "--no-hourly" not in sys.argv:
        fetch_hourly(u)
