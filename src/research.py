"""
research.py
-----------
Full momentum / reversal research programme for the WSQ crypto statistical-
arbitrage project.  Every block maps to an item in the class project brief:

  A. Time horizon        - momentum vs reversal across look-backs (1h ... 90d)
  B. New info / activity - volume-shock conditioning (informed vs uninformed)
  C. Seasonality         - weekday vs weekend, US-hours vs off-hours (hourly)
  D. Investment themes   - theme (sector) momentum
  E. Technical plays     - front-running the US (institutional) session
  F. Correlation         - market-residual reversal and cointegration pairs
  G. Macro               - reversal / momentum by volatility & dislocation regime
                           (implied vol = Deribit DVOL, realized vol, dispersion,
                           average pairwise correlation)
  H. Execution           - market (20 bps) vs limit (7 bps), holding periods,
                           no-trade bands, cost sweep 0-200 bps
  I. Weighting           - combining the momentum and reversal strategies
                           (equal, inverse-vol, risk parity, mean-variance)
  J. Performance         - returns, vol, Sharpe, max drawdown, alpha / beta

Research discipline: every parameter choice is made on the research period
(2021-07-01 to 2023-12-31) only; 2024-01-01 onwards is a hold-out that is
reported but never used for selection.

Run:  python3 src/research.py      (after fetch_data.py and statarb.py)
"""
import os
import sys
import json
import itertools

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
import sa_core as C

OUT, FIG = "data/research", "figures"
os.makedirs(OUT, exist_ok=True); os.makedirs(FIG, exist_ok=True)

NAVY, BLUE, CORAL, GOLD, GREEN, GREY = "#1E2761", "#5B8DEF", "#F96167", "#E6A817", "#2C8C5A", "#8A8A8A"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 100,
                     "axes.unicode_minus": False})


def savefig(name):
    plt.tight_layout()
    plt.savefig(f"{FIG}/{name}.png", dpi=150)
    plt.close()


def save(df, name, index=True):
    df.to_csv(f"{OUT}/{name}.csv", index=index)
    return df


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
close, rets, dvol_usd = C.load_panel()
btc = rets["BTC"]
mkt = rets.mean(axis=1)                       # equal-weight crypto market
vol30 = rets.rolling(30, min_periods=20).std()
abn_vol = dvol_usd / dvol_usd.rolling(30, min_periods=20).mean().shift(1)
DVOL = (pd.read_csv("data/dvol.csv", index_col=0, parse_dates=True)["DVOL_BTC"]
        .reindex(rets.index).ffill())
theme_of = {a: t for t, l in C.THEMES.items() for a in l}
theme_ret = pd.DataFrame({t: rets[l].mean(axis=1) for t, l in C.THEMES.items()})

SAMPLE_START, SAMPLE_END = str(close.index.min().date()), str(close.index.max().date())


def ret_L(L):
    return close.pct_change(L, fill_method=None)


def row(name, bt, **extra):
    """One results row: gross / net-20 / net-7 Sharpe for IS, OOS and full."""
    g, n20, n7 = (C.split_sharpes(bt.gross), C.split_sharpes(bt.net),
                  C.split_sharpes(C.net_at(bt, C.LIMIT_BPS)))
    out = {"Strategy": name, **extra,
           "Gross IS": g["IS"], "Gross OOS": g["OOS"], "Gross Full": g["Full"],
           "Net20 IS": n20["IS"], "Net20 OOS": n20["OOS"], "Net20 Full": n20["Full"],
           "Net7 IS": n7["IS"], "Net7 OOS": n7["OOS"], "Net7 Full": n7["Full"],
           "Gross Ann.Ret": bt.gross.mean() * C.ANN,
           "Turnover": bt.turnover.mean()}
    return out


def rolling_pct(x, win=365, minp=180):
    """Percentile of today's value within the trailing year (known at t)."""
    return x.rolling(win, min_periods=minp).rank(pct=True)


# --------------------------------------------------------------------------- #
# Strategy factories
# --------------------------------------------------------------------------- #
def w_ts_blend():
    sig = 0.4 * ret_L(7) + 0.35 * ret_L(14) + 0.25 * ret_L(28)
    return C.ts_weights(sig, vol30)


def w_theme(L):
    tr = (1 + theme_ret).rolling(L).apply(np.prod, raw=True) - 1
    tw = tr.rank(axis=1, pct=True)
    tw = tw.sub(tw.mean(axis=1), axis=0)
    w = pd.DataFrame({a: tw[theme_of[a]] / len(C.THEMES[theme_of[a]]) for a in C.UNIVERSE})
    return C.normalise(w.where(close.notna()))


def w_cs_mom(L, volume=False):
    w = C.cs_weights(ret_L(L))
    if volume:
        w = C.normalise(w * abn_vol.rank(axis=1, pct=True))
    return w


def high_regime(x, q=2 / 3):
    return (rolling_pct(x) >= q).astype(float)


