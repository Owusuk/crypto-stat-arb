"""
build_notebook.py - build and execute crypto_stat_arb_project.ipynb, a
walk-through of the full research pipeline that follows the class brief.
The notebook calls the same modules as the command-line pipeline, so its
numbers match the report, deck and workbook exactly.
"""
import json
import os
import sys

import nbformat as nbf
from nbclient import NotebookClient

sys.path.insert(0, os.path.dirname(__file__))
from textclean import clean

S = json.load(open("data/research/summary.json"))
import pandas as pd
FULL = pd.read_csv("data/research/J_performance_full.csv").set_index("Strategy")
OOS = pd.read_csv("data/research/J_performance_oos.csv").set_index("Strategy")
c, co = FULL.loc["Combined portfolio"], OOS.loc["Combined portfolio"]

nb = nbf.v4.new_notebook()
cells = []
def md(t): cells.append(nbf.v4.new_markdown_cell(clean(t)))
def code(t): cells.append(nbf.v4.new_code_cell(clean(t)))

md(f"""# Statistical Arbitrage in Cryptocurrencies - Momentum and Reversal on Live Data

**Wall Street Quants - Bootcamp Project.** This notebook reproduces every result in
`crypto_research_report.docx`, the deck and the workbook. Data run from {S['sample_start']} to **{S['sample_end']}**.

**Goal (from the brief):** research profitable momentum and/or reversal strategies in crypto, test them with
unconstrained backtests at 20 bps (market orders) / 7 bps (limit orders), combine them with a weighting
scheme, and report returns, volatility, Sharpe, max drawdown and alpha / beta.

| Brief item | Where it is tested |
|---|---|
| Momentum - time horizon | Section 3 (daily) and Section 4 (hourly) |
| Momentum - new information / activity | Section 5 |
| Momentum - seasonality | Section 6 |
| Momentum - investment themes | Section 7 |
| Momentum - technical plays | Section 4 (front-running the US session) |
| Reversal - time horizon / uninformed trading | Sections 3, 4 and 5 |
| Reversal - correlation | Section 8 (residual reversal, cointegrated pairs) |
| Reversal - macro | Section 9 (DVOL, realized vol, dispersion, correlation) |
| Execution | Section 10 |
| Weighting | Section 11 |
| Performance evaluation | Section 12 |

**Headline:** a market-neutral portfolio combining a momentum ensemble with long-horizon reversal earns a net
Sharpe of {c['Sharpe']:.2f}, alpha of {c['Alpha']*100:.1f}% a year (t = {c['Alpha t']:.2f}) and beta to Bitcoin of
{c['Beta']:.2f} over {S['bt_start']} to {S['sample_end']}; its hold-out (2024 onward) Sharpe is {co['Sharpe']:.2f}.
""")

md("## 0. Setup")
code("""import os, sys, json, inspect, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Image, display
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
sys.path.insert(0, "src")

REFRESH_DATA = False   # True: download the latest prices (hourly download takes ~45 minutes)
RUN_PAIRS = True       # re-run the cointegration engine (~1 minute)""")

md("## 1. Data\nDaily and hourly OHLCV from the Coinbase Exchange public API (Binance is geo-blocked here, "
   "HTTP 451) and the Deribit DVOL implied-volatility index. Set `REFRESH_DATA = True` to pull the latest data.")
code("""if REFRESH_DATA:
    import fetch_data
    fetch_data.fetch_daily(); fetch_data.fetch_dvol(); fetch_data.fetch_hourly()

import sa_core as C
close, rets, dollar_vol = C.load_panel()
coverage = pd.DataFrame({"first date": close.apply(lambda s: s.first_valid_index().date()),
                         "last date": close.apply(lambda s: s.last_valid_index().date()),
                         "days": close.notna().sum(),
                         "last close": close.ffill().iloc[-1]})
print(f"{close.shape[1]} coins, {close.index.min().date()} to {close.index.max().date()}")
coverage""")
code("""hourly = pd.read_csv("data/crypto_hourly.csv", usecols=["asset", "date"])
dvol = pd.read_csv("data/dvol.csv", index_col=0, parse_dates=True)
print(f"hourly bars: {len(hourly):,}  |  DVOL days: {len(dvol):,} ({dvol.index.min().date()} to {dvol.index.max().date()})")
ax = (close.loc["2021-07-01":] / close.loc["2021-07-01":].bfill().iloc[0]).plot(figsize=(11, 4.5), logy=True, legend=False, lw=0.8)
ax.set_title("Coin prices, rebased (log scale)"); plt.show()""")

md("## 2. The unconstrained backtest engine\nWeights use information up to the close of day t and earn day "
   "t+1's return. Gross exposure is scaled to 1. Cost = turnover x cost per unit (20 bps market, 7 bps limit).")
code("""for f in [C.cs_weights, C.ts_weights, C.hold, C.band, C.backtest, C.alpha_beta]:
    print(inspect.getsource(f))""")

md("## 3. Run the pipeline\nThe cointegration engine (`src/statarb.py`) and the research programme "
   "(`src/research.py`) write every table to `data/research/` and every chart to `figures/`.")
code("""if RUN_PAIRS:
    import subprocess
    out = subprocess.run([sys.executable, "src/statarb.py"], capture_output=True, text=True)
    print(out.stdout[-1500:])""")
code("""import research as RS
RS.main()
S = json.load(open("data/research/summary.json"))
rd = lambda n: pd.read_csv(f"data/research/{n}.csv")""")

