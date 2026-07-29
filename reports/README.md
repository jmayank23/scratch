# Tech Stock Analysis - Last 30 Days

In-depth, community-and-news-grounded analysis of three mega-cap tech stocks, generated on **2026-07-29** using the [`/last30days`](https://github.com/mvanhorn/last30days-skill) skill (v3.18.4). Each report synthesizes what investors are actually saying across Reddit, YouTube, Hacker News, and Polymarket prediction markets, supplemented with sell-side analyst coverage and news from web search.

## Reports

| Ticker | Company | Report | Raw research |
|--------|---------|--------|--------------|
| GOOG | Alphabet | [GOOG-alphabet-analysis.md](GOOG-alphabet-analysis.md) | [raw](raw/alphabet-goog-stock-raw-v3.md) |
| AAPL | Apple | [AAPL-apple-analysis.md](AAPL-apple-analysis.md) | [raw](raw/apple-aapl-stock-raw-v3.md) |
| NVDA | Nvidia | [NVDA-nvidia-analysis.md](NVDA-nvidia-analysis.md) | [raw](raw/nvidia-nvda-stock-raw-v3.md) |

## The one theme tying all three together: the AI-capex divide

The single question dominating mega-cap tech this month is whether enormous AI infrastructure spending is an asset or a liability - and the three stocks sit at different points on that spectrum.

- **Alphabet (GOOG)** printed its best quarter ever (revenue +24% to $119.8B, Cloud +82%, $514B backlog) and still sold off ~5-6% because it raised 2026 capex guidance to $195-205B. The market is trading the spend, not the results.
- **Nvidia (NVDA)** is the supplier at the center of that spend - and fell ~5% when it emerged it may backstop up to ~$250B (potentially ~$600B all-in) of OpenAI's buildout, reviving "circular financing" fears that its own money is inflating GPU demand.
- **Apple (AAPL)** is the deliberate outlier: it spends only ~2.5% of sales on capex versus ~39% for the hyperscalers, and the crowd rewarded that "capital-light" posture - Apple hit record highs, neared a $5T market cap, and briefly retook the most-valuable-company crown from Nvidia after an HSBC upgrade.

The "most valuable company" title changing hands between Apple and Nvidia in a single month is the clearest signal of how fast the market is repricing the AI-spend trade.

## How these were produced

1. Installed the open-source `/last30days` skill (mvanhorn/last30days-skill, MIT) into the skills directory.
2. For each ticker: ran web pre-research to resolve communities and recent news, generated a per-ticker query plan, and ran the skill's Python engine (`--emit=compact --plan ...`) across Reddit, YouTube, Hacker News, and Polymarket.
3. Supplemented with targeted web search for analyst targets and earnings/news context (appended to each raw file under `## WebSearch Supplemental Results`).
4. Synthesized each brief following the skill's output contract.

**Coverage note:** X/Twitter, TikTok, and Instagram were not available in this environment (no logged-in browser cookies or API keys), so coverage is weighted toward Reddit, YouTube, Hacker News, Polymarket, and the open web. GitHub and Stocktwits were rate-limited/unresolved during the runs.

## Not financial advice

These reports summarize public discussion and analyst commentary over a rolling 30-day window as of 2026-07-29. They are informational only and are not investment advice. Prices, odds, and estimates cited were current at generation time and move constantly.
