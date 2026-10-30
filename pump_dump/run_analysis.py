"""Test the pump-and-revert-to-trend hypothesis on a list of stocks.

    python -m pump_dump.run_analysis                       # top-50 S&P 500, Yahoo/Stooq
    python -m pump_dump.run_analysis --vs-market           # idiosyncratic: price relative to SPY
    python -m pump_dump.run_analysis --source csv --csv-dir my_prices/
    python -m pump_dump.run_analysis --synthetic           # self-check on planted patterns
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

from . import plots
from .data import load_prices
from .model import FitConfig, classify, config_dict, null_scores, score_series
from .universe import MARKET, TOP50


def analyse_one(args):
    ticker, dates, y, cfg, n_null, alpha, seed = args
    s = score_series(y, cfg)
    s["ticker"] = ticker
    if s["has_pump"] and n_null > 0:
        null = null_scores(y, cfg, n_paths=n_null, seed=seed)
        s["p_value"] = float((1 + np.sum(null[:, 0] >= s["score"])) / (1 + len(null)))
        r_null = null[:, 1]
        s["null_revert_rate"] = float(np.mean(np.abs(r_null - 1) <= cfg.revert_band))
    else:
        s["p_value"] = 1.0 if not s["has_pump"] else np.nan
        s["null_revert_rate"] = np.nan
    s["shape"], s["verdict"] = classify(s, s["p_value"] if np.isfinite(s["p_value"]) else 1.0, cfg, alpha)
    if s["has_pump"]:
        for k in ("t0", "t1", "t2"):
            s[{"t0": "start_date", "t1": "peak_date", "t2": "settle_date"}[k]] = str(dates[s[k]].date())
    return s


def aggregate(df: pd.DataFrame, alpha: float, rng=np.random.default_rng(0)):
    """Is the cross-section of stocks more pump-and-revert than chance?"""
    n = len(df)
    pumped = df[df["has_pump"]]
    obs_shape = int((pumped["shape"] == "pump_revert").sum())
    rates = pumped["null_revert_rate"].fillna(0).to_numpy()
    sims = (rng.random((20000, len(rates))) < rates).sum(1) if len(rates) else np.zeros(1)
    obs_sig = int((df["verdict"] == "SUPPORTS").sum())
    sims_sig = rng.binomial(n, alpha, 20000)
    return dict(
        n_stocks=n,
        n_with_pump=int(len(pumped)),
        n_revert_shape=obs_shape,
        expected_revert_shape_by_chance=float(rates.sum()),
        p_revert_shape_excess=float(np.mean(sims >= obs_shape)),
        n_supports=obs_sig,
        expected_supports_by_chance_upper=float(alpha * n),
        p_supports_excess=float(np.mean(sims_sig >= obs_sig)),
        median_r=float(pumped["r"].median()) if len(pumped) else float("nan"),
    )


def synthetic_universe(n_days=756, seed=7):
    """Planted patterns with KNOWN answers, used to validate the detector (not real data)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n_days)
    tau = np.arange(n_days)
    out = {}

    def base(drift=0.15, vol=0.012):
        return np.log(100) + drift / 252 * tau + np.cumsum(rng.normal(0, vol, n_days))

    def bump(t0, t1, t2, h, d):
        b = np.zeros(n_days)
        b[t0:t1] = h * (tau[t0:t1] - t0) / (t1 - t0)
        b[t1:t2] = h + (d - h) * (tau[t1:t2] - t1) / (t2 - t1)
        b[t2:] = d
        return b

    for i in range(4):
        t0 = 350 + 40 * i
        out[f"REVERT{i}"] = base() + bump(t0, t0 + 50, t0 + 150, 0.35, 0.0)
        out[f"HOLD{i}"] = base() + bump(t0, t0 + 50, t0 + 150, 0.35, 0.33)
        out[f"CRASH{i}"] = base() + bump(t0, t0 + 50, t0 + 150, 0.35, -0.30)
        out[f"NOISE{i}"] = base(vol=0.018)
    return {k: pd.Series(np.exp(v), index=dates) for k, v in out.items()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="*", help="override ticker list")
    ap.add_argument("--tickers-file", help="file with one ticker per line")
    ap.add_argument("--years", type=float, default=3.0, help="history to analyse (default 3y)")
    ap.add_argument("--source", default="auto", choices=["auto", "csv", "yfinance", "stooq"])
    ap.add_argument("--csv-dir", help="folder of <TICKER>.csv files (Date, Close/Adj Close)")
    ap.add_argument("--refresh", action="store_true", help="ignore cached downloads")
    ap.add_argument("--vs-market", action="store_true",
                    help=f"analyse price relative to {MARKET} (strips market-wide moves)")
    ap.add_argument("--n-null", type=int, default=200, help="bootstrap null paths per stock")
    ap.add_argument("--alpha", type=float, default=0.10)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--min-pump", type=float, default=0.10, help="min log excess at peak")
    ap.add_argument("--revert-band", type=float, default=0.4, help="|r-1| tolerance for 'reverted'")
    ap.add_argument("--recent-days", type=int, default=504, help="pump must start within N trading days")
    ap.add_argument("--out", default="results")
    ap.add_argument("--synthetic", action="store_true", help="run on planted synthetic patterns")
    a = ap.parse_args(argv)

    cfg = FitConfig(min_pump=a.min_pump, revert_band=a.revert_band, recent_days=a.recent_days)
    out = plots.ensure_dir(a.out)
    chart_dir = plots.ensure_dir(os.path.join(out, "charts"))

    if a.synthetic:
        prices, errors = synthetic_universe(), {}
    else:
        tickers = a.tickers or (open(a.tickers_file).read().split() if a.tickers_file else TOP50)
        need = list(tickers) + ([MARKET] if a.vs_market and MARKET not in tickers else [])
        print(f"Loading {len(need)} tickers ({a.source}) ...")
        prices, errors = load_prices(need, years=a.years, source=a.source, csv_dir=a.csv_dir,
                                     refresh=a.refresh)
        if a.vs_market:
            if MARKET not in prices:
                sys.exit(f"--vs-market needs {MARKET} data")
            mkt = prices.pop(MARKET) if MARKET not in tickers else prices[MARKET]
            prices = {k: (v / mkt).dropna() for k, v in prices.items() if k != MARKET}
    if not prices:
        print("\nNo price data could be loaded. Errors:")
        for k, v in list(errors.items())[:5]:
            print(f"  {k}: {v}")
        sys.exit(2)

    n_days = int(a.years * 252)
    jobs = []
    for i, (tk, s) in enumerate(prices.items()):
        s = s[s > 0].iloc[-n_days:]
        if len(s) < cfg.min_pre_days + 60:
            print(f"  [skip] {tk}: only {len(s)} days")
            continue
        jobs.append((tk, s.index, np.log(s.to_numpy()), cfg, a.n_null, a.alpha, 1000 + i))

    print(f"Fitting {len(jobs)} series with {a.n_null} bootstrap nulls each ...")
    with Pool(a.workers) as pool:
        results = pool.map(analyse_one, jobs)

    ylabel = f"Price relative to {MARKET} (log)" if a.vs_market else "Price (log scale)"
    for (tk, dates, y, *_), s in zip(jobs, results):
        plots.stock_chart(tk, dates, y, s, os.path.join(chart_dir, f"{tk}.png"), ylabel)

    df = pd.DataFrame([{k: v for k, v in s.items() if not k.startswith("_")} for s in results])
    df = df.sort_values(["score"], ascending=False).reset_index(drop=True)
    df.to_csv(os.path.join(out, "results.csv"), index=False)
    plots.summary_chart(df, os.path.join(out, "summary_reversion.png"), cfg.revert_band)
    agg = aggregate(df, a.alpha)
    meta = dict(config=config_dict(cfg), args=vars(a), aggregate=agg, data_errors=errors,
                last_date=str(max(j[1][-1] for j in jobs).date()))
    with open(os.path.join(out, "summary.json"), "w") as f:
        json.dump(meta, f, indent=2, default=str)
    write_report(df, agg, meta, os.path.join(out, "REPORT.md"))
    print_table(df, agg)


