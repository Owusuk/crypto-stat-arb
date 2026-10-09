"""
statarb.py
----------
Walk-forward cointegration statistical-arbitrage engine for crypto markets.

Why walk-forward?  Cointegration relationships in crypto are not stable for
years at a time; a pair that co-moves in 2021-22 can decouple in 2024.  So
instead of selecting pairs once and freezing them, we re-screen the universe on
a rolling FORMATION window and only trade the pairs that are *currently*
cointegrated.  Every trade still uses information available strictly before the
trade date, so there is no look-ahead.

Pipeline per rolling step
=========================
1.  FORMATION (look-back of `FORM_DAYS`): Engle-Granger cointegration p-value,
    OLS hedge ratio, Ornstein-Uhlenbeck half-life, Hurst exponent.  Keep the
    pairs that pass all filters; carry them into the next `STEP_DAYS` of trading.
2.  TRADING: a Kalman filter run *continuously* over the whole sample estimates
    a time-varying hedge ratio online; its standardised one-step forecast error
    is the z-score.  A z-score state machine produces dollar-neutral positions,
    but a pair only contributes P&L on days when it is in the active set.
3.  COSTS: linear transaction costs on leg turnover.
4.  BENCHMARKS: buy-&-hold BTC, equal-weight basket, vol-scaled time-series
    momentum, cross-sectional momentum.
5.  ANALYTICS: Sharpe, Sortino, max drawdown, Calmar, hit-rate (active days),
    Newey-West t-stat, market beta (neutrality check), turnover, trade count.

Run:  python3 src/statarb.py
"""
import os
import json
import itertools

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["axes.unicode_minus"] = False
from statsmodels.tsa.stattools import coint, adfuller
import statsmodels.api as sm

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
RAW, FIGDIR, DATADIR = "data/crypto_raw_data.csv", "figures", "data"
ANN = 365                          # crypto trades every calendar day

# Universe: drop XRP (long Coinbase listing gap) and MKR (delisted Jan-2026).
UNIVERSE = ["BTC", "ETH", "SOL", "ADA", "DOGE", "AVAX", "LINK", "LTC",
            "DOT", "ATOM", "UNI", "BCH", "XLM", "ALGO", "AAVE", "COMP"]

# Walk-forward windows.  Crypto cointegration relationships decay quickly, so we
# use a shorter formation look-back and re-screen monthly (rather than quarterly)
# and only keep fast mean-reverting spreads.
FORM_DAYS = 180                    # ~6m formation look-back
STEP_DAYS = 21                     # re-screen ~monthly
OOS_START = "2022-01-01"           # first tradeable date (>=1 formation window)

# Pair-selection filters (applied each formation window)
PVAL_MAX = 0.05
HALFLIFE_MIN, HALFLIFE_MAX = 2, 20   # only fast reverters survive crypto costs
HURST_MAX = 0.5
CORR_MIN = 0.5
MAX_PAIRS = 15                     # cap concurrent pairs (lowest p-value first)

# Kalman filter hyper-parameters (Chan, Algorithmic Trading, 2013)
DELTA, VE = 1e-4, 1e-3

# Trading rule
Z_ENTRY, Z_EXIT, Z_STOP = 2.0, 0.5, 4.0
COST_BPS = 20.0                    # brief: 20 bps all-in for market orders (per unit turnover)
TARGET_VOL = 0.10                  # vol-target overlay
FIGSIZE = (11, 5)


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def load_panel():
    df = pd.read_csv(RAW, parse_dates=["date"])
    df = df[df.asset.isin(UNIVERSE)]
    close = df.pivot(index="date", columns="asset", values="close").sort_index()
    full_idx = pd.date_range(close.index.min(), close.index.max(), freq="D")
    close = close.reindex(full_idx).ffill(limit=3)   # bridge tiny gaps only
    close = close[UNIVERSE]
    logp = np.log(close)
    rets = close.pct_change()
    return close, logp, rets


# --------------------------------------------------------------------------- #
# Pair-selection statistics
# --------------------------------------------------------------------------- #
def half_life(spread: pd.Series) -> float:
    s = spread.dropna()
    if len(s) < 30:
        return np.inf
    lag = s.shift(1)
    delta = s - lag
    d = pd.concat([delta, lag], axis=1).dropna()
    beta = np.polyfit(d.iloc[:, 1].values, d.iloc[:, 0].values, 1)[0]
    return np.inf if beta >= 0 else -np.log(2) / beta


