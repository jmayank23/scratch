#!/usr/bin/env python3
"""
Correction / drawdown analysis + strategy backtests for the reports directory.

Data: real daily adjusted-close from Yahoo Finance chart API (v8), full available
history per ticker, fetched through the agent proxy (REQUESTS_CA_BUNDLE).

Two research questions:
  A) Is the *time between corrections* (inter-correction interval) predictable?
  B) Is the *depth of the drop* predictable from info known at/near the peak?

Plus three rules-based strategies backtested vs buy & hold:
  1. Buy & Hold (benchmark)
  2. SMA-200 trend filter (invested only when price > 200d SMA)
  3. Trailing stop 15% + re-enter above 50d SMA ("sell the correction")

All signals use only lagged data (no look-ahead). No transaction costs/taxes
(sensitivity noted separately). This is exploratory, in-sample, single-path
analysis on a hand-picked set of mostly-large-winners (MRNA is the one decliner)
-> read the caveats.
"""
import os, json, math, datetime as dt
import numpy as np
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = "/home/user/scratch/reports/backtests"
DATA, CHARTS = f"{BASE}/data", f"{BASE}/charts"
H = {"User-Agent": "Mozilla/5.0"}
TICKERS = ["GOOG","AAPL","NVDA","MSFT","TSM","ASML","MRVL","AMD","JPM","AXP","AVGO","MRNA","MA"]
TRADING_DAYS = 252

P1 = int(dt.datetime(2006, 1, 1, tzinfo=dt.timezone.utc).timestamp())
P2 = int(dt.datetime(2026, 8, 31, tzinfo=dt.timezone.utc).timestamp())
def fetch(sym):
    # period1/period2 forces TRUE DAILY bars; range=max silently downsamples to monthly/quarterly.
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
                     params={"period1":P1,"period2":P2,"interval":"1d"}, headers=H, timeout=45)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    ts = res["timestamp"]; ind = res["indicators"]
    adj = ind.get("adjclose",[{}])[0].get("adjclose") if ind.get("adjclose") else None
    close = adj or ind["quote"][0]["close"]
    dates, px = [], []
    for t,c in zip(ts, close):
        if c is not None and c > 0:
            dates.append(dt.date.fromtimestamp(t)); px.append(float(c))
    return np.array(dates), np.array(px)

def sma(px, n):
    out = np.full(len(px), np.nan)
    if len(px) >= n:
        c = np.cumsum(np.insert(px, 0, 0.0))
        out[n-1:] = (c[n:] - c[:-n]) / n
    return out

def corrections(dates, px, theta):
    """Peak->trough drawdown episodes with depth >= theta. Returns list of dicts."""
    eps = []
    peak = px[0]; peak_i = 0; trough = px[0]; trough_i = 0; in_dd = False
    for i in range(1, len(px)):
        if px[i] >= peak:
            if in_dd:
                mag = 1 - trough/peak
                if mag >= theta:
                    eps.append(dict(peak_i=peak_i, trough_i=trough_i, peak=peak,
                                    trough=trough, depth=mag, recover_i=i, ongoing=False))
                in_dd = False
            peak = px[i]; peak_i = i; trough = px[i]; trough_i = i
        else:
            in_dd = True
            if px[i] < trough:
                trough = px[i]; trough_i = i
    if in_dd:
        mag = 1 - trough/peak
        if mag >= theta:
            eps.append(dict(peak_i=peak_i, trough_i=trough_i, peak=peak,
                            trough=trough, depth=mag, recover_i=None, ongoing=True))
    return eps

def pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y); x, y = x[m], y[m]
    n = len(x)
    if n < 3 or x.std() == 0 or y.std() == 0:
        return float("nan"), n, float("nan")
    r = np.corrcoef(x, y)[0,1]
    t = r*math.sqrt((n-2)/max(1e-12, 1-r*r))
    return r, n, t