def print_table(df, agg):
    cols = ["ticker", "verdict", "shape", "score", "p_value", "r", "pump_excess_pct",
            "settle_vs_trend_pct", "settle_vs_start_pct", "start_date", "peak_date", "settle_date"]
    cols = [c for c in cols if c in df]
    with pd.option_context("display.width", 200, "display.max_rows", 200, "display.float_format", "{:.3f}".format):
        print(df[cols].to_string(index=False))
    print("\nAggregate:", json.dumps(agg, indent=2))


def _pct(x):
    return "" if pd.isna(x) else f"{100 * x:+.0f}%"


def write_report(df, agg, meta, path):
    a = meta["args"]
    L = [
        "# Pump-and-revert-to-trend: results",
        "",
        f"Data through **{meta['last_date']}**, {a['years']}y daily history, "
        f"{'price relative to SPY' if a['vs_market'] else 'raw adjusted price'}, "
        f"{a['n_null']} bootstrap nulls per stock, alpha = {a['alpha']}."
        + (" **SYNTHETIC planted data - not market results.**" if a["synthetic"] else ""),
        "",
        "## Aggregate",
        "",
        f"- Stocks analysed: {agg['n_stocks']}; with a pump >= {meta['config']['min_pump']:.0%} (log) above trend: {agg['n_with_pump']}",
        f"- Revert-to-trend shape: **{agg['n_revert_shape']}** observed vs {agg['expected_revert_shape_by_chance']:.1f} "
        f"expected from random paths (p = {agg['p_revert_shape_excess']:.3f})",
        f"- SUPPORTS (revert shape and stock-level p < alpha): **{agg['n_supports']}** vs <= "
        f"{agg['expected_supports_by_chance_upper']:.1f} by chance (p = {agg['p_supports_excess']:.3f})",
        f"- Median reversion ratio r among pumped stocks: {agg['median_r']:.2f} (hypothesis predicts ~1)",
        "",
        "![summary](summary_reversion.png)",
        "",
        "## Per stock (sorted by signal score)",
        "",
        "| Ticker | Verdict | Shape | Score | p | r | Pump vs trend | Settle vs trend | Settle vs start | Start -> Peak -> Settle |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for _, s in df.iterrows():
        if not s["has_pump"]:
            L.append(f"| {s['ticker']} | {s['verdict']} | no_pump | 0 | | | | | | |")
            continue
        L.append(
            f"| [{s['ticker']}](charts/{s['ticker']}.png) | {s['verdict']} | {s['shape']} | {s['score']:.0f} | "
            f"{s['p_value']:.3f} | {s['r']:.2f} | {_pct(s['pump_excess_pct'])} | {_pct(s['settle_vs_trend_pct'])} | "
            f"{_pct(s['settle_vs_start_pct'])} | {s['start_date']} -> {s['peak_date']} -> {s['settle_date']} |")
    L += ["", "See README.md for the method and column definitions.", ""]
    with open(path, "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