def hurst(ts: np.ndarray) -> float:
    ts = np.asarray(ts, float)
    lags = range(2, 40)
    tau = [np.std(ts[lag:] - ts[:-lag]) for lag in lags]
    tau = np.array(tau)
    if np.any(tau <= 0):
        return np.nan
    return np.polyfit(np.log(list(lags)), np.log(tau), 1)[0]


def screen_window(logp_win, rets_win):
    """Return the list of pairs that pass all filters in this formation window."""
    cols = [c for c in logp_win.columns if logp_win[c].notna().sum() >= FORM_DAYS - 5]
    rmat = rets_win[cols].corr()
    rows = []
    for a, b in itertools.combinations(cols, 2):
        sub = pd.concat([logp_win[a], logp_win[b]], axis=1).dropna()
        if len(sub) < FORM_DAYS - 5:
            continue
        x, y = sub[a], sub[b]
        rho = rmat.loc[a, b]
        if not np.isfinite(rho) or rho < CORR_MIN:
            continue
        try:
            _, pval, _ = coint(y, x)
        except Exception:
            continue
        if pval >= PVAL_MAX:
            continue
        ols = sm.OLS(y, sm.add_constant(x)).fit()
        beta = ols.params[a]
        spread = y - (ols.params["const"] + beta * x)
        hl, hu = half_life(spread), hurst(spread.values)
        if not (HALFLIFE_MIN <= hl <= HALFLIFE_MAX) or not (hu < HURST_MAX):
            continue
        rows.append({"pair": f"{b}-{a}", "asset_y": b, "asset_x": a,
                     "eg_pvalue": pval, "corr": rho, "beta_ols": beta,
                     "half_life": hl, "hurst": hu})
    rows = sorted(rows, key=lambda r: r["eg_pvalue"])[:MAX_PAIRS]
    return rows


# --------------------------------------------------------------------------- #
# Kalman dynamic hedge ratio (run once, online, over the full sample)
# --------------------------------------------------------------------------- #
def kalman_spread(y: pd.Series, x: pd.Series):
    n = len(y)
    Vw = DELTA / (1 - DELTA) * np.eye(2)
    beta = np.zeros(2)
    P = np.zeros((2, 2))
    z = np.full(n, np.nan); b_s = np.full(n, np.nan); e_s = np.full(n, np.nan)
    yv, xv = y.values, x.values
    for t in range(n):
        if not (np.isfinite(yv[t]) and np.isfinite(xv[t])):
            b_s[t] = beta[1]; continue
        F = np.array([1.0, xv[t]])
        R = P + Vw
        e = yv[t] - F @ beta
        Q = F @ R @ F + VE
        K = R @ F / Q
        beta = beta + K * e
        P = R - np.outer(K, F) @ R
        z[t], b_s[t], e_s[t] = e / np.sqrt(Q), beta[1], e
    idx = y.index
    return pd.Series(z, idx), pd.Series(b_s, idx), pd.Series(e_s, idx)


def zscore_positions(z: pd.Series) -> pd.Series:
    pos = np.zeros(len(z)); cur = 0; zv = z.values
    for t in range(len(z)):
        zt = zv[t]
        if not np.isfinite(zt):
            pos[t] = cur; continue
        if abs(zt) >= Z_STOP:
            cur = 0
        elif cur == 0:
            cur = 1 if zt <= -Z_ENTRY else (-1 if zt >= Z_ENTRY else 0)
        elif cur == 1 and zt >= -Z_EXIT:
            cur = 0
        elif cur == -1 and zt <= Z_EXIT:
            cur = 0
        pos[t] = cur
    return pd.Series(pos, z.index)


def pair_pnl(asset_y, asset_x, logp, rets):
    """Continuous Kalman P&L for one pair over the full sample (gross & net)."""
    y, x = logp[asset_y], logp[asset_x]
    z, beta_t, _ = kalman_spread(y, x)
    pos = zscore_positions(z)
    bt = beta_t.clip(-5, 5).fillna(0)
    denom = (1 + bt.abs()).replace(0, np.nan)
    w_y = pos / denom
    w_x = -pos * bt / denom
    w_y_lag, w_x_lag = w_y.shift(1).fillna(0), w_x.shift(1).fillna(0)
    gross = (w_y_lag * rets[asset_y] + w_x_lag * rets[asset_x]).fillna(0)
    turn = (w_y.diff().abs() + w_x.diff().abs()).fillna(0)
    net = gross - turn * (COST_BPS / 1e4)
    return pd.DataFrame({"z": z, "pos": pos, "gross": gross,
                         "net": net, "turnover": turn})