def lstsq_r2(X, y):
    """Multiple regression R^2 with intercept. X is a list of predictor arrays."""
    cols = [np.asarray(c, float) for c in X]
    Xm = np.column_stack([np.ones(len(cols[0]))] + cols)
    y = np.asarray(y, float)
    m = np.all(np.isfinite(Xm),axis=1) & np.isfinite(y); Xm, yy = Xm[m], y[m]
    if len(yy) < Xm.shape[1] + 2: return float("nan"), len(yy)
    beta,_,_,_ = np.linalg.lstsq(Xm, yy, rcond=None)
    yhat = Xm @ beta
    ss_res = np.sum((yy-yhat)**2); ss_tot = np.sum((yy-yy.mean())**2)
    return (1 - ss_res/ss_tot if ss_tot>0 else float("nan")), len(yy)

def maxdd(equity):
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity/peak - 1))

def perf(daily_ret, position):
    daily_ret = np.asarray(daily_ret, float)
    strat = position * daily_ret
    eq = np.cumprod(1 + strat)
    n = len(strat)
    cagr = eq[-1]**(TRADING_DAYS/n) - 1 if n>0 and eq[-1]>0 else float("nan")
    vol = strat.std()*math.sqrt(TRADING_DAYS)
    sharpe = (strat.mean()/strat.std()*math.sqrt(TRADING_DAYS)) if strat.std()>0 else float("nan")
    entries = int(np.sum((position[1:]==1) & (position[:-1]==0)))
    return dict(cagr=cagr, vol=vol, sharpe=sharpe, maxdd=maxdd(eq),
                pct_invested=float(position.mean()), trades=entries, equity=eq)

# ---------------- run ----------------
os.makedirs(DATA, exist_ok=True); os.makedirs(CHARTS, exist_ok=True)
series = {}
for tk in TICKERS:
    d, p = fetch(tk); series[tk] = (d, p)
    print(f"[fetch] {tk}: {len(p)} days, {d[0]} -> {d[-1]}")

# ---- corrections tables + per-ticker stats ----
pool10 = []  # pooled correction records (10% threshold) with predictors
per_ticker = {}
rows10, rows20 = [], []
for tk in TICKERS:
    d, p = series[tk]
    s200 = sma(p, 200); s50 = sma(p, 50)
    ret = np.concatenate([[0.0], p[1:]/p[:-1]-1])
    for theta, rows in [(0.10, rows10), (0.20, rows20)]:
        eps = corrections(d, p, theta)
        # peak-to-peak intervals
        peak_days = [e["peak_i"] for e in eps]
        for k,e in enumerate(eps):
            pi, ti = e["peak_i"], e["trough_i"]
            dur = ti - pi
            recov = (e["recover_i"]-ti) if e["recover_i"] is not None else None
            prev_trough_i = eps[k-1]["trough_i"] if k>0 else 0
            runup = p[pi]/p[prev_trough_i]-1 if prev_trough_i < pi else float("nan")
            since_last_peak = (pi - eps[k-1]["peak_i"]) if k>0 else None
            vol60 = ret[max(0,pi-60):pi].std()*math.sqrt(TRADING_DAYS) if pi>60 else float("nan")
            ext = (p[pi]/s200[pi]-1) if pi<len(s200) and np.isfinite(s200[pi]) else float("nan")
            rec = dict(ticker=tk, thr=int(theta*100), peak_date=str(d[pi]), trough_date=str(d[ti]),
                       depth_pct=round(e["depth"]*100,2), peak_to_trough_days=int(dur),
                       recovery_days=(int(recov) if recov is not None else ""),
                       runup_pct=(round(runup*100,2) if np.isfinite(runup) else ""),
                       days_since_last_peak=(int(since_last_peak) if since_last_peak is not None else ""),
                       vol60_ann=(round(vol60*100,1) if np.isfinite(vol60) else ""),
                       pct_above_sma200=(round(ext*100,1) if np.isfinite(ext) else ""),
                       ongoing=e["ongoing"])
            rows.append(rec)
            if theta==0.10:
                pool10.append(dict(depth=e["depth"], dur=dur, runup=runup,
                                   since=since_last_peak, vol60=vol60, ext=ext,
                                   peak_i=pi))
        if theta==0.10:
            depths = np.array([e["depth"] for e in eps])
            intervals = np.diff(peak_days) if len(peak_days)>1 else np.array([])
            # lag-1 autocorr of intervals and depths
            def ac1(a):
                a=np.asarray(a,float)
                return float(np.corrcoef(a[:-1],a[1:])[0,1]) if len(a)>2 else float("nan")
            per_ticker[tk] = dict(
                start=str(d[0]), n_corr=len(eps),
                mean_depth=round(depths.mean()*100,1) if len(depths) else float("nan"),
                median_depth=round(float(np.median(depths))*100,1) if len(depths) else float("nan"),
                max_depth=round(depths.max()*100,1) if len(depths) else float("nan"),
                mean_interval_d=round(float(intervals.mean()),0) if len(intervals) else float("nan"),
                median_interval_d=round(float(np.median(intervals)),0) if len(intervals) else float("nan"),
                interval_cv=round(float(intervals.std()/intervals.mean()),2) if len(intervals) and intervals.mean()>0 else float("nan"),
                ac1_interval=round(ac1(intervals),2) if len(intervals)>2 else float("nan"),
                ac1_depth=round(ac1(depths),2) if len(depths)>2 else float("nan"),
            )

