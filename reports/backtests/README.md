# Can Corrections Be Predicted? A Backtest

An empirical test of the intuition that these stocks "grow, then correct back to a past level." Two questions, tested on **~20 years of real daily data** (2006-01 to 2026-08, Yahoo Finance) for the **11 charted tickers**, plus **three rules-based strategies** backtested against buy-and-hold.

> **Read this first.** These are hand-picked large-cap winners, tested **in-sample** on a **single historical path**, with **no transaction costs, taxes, or slippage**, and cash assumed to earn **0%**. That combination flatters nothing and proves nothing out-of-sample. Treat this as exploratory data analysis, **not** a validated trading system and **not** investment advice. `RVII` is excluded (no price history). `AVGO` history starts at its 2009 IPO.

## TL;DR

1. **The *timing* of corrections is essentially unpredictable.** Gaps between corrections are close to memoryless (lag-1 autocorrelation ≈ **-0.04** pooled; per-ticker all between -0.27 and +0.16) and highly irregular (coefficient of variation 0.7-2.2). Knowing when the last drop happened tells you almost nothing about when the next one comes.
2. **The *depth* of a drop is barely predictable.** The single most intuitive predictor - how far the stock ran up into the peak - has **r = 0.01** (none). The best weak hints are "how stretched above the 200-day trend" and recent volatility, each **r ≈ 0.14**. A 4-feature regression explains only **~3%** of the variance in drop depth. Your best estimate of the next drop is just the stock's own historical median (roughly **13-26%**), and the spread around it is enormous.
3. **One relationship *is* strong - but it's mechanical.** Deeper corrections are followed by longer gaps to the next peak (**r = 0.75**). That's mostly recovery-time arithmetic (a deep hole takes longer to climb out of), not foresight about the next top.
4. **The strategies cut drawdowns but usually cost return.** A 200-day trend filter shrank the average worst drawdown from **-70%** to **-52%** (lower drawdown in 9/11 names) but beat buy-and-hold on total return in only **2/11**. Risk-adjusted (Sharpe) it was roughly a wash. Crash-avoidance paid off outright only where crashes were deepest (NVDA, AMD).

## Method

- **Data:** daily adjusted close, 2006-01-03 to 2026-08-05 (~5,179 trading days per ticker; AVGO from its Aug-2009 IPO), Yahoo Finance v8 chart API via the agent proxy. Adjusted close folds in splits/dividends.
- **Correction (drawdown episode):** track the running peak; an episode runs peak → trough → recovery to a new high. Keep episodes whose peak-to-trough decline is **≥ 10%** (a secondary ≥ 20% table is also saved). This is the standard drawdown-episode definition; smaller wobbles inside one underwater stretch merge into the larger episode.
- **"Delta between corrections":** peak-to-peak spacing, in trading days.
- **Predictors (measured at the peak, using only prior data - no look-ahead):** run-up from the previous trough, days since the last peak, trailing 60-day annualized volatility, and % extension above the 200-day SMA.
- **Strategies (signals use only lagged data):**
  - **Buy & Hold** - benchmark.
  - **SMA-200 trend filter** - invested only while yesterday's close is above the 200-day SMA, else in cash (0%).
  - **Trailing-stop 15%** - exit when price falls 15% from its in-position high; re-enter when it closes back above the 50-day SMA ("sell the correction").
- **Metrics:** CAGR, annualized volatility, Sharpe (rf = 0), max drawdown, % time invested, number of round-trip entries.

Full code: [`backtest.py`](backtest.py). Raw outputs: [`data/`](data/) (`corrections_10pct.csv`, `corrections_20pct.csv`, `predictability.json`, `strategy_metrics.csv`, `strategy_aggregate.json`).

## Q1 - Is the time *between* corrections predictable?

No. Intervals are irregular and show no memory.

| Ticker | 10%+ corrections | Median depth | Max depth | Median gap (trading days) | Gap variability (CV) | Gap autocorr (lag-1) |
|--------|-----------------:|-------------:|----------:|--------------------------:|---------------------:|---------------------:|
| GOOG | 19 | 19.5% | 65.3% | 196 (~9 mo) | 0.94 | -0.13 |
| AAPL | 32 | 14.1% | 60.9% | 118 (~5.5 mo) | 0.96 | -0.23 |
| NVDA | 27 | 18.3% | 85.1% | 71 (~3.5 mo) | 2.24 | -0.03 |
| MSFT | 19 | 14.1% | 57.9% | 184 (~9 mo) | 1.10 | -0.22 |
| TSM | 32 | 18.4% | 56.5% | 144 (~7 mo) | 0.69 | -0.08 |
| ASML | 35 | 14.5% | 64.1% | 82 (~4 mo) | 1.10 | -0.21 |
| MRVL | 9 | 26.4% | 86.5% | 142 (~7 mo) | 1.81 | -0.27 |
| AMD | 11 | 26.1% | 96.2% | 130 (~6 mo) | 1.99 | -0.07 |
| JPM | 17 | 13.3% | 68.1% | 189 (~9 mo) | 1.15 | -0.13 |
| AXP | 15 | 19.8% | 83.9% | 153 (~7 mo) | 1.00 | -0.01 |
| AVGO | 32 | 14.3% | 48.3% | 92 (~4.4 mo) | 0.88 | +0.16 |

A lag-1 autocorrelation near zero (and pooled **-0.04**, n=226) means "the last gap was long/short" carries essentially no information about the next gap. The pooled test of "does the prior run-up predict time to the next correction" is also null (r = -0.05). Note AVGO has the **shallowest max drawdown of the group** (-48%) - the closest thing here to a "smooth" compounder, though its gaps are just as irregular as the rest.

