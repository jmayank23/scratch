# Stock Analysis Reports

A growing directory of in-depth, single-name stock analyses. Each report captures what investors are actually saying and what analysts are forecasting over a rolling 30-day window, and is organized below by category. Dates are the day the analysis was run, in **CST**.

## How these reports are created

Reports are generated with the open-source [`/last30days`](https://github.com/mvanhorn/last30days-skill) research skill (v3.18.4). For each ticker the workflow is:

1. **Pre-research** - web search resolves the relevant communities (subreddits, channels) and the latest news/earnings context for the ticker.
2. **Query plan** - a small JSON plan of sub-queries (primary + earnings/capex + valuation angles) is handed to the skill's engine.
3. **Multi-source sweep** - the engine pulls the last 30 days of discussion and engagement from **Reddit** (threads + comments), **YouTube** (videos + transcripts), **Hacker News**, and **Polymarket** prediction-market odds, then ranks the evidence into story clusters.
4. **Web supplement** - targeted searches add analyst price targets and news/analysis; these are recorded under `## WebSearch Supplemental Results` in each raw file.
5. **Synthesis** - the ranked evidence is written up as a narrative brief: headline findings, verbatim community voice, prediction-market odds, key patterns, and a source-count footer.
6. **5-year price chart** - each report closes with a 5-year adjusted-close price chart (real daily data from Yahoo Finance, rendered to [`charts/`](charts/)). Pre-IPO names with no trading history are noted instead of charted.

Each report links to its underlying raw research in [`raw/`](raw/). Recurring cross-cutting themes (for example, the AI-capex debate running through the mega-cap names) are discussed inside the individual reports.

**Coverage note:** runs to date used the free keyless sources (Reddit, YouTube, Hacker News, Polymarket) plus web search. X/Twitter, TikTok, and Instagram require credentials not present in this environment, so coverage is weighted toward the sources above.

## Analysis

- [**Can corrections be predicted? A backtest**](backtests/) - tests whether the timing and depth of drawdowns are predictable across the 11 charted tickers (~20 years of daily data), and backtests three rules-based strategies vs buy-and-hold. Short answer: timing is essentially unpredictable, depth is only weakly so, and trend/stop rules cut drawdowns but usually cost return. Exploratory and in-sample - see its caveats.
- [**MSFT technical indicator read**](indicators/MSFT-technical-read.md) - RSI, Money Flow Index divergence, Ichimoku, and DeMark TD Sequential (9) computed on real MSFT daily data, with a read on each. Net: bullish trend, tactically overbought/extended after the post-earnings breakout.

## Reports by category

### Semiconductors

| Ticker | Company | Report | Raw data | Analyzed (CST) |
|--------|---------|--------|----------|----------------|
| NVDA | Nvidia | [NVDA-nvidia-analysis.md](NVDA-nvidia-analysis.md) | [raw](raw/nvidia-nvda-stock-raw-v3.md) | 2026-07-29 |
| TSM | TSMC (Taiwan Semiconductor) | [TSM-tsmc-analysis.md](TSM-tsmc-analysis.md) | [raw](raw/tsmc-tsm-stock-raw-v3.md) | 2026-07-29 |
| ASML | ASML Holding | [ASML-asml-analysis.md](ASML-asml-analysis.md) | [raw](raw/asml-stock-raw-v3.md) | 2026-07-29 |
| MRVL | Marvell Technology | [MRVL-marvell-analysis.md](MRVL-marvell-analysis.md) | [raw](raw/marvell-mrvl-stock-raw-v3.md) | 2026-07-29 |
| AMD | Advanced Micro Devices | [AMD-amd-analysis.md](AMD-amd-analysis.md) | [raw](raw/amd-stock-raw-v3.md) | 2026-07-30 |
| AVGO | Broadcom | [AVGO-broadcom-analysis.md](AVGO-broadcom-analysis.md) | [raw](raw/broadcom-avgo-stock-raw-v3.md) | 2026-08-08 |

### Software & Cloud

| Ticker | Company | Report | Raw data | Analyzed (CST) |
|--------|---------|--------|----------|----------------|
| MSFT | Microsoft | [MSFT-microsoft-analysis.md](MSFT-microsoft-analysis.md) | [raw](raw/microsoft-msft-stock-raw-v3.md) | 2026-07-29 |

### Internet & Digital Advertising

| Ticker | Company | Report | Raw data | Analyzed (CST) |
|--------|---------|--------|----------|----------------|
| GOOG | Alphabet | [GOOG-alphabet-analysis.md](GOOG-alphabet-analysis.md) | [raw](raw/alphabet-goog-stock-raw-v3.md) | 2026-07-29 |

### Consumer Electronics

| Ticker | Company | Report | Raw data | Analyzed (CST) |
|--------|---------|--------|----------|----------------|
| AAPL | Apple | [AAPL-apple-analysis.md](AAPL-apple-analysis.md) | [raw](raw/apple-aapl-stock-raw-v3.md) | 2026-07-29 |

### Banks & Financial Services

| Ticker | Company | Report | Raw data | Analyzed (CST) |
|--------|---------|--------|----------|----------------|
| JPM | JPMorgan Chase | [JPM-jpmorgan-analysis.md](JPM-jpmorgan-analysis.md) | [raw](raw/jpmorgan-chase-jpm-stock-raw-v3.md) | 2026-08-03 |
| AXP | American Express | [AXP-american-express-analysis.md](AXP-american-express-analysis.md) | [raw](raw/american-express-axp-stock-raw-v3.md) | 2026-08-03 |

### IPOs & New Listings

_Pre-IPO / newly listed names. These have no trading history or earnings yet, so reports lean on filings/announcements plus early community sentiment rather than financial results._

| Ticker | Company | Report | Raw data | Analyzed (CST) |
|--------|---------|--------|----------|----------------|
| RVII | Robinhood Ventures Fund II | [RVII-robinhood-ventures-ii-analysis.md](RVII-robinhood-ventures-ii-analysis.md) | [raw](raw/robinhood-ventures-fund-ii-rvii-ipo-raw-v3.md) | 2026-08-03 |

## Adding a new report

1. Run the skill for the ticker (see the workflow above); it writes a `raw/<company>-<ticker>-stock-raw-v3.md` file.
2. Save the synthesized brief as `reports/<TICKER>-<company>-analysis.md`.
3. Add a row to the matching category table below (or create a new `###` category section using the same 5-column format), with the analysis date in CST.

## Not financial advice

These reports summarize public discussion and analyst commentary over a rolling 30-day window as of the analysis date. They are informational only and are not investment advice. Prices, odds, and estimates cited were current at generation time and move constantly.
