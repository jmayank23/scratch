# Do top S&P 500 stocks "pump, dump, and settle back on trend"?

**Short answer: not as a general pattern.** Among the 50 largest S&P 500
stocks, about 3–7 show this shape. Random price paths with the same volatility
would produce about 5 on their own. MSFT and CSCO are the two clear individual
cases. When prices are measured relative to SPY, the shape becomes more common
than chance. That excess comes mainly from one market event, the spring-2025
selloff and rebound, not from stocks being pumped one at a time.

Data: Yahoo Finance daily adjusted closes, Oct 2023 → **2026-10-29** (3 years).
Universe: 50 large-cap names (`pump_dump/universe.py`). Method, scoring and
validation: [`pump_dump/README.md`](pump_dump/README.md).

## What was tested

For each stock, the detector finds the most prominent recent episode where
the price:

1. rose rapidly above its pre-pump growth trend (the **pump**: ≤ 6 months long,
   ≥ 10% above trend),
2. fell back (the **dump**), and
3. settled somewhere.

It then measures where the price settled relative to the pre-pump trend line:

* **reversion ratio r = 1 − (excess at settle ÷ excess at peak)**
* r ≈ 1 → back on trend (your hypothesis)
* r ≈ 0 → kept the gains
* r > 1 → fell below trend

Each stock also gets a 0–100 **signal score**. Its **p-value** comes from 200
bootstrap random paths built from that stock's own daily returns: how often
does chance alone produce a fit this good?

## Results: raw prices

| | Count |
|---|---|
| Settled within ±0.4 of trend (r between 0.6 and 1.4) | **7** (≈ 5.4 expected by chance, p = 0.29) |
| …and individually significant (p < 0.10) | **5** (≈ 5 expected by chance) |
| Strict SUPPORTS (real fall, settled above start, significant) | **2**: MSFT, CSCO |
| Fell *below* trend after the pump (r > 1.4) | 24 |
| Kept gains / kept rising (r < 0.6) | 19 |
| Median r | 1.37 |

| Ticker | Verdict | p | r | Pump vs trend | Peak→settle | Settle vs start | Start → Peak → Settle |
|---|---|---:|---:|---:|---:|---:|---|
| **MSFT** | SUPPORTS | 0.03 | 0.83 | +38% | −27% | +13% | 2025-04-17 → 2025-08-07 → 2026-04-29 |
| **CSCO** | SUPPORTS | 0.09 | 0.65 | +42% | −11% | +18% | 2026-04-30 → 2026-05-21 → 2026-09-23 |
| AVGO | PARTIAL: plateau | 0.015 | 1.08 | +38% | +7% | +89% | 2025-04-28 → 2025-10-02 → 2026-10-05 |
| TSLA | PARTIAL: back on trend, below start | 0.08 | 0.71 | +118% | −41% | −11% | 2024-10-25 → 2024-12-17 → 2025-03-11 |
| ORCL | PARTIAL: back on trend, below start | 0.095 | 1.37 | +72% | −49% | −1% | 2025-05-19 → 2025-09-29 → 2026-02-04 |
| WMT | WEAK (not significant) | 0.10 | 1.37 | +20% | −16% | +3% | 2025-11-12 → 2026-03-03 → 2026-08-28 |
| PG | PARTIAL: back on trend, below start | 0.15 | 0.68 | +19% | −12% | −0% | 2026-01-22 → 2026-02-25 → 2026-03-11 |

* **MSFT** is the closest match to your hypothesis. It rose about 38% above
  trend from April to August 2025, fell back through spring 2026, and settled
  13% above where the run started, close to its pre-pump trend line.
* **AVGO** scores highest on fit but **did not dump**. It went sideways while
  its rising trend caught up, so it is labeled a plateau, not a pump-and-dump.
* **TSLA and ORCL** pumped and gave it all back, but settled at or slightly
  below their start price, not "slightly higher."
* **Most names do not fit.** META, NFLX, NOW, UNH, PLTR, INTU and others fell
  well *below* their pre-pump trend. NVDA, GOOGL, AAPL, MU, CAT and others kept
  most of their gains.

## Results: price relative to SPY (moves specific to each stock)

| | Count |
|---|---|
| Settled within ±0.4 of trend | **10** (≈ 5.2 expected by chance, **p = 0.03**) |
| …and individually significant (p < 0.10) | **10** (≈ 5 expected by chance, **p = 0.03**) |
| Strict SUPPORTS | 3: KO, AMZN, ABBV |
| PARTIAL | 7: ABT, MSFT, GE, BRK-B, LIN, MA, WMT |

This looks like evidence for the hypothesis, but **it is mostly one shared
event.** Six of the ten in-band episodes peak between March and May 2025
(KO, BRK-B, LIN, ABBV, ABT, MA). These are defensive names. They outperformed
while SPY sold off sharply in spring 2025, then gave the gap back as SPY
recovered. The stocks did not pump; the market dipped and recovered. Because
the episodes share dates, the 50 stocks are not independent tests, and the
p = 0.03 overstates the evidence.

## How much to trust this

* **The test is calibrated.** In synthetic tests on pure random walks, it
  returns a false "supports" verdict only 3–10% of the time.
* **Its power is limited.** At typical mega-cap volatility (1–1.5% per day), it
  catches a genuine ~40% pump-and-revert only 13–47% of the time. For ~80%
  pumps it rises to 33–60%. So the analysis can reject "this is common," but it
  can miss individual small cases.
* **About 20 of the 50 stocks had no clear pump.** Their best episode sits right
  at the 10% minimum, so their labels say little.
* **"Linear" is modeled as constant percentage growth** (a straight line on a
  log chart). Results may differ if you meant a straight line in dollar terms.

## Files

* `results/REPORT.md`, `results/results.csv`, `results/charts/*.png`: raw prices
* `results_vs_spy/…`: same, for prices relative to SPY
* `*/summary_reversion.png`: one dot per stock showing its r

Re-run with `python -m pump_dump.run_analysis` (add `--vs-market` for the
relative version). Results will shift as new data arrives.
