#!/usr/bin/env python3
"""
Weekly dollar-cost-averaging backtest.

$500 every week, split by fixed weights, fractional shares, no fees/taxes,
no rebalancing, never sell. Prices are yfinance "Adj Close" (auto_adjust=False),
so dividends are reinvested. Missing early history is back-filled with a
proxy's daily returns, chained onto the real ETF (return splice, not price).

Outputs (CSV + PNG) go to ./backtest_out
"""
import importlib
import subprocess
import sys

for pkg in ("yfinance", "pandas", "numpy", "matplotlib"):
    try:
        importlib.import_module(pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

import os
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import yfinance as yf

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
START = "2006-11-24"
WEEKLY = 500.0
OUT = "backtest_out"
N_RANDOM = 100
SEED = 42

TICKERS = ["VOO", "VXUS", "SCHD", "QQQ", "IAU", "RSP"]
PROXIES = {"VOO": "SPY", "VXUS": "VGTSX", "SCHD": "DVY"}

MIXES_RAW = {
    "2 ETFs": {"VOO": 45, "VXUS": 20},
    "3 ETFs": {"VOO": 25, "SCHD": 20, "VXUS": 20},
    "4 ETFs": {"VOO": 25, "SCHD": 20, "VXUS": 20, "QQQ": 15},
    "5 ETFs": {"VOO": 25, "SCHD": 20, "VXUS": 20, "QQQ": 15, "IAU": 20},
    "6 ETFs": {"VOO": 15, "RSP": 10, "SCHD": 20, "VXUS": 20, "QQQ": 15, "IAU": 20},
    "Baseline": {"VOO": 100},
}
MIXES = {k: {t: w / sum(v.values()) for t, w in v.items()} for k, v in MIXES_RAW.items()}

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
# Buy windows are 7-day blocks that start on Fri 2006-11-24, so every schedule
# makes exactly the same number of buys. Offset of each weekday inside a block:
DAY_OFFSET = {"Fri": 0, "Mon": 3, "Tue": 4, "Wed": 5, "Thu": 6}

os.makedirs(OUT, exist_ok=True)
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)


def mix_label(name):
    return name + "  (" + " / ".join(f"{t} {w:.0%}" for t, w in MIXES[name].items()) + ")"


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
all_syms = TICKERS + list(PROXIES.values())
raw = yf.download(all_syms, start="2006-11-01", auto_adjust=False,
                  progress=False, threads=False)
adj = raw["Adj Close"].copy()
adj.index = pd.to_datetime(adj.index).tz_localize(None)
missing = [s for s in all_syms if s not in adj.columns or adj[s].dropna().empty]
if missing:
    sys.exit(f"Download failed for: {missing}")

# Trading calendar = SPY's (NYSE) days. Drop today: its bar is an unfinished session.
cal = adj["SPY"].dropna().index
cal = cal[(cal >= START) & (cal.date < date.today())]
adj = adj.reindex(cal)

prices = pd.DataFrame(index=cal)
splice_rows = []
for t in TICKERS:
    real = raw["Adj Close"][t].copy()
    real.index = pd.to_datetime(real.index).tz_localize(None)
    first_real = real.dropna().index[0]
    s = adj[t].copy()
    if t in PROXIES and first_real > cal[0]:
        p = PROXIES[t]
        prox = adj[p].ffill()  # mutual-fund NAV can miss an odd day
        anchor = s.loc[first_real]
        before = cal < first_real
        # chain proxy returns backwards from the first real close
        s[before] = anchor * prox[before] / prox.loc[first_real]
        last_proxy_day = cal[before][-1]
        splice_rows.append(dict(ticker=t, first_real_date=first_real.date(), proxy=p,
                                proxy_from=cal[0].date(), proxy_to=last_proxy_day.date(),
                                proxy_trading_days=int(before.sum())))
    else:
        splice_rows.append(dict(ticker=t, first_real_date=first_real.date(), proxy="",
                                proxy_from="", proxy_to="", proxy_trading_days=0))
    prices[t] = s.ffill()

if prices.isna().any().any():
    sys.exit("NaNs remain in spliced prices:\n" + str(prices.isna().sum()))

splice = pd.DataFrame(splice_rows)
splice.to_csv(f"{OUT}/data_splice.csv", index=False)
END = cal[-1]

