# Kronos stock forecasting

Scripts for running [Kronos](https://github.com/shiyu-coder/Kronos) on any Yahoo Finance ticker (daily bars, CPU is fine).

## Setup
```
git clone https://github.com/shiyu-coder/Kronos && cd Kronos
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp /path/to/this/folder/*.py .
```
Needs network access to `huggingface.co` (weights) and `query1.finance.yahoo.com` (prices).

## Usage
```
python forecast.py TICKER [horizon_days=20] [small|base] [samples=10]   # ~3 min on 4 CPUs
PYTHONPATH=. python rolling_backtest.py TICKER                           # 12-window skill check vs "flat price"
```
`forecast.py` writes `TICKER_forecast.png` (backtest on the last `horizon` days + forward forecast with a 10–90% band) and `TICKER_forecast.csv`.

## AAPL result (2026-10-02, 20 trading days ahead)
- Kronos-small median: 333.69 -> 283.69 (p10 274, p90 295)
- Kronos-base median: 333.69 -> 268.45 (p10 254, p90 277)
- Rolling backtest, Kronos-small, 12 windows of 20 days:
  - lookback 400: average error 11.0% vs 4.4% for "price stays flat", direction right 50% of the time
  - lookback 128: average error 8.9% vs 4.4%, direction right 42%

On AAPL daily bars, the zero-shot model does worse than a no-change guess. It tends to pull price back toward its average over the lookback window. Treat the output as an experiment, not a signal.
