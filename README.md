# Statistical Arbitrage in Cryptocurrencies

Momentum and reversal research on live crypto market data - Wall Street Quants Bootcamp Project.

Data: Coinbase Exchange daily and hourly OHLCV and the Deribit DVOL implied-volatility index, 2021-01-01 to 2026-10-08.

## Headline result

A market-neutral portfolio that combines a momentum ensemble (time-series, theme and cross-sectional momentum) with a long-horizon reversal book, net of the brief's costs (20 bps market orders, 7 bps limit orders):

| Period | Sharpe | Alpha / year | Beta to BTC | Max drawdown |
|---|---|---|---|---|
| Full backtest (2021-12-28 to 2026-10-08) | 1.02 | 20.6% (t = 2.19) | -0.02 | -28.1% |
| Hold-out (2024-01-01 to 2026-10-08) | 0.55 | 11.6% | -0.01 | -23.5% |
| Buy & hold BTC (full backtest) | 0.45 | - | 1.00 | -67.0% |

All parameters were chosen on 2021-2023 data; 2024 onward is an untouched hold-out.

## Key findings

- **Horizon decides the sign.** Daily horizons of 1-30 days show momentum (cross-sectional peak at 14 days). Reversal appears only intraday (1-24 hours) and at 60-90 days.
- **Intraday reversal is strong but untradeable.** 1-hour reversal has a gross Sharpe of 4.9, but its turnover makes it lose money even at 7 bps.
- **The brief's conditioning variables work.** Volume shocks strengthen momentum; time-series momentum is much stronger on weekends; theme momentum was strong then decayed; momentum breaks down when implied volatility is high; reversal improves in volatile markets.
- **Execution is the binding constraint.** No-trade bands, slow signals and limit orders decide which edges survive costs.
- **Combining works.** Momentum and reversal are nearly uncorrelated, so the combination beats either part.

## Contents

| File | Description |
|---|---|
| `crypto_research_report.pdf` / `.docx` | Full research report (20 pages) |
| `crypto_stat_arb_deck  -  Final.pptx` | Presentation deck (14 slides) |
| `crypto_stat_arb_data.xlsx` | Workbook with every dataset and result table |
| `crypto_stat_arb_project.ipynb` | Notebook that runs the whole pipeline, outputs included |
| `src/` | Pipeline code |
| `data/` | Downloaded data and all result tables (`data/research/`) |
| `figures/` | Charts used in the report and deck |

## Pipeline

```bash
pip install -r requirements.txt
python3 src/fetch_data.py        # refresh data to today (hourly download takes ~45 min)
python3 src/statarb.py           # cointegration pairs engine (walk-forward, Kalman filter)
python3 src/research.py          # all research blocks, selection, weighting, performance
python3 src/make_report.py       # report (.docx + .pdf, needs LibreOffice for the PDF)
python3 src/build_pptx.py        # deck
python3 src/build_excel.py       # workbook
python3 src/build_notebook.py    # executes the notebook
```

| Module | Purpose |
|---|---|
| `sa_core.py` | Data loading, unconstrained backtest, costs, metrics (Sharpe, max DD, alpha / beta) |
| `research.py` | Horizon, activity, seasonality, themes, front-running, correlation, macro, execution, weighting |
| `statarb.py` | Engle-Granger / Kalman-filter cointegration pairs engine |
| `fetch_data.py` | Coinbase and Deribit downloads |

## Caveats

Backtests assume short positions are available (e.g. via perpetual futures) and do not model funding costs. The universe is 16 coins that survived to 2026 (survivorship bias). Costs are linear. 44 candidate strategies were compared, so research-period Sharpe ratios are biased upward; the hold-out is the honest measure. This is research, not investment advice.
