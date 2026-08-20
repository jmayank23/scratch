# Technical Indicators — Run + Backtest Across All Tickers

Four indicators — **RSI(14)**, **Money Flow Index(14) divergence**, **Ichimoku**, and **DeMark TD Sequential (9)** — computed for all 12 charted tickers on real daily OHLCV (Yahoo Finance, ~20 years; AVGO from its 2009 IPO, MRNA from its 2018 IPO; RVII excluded, no history), and **backtested** to answer one question: *for which stocks, if any, does each indicator actually have an edge?*

> **Read this first.** In-sample, single-path, no costs/taxes/slippage, raw close (small dividend distortion). 72 event tests were run (6 signals × 12 stocks), so ~4 false positives at |t|≥2 are expected by chance. This is exploratory analysis, **not** a validated system and **not** investment advice.

Code: [`indicator_backtest.py`](indicator_backtest.py), [`make_summary_charts.py`](make_summary_charts.py) · Data: [`data/`](data/) · Per-ticker panels: [`charts/`](charts/) (`{TICKER}-indicators.png`).

## How each indicator was tested

- **Event study** (RSI oversold `<30` / overbought `>70`, MFI bullish/bearish divergence, TD buy-setup-9 / sell-setup-9): measure the **forward 20-day return after each first-trigger event** and compare to the stock's unconditional baseline. `edge = conditional mean − baseline`. Bullish signals should show edge > 0; bearish signals edge < 0. A t-stat flags reliability (|t|≥2 marked `*`). No look-ahead — divergences are dated at swing *confirmation*.
- **Trend system** (Ichimoku): long only while yesterday's close is above the cloud, else cash (0%); compare CAGR / max drawdown / Sharpe vs buy-and-hold.

## The one-look answer

![Does each indicator help, per stock? Directional 20-day edge heatmap](charts/summary_edge_heatmap.png)

Green = the signal worked in its intended direction; `*` = |t| ≥ 2. The top row (RSI oversold) is the only one carrying real signal — and the key point is that it is **strongly green for the steady names and deep red for the high-beta ones**. Everything below it is mostly noise.

## Current snapshot (latest session)

| Stock | Close | RSI | MFI | vs Cloud | Tenkan/Kijun | TD setup |
|-------|------:|----:|----:|----------|--------------|----------|
| GOOG | $341.70 | 45 | 47 | below | bearish | buy-10 |
| AAPL | $316.83 | 54 | 50 | above | bearish | sell-3 |
| NVDA | $217.56 | 54 | 73 | above | bullish | buy-2 |
| MSFT | $484.31 | 64 | 67 | above | bullish | buy-6 |
| TSM | $412.09 | 47 | 65 | below | bullish | buy-2 |
| ASML | $1751.73 | 49 | 57 | in cloud | bullish | buy-2 |
| MRVL | $237.27 | 57 | 67 | below | bullish | sell-1 |
| AMD | $466.42 | 44 | 52 | in cloud | bearish | buy-1 |
| JPM | $357.26 | 55 | 53 | above | bullish | buy-3 |
| AXP | $339.90 | 49 | 58 | above | bullish | buy-3 |
| AVGO | $362.48 | 35 | 36 | below | bearish | buy-7 |
| **MRNA** | $174.38 | **92** | **95** | above | bullish | sell-1 |

**MRNA is the extreme reading of the whole set** — RSI 92 and MFI 95 after its ~177% single-day surge on the Phase 3 melanoma readout. Nothing else here is close (AVGO at RSI 35 is the other tail). Most names have cooled to mid-range since the prior run.

## RSI — the only indicator with a real edge, and it is entirely conditional

"Buy the RSI-oversold dip," 20-day forward edge vs baseline:

![RSI oversold 20-day edge by ticker](charts/summary_rsi_oversold_edge.png)

| Works (steadier names) | Edge | t | Backfires (high-beta) | Edge | t |
|------------------------|-----:|---:|----------------------|-----:|---:|
| AVGO | **+7.1%** | +2.2* | MRNA | **-9.6%** | **-2.8*** |
| TSM | **+3.9%** | +2.5* | NVDA | **-8.3%** | **-4.0*** |
| JPM | +2.8% | +1.8 | MRVL | -2.3% | -1.1 |
| ASML | +2.8% | +1.4 | AAPL | -2.2% | -1.1 |
| AXP | +2.1% | +1.2 | AMD | -2.1% | -1.1 |
| MSFT | +1.9% | +1.7 | | | |
| GOOG | +1.6% | +1.3 | | | |

**The split is the finding.** RSI mean-reversion worked on the steadier compounders (7 of 12 positive; TSM and AVGO significant) and was **actively destructive on the high-beta names**: MRNA (-9.6%, t -2.8) and NVDA (-8.3%, t -4.0) are now the two worst, both statistically significant. On those names "oversold" meant *falling knife*, not bounce — MRNA in particular spent years grinding down from its 2021 peak, and every oversold reading on the way down was another leg lower. RSI *overbought* as a sell signal was weak everywhere (only AVGO significant at -1.9%, t -2.4) and backfired on momentum names, which stay overbought while they climb.

**Adding MRNA flipped the pooled result — and that is the honest headline.** With 11 winners the pooled oversold edge was mildly positive (+0.25%); adding one big decliner turned it slightly **negative (-0.10%)**. There is no *general* dip-buying edge in this data. The edge exists only conditionally, per stock character, and the two tails nearly cancel in aggregate.

