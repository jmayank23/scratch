"""Default universe: ~50 largest S&P 500 constituents by market cap.

Snapshot from mid-2026 public knowledge; market-cap ranks drift, so pass
--tickers or --tickers-file to run on a different/refreshed list.
Tickers use Yahoo-style class shares (BRK-B). Alphabet is GOOGL only (no GOOG dup).
"""

TOP50 = [
    "NVDA", "MSFT", "AAPL", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "JPM",
    "WMT", "LLY", "ORCL", "V", "MA", "NFLX", "XOM", "JNJ", "COST", "PLTR",
    "HD", "ABBV", "BAC", "AMD", "PG", "UNH", "GE", "CVX", "KO", "CSCO",
    "IBM", "WFC", "MU", "CAT", "MS", "GS", "AXP", "CRM", "PM", "TMUS",
    "MRK", "RTX", "ABT", "MCD", "LIN", "ISRG", "PEP", "UBER", "NOW", "INTU",
]

MARKET = "SPY"