# --------------------------------------------------------------------------- #
# Walk-forward driver
# --------------------------------------------------------------------------- #
def walk_forward(close, logp, rets):
    dates = close.index
    oos_dates = dates[dates >= OOS_START]
    # Pre-compute Kalman P&L for every possible pair once.
    all_pairs = list(itertools.combinations(UNIVERSE, 2))
    pnl_cache = {}
    selection_log = []
    # selection mask: date -> set of active pair keys "y-x"
    active = pd.Series([set() for _ in range(len(dates))], index=dates)

    start = dates.get_indexer([oos_dates[0]])[0]
    step_starts = range(start, len(dates), STEP_DAYS)
    for s in step_starts:
        form_lo = max(0, s - FORM_DAYS)
        form_hi = s
        if form_hi - form_lo < FORM_DAYS - 5:
            continue
        logp_win = logp.iloc[form_lo:form_hi]
        rets_win = rets.iloc[form_lo:form_hi]
        chosen = screen_window(logp_win, rets_win)
        trade_lo, trade_hi = s, min(s + STEP_DAYS, len(dates))
        trade_idx = dates[trade_lo:trade_hi]
        keys = [c["pair"] for c in chosen]
        for d in trade_idx:
            active.loc[d] = set(keys)
        selection_log.append({"formation_end": str(dates[form_hi - 1].date()),
                              "n_pairs": len(chosen), "pairs": keys})
        for c in chosen:
            key = c["pair"]
            if key not in pnl_cache:
                pnl_cache[key] = pair_pnl(c["asset_y"], c["asset_x"], logp, rets)

    # Build portfolio: each active pair gets equal weight that day.
    gross = pd.Series(0.0, index=oos_dates)
    net = pd.Series(0.0, index=oos_dates)
    turn = pd.Series(0.0, index=oos_dates)
    n_active = pd.Series(0, index=oos_dates)
    for d in oos_dates:
        keys = active.loc[d]
        if not keys:
            continue
        w = 1.0 / len(keys)
        g = n = tn = 0.0
        for k in keys:
            p = pnl_cache.get(k)
            if p is None or d not in p.index:
                continue
            g += w * p.at[d, "gross"]
            n += w * p.at[d, "net"]
            tn += w * p.at[d, "turnover"]
        gross.at[d], net.at[d], turn.at[d], n_active.at[d] = g, n, tn, len(keys)

    return gross, net, turn, n_active, selection_log, pnl_cache, active


# --------------------------------------------------------------------------- #
# Benchmarks
# --------------------------------------------------------------------------- #
def bench_ts_momentum(close, rets, oos_idx):
    sig = (0.4 * close.pct_change(7) + 0.35 * close.pct_change(14)
           + 0.25 * close.pct_change(28))
    vol = rets.rolling(20, min_periods=10).std() * np.sqrt(ANN)
    pos = (np.sign(sig) * (TARGET_VOL / vol.clip(lower=0.05))).clip(-2, 2)
    gross = (pos.shift(1) * rets).mean(axis=1)
    cost = (pos.diff().abs() * (COST_BPS / 1e4)).mean(axis=1)   # charge turnover
    return (gross - cost).reindex(oos_idx).fillna(0)