# =========================================================================== #
# A. TIME HORIZON
# =========================================================================== #
def block_horizon():
    rows = []
    for L in [1, 2, 3, 5, 7, 14, 21, 30, 60, 90, 120]:
        for kind in ["Cross-sectional", "Time-series"]:
            w = C.cs_weights(ret_L(L)) if kind == "Cross-sectional" else C.ts_weights(ret_L(L), vol30)
            rows.append(row(f"{kind} L={L}d", C.backtest(w, rets), kind=kind, lookback_days=L))
    df = save(pd.DataFrame(rows), "A_horizon_scan", index=False)

    fig, ax = plt.subplots(figsize=(10, 4.6))
    labels = df[df.kind == "Cross-sectional"].lookback_days.astype(str) + "d"
    x = np.arange(len(labels)); wdt = 0.38
    for k, (kind, col) in enumerate([("Cross-sectional", NAVY), ("Time-series", BLUE)]):
        v = df[df.kind == kind]["Gross Full"].values
        ax.bar(x + (k - 0.5) * wdt, v, wdt, color=col, label=kind)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_xlabel("Look-back horizon (signal = trailing return, rebalanced daily)")
    ax.set_ylabel("Gross Sharpe (momentum sign)")
    ax.set_title("Momentum vs reversal by horizon (daily rebalance): positive = momentum, negative = reversal")
    ax.legend(frameon=False)
    savefig("A_horizon_scan")
    return df


# =========================================================================== #
# A2 / C / E. INTRADAY: hourly horizons, sessions, front-running the US open
# =========================================================================== #
def block_intraday():
    path = "data/crypto_hourly.csv"
    if not os.path.exists(path):
        print("  (hourly file missing - intraday block skipped)")
        return None
    h = pd.read_csv(path, parse_dates=["date"])
    hc = h.pivot(index="date", columns="asset", values="close").sort_index()
    hc = hc.reindex(pd.date_range(hc.index.min(), hc.index.max(), freq="h")).ffill(limit=2)
    hc = hc[[a for a in C.UNIVERSE if a in hc.columns]]
    hr = hc.pct_change(fill_method=None)
    ANN_H = 365 * 24
    res = {}

    # --- intraday horizon scan (cross-sectional, rebalanced each hour)
    rows = []
    for L in [1, 2, 4, 8, 12, 24]:
        w = C.cs_weights(hc.pct_change(L, fill_method=None))
        g = (w.shift(1) * hr).sum(axis=1)
        turn = w.diff().abs().sum(axis=1)
        g = g.loc["2022-01-02":]; turn = turn.loc[g.index]
        sh = lambda r: r.mean() / r.std() * np.sqrt(ANN_H)
        rows.append({"lookback_hours": L, "Gross Sharpe": sh(g),
                     "Gross Sharpe IS": sh(g.loc[:C.IS_END]),
                     "Gross Sharpe OOS": sh(g.loc[C.OOS_START:]),
                     "Gross bps/hour": g.mean() * 1e4,
                     "Turnover/hour": turn.mean(),
                     "Cost bps/hour @7": turn.mean() * 7,
                     "Net Sharpe @7": sh(g - turn * 7e-4),
                     "Net Sharpe @20": sh(g - turn * 20e-4)})
    res["horizon"] = save(pd.DataFrame(rows), "A2_intraday_horizon", index=False)

    # --- sessions (UTC).  US cash-equity hours ~ 13:30-20:00 UTC (EDT).
    sess = pd.Series("Asia (00-08 UTC)", index=hr.index)
    hh = hr.index.hour
    sess[(hh >= 8) & (hh < 13)] = "Europe (08-13 UTC)"
    sess[(hh >= 13) & (hh < 21)] = "US (13-21 UTC)"
    sess[(hh >= 21)] = "Late US (21-24 UTC)"
    wk = np.where(hr.index.dayofweek >= 5, "Weekend", "Weekday")
    ew = hr.mean(axis=1)
    tab = pd.DataFrame({"ret": ew, "btc": hr["BTC"], "sess": sess, "wk": wk}).loc["2022-01-01":]
    s_rows = []
    for (wkk, ss), g in tab.groupby(["wk", "sess"]):
        s_rows.append({"day_type": wkk, "session": ss,
                       "EW mean bps/hour": g.ret.mean() * 1e4,
                       "BTC mean bps/hour": g.btc.mean() * 1e4,
                       "EW vol bps/hour": g.ret.std() * 1e4})
    res["sessions"] = save(pd.DataFrame(s_rows), "C_session_returns", index=False)

    # --- daily session returns for the front-running test
    def sess_ret(lo, hi_):
        m = (hh >= lo) & (hh < hi_)
        return (1 + hr[m]).groupby(hr.index[m].normalize()).prod() - 1
    pre_us = sess_ret(0, 13)       # Asia + Europe, before the US open
    us = sess_ret(13, 21)          # US session
    after = sess_ret(21, 24)
    idx = pre_us.index.intersection(us.index)
    pre_us, us = pre_us.loc[idx], us.loc[idx]
    after = after.reindex(idx)
    us_prev = us.shift(1)
    ft_rows = []
    for name, sig, target in [
        ("Pre-US return -> US session (TS, each coin)", pre_us, us),
        ("Prior-day US session -> today's US session", us_prev, us),
        ("US session -> late-US / overnight", us, after),
    ]:
        for kind in ["Time-series", "Cross-sectional"]:
            if kind == "Time-series":
                w = C.normalise(np.sign(sig))
            else:
                w = C.cs_weights(sig)
            pnl = (w * target).sum(axis=1).loc["2022-01-02":]
            # session strategy opens and closes every day: turnover = 2 x gross
            turn = 2.0
            ft_rows.append({"Test": name, "kind": kind,
                            "Gross bps/day": pnl.mean() * 1e4,
                            "Gross Sharpe": C.sharpe(pnl),
                            "Gross Sharpe IS": C.sharpe(pnl.loc[:C.IS_END]),
                            "Gross Sharpe OOS": C.sharpe(pnl.loc[C.OOS_START:]),
                            "Net Sharpe @7": C.sharpe(pnl - turn * 7e-4),
                            "Net Sharpe @20": C.sharpe(pnl - turn * 20e-4),
                            "t-stat": C.nw_tstat(pnl)})
    res["frontrun"] = save(pd.DataFrame(ft_rows), "E_frontrun_us_session", index=False)

    # figures
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    d = res["horizon"]
    ax[0].bar(d.lookback_hours.astype(str) + "h", d["Gross Sharpe"],
              color=[CORAL if v < 0 else NAVY for v in d["Gross Sharpe"]])
    ax[0].axhline(0, color="black", lw=0.8)
    ax[0].set_title("Intraday cross-sectional signal (gross Sharpe)\nnegative = reversal")
    ax[0].set_xlabel("Look-back (hours), rebalanced hourly")
    sp = res["sessions"].pivot(index="session", columns="day_type", values="EW mean bps/hour")
    sp = sp.loc[["Asia (00-08 UTC)", "Europe (08-13 UTC)", "US (13-21 UTC)", "Late US (21-24 UTC)"]]
    sp.plot.bar(ax=ax[1], color=[GOLD, NAVY], rot=0)
    ax[1].axhline(0, color="black", lw=0.8)
    ax[1].set_title("Equal-weight crypto return by session (bps/hour)")
    ax[1].set_xticklabels([s.split(" (")[0] for s in sp.index]); ax[1].set_xlabel("")
    ax[1].legend(frameon=False)
    savefig("C_intraday_sessions")
    return res


