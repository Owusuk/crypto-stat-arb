"""
build_report.py  (V2) - generate crypto_research_report.docx from the canonical
outputs in data/ and data/research/.  Every number is read from those files.
Formatting comes from docx_helpers (TNR 11, indented bullets, plain hyphens).
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from docx_helpers import (doc, para, rich, bullet, heading, table, figure, tcap, add_toc,
                          finish, Inches, WD_ALIGN_PARAGRAPH)

R = "data/research"
S = json.load(open(f"{R}/summary.json"))
rd = lambda n, **k: pd.read_csv(f"{R}/{n}.csv", **k)
FULL = rd("J_performance_full").set_index("Strategy")
OOS = rd("J_performance_oos").set_index("Strategy")
INS = rd("J_performance_is").set_index("Strategy")
HOR, ACT, WKD = rd("A_horizon_scan"), rd("B_activity_volume"), rd("C_weekday_weekend").set_index("Strategy")
THM, COR, MAC = rd("D_theme_momentum"), rd("F_correlation").set_index("Strategy"), rd("G_macro_regimes")
DIRS, SEL, EXE = rd("H_signal_directions"), rd("H_candidate_selection"), rd("H_execution_variants")
SWP, WTS, RB = rd("H_cost_sweep").set_index("cost_bps"), rd("I_weighting_methods").set_index("Method"), rd("I_selection_robustness")
CORR = rd("I_sleeve_correlation", index_col=0)
IH = rd("A2_intraday_horizon") if os.path.exists(f"{R}/A2_intraday_horizon.csv") else None
FR = rd("E_frontrun_us_session") if os.path.exists(f"{R}/E_frontrun_us_session.csv") else None
SESS = rd("C_session_returns") if os.path.exists(f"{R}/C_session_returns.csv") else None
UNI = pd.read_csv("data/universe.csv")
PAIRS = json.load(open("data/run_summary.json"))
V1 = json.load(open("data/research/v1_reference.json"))

CMB, CMB20 = "Combined portfolio", "Combined (all trades at 20bps)"
MOM20, MOM7 = "Momentum book (20bps market)", "Momentum book (7bps limit)"
REV7, REV20 = "Reversal book (7bps limit)", "Reversal book (20bps market)"
PRS, EW, BTC = "Cointegrated pairs (20bps)", "Equal-weight crypto (B&H)", "Buy & Hold BTC"
co, ci, cf = OOS.loc[CMB], INS.loc[CMB], FULL.loc[CMB]
best_m = S["weighting_selected"]
n_in = int((UNI.status == "in universe").sum())


def pct(x, d=1):
    v = round(x * 100, d)
    return f"{0.0 if v == 0 else v:.{d}f}%"


def num(x, d=2):
    v = round(x, d)
    return f"{0.0 if v == 0 else v:.{d}f}"


def hz(kind, L, col="Gross IS"):
    return HOR[(HOR.kind == kind) & (HOR.lookback_days == L)][col].iloc[0]


def act(L, v, col="Gross IS"):
    return ACT[(ACT.lookback_days == L) & (ACT.variant == v)][col].iloc[0]


def mac(strat, ind, k, per="IS"):
    return MAC[(MAC.Strategy == strat) & (MAC.Indicator == ind)][f"{k} Sharpe {per}"].iloc[0]


def sel(name, col):
    return SEL[SEL.Strategy == name][col].iloc[0]


def pretty(name):
    return (name.replace(" MOM ", " momentum, hold ").replace(" REV ", " reversal, hold ")
            .replace("H=", "").replace("L=", "look-back ").replace("blend", "7/14/28 blend"))


PERF_KEYS = [CMB, CMB20, MOM20, MOM7, REV7, REV20, PRS, EW, BTC]
PERF_LABS = ["Combined portfolio *", "Combined (all trades at 20 bps)", "Momentum book (20 bps)",
             "Momentum book (7 bps)", "Reversal book (7 bps)", "Reversal book (20 bps)",
             "Cointegrated pairs (20 bps)", "Equal-weight crypto", "Buy & hold BTC"]
PERF_HEAD = ["Strategy", "Ann. return", "Ann. vol", "Sharpe", "Max DD", "Alpha", "Beta", "Alpha t", "Corr BTC"]
PERF_W = [2.0, 0.58, 0.55, 0.55, 0.58, 0.55, 0.5, 0.55, 0.6]
PNOTE = ("* Momentum book at 20 bps (market orders), reversal book at 7 bps (limit orders). Sharpe = mean / std x "
         "sqrt(252); return, volatility and alpha annualised with 252 days. Alpha, beta and correlation vs daily "
         "Bitcoin returns; alpha t uses Newey-West (5-lag) errors.")


def perf_rows(df, keys=PERF_KEYS, labs=PERF_LABS):
    out = []
    for k, lab in zip(keys, labs):
        r = df.loc[k]
        out.append([lab, pct(r["Ann.Return"]), pct(r["Ann.Vol"]), num(r["Sharpe"]), pct(r["MaxDD"]),
                    pct(r["Alpha"]), num(r["Beta"]), num(r["Alpha t"]), num(r["Corr BTC"])])
    return out


# =========================================================================== #
# TITLE + CONTENTS
# =========================================================================== #
for _ in range(5):
    doc.add_paragraph()
para("Statistical Arbitrage in Cryptocurrencies", bold=True, size=22, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para("Momentum and Reversal Research on Live Market Data - Version 2", italic=True, size=14,
     align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)
para("Wall Street Quants - Bootcamp Project", size=12, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para(f"Survivorship-free universe of {n_in} coins | data {S['sample_start']} to {S['sample_end']}",
     size=11, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para("Revised after trainer feedback, October 2026", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_page_break()
heading("Contents", 1)
add_toc()
doc.add_page_break()

# =========================================================================== #
# EXECUTIVE SUMMARY - hold-out first
# =========================================================================== #
heading("Executive Summary", 1)
para(
    "This is version 2 of the project. It answers the class brief - research momentum and reversal strategies in "
    "crypto, test them with unconstrained backtests at 20 bps (market orders) and 7 bps (limit orders), combine them "
    "with a weighting scheme and report returns, volatility, Sharpe, drawdown and alpha / beta - and it fixes the five "
    "points raised in the trainer's review of version 1 (Section 0).")
para("Headline: the hold-out result", bold=True, space_after=3)
para(
    f"All research and every design decision used only 2021-07 to 2023-12. On the untouched hold-out "
    f"({S['oos_start']} to {S['sample_end']}) the combined momentum + reversal portfolio earned a net Sharpe of "
    f"{num(co['Sharpe'])}, an annualised alpha of {pct(co['Alpha'])} with a t-statistic of only {num(co['Alpha t'])}, "
    f"a beta to Bitcoin of {num(co['Beta'])} and a correlation to Bitcoin of {num(co['Corr BTC'])}. In the research "
    f"period the same portfolio had a Sharpe of {num(ci['Sharpe'])} and an alpha t-statistic of {num(ci['Alpha t'])}. "
    "The edge did not survive out of sample at a statistically meaningful level.")
table(["Combined portfolio", "Sharpe", "Ann. return", "Ann. vol", "Max DD", "Alpha", "Alpha t", "Beta", "Corr BTC"],
      [[lab, num(r["Sharpe"]), pct(r["Ann.Return"]), pct(r["Ann.Vol"]), pct(r["MaxDD"]), pct(r["Alpha"]),
        num(r["Alpha t"]), num(r["Beta"]), num(r["Corr BTC"])]
       for lab, r in [(f"Hold-out {S['oos_start'][:4]}-{S['sample_end'][:4]}", co),
                      (f"Research {S['bt_start'][:4]}-{S['is_end'][:4]}", ci),
                      ("Full backtest", cf),
                      ("Buy & hold BTC, hold-out", OOS.loc[BTC])]],
      widths=[1.75, 0.55, 0.65, 0.6, 0.6, 0.55, 0.55, 0.5, 0.65], bold_rows={0},
      caption=tcap("Combined portfolio, net of costs. Hold-out first."), note=PNOTE)
para("Key findings", bold=True, space_after=3)
bullet(f"With {n_in} coins chosen by market cap at the start of 2021, research-period data show cross-sectional "
       f"reversal at 1-5 days (1-day gross Sharpe {num(hz('Cross-sectional', 1))}) and at 21-120 days, and "
       f"time-series momentum at 1-4 week horizons ({num(hz('Time-series', 30))} at 30 days).", "Horizon. ")
bullet("Short-horizon reversal is real in gross terms but its turnover makes it lose money even with 7 bps limit "
       "orders; only slow signals survive the brief's costs.", "Costs. ")
bullet(f"Time-series momentum with an implied-volatility (DVOL) filter is the one component that held up: research "
       f"net Sharpe {num(sel(S['momentum_members'][1] if len(S['momentum_members']) > 1 else S['momentum_members'][0], 'Net20 IS'))}, "
       f"hold-out {num(sel(S['momentum_members'][1] if len(S['momentum_members']) > 1 else S['momentum_members'][0], 'Net20 OOS'))} "
       "at 20 bps. Theme momentum and the slow reversal signals that looked best in 2021-2023 decayed.",
       "What survived. ")
bullet(f"Version 1 reported a Sharpe of 1.02 using sqrt(365). On the class sqrt(252) scale that is "
       f"{num(V1['sharpe_full_252'])} (full) and {num(V1['sharpe_oos_252'])} (hold-out). Removing survivorship bias "
       f"and hold-out contamination takes the hold-out Sharpe from {num(V1['sharpe_oos_252'])} to {num(co['Sharpe'])}.",
       "Version 1 vs version 2. ")

# =========================================================================== #
# 0. CHANGES
# =========================================================================== #
heading("0. Changes in Version 2 (Response to Trainer Feedback)", 1)
table(["Trainer comment", "Change in version 2", "Effect"], [
    ["Sharpe used sqrt(365); class uses mean / std x sqrt(252)",
     "All Sharpe ratios use sqrt(252); returns, volatility and alpha are annualised with 252 days (sa_core.ANN = 252)",
     f"V1 combined Sharpe 1.02 -> {num(V1['sharpe_full_252'])} (full), 0.55 -> {num(V1['sharpe_oos_252'])} (hold-out)"],
    ["Hold-out not untouched: exploration ran on 2021-2026 and the 60/90-day reversal only appears in 2024-2026",
     "Pre-registered mechanical protocol: every signal's direction, every candidate, the execution rule and the "
     "weighting are chosen on 2021-07 to 2023-12 only (Section 4.4)",
     f"The hold-out is now a true out-of-sample test; the combined hold-out Sharpe is {num(co['Sharpe'])}"],
    ["Lead with hold-out numbers; alpha t falls from 2.19 to 0.90; add correlation to BTC",
     "Hold-out reported first everywhere (summary, tables, README, deck); correlation to BTC added to every table",
     f"Hold-out alpha t = {num(co['Alpha t'])}; correlation to BTC = {num(co['Corr BTC'])}"],
    ["Universe: 30+ coins by market cap at the start, not the 16 survivors",
     f"Top 40 coins by market cap on 2021-01-03 (stablecoins and wrapped tokens excluded); {n_in} have free data. "
     "Coins that collapsed or were delisted (FTT, EOS, MKR) are kept until their prices end",
     "Removes survivorship bias; the universe includes the FTX collapse and other failures"],
    ["Be able to explain every choice and rebuild the backtest",
     "src/minimal_backtest.py rebuilds a strategy in ~60 lines and checks it against the engine; a separate "
     "methodology explainer covers every choice and likely interview questions",
     "Engine and minimal backtest agree to machine precision"],
], widths=[1.8, 2.75, 1.95], size=8.5, caption=tcap("Trainer feedback and the version 2 response."))

# =========================================================================== #
# 1-2. INTRO + LITERATURE
# =========================================================================== #
heading("1. Introduction", 1)
para(
    "Statistical arbitrage looks for price-volume patterns that predict returns. The brief highlights momentum (recent "
    "winners keep winning) and reversal (recent moves undo themselves), and gives a research outline for each: time "
    "horizon, new information and activity, seasonality, investment themes and technical plays for momentum; time "
    "horizon, uninformed trading, correlation and macro dislocation for reversal. It then asks for unconstrained "
    "backtests, realistic execution costs, a weighting scheme and standard performance metrics.")
para(
    "Version 2 keeps the research outline of version 1 but changes how conclusions are drawn. The universe is fixed "
    "by market cap at the start of the sample, so it includes coins that later failed. All exploration and selection "
    "uses the 2021-2023 research period, through a mechanical rule set written down before the hold-out is "
    "examined. The research question is unchanged: which momentum and reversal patterns exist in crypto, which "
    "survive realistic costs, and how should they be combined?")
heading("2. Literature Review", 1)
para(
    "Cross-sectional momentum (Jegadeesh & Titman, 1993), time-series momentum (Moskowitz, Ooi & Pedersen, 2012) and "
    "industry momentum (Moskowitz & Grinblatt, 1999) are robust across asset classes, but momentum crashes in "
    "high-volatility rebounds (Daniel & Moskowitz, 2016) and benefits from volatility scaling (Barroso & Santa-Clara, "
    "2015). Short-term reversal (Lehmann, 1990) is a reward for supplying liquidity: low-volume moves reverse more "
    "(Campbell, Grossman & Wang, 1993) and reversal profits rise with market volatility (Nagel, 2012). Long-horizon "
    "reversal reflects overreaction (De Bondt & Thaler, 1985). In crypto, Liu and Tsyvinski (2021) and Liu, Tsyvinski "
    "and Wu (2022) document a momentum factor, Han, Kang and Ryu (2024) find time-series momentum more robust than "
    "cross-sectional momentum after costs, and Fil and Kristoufek (2020) find pairs relationships unstable. Garleanu "
    "and Pedersen (2013) motivate partial trading toward targets; DeMiguel, Garlappi and Uppal (2009) show that "
    "simple weights are hard to beat. Harvey, Liu and Zhu (2016) and Bailey and Lopez de Prado (2014) warn that "
    "testing many strategies inflates backtest Sharpe ratios - the reason for version 2's protocol. Survivorship "
    "bias, the reason for version 2's universe, is a standard concern in any backtest that conditions on assets that "
    "still exist at the end of the sample.")

# =========================================================================== #
# 3. DATA
# =========================================================================== #
heading("3. Data", 1)
heading("3.1 A survivorship-free universe", 2)
para(
    "Version 1 traded 16 coins that were still liquid on Coinbase in 2026, which quietly excludes every coin that "
    "failed. Version 2 fixes the universe at the start of the sample: the 40 largest coins by market capitalisation "
    "in the CoinMarketCap historical snapshot of 2021-01-03, after removing stablecoins (USDT, USDC, DAI, BUSD) and "
    "wrapped tokens (WBTC). Membership never changes with hindsight. A coin leaves the cross-section only when its "
    f"price history ends. Of the 40, {n_in} have free price history; Revain (REV) has none and is the only drop.")
uni_in = UNI[UNI.status == "in universe"]
rows = []
for _, r in UNI[UNI.status != "excluded"].iterrows():
    note = r.reason if isinstance(r.reason, str) and r.reason else ""
    rows.append([int(r.cmc_rank), r.asset, r["name"], r.source if isinstance(r.source, str) else "-",
                 str(r["first"]) if isinstance(r["first"], str) else "-",
                 str(r["last"]) if isinstance(r["last"], str) else "-", note or "active"])
table(["Rank", "Coin", "Name", "Source", "First price", "Last price", "Status"], rows,
      widths=[0.45, 0.55, 1.3, 0.75, 0.9, 0.9, 1.65], size=8,
      caption=tcap("Universe: top 40 non-stablecoin coins by market cap on 2021-01-03."))
heading("3.2 Prices and sources", 2)
para(
    "For each coin, daily candles were requested from three free public APIs - Coinbase Exchange (USD), KuCoin and "
    "Gate.io (USDT) and Bitfinex (USD) - and the source with the most complete history from January 2021 was used, "
    "breaking ties by dollar volume. The same source supplies hourly candles where available. USDT is treated as USD. "
    "Binance is geo-restricted from the research environment (HTTP 451). Bitfinex keeps the history of delisted "
    "pairs, which is how FTX Token (FTT, collapsed November 2022) enters the sample. Implied volatility is the "
    "Deribit DVOL index.")
para(
    "Several coins trade thinly at their chosen venue (median daily dollar volume below $100,000 for XEM, CEL and "
    "FTT). Their prices are real but noisy, and a fund could not trade them at size; Section 11.3 discusses this. "
    "Prices are aligned to a daily calendar, gaps of up to three days are forward-filled, and simple close-to-close "
    "returns are used.")
heading("3.3 Investment themes", 2)
import sa_core as C
table(["Theme", "Coins"], [[t, ", ".join(l)] for t, l in C.THEMES.items()], widths=[2.0, 4.5],
      caption=tcap("Themes, assigned from each project's function rather than from returns."))

# =========================================================================== #
# 4. METHOD
# =========================================================================== #
heading("4. Backtest Methodology", 1)
heading("4.1 Unconstrained backtest", 2)
para(
    "Each day a signal is turned into weights using information up to that day's close; the weights earn the next "
    "day's return, so there is no look-ahead. Gross exposure (sum of absolute weights) is one. Cross-sectional "
    "strategies are dollar-neutral, with weights proportional to each coin's demeaned rank. Time-series strategies "
    "hold each coin long or short on its own signal, scaled by the inverse of its 30-day volatility. "
    "src/minimal_backtest.py reproduces this in about 60 lines and checks itself against the engine.")
heading("4.2 Costs", 2)
para(
    "Costs follow the brief: 20 bps per unit of turnover for market orders and 7 bps for limit orders. Momentum-"
    "direction strategies are charged 20 bps because they chase price and need immediate fills. Reversal-direction "
    "strategies are charged 7 bps because they buy what has fallen and sell what has risen, supplying liquidity, "
    "and they trade slowly enough to work passive orders. Every result is also shown with all trades at 20 bps.")
heading("4.3 Metrics", 2)
para(
    "Following the class convention, Sharpe = mean / standard deviation x sqrt(252) on daily returns, and annual "
    "return, volatility and alpha use 252 days. Crypto trades 365 days a year, so these are a common yardstick across "
    "projects rather than calendar-year figures (multiply by sqrt(365/252) = 1.20 for the calendar Sharpe). Alpha, "
    "beta and correlation come from daily returns against Bitcoin; the alpha t-statistic uses Newey-West (5-lag) "
    "standard errors. Maximum drawdown and CAGR use actual compounded returns.")
heading("4.4 Pre-registered protocol", 2)
para(f"The research period is {C.BT_START} to {S['is_end']}; the hold-out is {S['oos_start']} onward. The protocol, "
     "written before the hold-out was examined, makes every decision mechanically from research-period data:")
bullet(f"{S['n_signals']} signal variants across seven families - cross-sectional return (1-120 days, with and "
       "without a 14-day skip and volume weighting), time-series return (with and without a DVOL filter), theme "
       "return, residual versus the market, residual versus the coin's theme, short-term reversal in high-volatility "
       "regimes, and cointegrated pairs.", "Signals: ")
bullet("each signal's direction - follow it (momentum) or fade it (reversal) - is the sign of its research-period "
       "gross Sharpe. Nothing about direction is chosen by hand.", "Direction: ")
bullet(f"every signal is crossed with a grid of holding periods, giving {S['n_candidates']} candidates, each "
       "charged its book's cost.", "Candidates: ")
bullet("in each book (momentum, reversal) the best variant of each family is kept if its research-period net "
       "Sharpe is positive; the book is an equal-weight ensemble of the top three families.", "Books: ")
bullet("the execution rule (holding period or no-trade band) for each book and the weighting method for "
       "combining the books are chosen by research-period Sharpe.", "Execution and weighting: ")
para(
    "Exploration tables in Sections 5-6 show both periods for transparency, but only the research-period columns "
    "feed any decision. One caveat remains: version 1 results on a different 16-coin universe were seen before this "
    "protocol was written, and the protocol's ingredients (for example the DVOL filter and skip-period signals) were "
    "informed by that work. Because version 2 selects among them mechanically on 2021-2023 data, that influence is "
    "limited to which ingredients were available, not which were chosen.")

# =========================================================================== #
# 5. MOMENTUM
# =========================================================================== #
heading("5. Momentum Research (Research Period)", 1)
heading("5.1 Time horizon", 2)
figure("figures/A_horizon_scan.png",
       "Gross Sharpe of momentum-sign strategies by look-back. Dark bars (research period) drive decisions; light "
       "bars (hold-out) are shown only for transparency.")
para(
    f"In the research period the cross-sectional signal is reversal at 1-5 days (gross Sharpe {num(hz('Cross-sectional', 1))} "
    f"at 1 day, {num(hz('Cross-sectional', 5))} at 5 days), flat at 7-14 days, and reversal again at 21-120 days "
    f"({num(hz('Cross-sectional', 90))} at 90 days). Time-series momentum is positive at 7, 14 and 30 days "
    f"({num(hz('Time-series', 7))} at 7 days, {num(hz('Time-series', 14))} at 14, {num(hz('Time-series', 30))} at 30; "
    f"21 days is slightly negative at {num(hz('Time-series', 21))}) and turns to reversal at 60-120 days. With a broad "
    "survivorship-free universe, the brief's equity intuition - reversal at short horizons, momentum at medium ones - "
    "holds for the cross-section in crypto too, unlike the 16-coin result in version 1.")
table(["Look-back", "CS gross IS", "CS gross OOS", "CS net 7 IS", "TS gross IS", "TS gross OOS", "TS net 20 IS", "CS turnover"],
      [[f"{L} d", num(hz('Cross-sectional', L)), num(hz('Cross-sectional', L, 'Gross OOS')),
        num(hz('Cross-sectional', L, 'Net7 IS')), num(hz('Time-series', L)), num(hz('Time-series', L, 'Gross OOS')),
        num(hz('Time-series', L, 'Net20 IS')), num(hz('Cross-sectional', L, 'Turnover'))]
       for L in [1, 3, 7, 14, 30, 60, 90, 120]],
      widths=[0.7, 0.8, 0.85, 0.8, 0.8, 0.85, 0.85, 0.8], size=8.5,
      caption=tcap("Horizon scan (momentum sign; negative = reversal). IS = research period, OOS = hold-out."))
heading("5.2 New information and activity", 2)
figure("figures/B_activity_volume.png", "Cross-sectional signal conditioned on abnormal dollar volume, research period.")
para(
    f"The brief suggests activity strengthens momentum and that uninformed (low-activity) moves reverse more. At "
    f"1-3 days the data show the reverse of the uninformed-trading story: reversal is stronger among high-activity "
    f"coins ({num(act(1, 'High-activity coins only'))} at 1 day) than low-activity coins "
    f"({num(act(1, 'Low-activity coins only'))}). Volume shocks in this universe often mark liquidity-driven spikes "
    "in small coins that then retrace. Weighting by volume shock moves the signal toward momentum "
    f"(1 day: {num(act(1, 'All coins'))} to {num(act(1, 'Signal x volume shock'))}), consistent with the brief's "
    "momentum hypothesis, but not enough to make a positive momentum signal.")
heading("5.3 Seasonality", 2)
ts_wd, ts_we = WKD.loc["TS momentum (blend)", "Weekday Sharpe"], WKD.loc["TS momentum (blend)", "Weekend Sharpe"]
figure("figures/C_day_of_week.png", "Day-of-week profile of strategy returns, research period (weekend shaded).")
para(f"Time-series momentum is much stronger on weekends (gross Sharpe {num(ts_we)}) than on weekdays "
     f"({num(ts_wd)}), as in version 1: trends set by retail flow persist when institutions are away. Tuesday is "
     "consistently the worst day for trend-following.")
if SESS is not None:
    sr = SESS[SESS.period == "Research"]
    us = sr[(sr.day_type == "Weekday") & (sr.session == "US (13-21 UTC)")]["EW mean bps/hour"].iloc[0]
    late = sr[(sr.day_type == "Weekday") & (sr.session == "Late US (21-24 UTC)")]["EW mean bps/hour"].iloc[0]
    figure("figures/C_intraday_sessions.png", "Left: intraday cross-sectional signal. Right: mean return by session.")
    para(f"Hourly data show the session pattern: on research-period weekdays the US session averaged {num(us)} bps per "
         f"hour and the late-US hours {num(late)} bps per hour.")
heading("5.4 Investment themes", 2)
t14 = THM[THM.Strategy == "Theme L=14d H=7d"].iloc[0]
figure("figures/D_theme_indices.png", "Equal-weight theme indices (growth of $1, log scale). Dashed line: hold-out start.")
para(f"Theme momentum is positive at every look-back in the research period, best at 14 days (gross Sharpe "
     f"{num(t14['Gross IS'])} with a 7-day hold, net {num(t14['Net20 IS'])} at 20 bps). It was the top momentum candidate "
     f"but decayed in the hold-out (gross {num(t14['Gross OOS'])}).")
if FR is not None:
    heading("5.5 Technical plays: front-running the US session", 2)
    table(["Test", "Type", "Gross bps/day", "Gross IS", "Gross OOS", "Net at 7 bps", "t-stat"],
          [[r.Test, r.kind, num(r["Gross bps/day"]), num(r["Gross Sharpe IS"]), num(r["Gross Sharpe OOS"]),
            num(r["Net Sharpe @7"]), num(r["t-stat"])] for _, r in FR.iterrows()],
          widths=[2.2, 1.0, 0.7, 0.6, 0.65, 0.7, 0.55], size=8.5,
          caption=tcap("Session-based front-running tests (hourly data, 2022 onward)."))
    para("Each session strategy opens and closes a full position every day, so even with limit orders the round trip "
         "costs 14 bps a day - far more than any of these effects earn. Front-running institutional hours is not "
         "profitable at the brief's costs.")

# =========================================================================== #
# 6. REVERSAL
# =========================================================================== #
heading("6. Reversal Research (Research Period)", 1)
heading("6.1 Time horizon", 2)
para(f"Daily cross-sectional reversal is strongest at 1-2 days (gross Sharpe {num(-hz('Cross-sectional', 1))} and "
     f"{num(-hz('Cross-sectional', 2))} as reversal), but the 1-day version turns over "
     f"{num(hz('Cross-sectional', 1, 'Turnover'))}x its capital a day and loses money even at 7 bps "
     f"(net Sharpe {num(hz('Cross-sectional', 1, 'Net7 IS'))}). Slow reversal at 60-120 days trades a tenth as much.")
if IH is not None:
    table(["Look-back", "Gross IS", "Gross OOS", "Gross bps/hour", "Turnover/hour", "Net at 7 bps"],
          [[f"{int(r.lookback_hours)} h", num(r["Gross Sharpe IS"]), num(r["Gross Sharpe OOS"]), num(r["Gross bps/hour"]),
            num(r["Turnover/hour"]), num(r["Net Sharpe @7"], 1)] for _, r in IH.iterrows()],
          widths=[0.8, 0.8, 0.8, 1.0, 1.0, 1.0], size=8.5,
          caption=tcap("Intraday cross-sectional signal (momentum sign; negative = reversal), hourly rebalance."))
    para("Intraday, reversal is the dominant pattern in both periods, but two warnings apply. First, much of it is "
         "probably bid-ask bounce: in thinly traded coins the hourly close alternates between bid and ask prices, which "
         "looks like reversal but cannot be captured. Second, turnover of more than one times capital per hour puts it "
         "far out of reach at 7-20 bps. It is reported as evidence for the brief's horizon hypothesis, not as a strategy.")
heading("6.2 Correlation: residual baskets and cointegrated pairs", 2)
table(["Strategy (momentum sign)", "Gross IS", "Gross OOS", "Net 7 IS", "Turnover"],
      [[k, num(r["Gross IS"]), num(r["Gross OOS"]), num(r["Net7 IS"]), num(r["Turnover"], 3)] for k, r in COR.iterrows()],
      widths=[2.8, 0.8, 0.8, 0.8, 0.8], size=8.5,
      caption=tcap("Correlation-based signals. Negative gross = the residual reverses."))
rt60 = COR.loc["Residual vs theme L=60d"]
para(f"'Security A minus something correlated to it' reverses at every horizon in the research period, against "
     f"the market and even more against the coin's own theme (60-day theme residual {num(rt60['Gross IS'])} in "
     f"momentum sign, i.e. {num(-rt60['Gross IS'])} as reversal). Cointegrated pairs, traded with a Kalman-filter hedge "
     f"ratio and monthly re-selection across {PAIRS['unique_pairs_traded']} pairs, lost money in the research period "
     f"(gross {num(COR.loc['Cointegrated pairs (Kalman, walk-forward)', 'Gross IS'])}) and so were not selected - although "
     f"they did well in the hold-out ({num(COR.loc['Cointegrated pairs (Kalman, walk-forward)', 'Gross OOS'])}), a "
     "reminder of how unstable these relationships are.")
heading("6.3 Macro: volatility and dislocation", 2)
figure("figures/G_macro_regimes.png", "Gross Sharpe by macro regime, research period.", width=6.5)
para(f"The clearest macro result is for momentum: time-series momentum earns {num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'Low'))} "
     f"when implied volatility is low and {num(mac('TS momentum (blend)', 'Implied vol (BTC DVOL)', 'High'))} when it is high "
     "(the pattern repeats in the hold-out), which is why the DVOL filter is part of the selected strategy. For reversal, "
     f"1-day reversal is strongest when implied volatility is high (momentum-sign Sharpe "
     f"{num(mac('CS 1d (momentum sign)', 'Implied vol (BTC DVOL)', 'High'))}) and when average correlation is high "
     f"({num(mac('CS 1d (momentum sign)', 'Avg pairwise correlation (30d)', 'High'))}), in line with the brief and "
     "Nagel (2012).")

# =========================================================================== #
# 7. SELECTION
# =========================================================================== #
heading("7. Mechanical Strategy Selection", 1)
n_rev = int((DIRS["Direction (from IS)"] == "reversal").sum())
para(f"Of the {S['n_signals']} signal variants, the research period assigned {S['n_signals'] - n_rev} to the momentum "
     f"direction and {n_rev} to reversal. After crossing with holding periods, the best candidate per family was:")
top = SEL.sort_values("Selection IS", ascending=False).groupby(["book", "family"], sort=False).head(1).sort_values(["book", "Selection IS"], ascending=[True, False])
table(["Best candidate in family", "Book", "Net Sharpe IS (selection)", "Hold-out net 20", "Hold-out net 7", "Turnover"],
      [[pretty(r.Strategy), r.book, num(r["Selection IS"]), num(r["Net20 OOS"]), num(r["Net7 OOS"]), num(r.Turnover)]
       for _, r in top.iterrows()],
      widths=[2.6, 0.8, 0.95, 0.75, 0.75, 0.65], size=8.5, caption=tcap("Family winners (research-period net Sharpe at the book's cost)."))
para("Selected books (families with positive research-period net Sharpe, top three per book):", space_after=3)
for m in S["momentum_members"]:
    bullet(pretty(m), "Momentum: ")
for m in S["reversal_members"]:
    bullet(pretty(m), "Reversal: ")
para("Cross-sectional momentum has no variant with a positive net Sharpe after 20 bps, so the momentum book has two "
     "members.")

# =========================================================================== #
# 8. EXECUTION
# =========================================================================== #
heading("8. Execution", 1)
table(["Book", "Execution", "Turnover/day", "Gross Sharpe", "IS at book cost", "Full at book cost", "Full at other cost"],
      [[r.Book, r.Execution, num(r.Turnover, 3), num(r["Sharpe gross"]), num(r["Sharpe IS @book cost"]),
        num(r["Sharpe full @book cost"]), num(r["Sharpe full @other cost"])] for _, r in EXE.iterrows()],
      widths=[0.8, 1.55, 0.75, 0.75, 0.85, 0.85, 0.9], size=8.5,
      caption=tcap("Execution variants (book cost: momentum 20 bps, reversal 7 bps; 'other' swaps them)."))
para(f"The research period selected '{S['execution_selected']['Momentum']}' for momentum and "
     f"'{S['execution_selected']['Reversal']}' for reversal. A 2% band cuts momentum turnover without diluting the "
     "signal; wider bands or longer holds lose too much signal. The cost sweep below shows the combined portfolio "
     f"reaches zero Sharpe between 20 and 30 bps in the hold-out (Sharpe {num(SWP.loc[20, 'Combined hold-out'])} at 20 bps).")
figure("figures/H_cost_sweep.png", "Net Sharpe versus transaction cost (0-200 bps).", width=5.8)

# =========================================================================== #
# 9. WEIGHTING
# =========================================================================== #
heading("9. Weighting", 1)
para(f"The two books are slightly negatively correlated (daily correlation "
     f"{num(CORR.loc['Momentum book', 'Reversal book'])}). Four schemes were tested, all re-estimated every 21 days on "
     "the trailing 180 days only.")
table(["Method", "Avg weight momentum", "Avg weight reversal", "Sharpe IS", "Sharpe OOS", "Sharpe full"],
      [[m, pct(r["Avg weight Momentum"], 0), pct(r["Avg weight Reversal"], 0), num(r["Sharpe IS"]), num(r["Sharpe OOS"]),
        num(r["Sharpe"])] for m, r in WTS.iterrows()],
      widths=[1.9, 1.0, 1.0, 0.8, 0.8, 0.8], bold_rows={list(WTS.index).index(best_m)},
      caption=tcap("Weighting methods (selection on the research-period Sharpe)."))
figure("figures/I_sleeve_weights.png", f"Walk-forward book weights ({best_m.lower()}).", width=6.0)
table(["Construction", "Mom. IS", "Mom. OOS", "Rev. IS", "Rev. OOS", "Combined IS", "Combined OOS"],
      [[r.Construction, num(r["Momentum Sharpe IS"]), num(r["Momentum Sharpe OOS"]), num(r["Reversal Sharpe IS"]),
        num(r["Reversal Sharpe OOS"]), num(r["Combined Sharpe IS"]), num(r["Combined Sharpe OOS"])] for _, r in RB.iterrows()],
      widths=[2.2, 0.65, 0.7, 0.65, 0.7, 0.8, 0.85], size=8.5, caption=tcap("Ensemble versus single best strategy."))
para(f"Picking only the single best research-period strategy in each book would have given a hold-out Sharpe of "
     f"{num(RB.iloc[1]['Combined Sharpe OOS'])}; the three-family ensembles gave {num(RB.iloc[0]['Combined Sharpe OOS'])}. "
     "Diversifying across families reduces, but does not remove, selection risk.")

# =========================================================================== #
# 10. PERFORMANCE
# =========================================================================== #
heading("10. Performance Evaluation", 1)
table(PERF_HEAD, perf_rows(OOS), widths=PERF_W, bold_rows={0}, size=8.5,
      caption=tcap(f"Hold-out, {S['oos_start']} to {S['sample_end']} (never used for any decision)."), note=PNOTE)
table(PERF_HEAD, perf_rows(INS), widths=PERF_W, bold_rows={0}, size=8.5,
      caption=tcap(f"Research period, {S['bt_start']} to {S['is_end']} (all decisions made here)."))
table(PERF_HEAD, perf_rows(FULL), widths=PERF_W, bold_rows={0}, size=8.5,
      caption=tcap(f"Full backtest, {S['bt_start']} to {S['sample_end']}."))
figure("figures/J_equity_curves.png", "Growth of $1, net of costs (log scale). Shaded: hold-out.")
para(f"In the hold-out the combined portfolio returned {pct(co['Ann.Return'])} a year at {pct(co['Ann.Vol'])} "
     f"volatility (Sharpe {num(co['Sharpe'])}), with a maximum drawdown of {pct(co['MaxDD'])} against "
     f"{pct(OOS.loc[BTC, 'MaxDD'])} for Bitcoin. It is genuinely market-neutral - beta {num(co['Beta'])}, correlation "
     f"{num(co['Corr BTC'])} - but its alpha ({pct(co['Alpha'])}, t = {num(co['Alpha t'])}) is not statistically "
     f"distinguishable from zero. The momentum book held up (hold-out Sharpe {num(OOS.loc[MOM20, 'Sharpe'])} at 20 bps, "
     f"{num(OOS.loc[MOM7, 'Sharpe'])} at 7 bps); the reversal book did not ({num(OOS.loc[REV7, 'Sharpe'])}).")
figure("figures/J_drawdowns.png", "Drawdowns of the combined portfolio and Bitcoin.")
figure("figures/J_rolling_sharpe.png", "Rolling 180-day Sharpe ratio (net, x sqrt(252)). Dashed line: hold-out start.")

# =========================================================================== #
# 11. DISCUSSION
# =========================================================================== #
heading("11. Discussion", 1)
heading("11.1 Version 1 versus version 2", 2)
table(["", "Version 1", "Version 1 at sqrt(252)", "Version 2"], [
    ["Universe", "16 coins alive in 2026", "16 coins alive in 2026", f"{n_in} coins by market cap, Jan-2021"],
    ["Decisions made on", "Full sample (exploration)", "Full sample (exploration)", "2021-2023 only, mechanical"],
    ["Combined Sharpe, full", num(V1["sharpe_full_365"]), num(V1["sharpe_full_252"]), num(cf["Sharpe"])],
    ["Combined Sharpe, hold-out", num(V1["sharpe_oos_365"]), num(V1["sharpe_oos_252"]), num(co["Sharpe"])],
    ["Alpha t, hold-out", num(V1["alpha_t_oos"]), num(V1["alpha_t_oos"]), num(co["Alpha t"])],
    ["Correlation to BTC, full", num(V1["corr_btc_full"]), num(V1["corr_btc_full"]), num(cf["Corr BTC"])],
], widths=[1.8, 1.5, 1.6, 1.6], caption=tcap("What the trainer's corrections did to the headline numbers."))
para("The sqrt(252) convention alone lowers every Sharpe by 17%. The larger change comes from the universe and the "
     "protocol: version 1's long-horizon reversal book was chosen partly because it worked in 2024-2026, and its "
     "16 survivors excluded the coins whose collapses make cross-sectional strategies harder. Version 2's lower "
     "number is the more credible one.")
heading("11.2 What the research shows", 2)
bullet("Cross-sectional crypto returns reverse at short and long horizons; time-series returns trend at 1-4 weeks. "
       "Only the slower signals survive realistic costs.", "Horizon. ")
bullet("Time-series momentum with a DVOL filter was selected purely on 2021-2023 data and kept working in "
       "2024-2026. It is the one finding that passed a genuine out-of-sample test.", "The robust finding. ")
bullet("Theme momentum and slow residual reversal looked strong in 2021-2023 and faded. Pairs did the opposite. "
       "Relationships in crypto are unstable.", "Instability. ")
bullet("The final portfolio is market-neutral and diversifying (correlation to BTC near zero), but its hold-out "
       "alpha is not statistically significant. It is a research result, not a deployable strategy.", "Bottom line. ")
heading("11.3 Limitations", 2)
bullet("Short positions assume coins can be borrowed or shorted through perpetual futures; funding is not modelled.",
       "Shorting. ")
bullet("Several coins are thinly traded at their data venue; costs are linear and limit-order fills are assumed, "
       "which is optimistic for small coins and large capital.", "Liquidity. ")
bullet("Prices come from four venues (Coinbase, KuCoin, Gate.io, Bitfinex); venue differences add noise, and "
       "Revain is missing.", "Data. ")
bullet(f"{S['n_candidates']} candidates were compared; the research-period Sharpe of the winners is biased upward, "
       "which is why the hold-out leads.", "Multiple testing. ")
bullet("Hourly data are complete for 35 of 39 coins; CEL, HT and XEM have hourly prices only from September 2025 "
       "and FTT's hourly series is sparse, so the intraday cross-section is slightly smaller in 2022-2023.",
       "Intraday coverage. ")
heading("11.4 Next steps", 2)
bullet("Paper-trade the time-series momentum book with the DVOL filter on live data.")
bullet("Add perpetual-futures funding costs and a liquidity screen (minimum dollar volume) to the universe.")
bullet("Re-run the protocol each year as the hold-out grows, without changing its rules.")

heading("12. Conclusion", 1)
para(
    f"Applying the trainer's corrections - the sqrt(252) convention, a survivorship-free universe of {n_in} coins and a "
    "research protocol that never touches the hold-out - turns version 1's strong result into a modest one. Crypto "
    "shows reversal across the cross-section and momentum in individual coins' own trends, and the brief's "
    "conditioning variables (activity, seasonality, themes and especially implied volatility) all leave visible "
    f"marks. But after costs, the combined portfolio's hold-out Sharpe is {num(co['Sharpe'])} with an alpha t-statistic "
    f"of {num(co['Alpha t'])}. The one component that survived a genuine out-of-sample test is time-series momentum "
    "switched off when implied volatility is high. The main lesson is methodological: how a strategy is selected "
    "matters as much as what it is.")

heading("Appendix A. Reproducibility", 1)
for s_ in ["python3 src/fetch_data.py - universe, daily, hourly and DVOL data",
           "python3 src/statarb.py - cointegrated pairs engine",
           "python3 src/research.py - research blocks, mechanical selection, weighting, performance",
           "python3 src/minimal_backtest.py - 60-line rebuild of one strategy, checked against the engine",
           "python3 src/make_report.py, build_explainer.py, build_pptx.py, build_excel.py, build_notebook.py"]:
    bullet(s_)

heading("References", 1)
refs = [
    "Bailey, D. H., & Lopez de Prado, M. (2014). The deflated Sharpe ratio: Correcting for selection bias, backtest overfitting and non-normality. Journal of Portfolio Management, 40(5), 94-107.",
    "Barroso, P., & Santa-Clara, P. (2015). Momentum has its moments. Journal of Financial Economics, 116(1), 111-120.",
    "Campbell, J. Y., Grossman, S. J., & Wang, J. (1993). Trading volume and serial correlation in stock returns. Quarterly Journal of Economics, 108(4), 905-939.",
    "Daniel, K., & Moskowitz, T. J. (2016). Momentum crashes. Journal of Financial Economics, 122(2), 221-247.",
    "De Bondt, W. F. M., & Thaler, R. (1985). Does the stock market overreact? Journal of Finance, 40(3), 793-805.",
    "DeMiguel, V., Garlappi, L., & Uppal, R. (2009). Optimal versus naive diversification: How inefficient is the 1/N portfolio strategy? Review of Financial Studies, 22(5), 1915-1953.",
    "Fil, M., & Kristoufek, L. (2020). Pairs trading in cryptocurrency markets. IEEE Access, 8, 172644-172651.",
    "Garleanu, N., & Pedersen, L. H. (2013). Dynamic trading with predictable returns and transaction costs. Journal of Finance, 68(6), 2309-2340.",
    "Han, H., Kang, J., & Ryu, D. (2024). Time-series and cross-sectional momentum in the cryptocurrency market: A comprehensive analysis under realistic assumptions (SSRN Working Paper No. 4675565).",
    "Harvey, C. R., Liu, Y., & Zhu, H. (2016). ... and the cross-section of expected returns. Review of Financial Studies, 29(1), 5-68.",
    "Jegadeesh, N., & Titman, S. (1993). Returns to buying winners and selling losers: Implications for stock market efficiency. Journal of Finance, 48(1), 65-91.",
    "Lehmann, B. N. (1990). Fads, martingales, and market efficiency. Quarterly Journal of Economics, 105(1), 1-28.",
    "Liu, Y., & Tsyvinski, A. (2021). Risks and returns of cryptocurrency. Review of Financial Studies, 34(6), 2689-2727.",
    "Liu, Y., Tsyvinski, A., & Wu, X. (2022). Common risk factors in cryptocurrency. Journal of Finance, 77(2), 1133-1177.",
    "Moskowitz, T. J., & Grinblatt, M. (1999). Do industries explain momentum? Journal of Finance, 54(4), 1249-1290.",
    "Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). Time series momentum. Journal of Financial Economics, 104(2), 228-250.",
    "Nagel, S. (2012). Evaporating liquidity. Review of Financial Studies, 25(7), 2005-2039.",
    "Wall Street Quants. (2025). Statistical arbitrage in cryptocurrencies: Course project brief [Class handout].",
]
for ref in refs:
    p = para(ref, space_after=4)
    p.paragraph_format.left_indent = Inches(0.4)
    p.paragraph_format.first_line_indent = Inches(-0.4)

finish("crypto_research_report_V2.docx", "data/research/_heads.json")
print("saved crypto_research_report_V2.docx")