def bench_cs_momentum(close, rets, oos_idx):
    rank = close.pct_change(28).rank(axis=1, pct=True)
    pos = pd.DataFrame(0.0, index=rank.index, columns=rank.columns)
    pos[rank >= 0.8] = 1.0; pos[rank <= 0.2] = -1.0
    pos = pos.div(pos.abs().sum(axis=1).replace(0, np.nan), axis=0)
    gross = (pos.shift(1) * rets).sum(axis=1)
    cost = (pos.diff().abs() * (COST_BPS / 1e4)).sum(axis=1)     # charge turnover
    return (gross - cost).reindex(oos_idx).fillna(0)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def metrics(r, bench=None, name="", active_mask=None):
    r = r.fillna(0)
    if r.std() == 0:
        return {"Strategy": name}
    cum = (1 + r).cumprod()
    ann_ret = cum.iloc[-1] ** (ANN / len(r)) - 1
    ann_vol = r.std() * np.sqrt(ANN)
    sharpe = ann_ret / ann_vol if ann_vol else 0
    dn = r[r < 0].std() * np.sqrt(ANN)
    sortino = ann_ret / dn if dn else 0
    dd = (cum / cum.cummax() - 1).min()
    calmar = ann_ret / abs(dd) if dd else 0
    act = r[r != 0] if active_mask is None else r[active_mask]
    hit = (act > 0).mean() if len(act) else np.nan
    tstat = sm.OLS(r.values, np.ones((len(r), 1))).fit(
        cov_type="HAC", cov_kwds={"maxlags": 5}).tvalues[0]
    out = {"Strategy": name, "Ann.Return": ann_ret, "Ann.Vol": ann_vol,
           "Sharpe": sharpe, "Sortino": sortino, "MaxDD": dd, "Calmar": calmar,
           "HitRate": hit, "t-stat": tstat}
    if bench is not None:
        c = r.index.intersection(bench.index)
        b = bench.reindex(c).fillna(0); rr = r.reindex(c).fillna(0)
        if b.std() > 0:
            out["MktBeta"] = np.cov(rr, b)[0, 1] / np.var(b)
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    os.makedirs(FIGDIR, exist_ok=True); os.makedirs(DATADIR, exist_ok=True)
    close, logp, rets = load_panel()
    print(f"Panel: {close.shape[1]} assets, {close.shape[0]} days "
          f"({close.index.min().date()} -> {close.index.max().date()})")

    gross, net, turn, n_active, sel_log, pnl_cache, active = \
        walk_forward(close, logp, rets)
    oos_idx = net.index
    print(f"OOS: {oos_idx.min().date()} -> {oos_idx.max().date()} "
          f"({len(oos_idx)} days)")

    # vol-target overlay
    realised = net.rolling(30, min_periods=15).std() * np.sqrt(ANN)
    lever = (TARGET_VOL / realised.shift(1)).clip(upper=3).fillna(1)
    net_vt = (net * lever).fillna(0)

    # benchmarks on identical OOS window
    bh = rets["BTC"].reindex(oos_idx).fillna(0)
    ew = rets.mean(axis=1).reindex(oos_idx).fillna(0)
    tsm = bench_ts_momentum(close, rets, oos_idx)
    csm = bench_cs_momentum(close, rets, oos_idx)

    strat = pd.DataFrame({
        "StatArb (Kalman, gross)": gross, "StatArb (Kalman, net)": net,
        "StatArb (vol-targeted)": net_vt, "TS Momentum": tsm,
        "CS Momentum": csm, "Equal-Weight B&H": ew, "Buy & Hold BTC": bh,
    }).fillna(0)
    strat.to_csv(f"{DATADIR}/strategy_returns.csv")
    pd.DataFrame({"gross": gross, "net": net, "turnover": turn,
                  "n_active": n_active}).to_csv(f"{DATADIR}/coint_daily.csv")

    active_days = (n_active > 0)
    table = [
        metrics(gross, ew, "StatArb (Kalman, gross)", active_days),
        metrics(net, ew, "StatArb (Kalman, net)", active_days),
        metrics(net_vt, ew, "StatArb (vol-targeted, net)", active_days),
        metrics(tsm, ew, "TS Momentum (net)"),
        metrics(csm, ew, "CS Momentum (net)"),
        metrics(ew, bh, "Equal-Weight B&H"),
        metrics(bh, bh, "Buy & Hold BTC"),
    ]
    perf = pd.DataFrame(table).set_index("Strategy")
    perf.to_csv(f"{DATADIR}/backtest_performance.csv")

    # selection diagnostics
    pd.DataFrame(sel_log).to_csv(f"{DATADIR}/selection_log.csv", index=False)
    pair_freq = {}
    for rec in sel_log:
        for k in rec["pairs"]:
            pair_freq[k] = pair_freq.get(k, 0) + 1
    freq_df = (pd.Series(pair_freq, name="windows_selected")
               .sort_values(ascending=False).to_frame())
    freq_df["pct_of_windows"] = (freq_df.windows_selected / len(sel_log)).round(3)
    freq_df.to_csv(f"{DATADIR}/pair_frequency.csv")

    summary = {
        "n_assets": int(close.shape[1]),
        "oos_start": str(oos_idx.min().date()),
        "oos_end": str(oos_idx.max().date()),
        "oos_days": int(len(oos_idx)),
        "n_formation_windows": len(sel_log),
        "avg_pairs_per_window": round(np.mean([r["n_pairs"] for r in sel_log]), 2),
        "unique_pairs_traded": len(pair_freq),
        "avg_daily_turnover": round(float(turn.mean()), 4),
        "avg_active_pairs": round(float(n_active[n_active > 0].mean()), 2),
        "cost_bps_per_leg": COST_BPS,
        "form_days": FORM_DAYS, "step_days": STEP_DAYS,
        "z_entry": Z_ENTRY, "z_exit": Z_EXIT, "z_stop": Z_STOP,
    }
    with open(f"{DATADIR}/run_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n=== OOS performance ===")
    print(perf.round(3).to_string())
    print("\n=== run summary ===")
    print(json.dumps(summary, indent=2))
    print("\nMost-selected pairs:")
    print(freq_df.head(12).to_string())

    make_figures(strat, net, n_active, freq_df, pnl_cache, logp, sel_log)
    print(f"\nFigures -> {FIGDIR}/")


