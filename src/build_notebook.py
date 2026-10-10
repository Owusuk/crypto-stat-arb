"""
build_notebook.py  (V2) - build and execute crypto_stat_arb_project_V2.ipynb,
a walk-through of the full V2 pipeline.  It calls the same modules as the
command-line pipeline, so its numbers match the report, deck and workbook.
"""
import json
import os
import sys

import nbformat as nbf
import pandas as pd
from nbclient import NotebookClient

sys.path.insert(0, os.path.dirname(__file__))
from textclean import clean

S = json.load(open("data/research/summary.json"))
OOS = pd.read_csv("data/research/J_performance_oos.csv").set_index("Strategy")
INS = pd.read_csv("data/research/J_performance_is.csv").set_index("Strategy")
co, ci = OOS.loc["Combined portfolio"], INS.loc["Combined portfolio"]

nb = nbf.v4.new_notebook()
cells = []
def md(t): cells.append(nbf.v4.new_markdown_cell(clean(t)))
def code(t): cells.append(nbf.v4.new_code_cell(clean(t)))

md(f"""# Statistical Arbitrage in Cryptocurrencies - Version 2

**Wall Street Quants - Bootcamp Project.** Momentum and reversal research on a survivorship-free universe of
{S['n_assets']} coins, revised after trainer feedback. Data {S['sample_start']} to {S['sample_end']}.

**Hold-out result first ({S['oos_start']} to {S['sample_end']}, never used for any decision):** combined portfolio
Sharpe **{co['Sharpe']:.2f}** (mean / std x sqrt(252)), alpha {co['Alpha']*100:.1f}% a year with t = **{co['Alpha t']:.2f}**,
beta {co['Beta']:.2f}, correlation to BTC **{co['Corr BTC']:.2f}**. Research period (2021-2023): Sharpe {ci['Sharpe']:.2f},
alpha t {ci['Alpha t']:.2f}.

| Trainer comment | Version 2 change |
|---|---|
| Sharpe used sqrt(365) | `sa_core.ANN = 252`: Sharpe = mean / std x sqrt(252) |
| Hold-out contaminated by full-sample exploration | Mechanical protocol: directions, candidates, books, execution and weighting all chosen on 2021-2023 only |
| Lead with hold-out, add correlation to BTC | Hold-out first in every table; `Corr BTC` column added |
| 16 survivors | Top 40 coins by market cap on 2021-01-03 (ex stablecoins / wrapped), delisted coins kept |
| Explain and rebuild | `src/minimal_backtest.py` (60 lines, checked against the engine) and `V2_methodology_explainer.docx` |
""")

md("## 0. Setup")
code("""import os, sys, json, inspect, subprocess, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Image, display
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
pd.set_option("display.float_format", lambda x: f"{x:,.3f}")
sys.path.insert(0, "src")

REFRESH_DATA = False   # True: rebuild the universe and download prices (hourly takes ~1 hour)
RUN_PAIRS = False      # True: re-run the cointegration engine (~6 minutes)""")

md("## 1. Universe and data\nThe universe is fixed by market cap on 2021-01-03, so it includes coins that later "
   "failed. Each coin's prices come from the venue with the most complete history.")
code("""if REFRESH_DATA:
    subprocess.run([sys.executable, "src/fetch_data.py"], check=True)
uni = pd.read_csv("data/universe.csv")
print(uni.status.value_counts().to_string())
uni[["cmc_rank", "asset", "name", "status", "reason", "source", "first", "last"]]""")
code("""import sa_core as C
close, rets, dollar_vol = C.load_panel()
print(f"{close.shape[1]} coins, {close.index.min().date()} to {close.index.max().date()}")
print("Annualisation:", C.ANN, "| research ends", C.IS_END, "| hold-out starts", C.OOS_START)
ax = close.notna().sum(axis=1).loc["2021-01-01":].plot(figsize=(10, 3), title="Coins with a price each day")
plt.show()""")

md("## 2. The backtest engine, and a 60-line rebuild\nWeights use data up to day t's close and earn day t+1's "
   "return; gross exposure is 1; cost = turnover x bps. `minimal_backtest.py` rebuilds one strategy from scratch "
   "and asserts it matches the engine.")
