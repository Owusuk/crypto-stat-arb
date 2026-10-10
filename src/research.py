"""
research.py  (V2)
-----------------
Momentum / reversal research programme for the WSQ crypto statistical-
arbitrage project, version 2.

Every block maps to an item in the class brief:
  A. Time horizon        - momentum vs reversal across look-backs (1h ... 120d)
  B. New info / activity - volume-shock conditioning (informed vs uninformed)
  C. Seasonality         - weekday vs weekend, US-hours vs off-hours (hourly)
  D. Investment themes   - theme (sector) momentum / reversal
  E. Technical plays     - front-running the US (institutional) session
  F. Correlation         - market- and theme-residual reversal, cointegrated pairs
  G. Macro               - strategy returns by volatility / dislocation regime
  H. Execution           - 20 bps market vs 7 bps limit, holding periods, bands
  I. Weighting           - combining the momentum and reversal books
  J. Performance         - return, vol, Sharpe, max DD, alpha / beta, corr to BTC

Pre-registered protocol (V2)
============================
The research period is 2021-07-01 to 2023-12-31; the hold-out is 2024-01-01
onward.  Nothing from the hold-out enters any decision:

 1. Exploration tables are computed on both periods for transparency, but only
    the research-period columns are used.
 2. Candidate generation is mechanical.  Every signal family is evaluated at a
    fixed grid of look-backs; its DIRECTION (momentum = follow the signal,
    reversal = fade it) is set by the sign of its research-period gross Sharpe.
    Momentum-direction candidates are charged 20 bps (market orders),
    reversal-direction candidates 7 bps (passive limit orders).
 3. Within each book the best variant of each family is kept if its
    research-period net Sharpe is positive; the book is an equal-weight
    ensemble of the top three families.
 4. Execution rule and weighting method are chosen on the research period.

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

NAVY, BLUE, CORAL, GOLD, GREEN, GREY, LBLUE = ("#1E2761", "#5B8DEF", "#F96167", "#E6A817",
                                               "#2C8C5A", "#8A8A8A", "#B9CCF5")
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


def ret_L(L, skip=0):
    return close.shift(skip) / close.shift(L) - 1 if skip else close.pct_change(L, fill_method=None)


def row(name, bt, **extra):
    """One results row: gross / net-20 / net-7 Sharpe for IS, hold-out and full."""
    g, n20, n7 = (C.split_sharpes(bt.gross), C.split_sharpes(bt.net),
                  C.split_sharpes(C.net_at(bt, C.LIMIT_BPS)))
    return {"Strategy": name, **extra,
            "Gross IS": g["IS"], "Gross OOS": g["OOS"], "Gross Full": g["Full"],
            "Net20 IS": n20["IS"], "Net20 OOS": n20["OOS"], "Net20 Full": n20["Full"],
            "Net7 IS": n7["IS"], "Net7 OOS": n7["OOS"], "Net7 Full": n7["Full"],
            "Gross Ann.Ret IS": bt.gross.loc[:C.IS_END].mean() * C.ANN,
            "Turnover": bt.turnover.mean()}


def rolling_pct(x, win=365, minp=180):
    """Percentile of today's value within the trailing year (known at t)."""
    return x.rolling(win, min_periods=minp).rank(pct=True)


def high_regime(x, q=2 / 3):
    return (rolling_pct(x) >= q).astype(float)


# --------------------------------------------------------------------------- #
# Signal families: each returns MOMENTUM-SIGN weights (direction applied later)
# --------------------------------------------------------------------------- #
_beta = rets.rolling(60).cov(mkt).div(mkt.rolling(60).var(), axis=0)
RESID_MKT = rets - _beta.shift(1).mul(mkt, axis=0)
RESID_THEME = pd.DataFrame({a: rets[a] - theme_ret[theme_of[a]] for a in C.UNIVERSE})
RV30 = mkt.rolling(30).std() * np.sqrt(C.ANN)


def w_cs(L, skip=0, volume=False):
    w = C.cs_weights(ret_L(L, skip))
    if volume:
        w = C.normalise(w * abn_vol.rank(axis=1, pct=True))
    return w


def w_ts(L, dvol_filter=False):
    sig = (0.4 * ret_L(7) + 0.35 * ret_L(14) + 0.25 * ret_L(28)) if L == "blend" else ret_L(L)
    w = C.ts_weights(sig, vol30)
    if dvol_filter:
        w = w.mul(1 - high_regime(DVOL), axis=0)
    return w


def w_theme(L):
    tr = (1 + theme_ret).rolling(L).apply(np.prod, raw=True) - 1
    tw = tr.rank(axis=1, pct=True)
    tw = tw.sub(tw.mean(axis=1), axis=0)
    active = close.notna()
    n_act = pd.DataFrame({t: active[l].sum(axis=1) for t, l in C.THEMES.items()}).replace(0, np.nan)
    w = pd.DataFrame({a: tw[theme_of[a]] / n_act[theme_of[a]] for a in C.UNIVERSE})
    return C.normalise(w.where(active))


