"""
sa_core.py  (V2)
----------------
Shared building blocks for the crypto statistical-arbitrage research:
data loading, the "unconstrained" daily backtest used in class, transaction
costs, and the performance metrics required by the project brief
(return, volatility, Sharpe, max drawdown, alpha / beta, correlation to BTC).

Conventions
===========
* Annualisation follows the class convention: Sharpe = mean / std * sqrt(252),
  annual return = mean * 252, annual volatility = std * sqrt(252), annual
  alpha = daily intercept * 252.  Crypto trades 365 days a year, so these are
  a common yardstick across projects rather than calendar-year figures.
  CAGR is the only calendar measure (compounded over actual calendar years).
* Weights are formed with information up to the close of day t and earn the
  return of day t+1 (positions are lagged one day - no look-ahead).
* "Unconstrained" backtest: gross exposure sum(|w|) = 1 every day; no
  leverage, borrow or capacity constraints.
* Transaction cost = turnover x cost, turnover = sum |w_t - w_{t-1}|.
  Brief: 20 bps all-in for market orders (7 commission + 13 slippage),
  7 bps for limit orders.
* Universe: the 40 largest coins by market cap on 2021-01-03 (stablecoins and
  wrapped tokens excluded) that have price history before the first trade
  date - see src/fetch_data.py and data/universe.csv.  Coins that collapse or
  are delisted leave the cross-section when their price history ends.
"""
import os

import numpy as np
import pandas as pd
import statsmodels.api as sm

RAW = "data/crypto_raw_data.csv"
UNIVERSE_FILE = "data/universe.csv"
ANN = 252              # class convention for annualising Sharpe, return, vol, alpha
CAL_DAYS = 365         # calendar days per year (CAGR only)
MARKET_BPS = 20.0
LIMIT_BPS = 7.0

BT_START = "2021-07-01"      # first trade date
IS_END = "2023-12-31"        # research period ends here - all design decisions use data up to here
OOS_START = "2024-01-01"     # hold-out starts here - never used for any decision


def load_universe():
    u = pd.read_csv(UNIVERSE_FILE)
    return u[u.status == "in universe"].sort_values("cmc_rank").asset.tolist()


UNIVERSE = load_universe() if os.path.exists(UNIVERSE_FILE) else []

# Investment themes (assigned from each project's function, not from returns).
THEME_MAP = {
    "Payments & Privacy": ["BTC", "LTC", "BCH", "BSV", "XRP", "XLM", "DOGE", "DASH", "ZEC", "XMR", "XEM"],
    "Smart-Contract Platforms": ["ETH", "ADA", "DOT", "EOS", "TRX", "XTZ", "ATOM", "NEO", "ETC", "ZIL"],
    "DeFi & Oracle": ["UNI", "AAVE", "SNX", "YFI", "MKR", "COMP", "SUSHI", "LINK"],
    "Exchange & CeFi Tokens": ["BNB", "LEO", "CRO", "HT", "FTT", "CEL"],
    "Data, IoT & Media": ["THETA", "FIL", "VET", "IOTA"],
}
THEMES = {t: [a for a in l if a in UNIVERSE] for t, l in THEME_MAP.items()}
THEMES = {t: l for t, l in THEMES.items() if l}


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def load_panel(path=RAW):
    df = pd.read_csv(path, parse_dates=["date"])
    df = df[df.asset.isin(UNIVERSE)]
    close = df.pivot(index="date", columns="asset", values="close").sort_index()
    vol = df.pivot(index="date", columns="asset", values="volume").sort_index()
    idx = pd.date_range(close.index.min(), close.index.max(), freq="D")
    close = close.reindex(idx).ffill(limit=3)[UNIVERSE]
    vol = vol.reindex(idx)[UNIVERSE]
    # a coin whose history has ended leaves the cross-section (no forward fill)
    last = df.groupby("asset").date.max()
    for a in UNIVERSE:
        close.loc[close.index > last[a], a] = np.nan
    dollar_vol = close * vol
    rets = close.pct_change(fill_method=None)
    return close, rets, dollar_vol


# --------------------------------------------------------------------------- #
# Portfolio construction helpers
# --------------------------------------------------------------------------- #
def normalise(w):
    """Scale each row so gross exposure sum(|w|) = 1 (rows with no signal -> 0)."""
    g = w.abs().sum(axis=1).replace(0, np.nan)
    return w.div(g, axis=0).fillna(0.0)


def cs_weights(signal, direction=1):
    """Cross-sectional dollar-neutral weights proportional to the demeaned
    cross-sectional rank of `signal`.  direction=+1 momentum, -1 reversal."""
    r = signal.rank(axis=1, pct=True)
    r = r.sub(r.mean(axis=1), axis=0)
    return normalise(direction * r)


def ts_weights(signal, vol=None, direction=1):
    """Time-series weights: sign of each asset's own signal, optionally
    inverse-volatility scaled, then gross-normalised."""
    w = direction * np.sign(signal)
    if vol is not None:
        w = w / vol
    return normalise(w.replace([np.inf, -np.inf], np.nan).fillna(0))