# write CSVs
def write_csv(path, rows):
    if not rows: return
    keys = list(rows[0].keys())
    with open(path,"w") as f:
        f.write(",".join(keys)+"\n")
        for r in rows:
            f.write(",".join(str(r[k]) for k in keys)+"\n")
write_csv(f"{DATA}/corrections_10pct.csv", rows10)
write_csv(f"{DATA}/corrections_20pct.csv", rows20)

# ---- predictability (pooled, 10% corrections) ----
depth = np.array([r["depth"] for r in pool10])
runup = np.array([r["runup"] if r["runup"] is not None else np.nan for r in pool10])
ext   = np.array([r["ext"] for r in pool10])
vol60 = np.array([r["vol60"] for r in pool10])
since = np.array([r["since"] if r["since"] is not None else np.nan for r in pool10])
dur   = np.array([r["dur"] for r in pool10])

pred = {}
pred["n_pooled_10pct"] = int(len(depth))
for name, x in [("runup_vs_depth",runup),("ext_above_sma200_vs_depth",ext),
                ("vol60_vs_depth",vol60),("since_last_vs_depth",since)]:
    r,n,t = pearson(x, depth); pred[name] = dict(r=round(r,3), n=n, t=round(t,2))
r2,ndep = lstsq_r2([runup, ext, vol60, since], depth)
pred["multi_reg_depth_R2"] = dict(R2=round(r2,3), n=ndep)
# does run-up predict how long until the NEXT peak? (interval predictability, pooled)
# build per-ticker interval series with predictors
iv_prev_runup, iv_prev_depth, iv_len, iv_prevlen_a, iv_prevlen_b = [], [], [], [], []
for tk in TICKERS:
    d,p = series[tk]
    eps = corrections(d,p,0.10)
    peaks=[e["peak_i"] for e in eps]; depths=[e["depth"] for e in eps]
    prev_tr=[0]+[e["trough_i"] for e in eps[:-1]]
    runups=[p[eps[k]["peak_i"]]/p[prev_tr[k]]-1 if prev_tr[k]<eps[k]["peak_i"] else np.nan for k in range(len(eps))]
    intervals=np.diff(peaks)
    for k in range(len(intervals)):
        iv_len.append(intervals[k]); iv_prev_runup.append(runups[k]); iv_prev_depth.append(depths[k])
    if len(intervals)>1:
        iv_prevlen_a.extend(intervals[:-1]); iv_prevlen_b.extend(intervals[1:])
