"""
build_explainer.py - V2_methodology_explainer.docx: every design choice in the
project (what / why / alternative / how to check), a step-by-step guide to
rebuilding the backtest by hand, and likely interview questions with answers.
All numbers are read from data/research/.
"""
import json
import os
import sys

os.environ.setdefault("DOC_TOC", "data/research/_toc_explainer.json")
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from docx_helpers import doc, para, bullet, heading, table, tcap, add_toc, finish, WD_ALIGN_PARAGRAPH

R = "data/research"
S = json.load(open(f"{R}/summary.json"))
OOS = pd.read_csv(f"{R}/J_performance_oos.csv").set_index("Strategy")
INS = pd.read_csv(f"{R}/J_performance_is.csv").set_index("Strategy")
FULL = pd.read_csv(f"{R}/J_performance_full.csv").set_index("Strategy")
SEL = pd.read_csv(f"{R}/H_candidate_selection.csv")
V1 = json.load(open(f"{R}/v1_reference.json"))
UNI = pd.read_csv("data/universe.csv")
co, ci = OOS.loc["Combined portfolio"], INS.loc["Combined portfolio"]
n_in = int((UNI.status == "in universe").sum())
num = lambda x, d=2: f"{x:.{d}f}"
pct = lambda x, d=1: f"{x * 100:.{d}f}%"

for _ in range(5):
    doc.add_paragraph()
para("Methodology Explainer and Interview Preparation", bold=True, size=20, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4)
para("Statistical Arbitrage in Cryptocurrencies - Version 2", italic=True, size=13, align=WD_ALIGN_PARAGRAPH.CENTER,
     space_after=20)