# =========================================================================== #
# B. NEW INFORMATION / ACTIVITY (volume)
# =========================================================================== #
def block_activity():
    rows = []
    hi = abn_vol.rank(axis=1, pct=True) > 0.5
    for L in [1, 3, 7, 14]:
        sig = ret_L(L)
        variants = {
            "All coins": C.cs_weights(sig),
            "High-activity coins only": C.cs_weights(sig.where(hi)),
            "Low-activity coins only": C.cs_weights(sig.where(~hi)),
            "Signal x volume shock": w_cs_mom(L, volume=True),
        }
        for v, w in variants.items():
            rows.append(row(f"CS momentum L={L}d | {v}", C.backtest(w, rets),
                            lookback_days=L, variant=v))
    df = save(pd.DataFrame(rows), "B_activity_volume", index=False)

    fig, ax = plt.subplots(figsize=(10, 4.4))
    piv = df.pivot(index="lookback_days", columns="variant", values="Gross Full")
    piv = piv[["All coins", "High-activity coins only", "Low-activity coins only", "Signal x volume shock"]]
    piv.plot.bar(ax=ax, color=[GREY, NAVY, GOLD, GREEN], rot=0, width=0.8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Look-back (days)"); ax.set_ylabel("Gross Sharpe")
    ax.set_title("Momentum is stronger when activity (abnormal dollar volume) is high")
    ax.legend(frameon=False, fontsize=8.5)
    savefig("B_activity_volume")
    return df


# =========================================================================== #
# C. SEASONALITY (daily): weekday vs weekend
# =========================================================================== #
def block_seasonality(strats):
    rows = []
    for name, (w, _) in strats.items():
        bt = C.backtest(w, rets)
        g = bt.gross
        wk = g.index.dayofweek >= 5
        rec = {"Strategy": name,
               "Weekday Sharpe": C.sharpe(g[~wk]), "Weekend Sharpe": C.sharpe(g[wk]),
               "Weekday bps/day": g[~wk].mean() * 1e4, "Weekend bps/day": g[wk].mean() * 1e4}
        for d, lab in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            rec[f"{lab} bps"] = g[g.index.dayofweek == d].mean() * 1e4
        rows.append(rec)
    df = save(pd.DataFrame(rows), "C_weekday_weekend", index=False)

    # weekend-only vs weekday-only time-series momentum (trading the season)
    w = w_ts_blend()
    wkend = pd.Series(w.index.dayofweek >= 4, index=w.index)   # hold Fri close -> Sun close
    s_rows = []
    for lab, mask in [("All days", pd.Series(True, index=w.index)),
                      ("Weekend only (Fri-Sun close)", wkend),
                      ("Weekdays only", ~wkend)]:
        ww = w.mul(mask.astype(float), axis=0)
        s_rows.append(row(f"TS momentum | {lab}", C.backtest(ww, rets), variant=lab))
    save(pd.DataFrame(s_rows), "C_weekend_momentum", index=False)

    fig, ax = plt.subplots(figsize=(10, 4.2))
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, (name, col) in enumerate(zip(df.Strategy, [NAVY, BLUE, GOLD, CORAL, GREEN])):
        ax.plot(days, df.loc[i, [f"{d} bps" for d in days]].values, marker="o", color=col, label=name)
    ax.axhline(0, color="black", lw=0.8); ax.axvspan(4.5, 6.5, color=GOLD, alpha=0.08)
    ax.set_ylabel("Mean gross return (bps/day)")
    ax.set_title("Day-of-week profile of strategy returns (weekend shaded)")
    ax.legend(frameon=False, fontsize=8.5)
    savefig("C_day_of_week")
    return df


# =========================================================================== #
# D. INVESTMENT THEMES
# =========================================================================== #
def block_themes():
    rows = []
    for L in [7, 14, 21, 30, 60]:
        for H in [1, 3, 7]:
            rows.append(row(f"Theme momentum L={L}d H={H}d", C.backtest(C.hold(w_theme(L), H), rets),
                            lookback_days=L, hold_days=H))
    df = save(pd.DataFrame(rows), "D_theme_momentum", index=False)
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for t, col in zip(C.THEMES, [GOLD, NAVY, BLUE, GREEN]):
        (1 + theme_ret[t].loc[C.BT_START:].fillna(0)).cumprod().plot(ax=ax, label=t, color=col, lw=1.4)
    ax.set_yscale("log"); ax.set_title("Theme indices (equal-weight, growth of $1, log scale)")
    ax.legend(frameon=False, fontsize=8.5); ax.set_xlabel("")
    savefig("D_theme_indices")
    return df


# =========================================================================== #
# F. CORRELATION: market-residual reversal + cointegration pairs
# =========================================================================== #
def block_correlation():
    beta = rets.rolling(60).cov(mkt).div(mkt.rolling(60).var(), axis=0)
    resid = rets - beta.shift(1).mul(mkt, axis=0)
    th_res = pd.DataFrame({a: rets[a] - theme_ret[theme_of[a]] for a in C.UNIVERSE})
    rows = []
    for L in [1, 3, 7, 30, 60]:
        rows.append(row(f"Market-residual reversal L={L}d",
                        C.backtest(C.cs_weights(resid.rolling(L).sum(), -1), rets),
                        family="Residual vs market", lookback_days=L))
        rows.append(row(f"Theme-residual reversal L={L}d",
                        C.backtest(C.cs_weights(th_res.rolling(L).sum(), -1), rets),
                        family="Residual vs theme", lookback_days=L))
    co = pd.read_csv("data/coint_daily.csv", index_col=0, parse_dates=True)
    bt = co[["gross", "net", "turnover"]].copy()
    bt["net"] = bt.gross - bt.turnover * C.MARKET_BPS / 1e4
    rows.append(row("Cointegration pairs (Kalman, walk-forward)", bt,
                    family="Cointegrated pairs", lookback_days=180))
    return save(pd.DataFrame(rows), "F_correlation_reversal", index=False)


def coint_bt():
    co = pd.read_csv("data/coint_daily.csv", index_col=0, parse_dates=True)
    bt = co[["gross", "turnover"]].reindex(rets.loc[C.BT_START:].index).fillna(0)
    bt["net"] = bt.gross - bt.turnover * C.MARKET_BPS / 1e4
    return bt[["gross", "net", "turnover"]]


# =========================================================================== #
# G. MACRO REGIMES
# =========================================================================== #
def avg_pairwise_corr(win=30):
    out = pd.Series(np.nan, index=rets.index)
    vals = rets.values
    for i in range(win, len(rets)):
        c = pd.DataFrame(vals[i - win + 1:i + 1]).corr().values
        m = ~np.eye(c.shape[0], dtype=bool)
        out.iloc[i] = np.nanmean(c[m])
    return out


def block_macro(strats):
    indicators = {
        "Implied vol (BTC DVOL)": DVOL,
        "Realized vol (30d, EW market)": mkt.rolling(30).std() * np.sqrt(C.ANN),
        "Return dispersion (7d avg)": rets.std(axis=1).rolling(7).mean(),
        "Avg pairwise correlation (30d)": avg_pairwise_corr(30),
    }
    pd.DataFrame(indicators).to_csv(f"{OUT}/G_macro_indicators.csv")
    rows = []
    for sname, (w, _) in strats.items():
        bt = C.backtest(w, rets)
        for iname, x in indicators.items():
            p = rolling_pct(x).shift(1)                 # regime known before the trade
            lab = pd.cut(p, [0, 1 / 3, 2 / 3, 1.0001], labels=["Low", "Mid", "High"])
            lab = lab.reindex(bt.index)
            rec = {"Strategy": sname, "Indicator": iname}
            for k in ["Low", "Mid", "High"]:
                g = bt.gross[lab == k]
                rec[f"{k} Sharpe"] = C.sharpe(g)
                rec[f"{k} bps/day"] = g.mean() * 1e4
            rows.append(rec)
    df = save(pd.DataFrame(rows), "G_macro_regimes", index=False)

    strat_names = list(strats)
    fig, axes = plt.subplots(1, len(indicators), figsize=(13, 3.9), sharey=True)
    for ax, iname in zip(axes, indicators):
        sub = df[df.Indicator == iname].set_index("Strategy").loc[strat_names, ["Low Sharpe", "Mid Sharpe", "High Sharpe"]]
        im = ax.imshow(sub.values, cmap="RdBu", vmin=-2.5, vmax=2.5, aspect="auto")
        for i in range(sub.shape[0]):
            for j in range(3):
                ax.text(j, i, f"{sub.values[i, j]:.2f}", ha="center", va="center", fontsize=8.5)
        ax.set_xticks(range(3)); ax.set_xticklabels(["Low", "Mid", "High"])
        ax.set_title(iname, fontsize=9); ax.grid(False)
    axes[0].set_yticks(range(len(strat_names))); axes[0].set_yticklabels(strat_names, fontsize=8.5)
    fig.suptitle("Gross Sharpe by macro regime (trailing-year tercile, known before the trade)", fontsize=11)
    savefig("G_macro_regimes")
    return df, indicators


# =========================================================================== #
# H. EXECUTION + strategy selection (research period only)
# =========================================================================== #
def candidate_grid(indicators):
    """Pre-specified candidate grid per family.  Selection = best research-period
    (IS) net Sharpe at the family's execution cost."""
    rv_on = high_regime(indicators["Realized vol (30d, EW market)"])
    dvol_off = 1 - high_regime(DVOL)
    cands = []
    # ---- momentum family (market orders, 20 bps)
    for H, filt in itertools.product([1, 3, 7], [False, True]):
        w = C.hold(w_ts_blend(), H)
        if filt:
            w = w.mul(dvol_off, axis=0)
        cands.append(("Momentum", f"TS momentum blend H={H}{' + DVOL filter' if filt else ''}", w))
    for L, H in itertools.product([14, 21, 30], [1, 3, 7]):
        cands.append(("Momentum", f"Theme momentum L={L} H={H}", C.hold(w_theme(L), H)))
    for L, H, v in itertools.product([7, 14, 21], [1, 3, 7], [False, True]):
        cands.append(("Momentum", f"CS momentum L={L} H={H}{' x volume' if v else ''}",
                      C.hold(w_cs_mom(L, v), H)))
    # ---- reversal family (passive limit orders, 7 bps)
    for H in [1, 2]:
        w = C.hold(C.cs_weights(ret_L(1), -1), H).mul(rv_on, axis=0)
        cands.append(("Reversal", f"Short-term reversal (1d) in high-vol regime H={H}", w))
    for L, skip, H in itertools.product([60, 90], [0, 14], [7, 14]):
        sig = close.shift(skip) / close.shift(L) - 1
        cands.append(("Reversal", f"Long-horizon reversal L={L} skip={skip} H={H}",
                      C.hold(C.cs_weights(sig, -1), H)))
    return cands


def block_selection(indicators):
    rows, books = [], {}
    for fam, name, w in candidate_grid(indicators):
        bt = C.backtest(w, rets)
        cost = C.MARKET_BPS if fam == "Momentum" else C.LIMIT_BPS
        r = row(name, bt, family=fam, exec_cost_bps=cost)
        r["Selection IS"] = r["Net20 IS"] if fam == "Momentum" else r["Net7 IS"]
        rows.append(r); books[name] = w
    cbt = coint_bt()
    r = row("Cointegration pairs (Kalman)", cbt, family="Reversal", exec_cost_bps=C.LIMIT_BPS)
    r["Selection IS"] = r["Net7 IS"]
    rows.append(r)
    df = pd.DataFrame(rows).sort_values(["family", "Selection IS"], ascending=[True, False])
    save(df, "H_candidate_selection", index=False)
    return df, books, cbt


EXEC_VARIANTS = {
    "Daily rebalance": lambda w: w,
    "Hold 3d (overlapping)": lambda w: C.hold(w, 3),
    "Hold 7d (overlapping)": lambda w: C.hold(w, 7),
    "No-trade band 2%": lambda w: C.band(w, 0.02),
    "No-trade band 5%": lambda w: C.band(w, 0.05),
}


def block_execution(w_mom, w_rev, mom_name, rev_name):
    """Show how execution choices change net performance for the chosen books."""
    rows = []
    base = {"Momentum": w_mom, "Reversal": w_rev}
    for fam, w in base.items():
        for v, fn in EXEC_VARIANTS.items():
            bt = C.backtest(fn(w), rets)
            rows.append({"Book": fam, "Execution": v,
                         "Turnover": bt.turnover.mean(),
                         "Sharpe IS @exec cost": C.sharpe(C.net_at(bt, 20 if fam == "Momentum" else 7).loc[:C.IS_END]),
                         "Sharpe gross": C.sharpe(bt.gross),
                         "Sharpe limit 7bps": C.sharpe(C.net_at(bt, 7)),
                         "Sharpe market 20bps": C.sharpe(C.net_at(bt, 20)),
                         "Cost drag/yr @20": bt.turnover.mean() * 20e-4 * C.ANN})
    df = save(pd.DataFrame(rows), "H_execution_variants", index=False)
    return df


# =========================================================================== #
# I. WEIGHTING
# =========================================================================== #
def combine(sleeves, method, lookback=180):
    """Walk-forward weights from trailing data only (rebalanced monthly)."""
    R = pd.DataFrame(sleeves).fillna(0)
    W = pd.DataFrame(np.nan, index=R.index, columns=R.columns)
    for t in range(lookback, len(R), 21):
        hist = R.iloc[t - lookback:t]
        vol = hist.std().replace(0, np.nan)
        if method == "Equal weight":
            w = pd.Series(1.0, index=R.columns)
        elif method == "Inverse volatility":
            w = 1 / vol
        elif method == "Risk parity (ERC)":
            cov = hist.cov().values
            w = (1 / vol).values
            for _ in range(200):          # equal risk contribution fixed point
                mrc = cov @ w
                rc = w * mrc
                w = w * (rc.mean() / np.maximum(rc, 1e-12)) ** 0.5
            w = pd.Series(w, index=R.columns)
        elif method == "Mean-variance (shrunk)":
            mu = hist.mean() * 0.5                        # shrink means 50% toward 0
            cov = 0.5 * hist.cov() + 0.5 * np.diag(np.diag(hist.cov()))
            w = pd.Series(np.linalg.pinv(cov.values) @ mu.values, index=R.columns).clip(lower=0)
            if w.sum() == 0:
                w = 1 / vol
        w = w / w.sum()
        W.iloc[t:t + 21] = w.values
    W = W.ffill()
    port = (W * R).sum(axis=1)
    port[W.isna().all(axis=1)] = np.nan
    return port, W


def vol_target(r, target=0.10, win=60):
    lev = (target / (r.rolling(win, min_periods=30).std() * np.sqrt(C.ANN))).shift(1).clip(upper=3)
    return (r * lev).dropna()


# =========================================================================== #
# MAIN
# =========================================================================== #
def main():
    print(f"Panel {SAMPLE_START} -> {SAMPLE_END}, {close.shape[1]} assets")
    print("A. horizon scan");          A = block_horizon()
    print("A2/C/E. intraday");         I = block_intraday()
    print("B. activity");              B = block_activity()
    print("D. themes");                D = block_themes()
    print("F. correlation");           F = block_correlation()

    diag = {
        "TS momentum (blend)": (w_ts_blend(), "mom"),
        "CS momentum 14d": (w_cs_mom(14), "mom"),
        "Theme momentum 21d": (w_theme(21), "mom"),
        "Short-term reversal 1d": (C.cs_weights(ret_L(1), -1), "rev"),
        "Long-horizon reversal 90d": (C.cs_weights(ret_L(90), -1), "rev"),
    }
    print("C. seasonality");           S = block_seasonality(diag)
    print("G. macro");                 G, indicators = block_macro(diag)
    print("H. selection");             sel, books, cbt = block_selection(indicators)

    # ---- Final sleeves.  Momentum = ensemble of the IS-best variant in each
    # momentum sub-family (time-series, theme, cross-sectional), equal weight.
    # Reversal = IS-best reversal candidate.  Execution variant per sleeve is
    # also chosen on the research period.
    def best_of(prefix, fam="Momentum"):
        sub = sel[(sel.family == fam) & sel.Strategy.str.startswith(prefix)]
        return sub.iloc[0]["Strategy"]
    ens_names = [best_of("TS momentum"), best_of("Theme momentum"), best_of("CS momentum")]
    single_mom = sel[sel.family == "Momentum"].iloc[0]["Strategy"]
    rev_name = sel[sel.family == "Reversal"].iloc[0]["Strategy"]
    print(f"   momentum ensemble: {ens_names}")
    print(f"   selected reversal: {rev_name}")
    w_ens = C.normalise(sum(books[n] for n in ens_names) / 3)
    w_rev = books.get(rev_name)
    if w_rev is None:
        raise SystemExit("cointegration selected as reversal sleeve - handle separately")
    H = block_execution(w_ens, w_rev, "Momentum ensemble", rev_name)
    exe = {}
    for book, w0, cost in [("Momentum", w_ens, C.MARKET_BPS), ("Reversal", w_rev, C.LIMIT_BPS)]:
        best_v, best_s = None, -np.inf
        for v, fn in EXEC_VARIANTS.items():
            bt = C.backtest(fn(w0), rets)
            s_is = C.sharpe(C.net_at(bt, cost).loc[:C.IS_END])
            if s_is > best_s:
                best_v, best_s = v, s_is
        exe[book] = best_v
    print(f"   execution chosen on IS: {exe}")
    w_mom = EXEC_VARIANTS[exe["Momentum"]](w_ens)
    w_rev = EXEC_VARIANTS[exe["Reversal"]](w_rev)
    mom_name = "Momentum ensemble"

    bt_mom = C.backtest(w_mom, rets)
    mom_net20 = bt_mom.net
    mom_net7 = C.net_at(bt_mom, C.LIMIT_BPS)
    bt_rev = C.backtest(w_rev, rets)
    rev_net7 = C.net_at(bt_rev, C.LIMIT_BPS)
    rev_net20 = C.net_at(bt_rev, C.MARKET_BPS)
    pairs_net7 = C.net_at(cbt, C.LIMIT_BPS)
    # sleeve components, for the report
    comp = {n: C.backtest(books[n], rets).net for n in ens_names}

    sleeves = {"Momentum": mom_net20, "Reversal": rev_net7}
    corr = pd.DataFrame({"Momentum ensemble": mom_net20, "Reversal": rev_net7,
                         **{n.split(" L=")[0].split(" H=")[0]: r for n, r in comp.items()},
                         "Cointegration pairs": pairs_net7, "BTC": btc.loc[C.BT_START:]}).corr()
    save(corr, "I_sleeve_correlation")

    methods = ["Equal weight", "Inverse volatility", "Risk parity (ERC)", "Mean-variance (shrunk)"]
    combos, weights = {}, {}
    for m in methods:
        combos[m], weights[m] = combine(sleeves, m)
    start = max(c.first_valid_index() for c in combos.values())
    w_rows = []
    for m in methods:
        ww = weights[m].loc[start:]
        w_rows.append({"Method": m, "Avg weight Momentum": ww["Momentum"].mean(),
                       "Avg weight Reversal": ww["Reversal"].mean(),
                       "Sharpe": C.sharpe(combos[m].loc[start:]),
                       "Sharpe IS": C.sharpe(combos[m].loc[start:C.IS_END]),
                       "Sharpe OOS": C.sharpe(combos[m].loc[C.OOS_START:])})
    wt = save(pd.DataFrame(w_rows), "I_weighting_methods", index=False)
    # choose the combination method on the research period only
    best_m = wt.sort_values("Sharpe IS", ascending=False).iloc[0]["Method"]
    print(f"   weighting method chosen on IS: {best_m}")
    combo = combos[best_m].loc[start:]

    # ---- robustness: what if we had simply picked the single IS-best momentum
    # strategy, or used time-series momentum alone?
    rb_rows = []
    for lab, mom_r in [("Final: momentum ensemble (best TS + theme + CS)", mom_net20),
                       (f"Single IS-best momentum ({single_mom})", C.backtest(books[single_mom], rets).net),
                       (f"TS momentum only ({ens_names[0]})", C.backtest(books[ens_names[0]], rets).net)]:
        cmb, _ = combine({"Momentum": mom_r, "Reversal": rev_net7}, best_m)
        cmb = cmb.loc[start:]
        rb_rows.append({"Momentum sleeve": lab,
                        "Momentum Sharpe IS": C.sharpe(mom_r.loc[start:C.IS_END]),
                        "Momentum Sharpe OOS": C.sharpe(mom_r.loc[C.OOS_START:]),
                        "Combined Sharpe IS": C.sharpe(cmb.loc[:C.IS_END]),
                        "Combined Sharpe OOS": C.sharpe(cmb.loc[C.OOS_START:]),
                        "Combined Sharpe Full": C.sharpe(cmb)})
    save(pd.DataFrame(rb_rows), "I_selection_robustness", index=False)

    # ---- J. performance table (common window)
    idx = combo.index
    ew = mkt.reindex(idx).fillna(0)
    series = {
        "Momentum ensemble (net 20bps market)": mom_net20.reindex(idx),
        "Momentum ensemble (net 7bps limit)": mom_net7.reindex(idx),
        "Reversal (net 7bps limit)": rev_net7.reindex(idx),
        "Reversal (net 20bps market)": rev_net20.reindex(idx),
        "Cointegration pairs (net 20bps)": cbt.net.reindex(idx),
        "Combined portfolio": combo,
        "Combined portfolio (all at 20bps market)": combine(
            {"Momentum": mom_net20, "Reversal": rev_net20}, best_m)[0].reindex(idx),
        "Equal-weight crypto (B&H)": ew,
        "Buy & Hold BTC": btc.reindex(idx).fillna(0),
    }
    turns = {"Momentum ensemble (net 20bps market)": bt_mom.turnover.reindex(idx),
             "Reversal (net 7bps limit)": bt_rev.turnover.reindex(idx)}
    full = C.perf_table(series, btc.reindex(idx), turns)
    oos = C.perf_table({k: v.loc[C.OOS_START:] for k, v in series.items()}, btc.loc[C.OOS_START:])
    ins = C.perf_table({k: v.loc[:C.IS_END] for k, v in series.items()}, btc.loc[:C.IS_END])
    save(full, "J_performance_full"); save(oos, "J_performance_oos"); save(ins, "J_performance_is")
    pd.DataFrame(series).to_csv(f"{OUT}/J_daily_returns.csv")

    # cost sweep for the final books (memo: 5-200 bps)
    sw = []
    for bps in [0, 5, 7, 10, 20, 30, 50, 100, 200]:
        mom_c = C.net_at(bt_mom, bps).reindex(idx)
        rev_c = C.net_at(bt_rev, bps).reindex(idx)
        cmb, _ = combine({"Momentum": C.net_at(bt_mom, bps), "Reversal": C.net_at(bt_rev, bps)}, best_m)
        sw.append({"cost_bps": bps, "Momentum": C.sharpe(mom_c), "Reversal": C.sharpe(rev_c),
                   "Cointegration pairs": C.sharpe(C.net_at(cbt, bps).reindex(idx)),
                   "Combined": C.sharpe(cmb.loc[start:])})
    sweep = save(pd.DataFrame(sw), "H_cost_sweep", index=False)

    make_final_figures(series, mom_name, rev_name, best_m, sweep, weights[best_m].loc[start:], corr)

    summary = {
        "sample_start": SAMPLE_START, "sample_end": SAMPLE_END,
        "bt_start": str(idx.min().date()), "bt_end": str(idx.max().date()),
        "is_end": C.IS_END, "oos_start": C.OOS_START, "n_days": int(len(idx)),
        "n_assets": int(close.shape[1]),
        "momentum_selected": mom_name, "momentum_components": ens_names,
        "single_best_momentum": single_mom, "reversal_selected": rev_name,
        "execution_selected": exe,
        "weighting_selected": best_m,
        "market_bps": C.MARKET_BPS, "limit_bps": C.LIMIT_BPS,
        "n_candidates": int(len(sel)),
    }
    json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=2)
    pd.set_option("display.width", 250)
    print("\n=== Full-period performance ===")
    print(full.round(3).to_string())
    print("\n=== Hold-out (OOS) performance ===")
    print(oos[["Ann.Return", "Ann.Vol", "Sharpe", "MaxDD", "Alpha", "Beta", "Alpha t"]].round(3).to_string())
    print("\n=== weighting ===\n", wt.round(3).to_string())
    print(json.dumps(summary, indent=2))