def make_figures(strat, net, n_active, freq_df, pnl_cache, logp, sel_log):
    # 1. equity curves
    plt.figure(figsize=FIGSIZE)
    for c in ["StatArb (Kalman, net)", "StatArb (vol-targeted)", "TS Momentum",
              "CS Momentum", "Equal-Weight B&H", "Buy & Hold BTC"]:
        (1 + strat[c]).cumprod().plot(label=c, linewidth=1.6)
    plt.yscale("log"); plt.title("Out-of-Sample Growth of $1 (log scale)")
    plt.ylabel("Growth of $1"); plt.legend(fontsize=8); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(f"{FIGDIR}/equity_curves.png", dpi=140); plt.close()

    # 2. drawdown
    cum = (1 + net).cumprod(); dd = cum / cum.cummax() - 1
    plt.figure(figsize=FIGSIZE)
    plt.fill_between(dd.index, dd.values, 0, color="firebrick", alpha=0.4)
    plt.title("Statistical Arbitrage Portfolio - Drawdown (net)")
    plt.ylabel("Drawdown"); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(f"{FIGDIR}/drawdown.png", dpi=140); plt.close()

    # 3. example pair z-score + pnl
    if freq_df.shape[0]:
        key = freq_df.index[0]
        p = pnl_cache[key]
        fig, ax = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
        p["z"].plot(ax=ax[0], color="navy", lw=0.9)
        for lev in (Z_ENTRY, -Z_ENTRY, 0):
            ax[0].axhline(lev, color="grey", ls="--", lw=0.8)
        ax[0].set_title(f"Most-traded pair {key}: Kalman spread z-score")
        ax[0].grid(alpha=0.3)
        (1 + p["net"]).cumprod().plot(ax=ax[1], color="darkgreen")
        ax[1].set_title(f"{key} cumulative net P&L (continuous Kalman)")
        ax[1].grid(alpha=0.3)
        plt.tight_layout(); plt.savefig(f"{FIGDIR}/example_pair.png", dpi=140); plt.close()

    # 4. rolling 90d Sharpe
    roll = net.rolling(90).mean() / net.rolling(90).std() * np.sqrt(ANN)
    plt.figure(figsize=FIGSIZE)
    roll.plot(color="purple"); plt.axhline(0, color="black", lw=0.8)
    plt.title("StatArb - Rolling 90-Day Annualised Sharpe (net)")
    plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(f"{FIGDIR}/rolling_sharpe.png", dpi=140); plt.close()

    # 5. active pairs through time
    plt.figure(figsize=FIGSIZE)
    n_active.plot(color="teal")
    plt.title("Number of Active Cointegrated Pairs Through Time")
    plt.ylabel("# pairs"); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(f"{FIGDIR}/active_pairs.png", dpi=140); plt.close()


if __name__ == "__main__":
    main()
