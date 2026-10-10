# Statistical Arbitrage in Cryptocurrencies - Version 2

Momentum and reversal research on a survivorship-free crypto universe - Wall Street Quants Bootcamp Project.

## Hold-out result (read this first)

All research and every design decision used **2021-12-28 to 2023-12-31** only. The hold-out,
**2024-01-01 to 2026-10-08**, was never used for any decision.

Combined momentum + reversal portfolio, net of costs (momentum 20 bps market orders, reversal 7 bps limit orders):

| Period | Sharpe | Ann. return | Ann. vol | Max DD | Alpha | Alpha t | Beta | Corr BTC |
|---|---|---|---|---|---|---|---|---|
| **Hold-out 2024-2026** | 0.20 | 2.1% | 10.3% | -26.7% | 2.8% | 0.52 | -0.03 | -0.12 |
| Research 2021-2023 | 0.93 | 9.4% | 10.1% | -13.3% | 9.6% | 1.64 | -0.03 | -0.15 |
| Full backtest | 0.50 | 5.2% | 10.2% | -26.7% | 5.7% | 1.42 | -0.03 | -0.13 |
| Buy & hold BTC (hold-out) | 0.61 | 24.1% | 39.4% | -53.1% | 0.0% | 0.33 | 1.00 | 1.00 |

Sharpe = mean / std x sqrt(252); return, volatility and alpha annualised with 252 days (class convention).
Alpha, beta and correlation are against daily Bitcoin returns; alpha t uses Newey-West errors.

**Bottom line:** the portfolio is market-neutral (correlation to BTC -0.12) but its hold-out
alpha t-statistic is 0.52 - not statistically significant. The alpha t falls from
1.64 in the research period to 0.52 out of sample. Time-series momentum
with an implied-volatility (DVOL) filter is the one component that held up
(hold-out Sharpe 0.30 for the momentum book at 20 bps).

## Changes in version 2

| V1 | V2 | Effect |
|---|---|---|
| Sharpe annualised with sqrt(365) | mean / std x sqrt(252) everywhere | V1 combined Sharpe 1.02 -> 0.85 (full), 0.55 -> 0.46 (hold-out) |
| Exploration on the full 2021-2026 sample, so the hold-out was not untouched | Pre-registered mechanical protocol on 2021-2023 only | True out-of-sample hold-out: Sharpe 0.20 |
| Full-sample results reported first; no correlation to BTC | Hold-out first everywhere; `Corr BTC` in every table | Hold-out alpha t 0.52, corr -0.12 |
| 16 coins that survived to 2026 | Top 40 by market cap on 2021-01-03 (ex stablecoins / wrapped); 39 with data | Failures (FTT, EOS, MKR exits) included |
| No standalone rebuild or methodology guide | `src/minimal_backtest.py` + `V2_methodology_explainer.docx` | Rebuild matches the engine exactly |

## Protocol (all on 2021-07 to 2023-12)

1. 51 signal variants in seven families (cross-sectional, time-series, theme, residual vs market,
   residual vs theme, short-term in high-vol regimes, cointegrated pairs).
2. Each signal's direction (momentum or reversal) = sign of its research-period gross Sharpe.
3. Crossed with holding periods -> 167 candidates, charged 20 bps (momentum) or 7 bps (reversal).
4. Per book, the best variant of each family is kept if its research-period net Sharpe > 0; top three families.
5. Execution rule and weighting method chosen on the research period.

Selected: momentum = Theme L=14 MOM H=7; TS L=blend + DVOL filter MOM H=1 (No-trade band 2%);
reversal = Residual vs theme L=60 REV H=7; CS L=120 REV H=7; Residual vs market L=60 REV H=7 (Hold 3d (overlapping));
weighting = Inverse volatility.

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
Several coins are thinly traded at their data venue. Costs are linear. 167 candidates were compared,
so research-period Sharpe ratios are biased upward - which is why the hold-out leads. This is research, not
investment advice.