def w_resid(kind, L):
    res = RESID_MKT if kind == "market" else RESID_THEME
    return C.cs_weights(res.rolling(L).sum())


def w_hv_short():
    return C.cs_weights(ret_L(1)).mul(high_regime(RV30), axis=0)


FAMILY_LABEL = {"CS": "Cross-sectional", "TS": "Time-series", "THEME": "Theme",
                "RMKT": "Residual vs market", "RTHM": "Residual vs theme",
                "HV": "Short-term in high-vol regime", "PAIRS": "Cointegrated pairs"}


def signal_grid():
    """(family, key, label, momentum-sign weights) for every signal variant."""
    out = []
    for L in [1, 2, 3, 5, 7, 14, 21, 30, 60, 90, 120]:
        for skip in ([0, 14] if L >= 60 else [0]):
            for vol in ([False, True] if L <= 14 else [False]):
                lab = f"CS L={L}" + (f" skip={skip}" if skip else "") + (" x volume" if vol else "")
                out.append(("CS", lab, w_cs(L, skip, vol)))
    for L in ["blend", 7, 14, 30, 60, 90]:
        for f in [False, True]:
            out.append(("TS", f"TS L={L}" + (" + DVOL filter" if f else ""), w_ts(L, f)))
    for L in [7, 14, 21, 30, 60, 90]:
        out.append(("THEME", f"Theme L={L}", w_theme(L)))
    for L in [1, 3, 7, 14, 30, 60]:
        out.append(("RMKT", f"Residual vs market L={L}", w_resid("market", L)))
        out.append(("RTHM", f"Residual vs theme L={L}", w_resid("theme", L)))
    out.append(("HV", "Short-term (1d) in high-vol regime", w_hv_short()))
    return out


HOLDS = {"CS": [1, 3, 7, 14], "TS": [1, 3, 7], "THEME": [1, 3, 7, 14],
         "RMKT": [1, 7], "RTHM": [1, 7], "HV": [1, 2]}


