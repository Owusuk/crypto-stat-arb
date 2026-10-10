"""build_readme.py - write README.md from data/research/ (hold-out first)."""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from textclean import clean

R = "data/research"
S = json.load(open(f"{R}/summary.json"))
V1 = json.load(open(f"{R}/v1_reference.json"))
OOS = pd.read_csv(f"{R}/J_performance_oos.csv").set_index("Strategy")
INS = pd.read_csv(f"{R}/J_performance_is.csv").set_index("Strategy")
FULL = pd.read_csv(f"{R}/J_performance_full.csv").set_index("Strategy")
UNI = pd.read_csv("data/universe.csv")
n_in = int((UNI.status == "in universe").sum())
f2 = lambda x: f"{x:.2f}"
pc = lambda x: f"{x * 100:.1f}%"


def row(lab, r):
    return (f"| {lab} | {f2(r['Sharpe'])} | {pc(r['Ann.Return'])} | {pc(r['Ann.Vol'])} | {pc(r['MaxDD'])} | "
            f"{pc(r['Alpha'])} | {f2(r['Alpha t'])} | {f2(r['Beta'])} | {f2(r['Corr BTC'])} |")


hdr = ("| Period | Sharpe | Ann. return | Ann. vol | Max DD | Alpha | Alpha t | Beta | Corr BTC |\n"
       "|---|---|---|---|---|---|---|---|---|")
c = "Combined portfolio"
txt = f"""# Statistical Arbitrage in Cryptocurrencies - Version 2

Momentum and reversal research on a survivorship-free crypto universe - Wall Street Quants Bootcamp Project.
Revised after trainer feedback (see "Changes in version 2").

## Hold-out result (read this first)

All research and every design decision used **{S['bt_start']} to {S['is_end']}** only. The hold-out,
**{S['oos_start']} to {S['sample_end']}**, was never used for any decision.

Combined momentum + reversal portfolio, net of costs (momentum 20 bps market orders, reversal 7 bps limit orders):

{hdr}
{row(f"**Hold-out {S['oos_start'][:4]}-{S['sample_end'][:4]}**", OOS.loc[c])}
{row(f"Research {S['bt_start'][:4]}-{S['is_end'][:4]}", INS.loc[c])}
{row("Full backtest", FULL.loc[c])}
{row("Buy & hold BTC (hold-out)", OOS.loc['Buy & Hold BTC'])}

Sharpe = mean / std x sqrt(252); return, volatility and alpha annualised with 252 days (class convention).
Alpha, beta and correlation are against daily Bitcoin returns; alpha t uses Newey-West errors.

**Bottom line:** the portfolio is market-neutral (correlation to BTC {f2(OOS.loc[c, 'Corr BTC'])}) but its hold-out
alpha t-statistic is {f2(OOS.loc[c, 'Alpha t'])} - not statistically significant. The alpha t falls from
{f2(INS.loc[c, 'Alpha t'])} in the research period to {f2(OOS.loc[c, 'Alpha t'])} out of sample. Time-series momentum
with an implied-volatility (DVOL) filter is the one component that held up
(hold-out Sharpe {f2(OOS.loc['Momentum book (20bps market)', 'Sharpe'])} for the momentum book at 20 bps).

## Changes in version 2

| Trainer comment | Version 2 change | Effect |
|---|---|---|
| Sharpe used sqrt(365) | mean / std x sqrt(252) everywhere | V1 combined Sharpe 1.02 -> {f2(V1['sharpe_full_252'])} (full), 0.55 -> {f2(V1['sharpe_oos_252'])} (hold-out) |
| Hold-out not untouched (exploration on 2021-2026) | Pre-registered mechanical protocol on 2021-2023 only | True out-of-sample hold-out: Sharpe {f2(OOS.loc[c, 'Sharpe'])} |
| Lead with hold-out; add correlation to BTC | Hold-out first everywhere; `Corr BTC` in every table | Hold-out alpha t {f2(OOS.loc[c, 'Alpha t'])}, corr {f2(OOS.loc[c, 'Corr BTC'])} |
| 16 coins that survived to 2026 | Top 40 by market cap on 2021-01-03 (ex stablecoins / wrapped); {n_in} with data | Failures (FTT, EOS, MKR exits) included |
| Be able to explain and rebuild | `src/minimal_backtest.py` + `V2_methodology_explainer.docx` | Rebuild matches the engine exactly |

## Protocol (all on 2021-07 to 2023-12)

1. {S['n_signals']} signal variants in seven families (cross-sectional, time-series, theme, residual vs market,
   residual vs theme, short-term in high-vol regimes, cointegrated pairs).
2. Each signal's direction (momentum or reversal) = sign of its research-period gross Sharpe.
3. Crossed with holding periods -> {S['n_candidates']} candidates, charged 20 bps (momentum) or 7 bps (reversal).
4. Per book, the best variant of each family is kept if its research-period net Sharpe > 0; top three families.
5. Execution rule and weighting method chosen on the research period.

Selected: momentum = {'; '.join(S['momentum_members'])} ({S['execution_selected']['Momentum']});
reversal = {'; '.join(S['reversal_members'])} ({S['execution_selected']['Reversal']});
weighting = {S['weighting_selected']}.

## Contents

| File | Description |
|---|---|
| `crypto_research_report_V2.pdf` / `.docx` | Full research report |
| `V2_methodology_explainer.pdf` / `.docx` | Every design choice, how to rebuild the backtest, interview Q&A |
| `crypto_stat_arb_deck_V2.pptx` | Presentation deck |
| `crypto_stat_arb_data_V2.xlsx` | Workbook with every dataset and result |
| `crypto_stat_arb_project_V2.ipynb` | Notebook that runs the pipeline, outputs included |
| `src/` | Pipeline code |
| `data/` | Universe, prices, and all result tables (`data/research/`) |
| `figures/` | Charts |

## Pipeline

```bash
pip install -r requirements.txt
python3 src/fetch_data.py         # universe + daily, hourly and DVOL data (~1 hour with hourly)
python3 src/statarb.py            # cointegrated pairs engine (~6 minutes)
python3 src/research.py           # research blocks, mechanical selection, weighting, performance
python3 src/minimal_backtest.py   # 60-line rebuild, checked against the engine
python3 src/make_report.py        # report + explainer (.docx and .pdf; PDF needs LibreOffice)
python3 src/build_pptx.py && python3 src/build_excel.py && python3 src/build_notebook.py && python3 src/build_readme.py
```

## Caveats

Short positions assume coins can be borrowed or shorted via perpetual futures; funding costs are not modelled.
Several coins are thinly traded at their data venue. Costs are linear. {S['n_candidates']} candidates were compared,
so research-period Sharpe ratios are biased upward - which is why the hold-out leads. This is research, not
investment advice.
"""
open("README.md", "w").write(clean(txt))
print("saved README.md")