md("## 4. Time horizon - momentum vs reversal\n**Daily:** crypto shows momentum from 1 to 30 days and "
   "reversal only at 60-90 days, the opposite of the equity pattern in the brief.")
code("""display(Image("figures/A_horizon_scan.png"))
rd("A_horizon_scan")[["Strategy", "Gross IS", "Gross OOS", "Gross Full", "Net20 Full", "Net7 Full", "Turnover"]]""")
md("**Hourly:** the brief's short-horizon reversal does exist intraday, and it is strong, but turnover makes it "
   "untradeable at 7-20 bps. The session tests cover the 'technical plays' item (front-running the US session).")
code("""display(Image("figures/C_intraday_sessions.png"))
display(rd("A2_intraday_horizon"))
rd("E_frontrun_us_session")""")

md("## 5. New information / activity\nWeighting momentum by abnormal dollar volume strengthens short-horizon "
   "momentum; low-activity (uninformed) moves show weaker momentum.")
code("""display(Image("figures/B_activity_volume.png"))
rd("B_activity_volume")[["Strategy", "Gross IS", "Gross OOS", "Gross Full", "Net7 Full"]]""")

md("## 6. Seasonality\nTime-series momentum is far stronger on weekends; crypto gains accrue outside US hours.")
code("""display(Image("figures/C_day_of_week.png"))
display(rd("C_weekday_weekend")[["Strategy", "Weekday Sharpe", "Weekend Sharpe", "Weekday bps/day", "Weekend bps/day"]])
display(rd("C_weekend_momentum")[["Strategy", "Gross IS", "Gross OOS", "Net20 Full", "Net7 Full", "Turnover"]])
rd("C_session_returns")""")

md("## 7. Investment themes\nTheme momentum was the strongest research-period signal but decayed in the hold-out.")
code("""display(Image("figures/D_theme_indices.png"))
rd("D_theme_momentum")[["Strategy", "Gross IS", "Gross OOS", "Net20 Full", "Net7 Full", "Turnover"]]""")

md("## 8. Correlation-based reversal\nResiduals vs the market trend; residuals vs the coin's own theme revert "
   "over 1-2 months; cointegrated pairs are market-neutral but too weak after costs.")
code("""display(rd("F_correlation_reversal")[["Strategy", "Gross IS", "Gross OOS", "Gross Full", "Net20 Full", "Net7 Full", "Turnover"]])
display(Image("figures/example_pair.png"))
pd.read_csv("data/pair_frequency.csv").head(10)""")

md("## 9. Macro regimes\nReversal does better when volatility and correlation are high; time-series momentum "
   "breaks down when implied volatility (DVOL) is high.")
code("""display(Image("figures/G_macro_regimes.png"))
rd("G_macro_regimes")[["Strategy", "Indicator", "Low Sharpe", "Mid Sharpe", "High Sharpe"]]""")

md("## 10. Strategy selection and execution\nAll choices use the research period only. The momentum book is an "
   "ensemble of the best time-series, theme and cross-sectional variants.")
code("""print(json.dumps({k: S[k] for k in ["momentum_components", "reversal_selected", "execution_selected", "weighting_selected"]}, indent=2))
sel = rd("H_candidate_selection")
display(sel.groupby("family").head(6)[["Strategy", "family", "Selection IS", "Net20 OOS", "Net7 OOS", "Turnover"]])
display(rd("H_execution_variants"))
display(Image("figures/H_cost_sweep.png"))
rd("H_cost_sweep")""")

md("## 11. Weighting")
code("""display(rd("I_sleeve_correlation").set_index("Unnamed: 0"))
display(rd("I_weighting_methods"))
display(Image("figures/I_sleeve_weights.png"))
rd("I_selection_robustness")""")

md("## 12. Performance evaluation\nReturns, volatility, Sharpe, max drawdown and alpha / beta (vs Bitcoin), "
   "for the full backtest, research period and hold-out.")
code("""cols = ["Ann.Return", "Ann.Vol", "Sharpe", "MaxDD", "Alpha", "Beta", "Alpha t"]
for name, f in [("Full backtest", "J_performance_full"), ("Research period", "J_performance_is"), ("Hold-out", "J_performance_oos")]:
    print(name); display(rd(f).set_index("Strategy")[cols])""")
code("""display(Image("figures/J_equity_curves.png"))
display(Image("figures/J_drawdowns.png"))
display(Image("figures/J_rolling_sharpe.png"))""")

md(f"""## 13. Conclusion
* Crypto shows **momentum at horizons of days to weeks** and **reversal at the extremes** (within the hour and over
  about two months). The brief's conditioning variables - activity, seasonality, themes and macro - are all visible.
* **Execution decides** which edges survive: no-trade bands, slow signals and limit orders matter as much as the signal.
* **Combining** an uncorrelated momentum ensemble and reversal book gives a market-neutral portfolio with a higher
  Sharpe and smaller drawdown than either part.
* **Expect decay:** the hold-out Sharpe is lower than the research-period Sharpe; live paper trading is the next step.
""")

nb["cells"] = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
client = NotebookClient(nb, timeout=1800, kernel_name="python3", resources={"metadata": {"path": "."}})
client.execute()
nbf.write(nb, "crypto_stat_arb_project.ipynb")
print("saved and executed crypto_stat_arb_project.ipynb")