# =========================================================================== #
# A. TIME HORIZON (daily)
# =========================================================================== #
def block_horizon():
    rows = []
    for L in [1, 2, 3, 5, 7, 14, 21, 30, 60, 90, 120]:
        for kind in ["Cross-sectional", "Time-series"]:
            w = C.cs_weights(ret_L(L)) if kind == "Cross-sectional" else C.ts_weights(ret_L(L), vol30)
            rows.append(row(f"{kind} L={L}d", C.backtest(w, rets), kind=kind, lookback_days=L))
    df = save(pd.DataFrame(rows), "A_horizon_scan", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    for ax, kind in zip(axes, ["Cross-sectional", "Time-series"]):
        d = df[df.kind == kind]
        x = np.arange(len(d)); wdt = 0.4
        ax.bar(x - wdt / 2, d["Gross IS"], wdt, color=NAVY, label="Research period 2021-23 (used)")
        ax.bar(x + wdt / 2, d["Gross OOS"], wdt, color=LBLUE, label="Hold-out 2024+ (not used)")
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(x); ax.set_xticklabels(d.lookback_days.astype(str) + "d", fontsize=8.5)
        ax.set_title(f"{kind}: positive = momentum, negative = reversal", fontsize=10)
        ax.set_xlabel("Look-back (daily rebalance)")
    axes[0].set_ylabel("Gross Sharpe (momentum sign)")
    axes[0].legend(frameon=False, fontsize=8.5)
    savefig("A_horizon_scan")
    return df


# =========================================================================== #
# A2 / C / E. INTRADAY (hourly)
# =========================================================================== #
def block_intraday():
    path = "data/crypto_hourly.csv.gz"
    if not os.path.exists(path):
        print("  (hourly file missing - intraday block skipped)")
        return None
    h = pd.read_csv(path, parse_dates=["date"])
    h = h[h.asset.isin(C.UNIVERSE)]
    hc = h.pivot_table(index="date", columns="asset", values="close").sort_index()
    hc = hc.reindex(pd.date_range(hc.index.min(), hc.index.max(), freq="h")).ffill(limit=2)
    hr = hc.pct_change(fill_method=None).clip(-0.5, 0.5)
    ANN_H = C.ANN * 24
    sh = lambda r: r.mean() / r.std() * np.sqrt(ANN_H) if r.std() > 0 else np.nan
    res = {}

    rows = []
    for L in [1, 2, 4, 8, 12, 24]:
        w = C.cs_weights(hc.pct_change(L, fill_method=None))
        g = (w.shift(1) * hr).sum(axis=1).loc["2022-01-02":]
        turn = w.diff().abs().sum(axis=1).loc[g.index]
        rows.append({"lookback_hours": L, "Gross Sharpe IS": sh(g.loc[:C.IS_END]),
                     "Gross Sharpe OOS": sh(g.loc[C.OOS_START:]), "Gross Sharpe": sh(g),
                     "Gross bps/hour": g.mean() * 1e4, "Turnover/hour": turn.mean(),
                     "Cost bps/hour @7": turn.mean() * 7,
                     "Net Sharpe @7": sh(g - turn * 7e-4), "Net Sharpe @20": sh(g - turn * 20e-4)})
    res["horizon"] = save(pd.DataFrame(rows), "A2_intraday_horizon", index=False)

    hh = hr.index.hour
    sess = pd.Series("Asia (00-08 UTC)", index=hr.index)
    sess[(hh >= 8) & (hh < 13)] = "Europe (08-13 UTC)"
    sess[(hh >= 13) & (hh < 21)] = "US (13-21 UTC)"
    sess[(hh >= 21)] = "Late US (21-24 UTC)"
    wk = np.where(hr.index.dayofweek >= 5, "Weekend", "Weekday")
    tab = pd.DataFrame({"ret": hr.mean(axis=1), "btc": hr["BTC"], "sess": sess, "wk": wk}).loc["2022-01-01":]
    s_rows = []
    for per, sub in [("Research", tab.loc[:C.IS_END]), ("Hold-out", tab.loc[C.OOS_START:])]:
        for (wkk, ss), g in sub.groupby(["wk", "sess"]):
            s_rows.append({"period": per, "day_type": wkk, "session": ss,
                           "EW mean bps/hour": g.ret.mean() * 1e4, "BTC mean bps/hour": g.btc.mean() * 1e4})
    res["sessions"] = save(pd.DataFrame(s_rows), "C_session_returns", index=False)

    def sess_ret(lo, hi_):
        m = (hh >= lo) & (hh < hi_)
        return (1 + hr[m]).groupby(hr.index[m].normalize()).prod() - 1
    pre_us, us, after = sess_ret(0, 13), sess_ret(13, 21), sess_ret(21, 24)
    idx = pre_us.index.intersection(us.index)
    pre_us, us, after = pre_us.loc[idx], us.loc[idx], after.reindex(idx)
    ft_rows = []
    for name, sig, target in [("Pre-US return -> US session", pre_us, us),
                              ("Prior-day US session -> today's US session", us.shift(1), us),
                              ("US session -> late-US hours", us, after)]:
        for kind in ["Time-series", "Cross-sectional"]:
            w = C.normalise(np.sign(sig)) if kind == "Time-series" else C.cs_weights(sig)
            pnl = (w * target).sum(axis=1).loc["2022-01-02":]
            ft_rows.append({"Test": name, "kind": kind, "Gross bps/day": pnl.mean() * 1e4,
                            "Gross Sharpe IS": C.sharpe(pnl.loc[:C.IS_END]),
                            "Gross Sharpe OOS": C.sharpe(pnl.loc[C.OOS_START:]),
                            "Net Sharpe @7": C.sharpe(pnl - 2 * 7e-4),
                            "t-stat": C.nw_tstat(pnl)})
    res["frontrun"] = save(pd.DataFrame(ft_rows), "E_frontrun_us_session", index=False)

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    d = res["horizon"]; x = np.arange(len(d))
    ax[0].bar(x - 0.2, d["Gross Sharpe IS"], 0.4, color=NAVY, label="Research 2022-23")
    ax[0].bar(x + 0.2, d["Gross Sharpe OOS"], 0.4, color=LBLUE, label="Hold-out 2024+")
    ax[0].set_xticks(x); ax[0].set_xticklabels(d.lookback_hours.astype(str) + "h")
    ax[0].axhline(0, color="black", lw=0.8); ax[0].legend(frameon=False, fontsize=8.5)
    ax[0].set_title("Intraday cross-sectional signal (gross Sharpe)\nnegative = reversal")
    sp = res["sessions"][res["sessions"].period == "Research"].pivot(index="session", columns="day_type",
                                                                        values="EW mean bps/hour")
    sp = sp.loc[["Asia (00-08 UTC)", "Europe (08-13 UTC)", "US (13-21 UTC)", "Late US (21-24 UTC)"]]
    sp.plot.bar(ax=ax[1], color=[GOLD, NAVY], rot=0)
    ax[1].axhline(0, color="black", lw=0.8); ax[1].set_xlabel("")
    ax[1].set_title("Equal-weight return by session, research period (bps/hour)")
    ax[1].set_xticklabels([s.split(" (")[0] for s in sp.index]); ax[1].legend(frameon=False)
    savefig("C_intraday_sessions")
    return res


# =========================================================================== #
# B. ACTIVITY
# =========================================================================== #
def block_activity():
    rows = []
    hi = abn_vol.rank(axis=1, pct=True) > 0.5
    for L in [1, 3, 7, 14]:
        sig = ret_L(L)
        for v, w in {"All coins": C.cs_weights(sig),
                     "High-activity coins only": C.cs_weights(sig.where(hi)),
                     "Low-activity coins only": C.cs_weights(sig.where(~hi)),
                     "Signal x volume shock": w_cs(L, volume=True)}.items():
            rows.append(row(f"CS L={L}d | {v}", C.backtest(w, rets), lookback_days=L, variant=v))
    df = save(pd.DataFrame(rows), "B_activity_volume", index=False)
    fig, ax = plt.subplots(figsize=(10, 4.4))
    piv = df.pivot(index="lookback_days", columns="variant", values="Gross IS")
    piv = piv[["All coins", "High-activity coins only", "Low-activity coins only", "Signal x volume shock"]]
    piv.plot.bar(ax=ax, color=[GREY, NAVY, GOLD, GREEN], rot=0, width=0.8)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xlabel("Look-back (days)"); ax.set_ylabel("Gross Sharpe, research period")
    ax.set_title("Cross-sectional signal conditioned on abnormal dollar volume (momentum sign)")
    ax.legend(frameon=False, fontsize=8.5)
    savefig("B_activity_volume")
    return df


# =========================================================================== #
# C. SEASONALITY (daily)
# =========================================================================== #
def block_seasonality(diag):
    rows = []
    for name, w in diag.items():
        g = C.backtest(w, rets).gross.loc[:C.IS_END]
        wk = g.index.dayofweek >= 5
        rec = {"Strategy": name, "Weekday Sharpe": C.sharpe(g[~wk]), "Weekend Sharpe": C.sharpe(g[wk]),
               "Weekday bps/day": g[~wk].mean() * 1e4, "Weekend bps/day": g[wk].mean() * 1e4}
        for d, lab in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            rec[f"{lab} bps"] = g[g.index.dayofweek == d].mean() * 1e4
        rows.append(rec)
    df = save(pd.DataFrame(rows), "C_weekday_weekend", index=False)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, col in zip(range(len(df)), [NAVY, BLUE, GOLD, CORAL, GREEN]):
        ax.plot(days, df.loc[i, [f"{d} bps" for d in days]].values, marker="o", color=col, label=df.Strategy[i])
    ax.axhline(0, color="black", lw=0.8); ax.axvspan(4.5, 6.5, color=GOLD, alpha=0.08)
    ax.set_ylabel("Mean gross return (bps/day)")
    ax.set_title("Day-of-week profile, research period (weekend shaded)")
    ax.legend(frameon=False, fontsize=8.5)
    savefig("C_day_of_week")
    return df


# =========================================================================== #
# D. THEMES
# =========================================================================== #
def block_themes():
    rows = []
    for L in [7, 14, 21, 30, 60, 90]:
        for H in [1, 7]:
            rows.append(row(f"Theme L={L}d H={H}d", C.backtest(C.hold(w_theme(L), H), rets),
                            lookback_days=L, hold_days=H))
    df = save(pd.DataFrame(rows), "D_theme_momentum", index=False)
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for t, col in zip(C.THEMES, [GOLD, NAVY, GREEN, CORAL, BLUE]):
        (1 + theme_ret[t].loc[C.BT_START:].fillna(0)).cumprod().plot(ax=ax, label=t, color=col, lw=1.4)
    ax.axvline(pd.Timestamp(C.OOS_START), color="black", ls="--", lw=0.8)
    ax.set_yscale("log"); ax.set_title("Theme indices (equal-weight, growth of $1, log scale)")
    ax.legend(frameon=False, fontsize=8.5); ax.set_xlabel("")
    savefig("D_theme_indices")
    return df


# =========================================================================== #
# F. CORRELATION
# =========================================================================== #
def coint_bt():
    co = pd.read_csv("data/coint_daily.csv", index_col=0, parse_dates=True)
    bt = co[["gross", "turnover"]].reindex(rets.loc[C.BT_START:].index).fillna(0)
    bt["net"] = bt.gross - bt.turnover * C.MARKET_BPS / 1e4
    return bt[["gross", "net", "turnover"]]


def block_correlation():
    rows = []
    for L in [1, 3, 7, 14, 30, 60]:
        rows.append(row(f"Residual vs market L={L}d", C.backtest(w_resid("market", L), rets),
                        family="Residual vs market", lookback_days=L))
        rows.append(row(f"Residual vs theme L={L}d", C.backtest(w_resid("theme", L), rets),
                        family="Residual vs theme", lookback_days=L))
    rows.append(row("Cointegrated pairs (Kalman, walk-forward)", coint_bt(),
                    family="Cointegrated pairs", lookback_days=180))
    return save(pd.DataFrame(rows), "F_correlation", index=False)


# =========================================================================== #
# G. MACRO
# =========================================================================== #
def avg_pairwise_corr(win=30):
    out = pd.Series(np.nan, index=rets.index)
    vals = rets.values
    for i in range(win, len(rets)):
        c = pd.DataFrame(vals[i - win + 1:i + 1]).corr().values
        m = ~np.eye(c.shape[0], dtype=bool)
        out.iloc[i] = np.nanmean(c[m])
    return out


def block_macro(diag):
    indicators = {"Implied vol (BTC DVOL)": DVOL, "Realized vol (30d)": RV30,
                  "Return dispersion (7d)": rets.std(axis=1).rolling(7).mean(),
                  "Avg pairwise correlation (30d)": avg_pairwise_corr(30)}
    pd.DataFrame(indicators).to_csv(f"{OUT}/G_macro_indicators.csv")
    rows = []
    for sname, w in diag.items():
        bt = C.backtest(w, rets)
        for iname, x in indicators.items():
            lab = pd.cut(rolling_pct(x).shift(1), [0, 1 / 3, 2 / 3, 1.0001],
                         labels=["Low", "Mid", "High"]).reindex(bt.index)
            rec = {"Strategy": sname, "Indicator": iname}
            for per, sl in [("IS", slice(None, C.IS_END)), ("OOS", slice(C.OOS_START, None))]:
                for k in ["Low", "Mid", "High"]:
                    g = bt.gross.loc[sl][lab.loc[sl] == k]
                    rec[f"{k} Sharpe {per}"] = C.sharpe(g)
            rows.append(rec)
    df = save(pd.DataFrame(rows), "G_macro_regimes", index=False)
    names = list(diag)
    fig, axes = plt.subplots(1, len(indicators), figsize=(13, 3.9), sharey=True)
    for ax, iname in zip(axes, indicators):
        sub = df[df.Indicator == iname].set_index("Strategy").loc[names, ["Low Sharpe IS", "Mid Sharpe IS", "High Sharpe IS"]]
        ax.imshow(sub.values, cmap="RdBu", vmin=-2.5, vmax=2.5, aspect="auto")
        for i in range(sub.shape[0]):
            for j in range(3):
                ax.text(j, i, f"{sub.values[i, j]:.2f}", ha="center", va="center", fontsize=8.5)
        ax.set_xticks(range(3)); ax.set_xticklabels(["Low", "Mid", "High"])
        ax.set_title(iname, fontsize=9); ax.grid(False)
    axes[0].set_yticks(range(len(names))); axes[0].set_yticklabels(names, fontsize=8.5)
    fig.suptitle("Gross Sharpe by macro regime, research period (trailing-year tercile, known before the trade)",
                 fontsize=11)
    savefig("G_macro_regimes")
    return df


# =========================================================================== #
# H. MECHANICAL CANDIDATE GENERATION + SELECTION (research period only)
# =========================================================================== #
EXEC_VARIANTS = {
    "Daily rebalance": lambda w: w,
    "Hold 3d (overlapping)": lambda w: C.hold(w, 3),
    "Hold 7d (overlapping)": lambda w: C.hold(w, 7),
    "No-trade band 2%": lambda w: C.band(w, 0.02),
    "No-trade band 5%": lambda w: C.band(w, 0.05),
}


def block_candidates():
    """Direction from the research-period gross Sharpe, then a holding-period
    grid; every row records which book it falls in and its IS / OOS stats."""
    dir_rows, rows, books = [], [], {}
    for fam, lab, w0 in signal_grid():
        base = C.backtest(w0, rets)
        g_is = C.sharpe(base.gross.loc[:C.IS_END])
        d = 1 if g_is >= 0 else -1
        book = "Momentum" if d == 1 else "Reversal"
        dir_rows.append({"family": FAMILY_LABEL[fam], "signal": lab, "Gross IS (momentum sign)": g_is,
                         "Direction (from IS)": "momentum" if d == 1 else "reversal",
                         "Gross OOS (momentum sign)": C.sharpe(base.gross.loc[C.OOS_START:])})
        for H in HOLDS[fam]:
            w = C.hold(d * w0, H)
            name = f"{lab} {'MOM' if d == 1 else 'REV'} H={H}"
            bt = C.backtest(w, rets)
            cost = C.MARKET_BPS if book == "Momentum" else C.LIMIT_BPS
            r = row(name, bt, family=FAMILY_LABEL[fam], book=book, exec_cost_bps=cost)
            r["Selection IS"] = C.sharpe(C.net_at(bt, cost).loc[:C.IS_END])
            rows.append(r); books[name] = w
    # cointegrated pairs: reversal by construction
    cbt = coint_bt()
    r = row("Cointegrated pairs REV", cbt, family=FAMILY_LABEL["PAIRS"], book="Reversal", exec_cost_bps=C.LIMIT_BPS)
    r["Selection IS"] = C.sharpe(C.net_at(cbt, C.LIMIT_BPS).loc[:C.IS_END])
    rows.append(r)
    save(pd.DataFrame(dir_rows), "H_signal_directions", index=False)
    sel = pd.DataFrame(rows).sort_values(["book", "Selection IS"], ascending=[True, False])
    save(sel, "H_candidate_selection", index=False)
    return sel, books, cbt


def pick_book(sel, book, n_fam=3):
    sub = sel[(sel.book == book) & (sel["Selection IS"] > 0)]
    best = sub.sort_values("Selection IS", ascending=False).groupby("family", sort=False).head(1)
    return best.head(n_fam)


def sleeve_returns(members, books, cbt, cost, exec_name):
    """Return-level equal-weight ensemble of the book's members at its cost."""
    nets, turns = [], []
    for name in members:
        if name.startswith("Cointegrated pairs"):
            nets.append(C.net_at(cbt, cost)); turns.append(cbt.turnover)
        else:
            bt = C.backtest(EXEC_VARIANTS[exec_name](books[name]), rets)
            nets.append(C.net_at(bt, cost)); turns.append(bt.turnover)
    gross_turn = pd.concat(turns, axis=1).mean(axis=1)
    return pd.concat(nets, axis=1).mean(axis=1), gross_turn


def sleeve_gross(members, books, cbt, exec_name):
    out = []
    for name in members:
        if name.startswith("Cointegrated pairs"):
            out.append(cbt.gross)
        else:
            out.append(C.backtest(EXEC_VARIANTS[exec_name](books[name]), rets).gross)
    return pd.concat(out, axis=1).mean(axis=1)


# =========================================================================== #
# I. WEIGHTING
# =========================================================================== #
def combine(sleeves, method, lookback=180):
    """Walk-forward weights from trailing data only (rebalanced every 21 days)."""
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
            for _ in range(200):
                rc = w * (cov @ w)
                w = w * (rc.mean() / np.maximum(rc, 1e-12)) ** 0.5
            w = pd.Series(w, index=R.columns)
        else:   # Mean-variance (shrunk)
            mu = hist.mean() * 0.5
            cov = 0.5 * hist.cov() + 0.5 * np.diag(np.diag(hist.cov()))
            w = pd.Series(np.linalg.pinv(cov.values) @ mu.values, index=R.columns).clip(lower=0)
            if w.sum() == 0:
                w = 1 / vol
        W.iloc[t:t + 21] = (w / w.sum()).values
    W = W.ffill()
    port = (W * R).sum(axis=1)
    port[W.isna().all(axis=1)] = np.nan
    return port, W


# =========================================================================== #
# MAIN
# =========================================================================== #
def main():
    print(f"Panel {SAMPLE_START} -> {SAMPLE_END}, {close.shape[1]} assets")
    print("A. horizon");          block_horizon()
    print("A2/C/E. intraday");    block_intraday()
    print("B. activity");         block_activity()
    print("D. themes");           block_themes()
    print("F. correlation");      block_correlation()
    diag = {"TS momentum (blend)": w_ts("blend"), "CS 14d (momentum sign)": w_cs(14),
            "Theme 21d (momentum sign)": w_theme(21), "CS 1d (momentum sign)": w_cs(1),
            "CS 90d (momentum sign)": w_cs(90)}
    print("C. seasonality");      block_seasonality(diag)
    print("G. macro");            block_macro(diag)
    print("H. candidates");       sel, books, cbt = block_candidates()

    mom = pick_book(sel, "Momentum"); rev = pick_book(sel, "Reversal")
    mom_members, rev_members = mom.Strategy.tolist(), rev.Strategy.tolist()
    print(f"   momentum book: {mom_members}")
    print(f"   reversal book: {rev_members}")
    if not mom_members or not rev_members:
        raise SystemExit("a book has no member with positive research-period net Sharpe")

    # execution variant per book, chosen on the research period
    exe, ex_rows = {}, []
    for book, members, cost in [("Momentum", mom_members, C.MARKET_BPS), ("Reversal", rev_members, C.LIMIT_BPS)]:
        best_v, best_s = None, -np.inf
        for v in EXEC_VARIANTS:
            net, turn = sleeve_returns(members, books, cbt, cost, v)
            g = sleeve_gross(members, books, cbt, v)
            s_is = C.sharpe(net.loc[:C.IS_END])
            alt = C.MARKET_BPS if book == "Reversal" else C.LIMIT_BPS
            net_alt, _ = sleeve_returns(members, books, cbt, alt, v)
            ex_rows.append({"Book": book, "Execution": v, "Turnover": turn.mean(),
                            "Sharpe gross": C.sharpe(g), "Sharpe IS @book cost": s_is,
                            f"Sharpe full @book cost": C.sharpe(net),
                            "Sharpe full @other cost": C.sharpe(net_alt),
                            "Cost drag/yr @book cost": turn.mean() * cost / 1e4 * C.ANN})
            if s_is > best_s:
                best_v, best_s = v, s_is
        exe[book] = best_v
    save(pd.DataFrame(ex_rows), "H_execution_variants", index=False)
    print(f"   execution chosen on IS: {exe}")

    mom_net20, mom_turn = sleeve_returns(mom_members, books, cbt, C.MARKET_BPS, exe["Momentum"])
    mom_net7, _ = sleeve_returns(mom_members, books, cbt, C.LIMIT_BPS, exe["Momentum"])
    rev_net7, rev_turn = sleeve_returns(rev_members, books, cbt, C.LIMIT_BPS, exe["Reversal"])
    rev_net20, _ = sleeve_returns(rev_members, books, cbt, C.MARKET_BPS, exe["Reversal"])

    sleeves = {"Momentum": mom_net20, "Reversal": rev_net7}
    corr = pd.DataFrame({"Momentum book": mom_net20, "Reversal book": rev_net7,
                         "Cointegrated pairs": C.net_at(cbt, C.LIMIT_BPS),
                         "BTC": btc.loc[C.BT_START:]}).corr()
    save(corr, "I_sleeve_correlation")

    methods = ["Equal weight", "Inverse volatility", "Risk parity (ERC)", "Mean-variance (shrunk)"]
    combos, weights = {}, {}
    for m in methods:
        combos[m], weights[m] = combine(sleeves, m)
    start = max(c.first_valid_index() for c in combos.values())
    wt = save(pd.DataFrame([{"Method": m,
                             "Avg weight Momentum": weights[m].loc[start:, "Momentum"].mean(),
                             "Avg weight Reversal": weights[m].loc[start:, "Reversal"].mean(),
                             "Sharpe IS": C.sharpe(combos[m].loc[start:C.IS_END]),
                             "Sharpe OOS": C.sharpe(combos[m].loc[C.OOS_START:]),
                             "Sharpe": C.sharpe(combos[m].loc[start:])} for m in methods]),
              "I_weighting_methods", index=False)
    best_m = wt.sort_values("Sharpe IS", ascending=False).iloc[0]["Method"]
    print(f"   weighting chosen on IS: {best_m}")
    combo = combos[best_m].loc[start:]
    combo20 = combine({"Momentum": mom_net20, "Reversal": rev_net20}, best_m)[0].loc[start:]

    # robustness: single IS-best member per book instead of the ensemble
    rb = []
    for lab, mm, rr in [("Final: top-3 family ensembles", mom_members, rev_members),
                        ("Single IS-best strategy per book", mom_members[:1], rev_members[:1])]:
        mn, _ = sleeve_returns(mm, books, cbt, C.MARKET_BPS, exe["Momentum"])
        rn, _ = sleeve_returns(rr, books, cbt, C.LIMIT_BPS, exe["Reversal"])
        cmb = combine({"Momentum": mn, "Reversal": rn}, best_m)[0].loc[start:]
        rb.append({"Construction": lab, "Momentum Sharpe IS": C.sharpe(mn.loc[start:C.IS_END]),
                   "Momentum Sharpe OOS": C.sharpe(mn.loc[C.OOS_START:]),
                   "Reversal Sharpe IS": C.sharpe(rn.loc[start:C.IS_END]),
                   "Reversal Sharpe OOS": C.sharpe(rn.loc[C.OOS_START:]),
                   "Combined Sharpe IS": C.sharpe(cmb.loc[:C.IS_END]),
                   "Combined Sharpe OOS": C.sharpe(cmb.loc[C.OOS_START:])})
    save(pd.DataFrame(rb), "I_selection_robustness", index=False)

    # J. performance
    idx = combo.index
    series = {
        "Combined portfolio": combo,
        "Combined (all trades at 20bps)": combo20,
        "Momentum book (20bps market)": mom_net20.reindex(idx),
        "Momentum book (7bps limit)": mom_net7.reindex(idx),
        "Reversal book (7bps limit)": rev_net7.reindex(idx),
        "Reversal book (20bps market)": rev_net20.reindex(idx),
        "Cointegrated pairs (20bps)": cbt.net.reindex(idx),
        "Equal-weight crypto (B&H)": mkt.reindex(idx).fillna(0),
        "Buy & Hold BTC": btc.reindex(idx).fillna(0),
    }
    turns = {"Momentum book (20bps market)": mom_turn.reindex(idx),
             "Reversal book (7bps limit)": rev_turn.reindex(idx)}
    b = btc.reindex(idx)
    oos = C.perf_table({k: v.loc[C.OOS_START:] for k, v in series.items()}, b.loc[C.OOS_START:])
    ins = C.perf_table({k: v.loc[:C.IS_END] for k, v in series.items()}, b.loc[:C.IS_END])
    full = C.perf_table(series, b, turns)
    save(oos, "J_performance_oos"); save(ins, "J_performance_is"); save(full, "J_performance_full")
    pd.DataFrame(series).to_csv(f"{OUT}/J_daily_returns.csv")

    sw = []
    for bps in [0, 5, 7, 10, 20, 30, 50, 100, 200]:
        mn, _ = sleeve_returns(mom_members, books, cbt, bps, exe["Momentum"])
        rn, _ = sleeve_returns(rev_members, books, cbt, bps, exe["Reversal"])
        cmb = combine({"Momentum": mn, "Reversal": rn}, best_m)[0].loc[start:]
        sw.append({"cost_bps": bps, "Momentum book": C.sharpe(mn.loc[start:]),
                   "Reversal book": C.sharpe(rn.loc[start:]),
                   "Combined": C.sharpe(cmb), "Combined hold-out": C.sharpe(cmb.loc[C.OOS_START:])})
    sweep = save(pd.DataFrame(sw), "H_cost_sweep", index=False)

    make_final_figures(series, best_m, sweep, weights[best_m].loc[start:])
    n_dir = pd.read_csv(f"{OUT}/H_signal_directions.csv")
    summary = {
        "version": "V2", "sample_start": SAMPLE_START, "sample_end": SAMPLE_END,
        "bt_start": str(idx.min().date()), "bt_end": str(idx.max().date()),
        "is_end": C.IS_END, "oos_start": C.OOS_START, "n_assets": int(close.shape[1]),
        "annualisation": C.ANN, "momentum_members": mom_members, "reversal_members": rev_members,
        "execution_selected": exe, "weighting_selected": best_m,
        "n_signals": int(len(n_dir)), "n_candidates": int(len(sel)),
        "market_bps": C.MARKET_BPS, "limit_bps": C.LIMIT_BPS,
    }
    json.dump(summary, open(f"{OUT}/summary.json", "w"), indent=2)
    pd.set_option("display.width", 250)
    cols = ["Ann.Return", "Ann.Vol", "Sharpe", "MaxDD", "Alpha", "Beta", "Alpha t", "Corr BTC"]
    print("\n=== HOLD-OUT ===\n", oos[cols].round(3).to_string())
    print("\n=== RESEARCH ===\n", ins[cols].round(3).to_string())
    print("\n=== FULL ===\n", full[cols].round(3).to_string())
    print("\n", wt.round(3).to_string())
    print(json.dumps(summary, indent=2))


def make_final_figures(series, best_m, sweep, wts):
    fig, ax = plt.subplots(figsize=(11, 5))
    for k, lab, col, lw in [("Combined portfolio", f"Combined ({best_m.lower()} weights)", GREEN, 2.4),
                            ("Momentum book (20bps market)", "Momentum book (20 bps)", NAVY, 1.4),
                            ("Reversal book (7bps limit)", "Reversal book (7 bps)", GOLD, 1.4),
                            ("Buy & Hold BTC", "Buy & Hold BTC", GREY, 1.2),
                            ("Equal-weight crypto (B&H)", "Equal-weight crypto", CORAL, 1.0)]:
        (1 + series[k].fillna(0)).cumprod().plot(ax=ax, label=lab, color=col, lw=lw)
    ax.axvline(pd.Timestamp(C.OOS_START), color="black", ls="--", lw=0.9)
    ax.axvspan(pd.Timestamp(C.OOS_START), series["Combined portfolio"].index[-1], color=GOLD, alpha=0.06)
    ax.text(pd.Timestamp(C.OOS_START), ax.get_ylim()[1] * 0.95, "  hold-out (never used for decisions)",
            va="top", fontsize=9)
    ax.set_yscale("log"); ax.set_title("Growth of $1 (log scale), net of transaction costs")
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=3); ax.set_xlabel("")
    savefig("J_equity_curves")

    fig, ax = plt.subplots(figsize=(11, 4))
    for k, lab, col, a in [("Combined portfolio", "Combined", GREEN, 0.35),
                           ("Buy & Hold BTC", "Buy & Hold BTC", GREY, 0.15)]:
        cum = (1 + series[k].fillna(0)).cumprod()
        ax.fill_between(cum.index, (cum / cum.cummax() - 1).values, 0, alpha=a, color=col, label=lab)
    ax.set_title("Drawdowns"); ax.legend(frameon=False, fontsize=9); ax.set_ylabel("Drawdown")
    savefig("J_drawdowns")

    fig, ax = plt.subplots(figsize=(11, 4))
    for k, lab, col in [("Combined portfolio", "Combined", GREEN), ("Momentum book (20bps market)", "Momentum", NAVY),
                        ("Reversal book (7bps limit)", "Reversal", GOLD)]:
        r = series[k]
        (r.rolling(180).mean() / r.rolling(180).std() * np.sqrt(C.ANN)).plot(ax=ax, label=lab, color=col)
    ax.axhline(0, color="black", lw=0.8); ax.axvline(pd.Timestamp(C.OOS_START), color="black", ls="--", lw=0.8)
    ax.set_title("Rolling 180-day Sharpe (net, x sqrt(252))"); ax.legend(frameon=False, fontsize=9); ax.set_xlabel("")
    savefig("J_rolling_sharpe")

    fig, ax = plt.subplots(figsize=(9, 4.4))
    for c, col in zip(["Momentum book", "Reversal book", "Combined", "Combined hold-out"], [NAVY, GOLD, GREEN, GREY]):
        ax.plot(sweep.cost_bps, sweep[c], marker="o", label=c, color=col, lw=2 if c == "Combined" else 1.4,
                ls="--" if "hold-out" in c else "-")
    ax.axhline(0, color="black", lw=0.8)
    for bb, lab in [(7, "limit 7"), (20, "market 20")]:
        ax.axvline(bb, color=GREY, ls=":", lw=1); ax.text(bb, ax.get_ylim()[1] * 0.95, f" {lab}", fontsize=8.5)
    ax.set_xscale("symlog", linthresh=10); ax.set_xticks([0, 5, 7, 10, 20, 30, 50, 100, 200])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.set_xlabel("Transaction cost (bps per unit turnover)"); ax.set_ylabel("Net Sharpe")
    ax.set_title("Net Sharpe vs transaction cost"); ax.legend(frameon=False, fontsize=9)
    savefig("H_cost_sweep")

    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.stackplot(wts.index, wts["Momentum"], wts["Reversal"], labels=["Momentum", "Reversal"],
                 colors=[NAVY, GOLD], alpha=0.85)
    ax.set_ylim(0, 1); ax.set_title(f"Walk-forward book weights ({best_m})")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    savefig("I_sleeve_weights")


if __name__ == "__main__":
    import warnings
    warnings.filterwarnings("ignore")
    main()
