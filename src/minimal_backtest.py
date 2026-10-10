"""
minimal_backtest.py - the whole backtest in ~60 lines of plain pandas / numpy.

Purpose: show (and check) that the research engine does nothing more than
this.  It rebuilds one strategy from scratch - cross-sectional reversal on the
60-day return, skipping the last 14 days, held 14 days - and then asserts that
the result matches src/sa_core.py to machine precision.

Run:  python3 src/minimal_backtest.py
"""
import numpy as np
import pandas as pd

L, SKIP, HOLD, COST_BPS = 60, 14, 14, 7      # look-back, skip, holding period, cost per unit turnover
START, IS_END, OOS_START = "2021-07-01", "2023-12-31", "2024-01-01"

# 1. Prices: one column per coin, one row per calendar day ------------------
uni = pd.read_csv("data/universe.csv").query("status == 'in universe'").asset.tolist()
raw = pd.read_csv("data/crypto_raw_data.csv", parse_dates=["date"])
raw = raw[raw.asset.isin(uni)]
px = raw.pivot(index="date", columns="asset", values="close")
px = px.reindex(pd.date_range(px.index.min(), px.index.max(), freq="D")).ffill(limit=3)[uni]
last_day = raw.groupby("asset").date.max()
for a in uni:                                  # a coin that stops trading leaves the universe
    px.loc[px.index > last_day[a], a] = np.nan
ret = px.pct_change(fill_method=None)

# 2. Signal: return from t-60 to t-14 (known at the close of day t) ---------
signal = px.shift(SKIP) / px.shift(L) - 1

# 3. Weights: demeaned cross-sectional rank, reversal sign, gross exposure 1 -
rank = signal.rank(axis=1, pct=True)
w = -(rank.sub(rank.mean(axis=1), axis=0))
w = w.div(w.abs().sum(axis=1), axis=0).fillna(0)

# 4. Holding period: average of the last 14 daily target portfolios ---------
w = w.rolling(HOLD, min_periods=1).mean()
w = w.div(w.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(0)

# 5. P&L: yesterday's weights x today's returns, minus cost on turnover -----
gross = (w.shift(1) * ret.fillna(0)).sum(axis=1)
turnover = w.diff().abs().sum(axis=1)
net = (gross - turnover * COST_BPS / 1e4).loc[START:]

# 6. Metrics (class convention: x252 / sqrt(252)) ---------------------------
def sharpe(r):
    return r.mean() / r.std() * np.sqrt(252)

btc = ret["BTC"].reindex(net.index)
X = np.column_stack([np.ones(len(net)), btc.fillna(0).values])
alpha_d, beta = np.linalg.lstsq(X, net.values, rcond=None)[0]
cum = (1 + net).cumprod()
print(f"Reversal L={L} skip={SKIP} hold={HOLD} at {COST_BPS} bps")
print(f"  Sharpe full {sharpe(net):.3f} | research {sharpe(net.loc[:IS_END]):.3f} | hold-out {sharpe(net.loc[OOS_START:]):.3f}")
print(f"  ann. return {net.mean() * 252:.1%} | ann. vol {net.std() * np.sqrt(252):.1%} | "
      f"max DD {(cum / cum.cummax() - 1).min():.1%}")
print(f"  alpha {alpha_d * 252:.1%}/yr | beta {beta:.3f} | corr BTC {np.corrcoef(net, btc.fillna(0))[0, 1]:.3f}")
print(f"  avg daily turnover {turnover.loc[START:].mean():.3f}")

# 7. Cross-check against the research engine --------------------------------
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import sa_core as C
close, rets, _ = C.load_panel()
w_engine = C.hold(C.cs_weights(close.shift(SKIP) / close.shift(L) - 1, -1), HOLD)
net_engine = C.net_at(C.backtest(w_engine, rets), COST_BPS)
diff = (net - net_engine).abs().max()
assert diff < 1e-12, diff
print(f"  matches sa_core engine (max daily difference {diff:.1e})")