para("Wall Street Quants - Bootcamp Project", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_page_break()
heading("Contents", 1)
add_toc()
doc.add_page_break()

heading("1. How to Use This Document", 1)
para("The trainer's last comment was: be able to explain every choice and rebuild the backtest yourself. This "
     "document is built for that. Section 2 is the project in one page. Section 3 walks through every design "
     "choice: what was done, why, what the alternative was, and how to check it. Section 4 rebuilds the backtest "
     "step by step - follow it with src/minimal_backtest.py open. Section 5 lists questions an interviewer is likely "
     "to ask, with short answers. Section 6 lists the numbers worth knowing by heart.")
para("A good test of understanding: close this document, open a blank notebook, and rebuild Section 4 from memory. "
     "Then run src/minimal_backtest.py and compare.", italic=True)

heading("2. The Project in One Page", 1)
bullet("research momentum and reversal strategies in crypto, backtest them unconstrained at 20 bps (market) / "
       "7 bps (limit), combine them, and report return, volatility, Sharpe, drawdown and alpha / beta.", "Brief: ")
bullet(f"the 40 largest coins by market cap on 2021-01-03, minus stablecoins and wrapped tokens; {n_in} have data. "
       "Coins that later failed stay in until their prices stop.", "Universe: ")
bullet(f"research 2021-07 to 2023-12 (every decision), hold-out {S['oos_start']} to {S['sample_end']} (never "
       "touched).", "Periods: ")
bullet(f"{S['n_signals']} signals, direction (momentum or reversal) set by the research-period sign, crossed with "
       f"holding periods into {S['n_candidates']} candidates; best per family kept if positive net Sharpe; top three "
       "families per book; execution rule and weighting chosen on the research period.", "Protocol: ")
pretty = lambda n: (n.replace(" MOM ", " momentum, hold ").replace(" REV ", " reversal, hold ").replace("H=", "")
                    .replace("L=", "look-back ").replace("blend", "7/14/28 blend"))
bullet(f"momentum book = {'; '.join(map(pretty, S['momentum_members']))}; reversal book = {'; '.join(map(pretty, S['reversal_members']))}; "
       f"weighting = {S['weighting_selected']}.", "What was selected: ")
bullet(f"hold-out Sharpe {num(co['Sharpe'])}, alpha {pct(co['Alpha'])} (t = {num(co['Alpha t'])}), beta "
       f"{num(co['Beta'])}, correlation to BTC {num(co['Corr BTC'])}. Research-period Sharpe {num(ci['Sharpe'])}.",
       "Result: ")
bullet("the edge shrank out of sample and is not statistically significant; time-series momentum with an "
       "implied-volatility filter is the one component that held up.", "Honest conclusion: ")

heading("3. Every Design Choice", 1)
choices = [
    ("Daily data, close-to-close returns",
     "Daily candles from free exchange APIs; returns are close(t) / close(t-1) - 1.",
     "The brief's strategies are daily or slower; daily data are free and complete back to 2021.",
     "Hourly data for everything (used only for the intraday tests).",
     "data/crypto_raw_data.csv, one row per coin per day."),
    ("Survivorship-free universe",
     "Top 40 by market cap on 2021-01-03, excluding stablecoins and wrapped tokens; fixed for the whole sample.",
     "Choosing coins that exist today removes the failures (FTT, CEL, EOS) and flatters any backtest. Picking by "
     "market cap at the start uses only information available then.",
     "Version 1's 16 coins still on Coinbase in 2026 (survivorship-biased); a rolling top-N universe (better but "
     "needs historical market caps every month).",
     "data/universe.csv lists rank, source, first and last price date and why any coin is missing."),
    ("Multiple data venues",
     "For each coin, the venue with the most complete history (Coinbase, KuCoin, Gate.io or Bitfinex).",
     "No single free venue covers all 40 coins, and only some keep the history of delisted coins (Bitfinex has FTT).",
     "A paid aggregated source (CoinMetrics, Kaiko); a single venue with fewer coins.",
     "the 'source' column in data/universe.csv."),
    ("No look-ahead: positions lagged one day",
     "Weights use data up to the close of day t and earn the return of day t+1: P&L = w(t-1) x r(t).",
     "Using w(t) x r(t) would trade on information you did not have, the most common backtest bug.",
     "Lag by more (e.g. trade at next open) to allow execution time.",
     "gross = (w.shift(1) * ret).sum(axis=1) in sa_core.backtest and step 5 of minimal_backtest.py."),
    ("Unconstrained backtest, gross exposure 1",
     "Weights are rescaled each day so the sum of absolute weights is 1.",
     "The brief asks for the class's unconstrained style; fixing gross exposure makes strategies comparable.",
     "Fixed notional per coin; volatility targeting at the portfolio level.",
     "w.abs().sum(axis=1) equals 1 on every trading day."),
    ("Rank-based cross-sectional weights",
     "Weight proportional to the coin's cross-sectional rank minus the average rank (dollar-neutral).",
     "Ranks are robust to the extreme returns common in crypto; demeaning makes the book market-neutral.",
     "Top / bottom quintile long-short; weights proportional to the raw signal z-score.",
     "weights sum to zero each day."),
    ("Time-series weights scaled by inverse volatility",
     "Each coin long or short on the sign of its own trailing return, divided by its 30-day volatility.",
     "Equalises risk across coins; volatility scaling improves momentum (Barroso and Santa-Clara, 2015).",
     "Equal weights; sign only.",
     "sa_core.ts_weights."),
    ("Costs: 20 bps momentum, 7 bps reversal",
     "Cost = turnover x cost per unit, turnover = sum of absolute weight changes.",
     "The brief gives 20 bps for market orders and 7 bps for limit orders. Momentum chases price and needs fills; "
     "reversal supplies liquidity and trades slowly, so passive orders are plausible.",
     "Everything at 20 bps (reported as 'all trades at 20 bps'); a cost sweep 0-200 bps.",
     "net = gross - turnover x bps / 10,000."),
    ("Sharpe = mean / std x sqrt(252)",
     "Class convention; annual return, volatility and alpha also use 252.",
     "Every project on the same scale. Crypto trades 365 days, so the calendar Sharpe is 1.20 times larger.",
     "sqrt(365) (version 1).",
     f"Version 1's 1.02 at sqrt(365) is {num(V1['sharpe_full_252'])} at sqrt(252)."),
    ("Alpha, beta, correlation vs Bitcoin",
     "Daily regression r = a + b x r_BTC + e with Newey-West errors; alpha = a x 252; correlation of daily returns.",
     "Shows whether returns are just Bitcoin exposure. Newey-West corrects for autocorrelated errors from "
     "overlapping holding periods.",
     "Equal-weight crypto market as the benchmark; multi-factor regression.",
     "sa_core.alpha_beta; minimal_backtest.py prints the same alpha and beta."),
    ("Research / hold-out split and a mechanical protocol",
     "Every decision is a rule applied to 2021-2023 data; 2024 onward is reported but never used.",
     "With many candidates, the best in-sample Sharpe is biased upward. A protocol written in advance and applied "
     "mechanically makes the hold-out a real test. Version 1 explored on the full sample, so its hold-out was "
     "contaminated.",
     "Walk-forward re-selection every year (more data-efficient, more complex); calling 2024+ a robustness check.",
     "research.py block_candidates uses only .loc[:IS_END] for direction and selection."),
    ("Direction from the research-period sign",
     "Each signal is followed if its 2021-2023 gross Sharpe is positive and faded if negative.",
     "Removes any human choice of 'momentum here, reversal there' that could be informed by hindsight.",
     "Hypothesis-driven directions from the literature.",
     "data/research/H_signal_directions.csv."),
    ("Holding periods and no-trade bands",
     "Overlapping portfolios average the last H days' targets; a band only trades when a position is more than "
     "2% or 5% from target.",
     "Both cut turnover; bands do it with less signal decay (Garleanu and Pedersen, 2013).",
     "Trade every day to target.",
     "data/research/H_execution_variants.csv."),
    ("Family ensembles rather than single winners",
     "Each book averages the best variant of up to three signal families.",
     "Single best candidates are the most overfit; diversifying across families reduces selection risk.",
     "One best strategy per book (reported as a robustness check).",
     "data/research/I_selection_robustness.csv."),
    ("Walk-forward weighting",
     "Book weights re-estimated every 21 days from the trailing 180 days; method chosen on the research period.",
     "Weights use only past data; inverse volatility and risk parity need no return forecasts.",
     "Fixed 50/50; full mean-variance (sensitive to noisy means).",
     "data/research/I_weighting_methods.csv."),
]
for i, (title, what, why, alt, check) in enumerate(choices, 1):
    heading(f"3.{i} {title}", 2)
    bullet(what, "What: ")
    bullet(why, "Why: ")
    bullet(alt, "Alternative: ")
    bullet(check, "How to check: ")

heading("4. Rebuild the Backtest Yourself", 1)
para("This is exactly what src/minimal_backtest.py does. Each step is a few lines of pandas.")
steps = [
    ("Load prices.", "Read data/crypto_raw_data.csv, keep the universe, pivot to a date x coin table of closes, "
     "reindex to every calendar day, forward-fill gaps of up to three days, and blank prices after a coin's last "
     "trading day."),
    ("Returns.", "ret = close.pct_change()."),
    ("Signal.", "For the example strategy: signal = close.shift(14) / close.shift(60) - 1 (the return from 60 to 14 "
     "days ago). Everything in it is known at today's close."),
    ("Weights.", "rank = signal.rank(axis=1, pct=True); w = -(rank - rank.mean(axis=1)) for reversal; divide each "
     "row by its sum of absolute values so gross exposure is 1."),
    ("Holding period.", "w = w.rolling(14).mean(), then rescale to gross 1 again."),
    ("P&L.", "gross = (w.shift(1) * ret).sum(axis=1); turnover = w.diff().abs().sum(axis=1); "
     "net = gross - turnover x 7 / 10,000."),
    ("Metrics.", "Sharpe = net.mean() / net.std() x sqrt(252); annual return = mean x 252; drawdown from the "
     "cumulative product of (1 + net); regress net on BTC returns for alpha and beta."),
    ("Check.", "Compare with sa_core: the script asserts the two agree to 1e-12 per day."),
]
for i, (lead, txt) in enumerate(steps, 1):
    bullet(txt, f"Step {i} - {lead} ")
para("Common mistakes to avoid: forgetting the one-day lag; computing the signal with today's return included "
     "when you trade at today's close (fine) versus at today's open (look-ahead); charging cost on weights instead "
     "of weight changes; annualising with the wrong day count; letting a delisted coin's last price carry forward "
     "forever.")

heading("5. Likely Interview Questions", 1)
qa = [
    ("Why is your hold-out Sharpe so much lower than your research Sharpe?",
     f"Selection bias and instability. I compared {S['n_candidates']} candidates on 2021-2023 data, so the winners' "
     "research Sharpe is biased upward, and several relationships (theme momentum, slow residual reversal) weakened "
     "after 2023. The hold-out is the honest number."),
    ("How do you know there is no look-ahead bias?",
     "Positions formed at day t's close earn day t+1's return; the universe is fixed with 2021 market caps; regime "
     "indicators use trailing-year percentiles known before the trade; and every selection uses only data up to "
     "2023-12-31. minimal_backtest.py shows the lag explicitly."),
    ("What is survivorship bias and how did you handle it?",
     "Testing only on assets that survived to today excludes the failures. I took the top 40 coins by market cap at "
     "the start of 2021 and kept coins like FTX Token until their prices stopped, so the FTX collapse is in the data."),
    ("Why sqrt(252) for a market that trades every day?",
     "It is the class convention so all projects are comparable. On a calendar basis the Sharpe would be 1.20x "
     "higher; the ranking of strategies does not change."),
    ("Why charge reversal only 7 bps?",
     "Reversal buys what fell and sells what rose, so it can post passive limit orders and be paid to supply "
     "liquidity, and my reversal book turns over only about 6% a day. I also report everything at 20 bps."),
    ("Is the alpha significant?",
     f"Not in the hold-out: alpha t = {num(co['Alpha t'])}. In the research period it was {num(ci['Alpha t'])}. The "
     "result is market-neutral and diversifying but not proven."),
    ("What would you do with more time or money?",
     "Add funding costs for shorts, a liquidity filter, a rolling market-cap universe, and paper-trade the "
     "time-series momentum book to build a live record before risking capital."),
    ("Why did the DVOL filter help?",
     "Trends break when option markets price large moves - the crypto version of momentum crashes. Switching "
     "time-series momentum off in the top third of implied volatility removes those episodes, and it worked in "
     "both periods."),
    ("What is the difference between cross-sectional and time-series momentum?",
     "Cross-sectional ranks coins against each other and is dollar-neutral; time-series takes each coin long or "
     "short on its own trend and can be net long or short the market."),
    ("How did the trainer's feedback change your results?",
     f"The Sharpe convention alone cut version 1's 1.02 to {num(V1['sharpe_full_252'])}. Removing survivorship bias "
     f"and hold-out contamination took the hold-out Sharpe from {num(V1['sharpe_oos_252'])} to {num(co['Sharpe'])}."),
    ("Did you use AI tools?",
     "Yes, for coding and drafting, as allowed. Every choice is documented here, the backtest can be rebuilt in 60 "
     "lines, and I checked the engine against that rebuild."),
]
for q, a in qa:
    para(q, bold=True, space_after=2)
    para(a, space_after=8)

heading("6. Numbers to Know", 1)
table(["Measure", "Hold-out", "Research", "Full"],
      [[lab, f(OOS.loc["Combined portfolio", k]), f(INS.loc["Combined portfolio", k]), f(FULL.loc["Combined portfolio", k])]
       for lab, k, f in [("Sharpe (x sqrt 252)", "Sharpe", num), ("Annual return", "Ann.Return", pct),
                         ("Annual volatility", "Ann.Vol", pct), ("Max drawdown", "MaxDD", pct),
                         ("Alpha (annual)", "Alpha", pct), ("Alpha t-stat", "Alpha t", num),
                         ("Beta to BTC", "Beta", num), ("Correlation to BTC", "Corr BTC", num)]],
      widths=[2.4, 1.3, 1.3, 1.3], caption=tcap("Combined portfolio, net of costs."))
table(["Item", "Value"], [
    ["Universe", f"{n_in} coins (top 40 by market cap on 2021-01-03, ex stablecoins / wrapped)"],
    ["Research period", f"2021-07-01 to {S['is_end']}"], ["Hold-out", f"{S['oos_start']} to {S['sample_end']}"],
    ["Signals / candidates", f"{S['n_signals']} / {S['n_candidates']}"],
    ["Costs", "20 bps momentum (market), 7 bps reversal (limit)"],
    ["Version 1 Sharpe (sqrt 365 / sqrt 252)", f"{num(V1['sharpe_full_365'])} / {num(V1['sharpe_full_252'])}"],
], widths=[2.4, 4.0], caption=tcap("Set-up facts."))

finish("V2_methodology_explainer.docx", "data/research/_heads_explainer.json")
print("saved V2_methodology_explainer.docx")