code("""for f in [C.cs_weights, C.ts_weights, C.hold, C.backtest, C.sharpe, C.alpha_beta]:
    print(inspect.getsource(f))""")
code("""print(subprocess.run([sys.executable, "src/minimal_backtest.py"], capture_output=True, text=True).stdout)""")

md("## 3. Run the pipeline")
code("""if RUN_PAIRS:
    print(subprocess.run([sys.executable, "src/statarb.py"], capture_output=True, text=True).stdout[-1200:])
import research as RS
RS.main()
S = json.load(open("data/research/summary.json"))
rd = lambda n: pd.read_csv(f"data/research/{n}.csv")""")

md("## 4. Performance - hold-out first")
code("""cols = ["Ann.Return", "Ann.Vol", "Sharpe", "MaxDD", "Alpha", "Beta", "Alpha t", "Corr BTC"]
for name, f in [("HOLD-OUT (never used for decisions)", "J_performance_oos"),
                ("Research period (all decisions)", "J_performance_is"), ("Full backtest", "J_performance_full")]:
    print(name); display(rd(f).set_index("Strategy")[cols])""")
code("""display(Image("figures/J_equity_curves.png")); display(Image("figures/J_drawdowns.png"))
display(Image("figures/J_rolling_sharpe.png"))""")

md("## 5. Exploration (research period drives decisions)\n### 5.1 Time horizon")
code("""display(Image("figures/A_horizon_scan.png"))
rd("A_horizon_scan")[["Strategy", "Gross IS", "Gross OOS", "Net20 IS", "Net7 IS", "Turnover"]]""")
code("""display(Image("figures/C_intraday_sessions.png"))
display(rd("A2_intraday_horizon")); rd("E_frontrun_us_session")""")
md("### 5.2 Activity, seasonality, themes")
code("""display(Image("figures/B_activity_volume.png"))
display(rd("B_activity_volume")[["Strategy", "Gross IS", "Gross OOS"]])
display(Image("figures/C_day_of_week.png")); display(rd("C_weekday_weekend"))
display(Image("figures/D_theme_indices.png"))
rd("D_theme_momentum")[["Strategy", "Gross IS", "Gross OOS", "Net20 IS", "Turnover"]]""")
md("### 5.3 Correlation and macro")
code("""display(rd("F_correlation")[["Strategy", "Gross IS", "Gross OOS", "Net7 IS", "Turnover"]])
display(Image("figures/G_macro_regimes.png"))
rd("G_macro_regimes")[["Strategy", "Indicator", "Low Sharpe IS", "Mid Sharpe IS", "High Sharpe IS", "Low Sharpe OOS", "High Sharpe OOS"]]""")

md("## 6. Mechanical selection")
code("""display(rd("H_signal_directions"))
sel = rd("H_candidate_selection")
display(sel.sort_values("Selection IS", ascending=False).groupby(["book", "family"]).head(1)
        [["Strategy", "book", "family", "Selection IS", "Net20 OOS", "Net7 OOS", "Turnover"]])
print(json.dumps({k: S[k] for k in ["momentum_members", "reversal_members", "execution_selected", "weighting_selected"]}, indent=2))""")

md("## 7. Execution and weighting")
code("""display(rd("H_execution_variants")); display(Image("figures/H_cost_sweep.png")); display(rd("H_cost_sweep"))
display(rd("I_weighting_methods")); display(Image("figures/I_sleeve_weights.png"))
display(rd("I_sleeve_correlation").set_index("Unnamed: 0")); rd("I_selection_robustness")""")

md(f"""## 8. Conclusion
* With a survivorship-free universe and an honest protocol, the combined portfolio's hold-out Sharpe is
  {co['Sharpe']:.2f} with an alpha t-statistic of {co['Alpha t']:.2f}: market-neutral (correlation to BTC {co['Corr BTC']:.2f})
  but not statistically significant.
* Time-series momentum with a DVOL filter, selected on 2021-2023 alone, is the component that held up out of sample.
* The cross-section shows reversal at short and long horizons, but turnover and instability erase most of it after costs.
""")

nb["cells"] = cells
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
NotebookClient(nb, timeout=1800, kernel_name="python3", resources={"metadata": {"path": "."}}).execute()
nbf.write(nb, "crypto_stat_arb_project_V2.ipynb")
print("saved and executed crypto_stat_arb_project_V2.ipynb")
