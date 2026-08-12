# Technical Indicators — Run + Backtest Across All Tickers

Four indicators — **RSI(14)**, **Money Flow Index(14) divergence**, **Ichimoku**, and **DeMark TD Sequential (9)** — computed for all 11 charted tickers on real daily OHLCV (Yahoo Finance, ~20 years; AVGO from its 2009 IPO; RVII excluded, no history), and **backtested** to answer one question: *for which stocks, if any, does each indicator actually have an edge?*

> **Read this first.** In-sample, single-path, hand-picked winners, no costs/taxes/slippage, raw close (small dividend distortion). 66 event tests were run (6 signals × 11 stocks), so ~3 false positives at |t|≥2 are expected by chance. This is exploratory analysis, **not** a validated system and **not** investment advice.

Code: [`indicator_backtest.py`](indicator_backtest.py) · Data: [`data/`](data/) · Per-ticker indicator panels: [`charts/`](charts/) (`{TICKER}-indicators.png`).

## How each indicator was tested

- **Event study** (RSI oversold `<30` / overbought `>70`, MFI bullish/bearish divergence, TD buy-setup-9 / sell-setup-9): measure the **forward 20-day return after each first-trigger event** and compare to the stock's unconditional baseline. `edge = conditional mean − baseline`. Bullish signals should show edge > 0; bearish signals edge < 0. A t-stat on the event sample flags reliability (|t|≥2 marked `*`). No look-ahead — divergences are dated at swing *confirmation*.
- **Trend system** (Ichimoku): long only while yesterday's close is above the cloud, else cash (0%); compare CAGR / max drawdown / Sharpe vs buy-and-hold.

## The one-look answer

![Does each indicator help, per stock? Directional 20-day edge heatmap](charts/summary_edge_heatmap.png)

Green = the signal worked in its intended direction; `*` = |t| ≥ 2. The only column of consistent, sizable green is the top row (RSI oversold) — and only for the steadier names. Everything below it is mostly noise.

## Current snapshot (latest session)

| Stock | Close | RSI | MFI | vs Cloud | Tenkan/Kijun | TD setup |
|-------|------:|----:|----:|----------|--------------|----------|
| GOOG | $343.00 | 46 | 51 | below | bullish | buy-4 |
| AAPL | $304.91 | 42 | 51 | above | bearish | buy-2 |
| NVDA | $217.50 | 58 | 52 | above | bullish | buy-1 |
| MSFT | $503.81 | 78 | 79 | above | bullish | sell-11 |
| TSM | $422.06 | 53 | 46 | in cloud | bearish | sell-8 |
| ASML | $1799.38 | 56 | 41 | in cloud | bullish | sell-7 |
| MRVL | $212.31 | 50 | 49 | below | bearish | sell-1 |
| AMD | $474.32 | 46 | 33 | in cloud | bearish | buy-3 |
| JPM | $362.04 | 66 | 81 | above | bullish | sell-6 |
| AXP | $340.81 | 49 | 51 | above | bullish | buy-3 |
| AVGO | $416.08 | 58 | 48 | in cloud | bullish | buy-1 |