def hold(w, h):
    """Overlapping-portfolio holding period (Jegadeesh-Titman): average of the
    last h daily target portfolios.  Cuts turnover roughly by a factor h."""
    if h <= 1:
        return w
    return normalise(w.rolling(h, min_periods=1).mean())


def band(w, threshold):
    """No-trade band: only move a position when the target differs from the
    current holding by more than `threshold` (in weight units)."""
    out = np.zeros_like(w.values)
    cur = np.zeros(w.shape[1])
    tv = np.nan_to_num(w.values)
    for t in range(len(w)):
        diff = tv[t] - cur
        move = np.abs(diff) > threshold
        cur = np.where(move, tv[t], cur)
        cur = np.where(tv[t] == 0, 0.0, cur)     # exited coins are closed
        out[t] = cur
    return pd.DataFrame(out, index=w.index, columns=w.columns)


# --------------------------------------------------------------------------- #
# Backtest
# --------------------------------------------------------------------------- #
def backtest(w, rets, cost_bps=MARKET_BPS, start=BT_START, end=None):
    """Unconstrained daily backtest.  Returns DataFrame(gross, net, turnover)."""
    w = w.reindex(rets.index).fillna(0.0)
    r = rets.reindex(columns=w.columns).fillna(0.0)
    gross = (w.shift(1) * r).sum(axis=1)
    turn = w.diff().abs().sum(axis=1)
    net = gross - turn * cost_bps / 1e4
    out = pd.DataFrame({"gross": gross, "net": net, "turnover": turn})
    return out.loc[start:end] if end else out.loc[start:]


def net_at(bt, cost_bps):
    return bt["gross"] - bt["turnover"] * cost_bps / 1e4


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def sharpe(r):
    """Class convention: mean / std * sqrt(252) on daily returns."""
    r = pd.Series(r).dropna()
    s = r.std()
    return float(r.mean() / s * np.sqrt(ANN)) if s > 0 else np.nan


def max_dd(r):
    cum = (1 + pd.Series(r).fillna(0)).cumprod()
    return float((cum / cum.cummax() - 1).min())


def nw_tstat(r, lags=5):
    r = pd.Series(r).dropna()
    if r.std() == 0 or len(r) < 30:
        return np.nan
    return float(sm.OLS(r.values, np.ones(len(r))).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags}).tvalues[0])


def alpha_beta(r, bench, lags=5):
    """r_t = a + b * bench_t + e_t (daily, Newey-West errors).
    Returns annualised alpha (x252), beta, alpha t-stat and correlation."""
    d = pd.concat([pd.Series(r), pd.Series(bench)], axis=1).dropna()
    if len(d) < 30 or d.iloc[:, 0].std() == 0:
        return np.nan, np.nan, np.nan, np.nan
    m = sm.OLS(d.iloc[:, 0].values, sm.add_constant(d.iloc[:, 1].values)).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags})
    corr = float(np.corrcoef(d.iloc[:, 0], d.iloc[:, 1])[0, 1])
    return float(m.params[0] * ANN), float(m.params[1]), float(m.tvalues[0]), corr


def perf(r, bench=None, name="", turnover=None):
    r = pd.Series(r).fillna(0)
    ann_ret = r.mean() * ANN
    ann_vol = r.std() * np.sqrt(ANN)
    years = len(r) / CAL_DAYS
    cagr = (1 + r).prod() ** (1 / years) - 1 if len(r) else np.nan
    dn = r[r < 0].std() * np.sqrt(ANN)
    dd = max_dd(r)
    out = {"Strategy": name,
           "Ann.Return": ann_ret, "CAGR": cagr, "Ann.Vol": ann_vol,
           "Sharpe": ann_ret / ann_vol if ann_vol else np.nan,
           "Sortino": ann_ret / dn if dn else np.nan,
           "MaxDD": dd, "Calmar": cagr / abs(dd) if dd else np.nan,
           "HitRate": float((r[r != 0] > 0).mean()) if (r != 0).any() else np.nan,
           "t-stat": nw_tstat(r)}
    if bench is not None:
        a, b, ta, c = alpha_beta(r, bench)
        out.update({"Alpha": a, "Beta": b, "Alpha t": ta, "Corr BTC": c})
    if turnover is not None:
        out["Turnover"] = float(pd.Series(turnover).mean())
    return out


def perf_table(series_dict, bench, turnovers=None):
    turnovers = turnovers or {}
    rows = [perf(r, bench, k, turnovers.get(k)) for k, r in series_dict.items()]
    return pd.DataFrame(rows).set_index("Strategy")


def split_sharpes(r):
    """Sharpe in the research period, the hold-out period and the full sample."""
    r = pd.Series(r)
    return {"IS": sharpe(r.loc[:IS_END]), "OOS": sharpe(r.loc[OOS_START:]),
            "Full": sharpe(r)}