r,n,t = pearson(iv_prev_runup, iv_len); pred["prev_runup_vs_interval"]=dict(r=round(r,3),n=n,t=round(t,2))
r,n,t = pearson(iv_prev_depth, iv_len); pred["prev_depth_vs_interval"]=dict(r=round(r,3),n=n,t=round(t,2))
r,n,t = pearson(iv_prevlen_a, iv_prevlen_b); pred["interval_lag1_autocorr_pooled"]=dict(r=round(r,3),n=n,t=round(t,2))
r,n,t = pearson(runup, dur); pred["runup_vs_duration"]=dict(r=round(r,3),n=n,t=round(t,2))

json.dump(dict(per_ticker=per_ticker, predictability=pred), open(f"{DATA}/predictability.json","w"), indent=2)

# ---- strategy backtests ----
strat_rows = []
equity_store = {}
for tk in TICKERS:
    d,p = series[tk]
    ret = np.concatenate([[0.0], p[1:]/p[:-1]-1])
    s200 = sma(p,200); s50 = sma(p,50)
    n=len(p)
    # position arrays (decision uses yesterday's data -> shift)
    bh = np.ones(n)
    # SMA200 trend
    trend = np.zeros(n)
    for i in range(1,n):
        if np.isfinite(s200[i-1]):
            trend[i] = 1.0 if p[i-1] > s200[i-1] else 0.0
        else:
            trend[i] = 1.0  # before SMA available, be invested (benchmark-fair)
    # trailing stop 15% + re-enter above SMA50
    ts = np.zeros(n); invested=True; inpeak=p[0]
    for i in range(1,n):
        if invested:
            inpeak=max(inpeak,p[i-1])
            if p[i-1] <= inpeak*0.85:  # breached trailing stop as of yesterday
                invested=False
        else:
            if np.isfinite(s50[i-1]) and p[i-1] > s50[i-1]:
                invested=True; inpeak=p[i-1]
        ts[i]=1.0 if invested else 0.0
    for name,pos in [("BuyHold",bh),("SMA200",trend),("TrailStop15",ts)]:
        m=perf(ret,pos)
        equity_store[(tk,name)]=(d,m["equity"])
        strat_rows.append(dict(ticker=tk, strategy=name,
            CAGR_pct=round(m["cagr"]*100,1), Vol_pct=round(m["vol"]*100,1),
            Sharpe=round(m["sharpe"],2), MaxDD_pct=round(m["maxdd"]*100,1),
            PctInvested=round(m["pct_invested"]*100,0), Trades=m["trades"]))
write_csv(f"{DATA}/strategy_metrics.csv", strat_rows)

# aggregate averages by strategy
agg={}
for name in ["BuyHold","SMA200","TrailStop15"]:
    sub=[r for r in strat_rows if r["strategy"]==name]
    agg[name]=dict(
        avg_CAGR=round(np.mean([r["CAGR_pct"] for r in sub]),1),
        avg_MaxDD=round(np.mean([r["MaxDD_pct"] for r in sub]),1),
        avg_Sharpe=round(np.mean([r["Sharpe"] for r in sub]),2),
        avg_Vol=round(np.mean([r["Vol_pct"] for r in sub]),1),
        median_CAGR=round(float(np.median([r["CAGR_pct"] for r in sub])),1),
        beats_bh_cagr=None)
# how often each strategy beats B&H on CAGR / on MaxDD
bh_by_tk={r["ticker"]:r for r in strat_rows if r["strategy"]=="BuyHold"}
for name in ["SMA200","TrailStop15"]:
    sub=[r for r in strat_rows if r["strategy"]==name]
    agg[name]["beats_bh_cagr"]=f"{sum(1 for r in sub if r['CAGR_pct']>bh_by_tk[r['ticker']]['CAGR_pct'])}/{len(sub)}"
    agg[name]["better_maxdd"]=f"{sum(1 for r in sub if r['MaxDD_pct']>bh_by_tk[r['ticker']]['MaxDD_pct'])}/{len(sub)}"