(MSFT stands out as overbought/extended — RSI 78, MFI 79, TD sell-11; JPM's MFI 81 is also hot. Most others are mid-range.)

## RSI — the only indicator with a real (but conditional) edge

"Buy the RSI-oversold dip," 20-day forward edge vs baseline:

![RSI oversold 20-day edge by ticker](charts/summary_rsi_oversold_edge.png)

| Stock | Edge after RSI<30 | t | Stock | Edge after RSI<30 | t |
|-------|------------------:|---:|-------|------------------:|---:|
| AVGO | **+7.1%** | +2.2* | AAPL | -2.2% | -1.1 |
| TSM | **+3.9%** | +2.5* | AMD | -2.1% | -1.1 |
| JPM | +2.8% | +1.8 | MRVL | -2.3% | -1.1 |
| ASML | +2.8% | +1.4 | NVDA | **-8.3%** | **-4.0*** |
| AXP | +2.1% | +1.2 | | | |
| MSFT | +2.0% | +1.8 | | | |
| GOOG | +1.6% | +1.3 | | | |

**The clean split:** RSI mean-reversion works on the steadier compounders (7 of 11 positive, TSM and AVGO significant) and is **actively harmful on the high-beta momentum names** — NVDA is the poster child (buying oversold historically *lost* 8.3% over the next 20 days, t = -4.0), with AMD, MRVL, and AAPL also negative. On those names, "oversold" usually meant "falling knife," not "bounce." RSI *overbought* as a sell signal was weak everywhere (only AVGO significant at -1.9%, t -2.4) and backfired on momentum names, which stay overbought while they climb.

## MFI divergence, TD Sequential 9 — no standalone edge

Pooled across all 11 stocks (20-day forward edge vs baseline):

| Signal | Events | Edge | Hit rate | t | Useful? |
|--------|-------:|-----:|---------:|---:|---------|
| RSI oversold (buy) | 488 | +0.25% | 62% | 0.4 | only per-stock (see above) |
| RSI overbought (sell) | 1267 | +0.02% | 59% | 0.1 | no |
| MFI bullish divergence | 434 | +0.12% | 59% | 0.2 | no |
| MFI bearish divergence | 665 | -0.09% | 58% | -0.2 | no |
| TD buy-setup 9 | 572 | -0.22% | 58% | -0.4 | no |
| TD sell-setup 9 | 940 | -0.06% | 60% | -0.2 | no |

- **MFI divergence** produced no reliable edge on any single name (all |t| < 1.6), and *bearish* divergence frequently backfired — in these persistent uptrends, "bearish divergence" was mostly followed by more upside (divergences can persist far longer than they resolve).
- **TD Sequential 9** (buy or sell) marks plausible exhaustion points on the charts, but they did **not** translate into a 20-day forward edge on any stock (all |t| < 1.5, pooled ≈ 0). It may still have value as a confluence/context tool, but the data does not support it as a standalone timing signal.

## Ichimoku — a drawdown tool, not an edge

Long only above the cloud, else cash:

![Ichimoku trend vs buy & hold: max drawdown by ticker](charts/summary_ichimoku.png)

| | Avg CAGR | Avg max drawdown | Avg Sharpe |
|--|--------:|-----------------:|-----------:|
| Buy & Hold | 20.2% | -70.8% | 0.68 |
| Ichimoku trend | 10.6% | -47.7% | 0.50 |

The cloud filter cut max drawdown in **9 of 11** names (avg -71% → -48%) but gave up roughly **half the CAGR** (20% → 11%) and produced a **worse Sharpe** in all but one. The lone risk-adjusted winner was **AMD** (Sharpe 0.51 → 0.61), the deepest crasher (-96% buy-and-hold drawdown) — crash-avoidance only pays when the crash is severe enough. **JPM** was the whipsaw casualty (drawdown got *worse*, -70% → -78%). Same lesson as the SMA-200 test in [`../backtests/`](../backtests/): trend filters buy insurance, not alpha.

## Verdict — for which stocks are these useful?

| Indicator | Useful on… | Not useful / harmful on… |
|-----------|-----------|--------------------------|
| **RSI oversold (dip-buy)** | Steadier compounders: **TSM, AVGO** (significant), JPM, MSFT, ASML, AXP, GOOG | High-beta momentum: **NVDA** (badly), AMD, MRVL, AAPL |
| **RSI overbought (sell)** | Marginally AVGO only | Everyone else; backfires on NVDA/AMD/MRVL/AAPL |
| **MFI divergence** | None reliably | All 11 (bearish divergence often backfires) |
| **TD Sequential 9** | None reliably (standalone) | All 11 |
| **Ichimoku trend** | Drawdown insurance; risk-adjusted only **AMD** | Costs return on the rest; whipsaws JPM |

**Bottom line:** across these 11 names, the only technical signal with a real, economically-sensible edge is **RSI-oversold dip-buying on lower-beta compounders** — and the same signal is a trap on parabolic momentum names, where trend-continuation dominates mean-reversion. MFI divergence and TD Sequential 9 show no standalone forward-return edge on any of these stocks, and Ichimoku is a drawdown reducer that costs too much return to be an edge. The mean-reversion-vs-momentum split (steady names revert, high-beta names trend) is the single most useful, transferable takeaway — and it's consistent enough across stocks and directions to be more than the multiple-comparisons noise floor, though it remains in-sample and selection-biased.

## Caveats

In-sample, single historical path, 11 survivors that all rose a lot (selection bias cuts both ways — it flatters dip-buying on steady names and momentum-continuation on high-beta names), no costs/taxes/slippage, raw close, single (daily) timeframe, and 66 event tests (multiple-comparisons risk). Indicators are mechanical and lagging and say nothing about fundamentals. **Not investment advice.**