def make_final_figures(series, mom_name, rev_name, best_m, sweep, wts, corr):
    keys = list(series)
    k_mom, k_rev = keys[0], keys[2]
    k_cmb = keys[5]
    # equity curves
    fig, ax = plt.subplots(figsize=(11, 5))
    for k, lab, col, lw in [(k_mom, "Momentum (net 20 bps)", NAVY, 1.6),
                            (k_rev, "Reversal (net 7 bps limit)", GOLD, 1.6),
                            (k_cmb, f"Combined ({best_m.lower()} weights)", GREEN, 2.4),
                            ("Buy & Hold BTC", "Buy & Hold BTC", GREY, 1.2),
                            ("Equal-weight crypto (B&H)", "Equal-weight crypto", CORAL, 1.0)]:
        (1 + series[k].fillna(0)).cumprod().plot(ax=ax, label=lab, color=col, lw=lw)
    ax.axvline(pd.Timestamp(C.OOS_START), color="black", ls="--", lw=0.9)
    ax.text(pd.Timestamp(C.OOS_START), ax.get_ylim()[1] * 0.97, "  hold-out begins", va="top", fontsize=9)
    ax.set_yscale("log"); ax.set_title("Growth of $1 (log scale), net of transaction costs")
    ax.legend(frameon=False, fontsize=9); ax.set_xlabel("")
    savefig("J_equity_curves")

    # drawdowns
    fig, ax = plt.subplots(figsize=(11, 4))
    for k, lab, col in [(k_cmb, "Combined", GREEN), (k_mom, "Momentum", NAVY),
                        ("Buy & Hold BTC", "Buy & Hold BTC", GREY)]:
        cum = (1 + series[k].fillna(0)).cumprod()
        dd = cum / cum.cummax() - 1
        ax.fill_between(dd.index, dd.values, 0, alpha=0.35 if k != "Buy & Hold BTC" else 0.15,
                        color=col, label=lab)
    ax.set_title("Drawdowns"); ax.legend(frameon=False, fontsize=9); ax.set_ylabel("Drawdown")
    savefig("J_drawdowns")

    # rolling sharpe
    fig, ax = plt.subplots(figsize=(11, 4))
    for k, lab, col in [(k_cmb, "Combined", GREEN), (k_mom, "Momentum", NAVY), (k_rev, "Reversal", GOLD)]:
        r = series[k]
        (r.rolling(180).mean() / r.rolling(180).std() * np.sqrt(C.ANN)).plot(ax=ax, label=lab, color=col)
    ax.axhline(0, color="black", lw=0.8); ax.set_title("Rolling 180-day Sharpe (net)")
    ax.legend(frameon=False, fontsize=9); ax.set_xlabel("")
    savefig("J_rolling_sharpe")

    # cost sweep
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for c, col in zip(["Momentum", "Reversal", "Cointegration pairs", "Combined"], [NAVY, GOLD, BLUE, GREEN]):
        ax.plot(sweep.cost_bps, sweep[c], marker="o", label=c, color=col, lw=2 if c == "Combined" else 1.4)
    ax.axhline(0, color="black", lw=0.8)
    for b, lab in [(7, "limit 7"), (20, "market 20")]:
        ax.axvline(b, color=GREY, ls=":", lw=1); ax.text(b, ax.get_ylim()[1] * 0.95, f" {lab}", fontsize=8.5)
    ax.set_xscale("symlog", linthresh=10); ax.set_xticks([0, 5, 7, 10, 20, 30, 50, 100, 200])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("Transaction cost (bps per unit turnover)"); ax.set_ylabel("Net Sharpe")
    ax.set_title("Net Sharpe vs transaction cost"); ax.legend(frameon=False, fontsize=9)
    savefig("H_cost_sweep")

    # weights through time
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.stackplot(wts.index, wts["Momentum"], wts["Reversal"], labels=["Momentum", "Reversal"],
                 colors=[NAVY, GOLD], alpha=0.85)
    ax.set_ylim(0, 1); ax.set_title(f"Walk-forward sleeve weights ({best_m})")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    savefig("I_sleeve_weights")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    main()