print("=" * 78)
print("DATA")
print("=" * 78)
print(f"Trading days used: {cal[0].date()} -> {END.date()} ({len(cal)} days)")
for r in splice_rows:
    line = f"  {r['ticker']:5s} real data from {r['first_real_date']}"
    if r["proxy"]:
        line += (f"   | proxy {r['proxy']} used {r['proxy_from']} -> {r['proxy_to']}"
                 f" ({r['proxy_trading_days']} days)")
    print(line)

# ----------------------------------------------------------------------------
# Schedules
# ----------------------------------------------------------------------------
cal_np = cal.values.astype("datetime64[D]")


def next_trading_idx(dates):
    """Index of the first trading day on/after each date (holiday -> next day)."""
    return np.searchsorted(cal_np, np.asarray(dates, dtype="datetime64[D]"), side="left")


start_d = np.datetime64(START, "D")
n_blocks_max = int((cal_np[-1] - start_d).astype(int) // 7) + 1
block_start = start_d + (7 * np.arange(n_blocks_max)).astype("timedelta64[D]")
# keep only blocks where every weekday's buy (after holiday shift) is in the data
last_ok = np.ones(n_blocks_max, bool)
for d, off in DAY_OFFSET.items():
    idx = next_trading_idx(block_start + np.timedelta64(off, "D"))
    last_ok &= idx < len(cal_np)
block_start = block_start[last_ok]
N_BUYS = len(block_start)


def schedule_for_day(day):
    return next_trading_idx(block_start + np.timedelta64(DAY_OFFSET[day], "D"))


def random_schedule(rng):
    offs = np.array(list(DAY_OFFSET.values()))[rng.integers(0, 5, N_BUYS)]
    return next_trading_idx(block_start + offs.astype("timedelta64[D]"))


SCHED = {d: schedule_for_day(d) for d in DAYS}
for d in DAYS:
    assert len(np.unique(SCHED[d])) == N_BUYS

print(f"\nBuys per schedule: {N_BUYS} (one per 7-day block, "
      f"first block starts Fri {START})")
for d in DAYS:
    print(f"  {d}: first buy {cal[SCHED[d][0]].date()}, last buy {cal[SCHED[d][-1]].date()}")
print(f"All portfolios valued at the close of {END.date()}")

# ----------------------------------------------------------------------------
# Engine
# ----------------------------------------------------------------------------
P = prices[TICKERS].values  # days x tickers
T = len(cal)
tidx = {t: i for i, t in enumerate(TICKERS)}
years_from_start = (cal_np - cal_np[0]).astype(float) / 365.0


def per_dollar_value(buy_idx):
    """Value series (days x tickers) of buying $1 of each ticker on each buy day."""
    units = np.zeros_like(P)
    np.add.at(units, buy_idx, 1.0 / P[buy_idx])
    return np.cumsum(units, axis=0) * P


def mix_value(G, mix):
    w = np.zeros(len(TICKERS))
    for t, x in mix.items():
        w[tidx[t]] = x
    return WEEKLY * G @ w


def xirr(buy_idx, final_value):
    """Money-weighted annual return: -$500 on each buy date, +final on END."""
    t = years_from_start[buy_idx]
    tf = years_from_start[-1]

    def npv(r):
        return final_value * (1 + r) ** (-tf) - WEEKLY * np.sum((1 + r) ** (-t))

    lo, hi = -0.95, 2.0
    flo, fhi = npv(lo), npv(hi)
    if flo * fhi > 0:
        return np.nan
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = npv(mid)
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
        if hi - lo < 1e-10:
            break
    return (lo + hi) / 2


def analyse(name, buy_idx, G):
    V = mix_value(G, MIXES[name])
    flows = np.zeros(T)
    flows[buy_idx] = WEEKLY
    invested = np.cumsum(flows)
    final = V[-1]
    tot_inv = invested[-1]
    irr = xirr(buy_idx, final)

    # max drawdown of the portfolio dollar value (as asked: includes new money)
    live = invested > 0
    Vs = pd.Series(V, index=cal)[live]
    peak = Vs.cummax()
    dd = Vs / peak - 1
    trough = dd.idxmin()
    peak_date = Vs.loc[:trough].idxmax()

    # time-weighted daily returns (strip out the new money bought at the close)
    Vprev = np.r_[np.nan, V[:-1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(Vprev > 0, (V - flows) / Vprev - 1, np.nan)
    r = pd.Series(r, index=cal)
    twr_index = (1 + r.fillna(0)).cumprod()[live]
    twr_dd = (twr_index / twr_index.cummax() - 1).min()

    yearly = (1 + r.dropna()).groupby(r.dropna().index.year).prod() - 1
    first_year, last_year = cal[0].year, END.year
    partial = {first_year: f"partial ({cal[buy_idx[0]].date()}->)",
               last_year: f"partial (->{END.date()})"}
    yr = pd.DataFrame({"mix": name, "year": yearly.index,
                       "return_net_of_new_money": yearly.values})
    yr["note"] = yr["year"].map(partial).fillna("full year")
    full = yr[yr["note"] == "full year"]
    worst = full.loc[full["return_net_of_new_money"].idxmin()]
    best = full.loc[full["return_net_of_new_money"].idxmax()]

    summary = dict(
        mix=name, weights=" / ".join(f"{t} {w:.1%}" for t, w in MIXES[name].items()),
        total_invested=tot_inv, final_value=final, gain=final - tot_inv,
        multiple=final / tot_inv, xirr=irr,
        max_drawdown=dd.min(), max_dd_peak_date=peak_date.date(),
        max_dd_trough_date=trough.date(),
        twr_max_drawdown=twr_dd,
        worst_year=int(worst["year"]), worst_year_return=worst["return_net_of_new_money"],
        best_year=int(best["year"]), best_year_return=best["return_net_of_new_money"],
    )
    summary["xirr_per_unit_dd"] = irr / abs(dd.min())
    return summary, V, invested, yr


# ----------------------------------------------------------------------------
# Run: weekday schedules
# ----------------------------------------------------------------------------
G_day = {d: per_dollar_value(SCHED[d]) for d in DAYS}
results = {}  # (mix, day) -> summary
series = {}
years = {}
for d in DAYS:
    for m in MIXES:
        s, V, inv, yr = analyse(m, SCHED[d], G_day[d])
        results[(m, d)] = s
        if d == "Mon":
            series[m] = (V, inv)
            years[m] = yr

# Monday summary table
mon = pd.DataFrame([results[(m, "Mon")] for m in MIXES]).set_index("mix")
mon.to_csv(f"{OUT}/summary_monday.csv")
pd.concat(years.values()).to_csv(f"{OUT}/calendar_years_monday.csv", index=False)
pd.DataFrame({m: series[m][0] for m in MIXES} | {"total_invested": series["Baseline"][1]},
             index=cal).rename_axis("date").to_csv(f"{OUT}/portfolio_value_monday.csv")

fmt_mon = pd.DataFrame({
    "Invested": mon["total_invested"].map("${:,.0f}".format),
    "Final value": mon["final_value"].map("${:,.0f}".format),
    "Gain": mon["gain"].map("${:,.0f}".format),
    "Multiple": mon["multiple"].map("{:.2f}x".format),
    "XIRR": mon["xirr"].map("{:.2%}".format),
    "Max DD": mon["max_drawdown"].map("{:.1%}".format),
    "DD trough": mon["max_dd_trough_date"],
    "Worst yr": [f"{y} {v:+.1%}" for y, v in zip(mon["worst_year"], mon["worst_year_return"])],
    "Best yr": [f"{y} {v:+.1%}" for y, v in zip(mon["best_year"], mon["best_year_return"])],
    "XIRR/|DD|": mon["xirr_per_unit_dd"].map("{:.3f}".format),
})
print("\n" + "=" * 78)
print("RESULTS PER MIX - MONDAY BUYS")
print("=" * 78)
print(fmt_mon.to_string())
print("\nTime-weighted max drawdown (new money stripped out), for reference:")
print("  " + ", ".join(f"{m} {v:.1%}" for m, v in mon["twr_max_drawdown"].items()))
print("Years 2006 and 2026 are partial and left out of worst/best year "
      "(see calendar_years_monday.csv).")

# ----------------------------------------------------------------------------
# Weekday table
# ----------------------------------------------------------------------------
wk = pd.DataFrame({d: [results[(m, d)]["xirr"] for m in MIXES] for d in DAYS},
                  index=list(MIXES)).rename_axis("mix")
fv = pd.DataFrame({d: [results[(m, d)]["final_value"] for m in MIXES] for d in DAYS},
                  index=list(MIXES))
wk["best_day"] = wk[DAYS].idxmax(axis=1)
wk["worst_day"] = wk[DAYS].idxmin(axis=1)
wk["spread_pp_per_year"] = (wk[DAYS].max(axis=1) - wk[DAYS].min(axis=1)) * 100
wk["spread_final_$"] = [fv.loc[m, wk.loc[m, "best_day"]] - fv.loc[m, wk.loc[m, "worst_day"]]
                        for m in wk.index]
wk.to_csv(f"{OUT}/weekday_xirr.csv")
fv.rename_axis("mix").to_csv(f"{OUT}/weekday_final_value.csv")

print("\n" + "=" * 78)
print("XIRR BY BUY WEEKDAY")
print("=" * 78)
show = wk[DAYS].map("{:.3%}".format)
show["Best-Worst"] = wk["spread_pp_per_year"].map("{:.3f} pp/yr".format)
show["Best-Worst $"] = wk["spread_final_$"].map("${:,.0f}".format)
show["Best/Worst day"] = wk["best_day"] + " / " + wk["worst_day"]
print(show.to_string())

# ----------------------------------------------------------------------------
# Random buy-day test
# ----------------------------------------------------------------------------
rng = np.random.default_rng(SEED)
rand_rows = []
for k in range(N_RANDOM):
    idx = random_schedule(rng)
    G = per_dollar_value(idx)
    for m in MIXES:
        V_end = mix_value(G[-1:], MIXES[m])[0]
        rand_rows.append(dict(run=k, mix=m, final_value=V_end, xirr=xirr(idx, V_end)))
rand = pd.DataFrame(rand_rows)
rand.to_csv(f"{OUT}/random_runs.csv", index=False)

boot_rng = np.random.default_rng(SEED + 1)
test_rows = []
for m in MIXES:
    x = rand.loc[rand.mix == m, "xirr"].values
    # How big is the best-minus-worst spread among 5 schedules picked at random?
    draws = np.array([np.ptp(boot_rng.choice(x, 5, replace=False)) for _ in range(20000)])
    obs = wk.loc[m, "spread_pp_per_year"] / 100
    test_rows.append(dict(
        mix=m, random_mean=x.mean(), random_std=x.std(ddof=1),
        random_p5=np.percentile(x, 5), random_p95=np.percentile(x, 95),
        random_min=x.min(), random_max=x.max(),
        weekday_best=wk.loc[m, DAYS].max(), weekday_worst=wk.loc[m, DAYS].min(),
        weekday_spread_pp=obs * 100,
        random_5pick_spread_median_pp=np.median(draws) * 100,
        random_5pick_spread_p95_pp=np.percentile(draws, 95) * 100,
        p_value_spread=(draws >= obs).mean(),
    ))
rtest = pd.DataFrame(test_rows).set_index("mix")
rtest.to_csv(f"{OUT}/random_test.csv")

print("\n" + "=" * 78)
print(f"RANDOM BUY DAY TEST ({N_RANDOM} runs, one random weekday per week)")
print("=" * 78)
rshow = pd.DataFrame({
    "Rand mean": rtest["random_mean"].map("{:.3%}".format),
    "Rand std": rtest["random_std"].map(lambda v: f"{v*1e4:.1f} bp"),
    "Rand 5-95%": [f"{a:.3%} .. {b:.3%}" for a, b in zip(rtest.random_p5, rtest.random_p95)],
    "Weekday range": [f"{a:.3%} .. {b:.3%}" for a, b in
                      zip(rtest.weekday_worst, rtest.weekday_best)],
    "Wkday spread": rtest["weekday_spread_pp"].map("{:.3f} pp".format),
    "Random 5-pick spread (median / p95)": [f"{a:.3f} / {b:.3f} pp" for a, b in zip(
        rtest.random_5pick_spread_median_pp, rtest.random_5pick_spread_p95_pp)],
    "p": rtest["p_value_spread"].map("{:.2f}".format),
})
print(rshow.to_string())
print("p = share of random 5-schedule groups whose best-minus-worst XIRR spread is "
      ">= the weekday spread.")

# ----------------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------------
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a8985"
GRID = "#e6e5e1"
LINE = "#2a78d6"
DAY_COLORS = dict(zip(DAYS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
})
money = mtick.FuncFormatter(lambda v, _: f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:.0f}k")

# 1. Portfolio value over time, small multiples (shared y-axis)
fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), sharex=True, sharey=True)
for ax, m in zip(axes.flat, MIXES):
    V, inv = series[m]
    live = inv > 0
    ax.plot(cal[live], V[live], color=LINE, lw=1.8, label="Portfolio value")
    ax.plot(cal[live], inv[live], color=INK2, lw=1.4, ls=(0, (4, 3)), label="Total invested")
    ax.set_title(m, pad=18)
    ax.text(0, 1.02, " / ".join(f"{t} {w:.0%}" for t, w in MIXES[m].items()),
            transform=ax.transAxes, fontsize=8.5, color=INK2)
    s = mon.loc[m]
    ax.text(0.03, 0.93, f"Final \\${s.final_value/1e6:.2f}M  ·  XIRR {s.xirr:.1%}\n"
            f"Max drawdown {s.max_drawdown:.1%}",
            transform=ax.transAxes, va="top", fontsize=9.5, color=INK)
    ax.yaxis.set_major_formatter(money)
    ax.grid(axis="x", visible=False)
h, l = axes.flat[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper right", ncol=2, frameon=False, fontsize=10)
fig.suptitle(f"Weekly \\${WEEKLY:,.0f} DCA, Monday buys, {cal[0].date()} to {END.date()}  "
             f"(invested \\${mon.total_invested.iloc[0]:,.0f} per mix)",
             x=0.01, ha="left", fontsize=13, fontweight="bold")
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(f"{OUT}/chart1_portfolio_value.png", dpi=180)
plt.close(fig)

# 2. XIRR by weekday per mix: absolute (top) and vs random-day mean (bottom)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9), height_ratios=[1.1, 1])
ax1.set_axisbelow(True)
ax2.set_axisbelow(True)
x = np.arange(len(MIXES))
bw = 0.16
for j, d in enumerate(DAYS):
    xs = x + (j - 2) * bw
    ax1.bar(xs, wk[d] * 100, bw, color=DAY_COLORS[d], label=d,
            edgecolor=SURFACE, linewidth=1.2)
    ax2.bar(xs, (wk[d] - rtest["random_mean"]) * 1e4, bw, color=DAY_COLORS[d],
            edgecolor=SURFACE, linewidth=1.2)
for i, m in enumerate(MIXES):
    ax1.text(i, wk.loc[m, DAYS].max() * 100 + 0.25, f"{wk.loc[m, DAYS].mean():.2%}",
             ha="center", fontsize=9, color=INK2)
    lo = (rtest.loc[m, "random_p5"] - rtest.loc[m, "random_mean"]) * 1e4
    hi = (rtest.loc[m, "random_p95"] - rtest.loc[m, "random_mean"]) * 1e4
    ax2.add_patch(plt.Rectangle((i - 2.5 * bw - 0.03, lo), 5 * bw + 0.06, hi - lo,
                                color=MUTED, alpha=0.22, lw=0, zorder=0))
ax1.set_xticks(x, [m for m in MIXES])
ax1.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}%"))
ax1.set_ylabel("XIRR (money-weighted, % / yr)")
ax1.set_title("XIRR by buy weekday (label = mean of the 5 days)")
ax1.grid(axis="x", visible=False)
ax1.legend(ncol=5, frameon=False, loc="upper left", bbox_to_anchor=(0, 1.0), fontsize=9)
ax1.set_ylim(0, wk[DAYS].values.max() * 100 * 1.15)
ax2.axhline(0, color=INK2, lw=1)
ax2.set_xticks(x, [m for m in MIXES])
ax2.set_ylabel("XIRR minus random-day mean (bp / yr)")
ax2.set_title(f"Same, relative to {N_RANDOM} random-weekday runs "
              f"(grey band = 5th–95th percentile of random runs)")
ax2.grid(axis="x", visible=False)
fig.tight_layout()
fig.savefig(f"{OUT}/chart2_xirr_by_weekday.png", dpi=180)
plt.close(fig)

# ----------------------------------------------------------------------------
# Summary
# ----------------------------------------------------------------------------
best_ratio = mon["xirr_per_unit_dd"].idxmax()
print("\n" + "=" * 78)
print("SUMMARY")
print("=" * 78)
rank = mon.sort_values("xirr_per_unit_dd", ascending=False)
for m, s in rank.iterrows():
    print(f"  {m:9s} XIRR {s.xirr:6.2%}  max DD {s.max_drawdown:6.1%}  "
          f"-> {s.xirr_per_unit_dd:.3f} XIRR per unit of DD")
print(f"Best return per unit of drawdown: {best_ratio}")
max_spread = wk["spread_pp_per_year"].max()
print(f"Largest weekday spread: {max_spread:.3f} pp/yr "
      f"(${wk['spread_final_$'].max():,.0f} on ~${mon.total_invested.iloc[0]:,.0f} invested); "
      f"min p-value vs random days {rtest.p_value_spread.min():.2f}")
print(f"\nCSV and PNG files written to ./{OUT}/")