## Q2 - Is the *size* of the drop predictable?

Barely. Pooled across all 248 corrections:

| Predictor of drop depth | Pearson r | n | Verdict |
|-------------------------|----------:|---:|---------|
| Run-up into the peak | **+0.01** | 248 | none |
| % extension above 200-day SMA | +0.14 | 235 | weak |
| Trailing 60-day volatility | +0.14 | 240 | weak |
| Days since last correction | -0.06 | 237 | none |
| **All four (multiple regression R²)** | **0.031** | 234 | ~3% explained |

The most seductive idea - "the more it ran up, the harder it falls" - is simply not there (r = 0.01, flat line below). The only faint signal is that stocks stretched far above their 200-day trend, or already trading with high volatility, tend to fall a little harder - but "a little" is the operative word (~2% of variance each).

![Run-up vs subsequent drawdown depth](charts/predictor_runup_vs_depth.png)

![Extension above 200-day SMA vs drawdown depth](charts/predictor_extension_vs_depth.png)

**The one strong relationship (and why it's not a crystal ball):** deeper corrections are followed by much longer peak-to-peak gaps (**r = 0.75**, n=237). This is largely mechanical - a 60% drawdown simply takes longer to recover and print a new high than a 12% dip does - so it describes recovery time after the fact, not a way to forecast the *next* top in advance.

## The strategies

Averaged over the 11 tickers (~20 years, no costs):

| Strategy | Avg CAGR | Median CAGR | Avg max drawdown | Avg Sharpe | Beat B&H on return | Lower drawdown than B&H |
|----------|---------:|------------:|-----------------:|-----------:|:------------------:|:-----------------------:|
| Buy & Hold | 21.9% | 18.6% | -70.3% | 0.72 | - | - |
| SMA-200 trend | 16.7% | 14.7% | -51.9% | 0.66 | 2/11 | 9/11 |
| Trailing-stop 15% | 17.9% | 15.3% | -57.9% | 0.68 | 1/11 | 11/11 |

![Average max drawdown vs CAGR by strategy](charts/strategy_maxdd_bar.png)

Per-ticker (CAGR% / max-drawdown%):

| Ticker | Buy & Hold | SMA-200 | Trailing-stop 15% |
|--------|-----------:|--------:|------------------:|
| GOOG | 18.6 / -65.3 | 14.7 / -34.3 | 15.3 / -45.7 |
| AAPL | 27.1 / -60.9 | 23.8 / -40.8 | 25.4 / -54.9 |
| NVDA | 38.0 / -85.1 | **40.5 / -54.2** | **42.1 / -55.5** |
| MSFT | 17.2 / -57.9 | 11.3 / -40.2 | 12.0 / -56.1 |
| TSM | 23.9 / -56.5 | 13.6 / -45.8 | 15.4 / -50.8 |
| ASML | 24.3 / -64.1 | 20.2 / -41.1 | 18.2 / -47.9 |
| MRVL | 11.0 / -86.5 | 6.4 / -70.4 | 7.2 / -70.0 |
| AMD | 14.0 / -96.2 | **20.5 / -64.5** | 11.9 / -89.6 |
| JPM | 14.2 / -68.1 | 4.2 / -77.7 | 9.5 / -66.7 |
| AXP | 11.3 / -83.9 | 5.9 / -38.6 | 10.3 / -60.8 |
| AVGO | **41.7 / -48.3** | 23.1 / -63.1 | 29.2 / -38.8 |

The pattern is consistent: the trend/stop rules almost always **reduce drawdown** (SMA-200 in 9/11, trailing-stop in 11/11) but usually **give back several points of CAGR** to whipsaws and missed rebounds, so on a risk-adjusted basis they land near buy-and-hold. The exceptions prove the logic - **NVDA** and **AMD**, whose buy-and-hold drawdowns were the deepest (-85% and -96%), are where sidestepping the crash actually improved returns. And there are now **two** cases where a trend filter made drawdown *worse* - **JPM** (SMA-200 -77.7% vs -68.1%) and **AVGO** (SMA-200 -63.1% vs a buy-and-hold -48.3%) - both whipsaw warnings: a stock that already rides through with a shallow max drawdown gets little protection from a filter that can sell the dip and buy the bounce. **AVGO** is the cleanest buy-and-hold compounder in the set (41.7% CAGR, the shallowest -48% drawdown, Sharpe 1.1), so the rules mostly just got in its way on return.

![NVDA strategy equity curves](charts/equity_NVDA.png)

![MSFT strategy equity curves](charts/equity_MSFT.png)

## Bottom line

- You **cannot** reliably predict *when* the next correction arrives - the spacing is close to random.
- You can **weakly** anticipate that a stock stretched far above trend or running hot on volatility may fall a bit harder, but the effect is small (r ≈ 0.14) and swamped by noise; the honest point estimate for the next drop is the stock's historical median (~13-26%) with a wide band.
- Simple trend/stop rules are a **drawdown-management** tool, not an alpha engine: they trade some upside for materially smaller crashes - and on the smoothest compounders (AVGO) they can even *raise* drawdown via whipsaw. Whether the trade-off is worth it depends on whether you value the smoother ride more than the forgone CAGR - and on costs/taxes this idealized test ignores.

## Caveats (again, because they matter)

Selection bias (11 survivors that all rose a lot), in-sample and single-path, no costs/taxes/slippage, cash at 0% (understates the trend strategies, which would have earned T-bill yield while out), pooled tests ignore cross-stock correlation, and many correlations were checked (multiple-comparisons risk). None of this generalizes to out-of-sample trading. **Not investment advice.**