json.dump(agg, open(f"{DATA}/strategy_aggregate.json","w"), indent=2)

# ---------------- charts ----------------
ACCENT="#2b6cb0"; INK="#1a202c"; MUTED="#6b7280"; GRID="#e5e7eb"
C2="#d97706"; C3="#059669"
# 1) scatter run-up vs depth
fig,ax=plt.subplots(figsize=(7.2,4.6),dpi=150)
m=np.isfinite(runup)&np.isfinite(depth)
ax.scatter(runup[m]*100, depth[m]*100, s=26, color=ACCENT, alpha=0.6, edgecolor="white", linewidth=0.5)
r,_,_=pearson(runup,depth)
# best fit
b=np.polyfit((runup[m]*100),(depth[m]*100),1); xs=np.linspace((runup[m]*100).min(),(runup[m]*100).max(),50)
ax.plot(xs, np.polyval(b,xs), color=INK, lw=1.5, ls="--")
ax.set_xlabel("Run-up into the peak (%)",color=MUTED); ax.set_ylabel("Subsequent drawdown depth (%)",color=MUTED)
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color(GRID)
ax.grid(color=GRID,lw=0.7); ax.set_axisbelow(True); ax.tick_params(colors=MUTED,length=0)
ax.set_title(f"Does a bigger run-up predict a deeper drop?  r = {r:.2f}  (n={int(m.sum())})",
             loc="left",fontsize=12,fontweight="bold",color=INK,pad=12)
fig.text(0.005,0.005,"Pooled 10%+ corrections across 10 tickers, full history · Yahoo Finance",fontsize=7.5,color=MUTED)
fig.tight_layout(); fig.savefig(f"{CHARTS}/predictor_runup_vs_depth.png",facecolor="white",bbox_inches="tight"); plt.close(fig)

# 2) scatter extension above 200d SMA vs depth
fig,ax=plt.subplots(figsize=(7.2,4.6),dpi=150)
m=np.isfinite(ext)&np.isfinite(depth)
ax.scatter(ext[m]*100, depth[m]*100, s=26, color=C2, alpha=0.6, edgecolor="white", linewidth=0.5)
r,_,_=pearson(ext,depth)
b=np.polyfit((ext[m]*100),(depth[m]*100),1); xs=np.linspace((ext[m]*100).min(),(ext[m]*100).max(),50)
ax.plot(xs,np.polyval(b,xs),color=INK,lw=1.5,ls="--")
ax.set_xlabel("Price extension above 200-day SMA at peak (%)",color=MUTED); ax.set_ylabel("Subsequent drawdown depth (%)",color=MUTED)
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color(GRID)
ax.grid(color=GRID,lw=0.7); ax.set_axisbelow(True); ax.tick_params(colors=MUTED,length=0)
ax.set_title(f"Does 'stretched above trend' predict a deeper drop?  r = {r:.2f}  (n={int(m.sum())})",
             loc="left",fontsize=12,fontweight="bold",color=INK,pad=12)
fig.text(0.005,0.005,"Pooled 10%+ corrections across 10 tickers, full history · Yahoo Finance",fontsize=7.5,color=MUTED)
fig.tight_layout(); fig.savefig(f"{CHARTS}/predictor_extension_vs_depth.png",facecolor="white",bbox_inches="tight"); plt.close(fig)