## MFI divergence, TD Sequential 9 — no standalone edge

Pooled across all 12 stocks (20-day forward edge vs baseline):

| Signal | Events | Edge | Hit rate | t | Useful? |
|--------|-------:|-----:|---------:|---:|---------|
| RSI oversold (buy) | 506 | **-0.10%** | 62% | -0.2 | only per-stock (see above) |
| RSI overbought (sell) | 1302 | +0.05% | 59% | +0.2 | no |
| MFI bullish divergence | 454 | +0.20% | 59% | +0.4 | no |
| MFI bearish divergence | 683 | +0.18% | 58% | +0.4 | no (wrong sign) |
| TD buy-setup 9 | 605 | -0.19% | 58% | -0.4 | no (wrong sign) |
| TD sell-setup 9 | 968 | -0.05% | 60% | -0.2 | no |

- **MFI divergence** still shows no reliable edge on any single name, and *bearish* divergence keeps pointing the wrong way — most spectacularly on **MRNA (+11.6% after bearish divergence**, n=17, t 1.3, not significant): flagging "distribution" right before a doubling. Divergences persist far longer than they resolve.
- **TD Sequential 9** marks plausible exhaustion points on the charts but produced no 20-day forward edge on any stock (all |t| < 1.5, pooled ≈ 0). Useful as context/confluence at best, not as a standalone timing signal.

## Ichimoku — a drawdown tool, and MRNA is its best case

Long only above the cloud, else cash:

![Ichimoku trend vs buy & hold: max drawdown by ticker](charts/summary_ichimoku.png)

| | Avg CAGR | Avg max drawdown | Avg Sharpe |
|--|--------:|-----------------:|-----------:|
| Buy & Hold | 21.3% | -72.9% | 0.67 |
| Ichimoku trend | 12.9% | -47.6% | 0.53 |

The cloud filter cut max drawdown in **11 of 12** names (avg -73% → -48%) but gave up roughly **40% of the CAGR** (21% → 13%), beating buy-and-hold on Sharpe in only 3 of 12. Those three are the tell:

| Stock | Buy & Hold (CAGR / MaxDD / Sharpe) | Ichimoku | Why it worked |
|-------|-----------------------------------|----------|---------------|
| **MRNA** | 33.9% / -95.4% / 0.67 | **39.0% / -47.3% / 0.89** | Parabolic COVID run then a 95% collapse — the filter sat out most of the collapse |
| **AMD** | 13.8% / -96.2% / 0.51 | 17.4% / -65.6% / 0.60 | Deepest crasher in the set |
| AAPL | 26.1% / -60.9% / 0.89 | 18.4% / -31.4% / 0.90 | Marginal — halved drawdown for a big CAGR give-up |

That pattern is consistent and economically sensible: **trend filters pay only when the crash you avoid is catastrophic.** MRNA (-95%) and AMD (-96%) are the two worst buy-and-hold drawdowns, and they are the two clear wins. **JPM** remains the whipsaw casualty (drawdown got *worse*, -70% → -78%). Same lesson as the SMA-200 test in [`../backtests/`](../backtests/) — where MRNA is an even more dramatic case (CAGR 33.9% → 66.4%): trend filters buy insurance, not alpha, and the insurance is only worth the premium on collapse-prone names.

## Verdict — for which stocks are these useful?

| Indicator | Useful on… | Not useful / harmful on… |
|-----------|-----------|--------------------------|
| **RSI oversold (dip-buy)** | Steadier compounders: **TSM, AVGO** (significant), JPM, MSFT, ASML, AXP, GOOG | High-beta / collapse-prone: **MRNA, NVDA** (both significantly harmful), AMD, MRVL, AAPL |
| **RSI overbought (sell)** | Marginally AVGO only | Everyone else; backfires on momentum names |
| **MFI divergence** | None reliably | All 12 (bearish divergence often points the wrong way — see MRNA) |
| **TD Sequential 9** | None reliably (standalone) | All 12 |
| **Ichimoku trend** | Drawdown insurance everywhere; risk-adjusted win only on **MRNA, AMD** (the deepest crashers) | Costs meaningful return on the other 9; whipsaws JPM |

**Bottom line:** across these 12 names there is **no general-purpose technical edge**. The one real signal — RSI-oversold dip-buying — is entirely conditional on the stock's character: reliably positive on lower-beta compounders, and significantly *destructive* on parabolic/collapse-prone names where trend-continuation dominates mean-reversion. The pooled edge is ~zero precisely because those two groups cancel. MFI divergence and TD Sequential 9 show no standalone forward-return edge on any of these stocks. Ichimoku is a drawdown reducer whose cost is only justified where drawdowns are catastrophic (MRNA, AMD). **Match the tool to the stock, or don't use the tool.**

## Caveats

In-sample, single historical path, 12 hand-picked large caps (11 big winners plus MRNA as the one decliner — better than an all-winners sample, but still not representative), no costs/taxes/slippage, raw close, single (daily) timeframe, and 72 event tests (multiple-comparisons risk). MRNA's own sample is small (18 oversold events, 17 bearish divergences), so its extremes are suggestive rather than settled. Indicators are mechanical and lagging and say nothing about fundamentals. **Not investment advice.**