# 3) avg max drawdown by strategy (bar)
fig,ax=plt.subplots(figsize=(7.2,4.2),dpi=150)
names=["BuyHold","SMA200","TrailStop15"]; cols=[ACCENT,C3,C2]
vals=[agg[n]["avg_MaxDD"] for n in names]; cagrs=[agg[n]["avg_CAGR"] for n in names]
bars=ax.bar(names, vals, color=cols, width=0.6)
for b,v,c in zip(bars,vals,cagrs):
    ax.text(b.get_x()+b.get_width()/2, v-1.5, f"{v:.0f}%", ha="center", va="top", color="white", fontweight="bold")
    ax.text(b.get_x()+b.get_width()/2, 1.0, f"CAGR {c:.0f}%", ha="center", va="bottom", color=INK, fontsize=9)
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color(GRID)
ax.axhline(0,color=GRID); ax.grid(axis="y",color=GRID,lw=0.7); ax.set_axisbelow(True); ax.tick_params(colors=MUTED,length=0)
ax.set_ylabel("Avg worst drawdown (%)",color=MUTED)
ax.set_title("Avg max drawdown vs avg CAGR by strategy (mean of 10 tickers)",loc="left",fontsize=12,fontweight="bold",color=INK,pad=12)
fig.text(0.005,0.005,"Full history per ticker · no costs/taxes · Yahoo Finance",fontsize=7.5,color=MUTED)
fig.tight_layout(); fig.savefig(f"{CHARTS}/strategy_maxdd_bar.png",facecolor="white",bbox_inches="tight"); plt.close(fig)

# 4) equity curves for NVDA and MSFT (log)
for tk in ["NVDA","MSFT"]:
    fig,ax=plt.subplots(figsize=(8.4,4.4),dpi=150)
    for name,c in [("BuyHold",ACCENT),("SMA200",C3),("TrailStop15",C2)]:
        d,eq=equity_store[(tk,name)]; ax.plot(d,eq,color=c,lw=1.6,label=name)
    ax.set_yscale("log")
    for s in ("top","right"): ax.spines[s].set_visible(False)
    for s in ("left","bottom"): ax.spines[s].set_color(GRID)
    ax.grid(color=GRID,lw=0.7,which="both"); ax.set_axisbelow(True); ax.tick_params(colors=MUTED,length=0)
    ax.set_ylabel("Growth of $1 (log)",color=MUTED)
    ax.legend(frameon=False,fontsize=9,loc="upper left")
    ax.set_title(f"{tk}: strategy equity curves (log scale)",loc="left",fontsize=12,fontweight="bold",color=INK,pad=12)
    fig.text(0.005,0.005,"Full history · no costs/taxes · Yahoo Finance",fontsize=7.5,color=MUTED)
    fig.tight_layout(); fig.savefig(f"{CHARTS}/equity_{tk}.png",facecolor="white",bbox_inches="tight"); plt.close(fig)

# ---------------- print summary ----------------
print("\n===== PER-TICKER (10% corrections) =====")
hdr=["tk","start","n","medDepth%","maxDepth%","medIntv_d","intv_CV","ac1_intv","ac1_depth"]
print("\t".join(hdr))
for tk in TICKERS:
    s=per_ticker[tk]
    print(f"{tk}\t{s['start']}\t{s['n_corr']}\t{s['median_depth']}\t{s['max_depth']}\t{s['median_interval_d']}\t{s['interval_cv']}\t{s['ac1_interval']}\t{s['ac1_depth']}")

print("\n===== PREDICTABILITY (pooled) =====")
print(json.dumps(pred, indent=2))

print("\n===== STRATEGY METRICS (per ticker) =====")
print("tk\tstrat\tCAGR%\tMaxDD%\tSharpe\t%inv\ttrades")
for r in strat_rows:
    print(f"{r['ticker']}\t{r['strategy']}\t{r['CAGR_pct']}\t{r['MaxDD_pct']}\t{r['Sharpe']}\t{r['PctInvested']}\t{r['Trades']}")

print("\n===== STRATEGY AGGREGATE =====")
print(json.dumps(agg, indent=2))
print("\nDONE")
