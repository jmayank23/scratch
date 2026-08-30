#!/usr/bin/env python3
"""
Run RSI(14), Money Flow Index(14) divergence, Ichimoku, and DeMark TD Sequential
for all charted tickers, and BACKTEST each as a signal to see where it has edge.

Data: daily OHLCV (raw) from Yahoo Finance v8 chart API via the agent proxy,
2006-01 to 2026-08 (~20y; AVGO from its 2009 IPO). RVII excluded (no history).
MRNA history begins at its Dec-2018 IPO and is the set's one big decliner.

Two kinds of test:
  * Event study (RSI oversold/overbought, MFI bull/bear divergence, TD buy-9/sell-9):
    forward 10- and 20-day returns after each first-trigger event vs the stock's
    unconditional baseline. Edge = conditional mean - baseline; t-stat on the event
    sample. Bullish signals want edge>0; bearish signals want edge<0.
  * Trend system (Ichimoku): long only while close is above the cloud (no look-ahead),
    else cash(0%); compare CAGR / max drawdown / Sharpe vs buy & hold.

Exploratory, in-sample, single-path, no costs/taxes; raw close (small dividend
distortion). NOT investment advice.
"""
import os, json, math, datetime as dt
import numpy as np, requests
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE="/home/user/scratch/reports/indicators"; DATA=f"{BASE}/data"; CH=f"{BASE}/charts"
os.makedirs(DATA,exist_ok=True); os.makedirs(CH,exist_ok=True)
H={"User-Agent":"Mozilla/5.0"}
TK=[("GOOG","Alphabet"),("AAPL","Apple"),("NVDA","NVIDIA"),("MSFT","Microsoft"),
    ("TSM","TSMC"),("ASML","ASML"),("MRVL","Marvell"),("AMD","AMD"),
    ("JPM","JPMorgan"),("AXP","Amex"),("AVGO","Broadcom"),("MRNA","Moderna"),("MA","Mastercard")]
P1=int(dt.datetime(2006,1,1,tzinfo=dt.timezone.utc).timestamp())
P2=int(dt.datetime(2026,8,31,tzinfo=dt.timezone.utc).timestamp())
TD_=252

def fetch(sym):
    r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}",
        params={"period1":P1,"period2":P2,"interval":"1d"},headers=H,timeout=45); r.raise_for_status()
    res=r.json()["chart"]["result"][0]; ts=res["timestamp"]; q=res["indicators"]["quote"][0]
    o,h,l,c,v=q["open"],q["high"],q["low"],q["close"],q["volume"]
    D=[];O=[];Hi=[];Lo=[];C=[];V=[]
    for i,t in enumerate(ts):
        if None in (h[i],l[i],c[i],v[i]) or c[i] is None: continue
        D.append(dt.date.fromtimestamp(t));O.append(o[i] or c[i]);Hi.append(h[i]);Lo.append(l[i]);C.append(c[i]);V.append(v[i] or 0)
    return np.array(D),np.array(O),np.array(Hi),np.array(Lo),np.array(C),np.array(V)

def rsi(c,p=14):
    d=np.diff(c); g=np.where(d>0,d,0.0); ls=np.where(d<0,-d,0.0)
    ag=np.full(len(c),np.nan); al=np.full(len(c),np.nan); ag[p]=g[:p].mean(); al[p]=ls[:p].mean()
    for i in range(p+1,len(c)):
        ag[i]=(ag[i-1]*(p-1)+g[i-1])/p; al[i]=(al[i-1]*(p-1)+ls[i-1])/p
    rs=ag/np.where(al==0,np.nan,al); out=100-100/(1+rs); out[al==0]=100; return out

def mfi(h,l,c,v,p=14):
    tp=(h+l+c)/3.0; rmf=tp*v; out=np.full(len(c),np.nan)
    up=np.zeros(len(c)); dn=np.zeros(len(c))
    for i in range(1,len(c)):
        if tp[i]>tp[i-1]: up[i]=rmf[i]
        elif tp[i]<tp[i-1]: dn[i]=rmf[i]
    for i in range(p,len(c)):
        pos=up[i-p+1:i+1].sum(); neg=dn[i-p+1:i+1].sum()
        out[i]=100.0 if neg==0 else 100-100/(1+pos/neg)
    return out

def donch_mid(h,l,p):
    out=np.full(len(h),np.nan)
    for i in range(p-1,len(h)): out[i]=(h[i-p+1:i+1].max()+l[i-p+1:i+1].min())/2
    return out

def swings(x,w=5):
    hi=[];lo=[]
    for i in range(w,len(x)-w):
        seg=x[i-w:i+w+1]
        if x[i]==seg.max() and np.argmax(seg)==w: hi.append(i)
        if x[i]==seg.min() and np.argmin(seg)==w: lo.append(i)
    return hi,lo

def first_triggers(cond):
    ev=[]
    for i in range(1,len(cond)):
        if cond[i] and not cond[i-1]: ev.append(i)
    return ev

def fwd(c,idxs,Hh):
    out=[]
    for e in idxs:
        if e+Hh < len(c): out.append(c[e+Hh]/c[e]-1)
    return np.array(out)

def baseline(c,Hh):
    r=c[Hh:]/c[:-Hh]-1; return r

def stat(evr, base):
    if len(evr)==0: return dict(n=0)
    edge=evr.mean()-base.mean()
    t=evr.mean()/(evr.std(ddof=1)/math.sqrt(len(evr))) if len(evr)>1 and evr.std()>0 else float("nan")
    te=edge/(evr.std(ddof=1)/math.sqrt(len(evr))) if len(evr)>1 and evr.std()>0 else float("nan")
    return dict(n=len(evr), mean=round(evr.mean()*100,2), base=round(base.mean()*100,2),
                edge=round(edge*100,2), hit=round(float((evr>0).mean())*100,0), t_edge=round(te,2))

def maxdd(eq): peak=np.maximum.accumulate(eq); return float(np.min(eq/peak-1))
def perf(ret,pos):
    strat=pos*ret; eq=np.cumprod(1+strat); n=len(strat)
    cagr=eq[-1]**(TD_/n)-1 if eq[-1]>0 else float("nan")
    sh=strat.mean()/strat.std()*math.sqrt(TD_) if strat.std()>0 else float("nan")
    return dict(cagr=cagr,maxdd=maxdd(eq),sharpe=sh,pct=float(pos.mean()),eq=eq)

def panel(sym,name,D,C,RSI,MFI,tenkan,kijun,spanA,spanB,sell,buy):
    n=len(C); INK="#1a202c";MUTED="#6b7280";GRID="#e5e7eb"
    BLUE="#2b6cb0";GREEN="#059669";RED="#b91c1c";ORANGE="#d97706";PURPLE="#6d28d9"
    shift=26; xf=np.arange(n+shift); dispA=np.full(n+shift,np.nan);dispB=np.full(n+shift,np.nan)
    dispA[shift:]=spanA; dispB[shift:]=spanB; x=np.arange(n); lo=max(0,n-160); hi=n+shift
    fig,ax=plt.subplots(3,1,figsize=(11,8.6),dpi=140,sharex=True,gridspec_kw={"height_ratios":[3,1,1],"hspace":0.08})
    a=ax[0]
    a.fill_between(xf,dispA,dispB,where=dispA>=dispB,color=GREEN,alpha=0.15,linewidth=0)
    a.fill_between(xf,dispA,dispB,where=dispA<dispB,color=RED,alpha=0.15,linewidth=0)
    a.plot(xf,dispA,color=GREEN,lw=0.7,alpha=0.7); a.plot(xf,dispB,color=RED,lw=0.7,alpha=0.7)
    a.plot(x,C,color=INK,lw=1.6,label="Close"); a.plot(x,tenkan,color=BLUE,lw=1.0,label="Tenkan")
    a.plot(x,kijun,color=ORANGE,lw=1.0,label="Kijun"); a.axvline(n-1,color=MUTED,ls=":",lw=0.8)
    for i in range(lo,n):
        if sell[i]==9: a.annotate("9",(i,C[i]),xytext=(0,9),textcoords="offset points",ha="center",color=RED,fontweight="bold",fontsize=10)
        if buy[i]==9:  a.annotate("9",(i,C[i]),xytext=(0,-15),textcoords="offset points",ha="center",color=GREEN,fontweight="bold",fontsize=10)
    a.set_title(f"{sym} ({name}) — Ichimoku + TD Sequential 9",loc="left",fontsize=12,fontweight="bold",color=INK,pad=8)
    a.legend(frameon=False,fontsize=8,loc="upper left",ncol=3); a.set_ylabel("Price ($)",color=MUTED)
    # rescale price axis to the VISIBLE window (full series is plotted but x is zoomed)
    visv=np.concatenate([C[lo:n],dispA[lo:hi],dispB[lo:hi],tenkan[lo:n],kijun[lo:n]])
    visv=visv[np.isfinite(visv)]
    if len(visv):
        padv=(visv.max()-visv.min())*0.08 or 1.0
        a.set_ylim(visv.min()-padv, visv.max()+padv)
    a2=ax[1]; a2.plot(x,RSI,color=PURPLE,lw=1.2); a2.axhline(70,color=RED,lw=0.8,ls="--");a2.axhline(30,color=GREEN,lw=0.8,ls="--");a2.axhline(50,color=GRID,lw=0.8)
    a2.set_ylim(0,100); a2.set_ylabel("RSI",color=MUTED); a2.set_yticks([30,50,70])
    a3=ax[2]; a3.plot(x,MFI,color=BLUE,lw=1.2); a3.axhline(80,color=RED,lw=0.8,ls="--");a3.axhline(20,color=GREEN,lw=0.8,ls="--")
    a3.set_ylim(0,100); a3.set_ylabel("MFI",color=MUTED); a3.set_yticks([20,50,80])
    ticks=list(range(lo,hi,21))
    for aa in ax:
        aa.set_xlim(lo,hi)
        for s in ("top","right"): aa.spines[s].set_visible(False)
        for s in ("left","bottom"): aa.spines[s].set_color(GRID)
        aa.grid(axis="y",color=GRID,lw=0.6); aa.set_axisbelow(True); aa.tick_params(colors=MUTED,length=0,labelsize=8)
    ax[-1].set_xticks(ticks); ax[-1].set_xticklabels([D[t].strftime("%b'%y") if t<n else "+" for t in ticks])
    fig.text(0.005,0.005,"Source: Yahoo Finance daily OHLCV · dotted line = latest session · cloud +26",fontsize=7,color=MUTED)
    fig.tight_layout(rect=(0,0.02,1,1)); fig.savefig(f"{CH}/{sym}-indicators.png",facecolor="white",bbox_inches="tight"); plt.close(fig)

# ---- run ----
snap=[]; ev_rows=[]; ich_rows=[]
pool={k:{"ev":[],"base":[]} for k in ["RSI_oversold","RSI_overbought","MFI_bulldiv","MFI_beardiv","TD_buy9","TD_sell9"]}
SIGDIR={"RSI_oversold":+1,"RSI_overbought":-1,"MFI_bulldiv":+1,"MFI_beardiv":-1,"TD_buy9":+1,"TD_sell9":-1}
for sym,name in TK:
    D,O,Hi,Lo,C,V=fetch(sym); n=len(C)
    RSI=rsi(C); MFI=mfi(Hi,Lo,C,V)
    tenkan=donch_mid(Hi,Lo,9); kijun=donch_mid(Hi,Lo,26); spanA=(tenkan+kijun)/2; spanB=donch_mid(Hi,Lo,52)
    sell=np.zeros(n,int); buy=np.zeros(n,int)
    for i in range(4,n):
        sell[i]=sell[i-1]+1 if C[i]>C[i-4] else 0
        buy[i]=buy[i-1]+1 if C[i]<C[i-4] else 0
    # events
    events={}
    events["RSI_oversold"]=first_triggers(RSI<30)
    events["RSI_overbought"]=first_triggers(RSI>70)
    events["TD_buy9"]=[i for i in range(n) if buy[i]==9]
    events["TD_sell9"]=[i for i in range(n) if sell[i]==9]
    ph,pl=swings(C,5); w=5
    bull=[]; bear=[]
    for k in range(1,len(pl)):
        a_,b_=pl[k-1],pl[k]
        if C[b_]<C[a_] and MFI[b_]>MFI[a_] and b_+w<n: bull.append(b_+w)
    for k in range(1,len(ph)):
        a_,b_=ph[k-1],ph[k]
        if C[b_]>C[a_] and MFI[b_]<MFI[a_] and b_+w<n: bear.append(b_+w)
    events["MFI_bulldiv"]=bull; events["MFI_beardiv"]=bear
    # forward-return stats (H=20 headline, also 10)
    for key,idxs in events.items():
        for Hh,tag in [(10,"10"),(20,"20")]:
            s=stat(fwd(C,idxs,Hh), baseline(C,Hh))
            if tag=="20":
                ev_rows.append(dict(ticker=sym,signal=key,n=s.get("n",0),
                    mean20=s.get("mean",""),base20=s.get("base",""),edge20=s.get("edge",""),
                    hit20=s.get("hit",""),t_edge20=s.get("t_edge","")))
                pool[key]["ev"].append(fwd(C,idxs,20)); pool[key]["base"].append(baseline(C,20))
    # ichimoku trend backtest
    ret=np.concatenate([[0.0],C[1:]/C[:-1]-1])
    cloud_top=np.full(n,np.nan)
    for t in range(26,n):
        aa=spanA[t-26]; bb=spanB[t-26]
        if np.isfinite(aa) and np.isfinite(bb): cloud_top[t]=max(aa,bb)
    pos=np.zeros(n)
    for i in range(1,n):
        if np.isfinite(cloud_top[i-1]): pos[i]=1.0 if C[i-1]>cloud_top[i-1] else 0.0
        else: pos[i]=1.0
    bh=perf(ret,np.ones(n)); ich=perf(ret,pos)
    ich_rows.append(dict(ticker=sym, BH_CAGR=round(bh["cagr"]*100,1),BH_MaxDD=round(bh["maxdd"]*100,1),BH_Sharpe=round(bh["sharpe"],2),
        ICH_CAGR=round(ich["cagr"]*100,1),ICH_MaxDD=round(ich["maxdd"]*100,1),ICH_Sharpe=round(ich["sharpe"],2),ICH_pct=round(ich["pct"]*100,0)))
    # snapshot (current)
    ct_now=max(spanA[-27],spanB[-27]); cb_now=min(spanA[-27],spanB[-27])
    reg="above" if C[-1]>ct_now else "below" if C[-1]<cb_now else "in"
    cur = f"sell{sell[-1]}" if sell[-1]>0 else (f"buy{buy[-1]}" if buy[-1]>0 else "-")
    snap.append(dict(ticker=sym,close=round(float(C[-1]),2),RSI=round(float(RSI[-1]),0),MFI=round(float(MFI[-1]),0),
        cloud=reg,TK=("bull" if tenkan[-1]>kijun[-1] else "bear"),TDsetup=cur))
    panel(sym,name,D,C,RSI,MFI,tenkan,kijun,spanA,spanB,sell,buy)
    print(f"[done] {sym}: {n} bars, close {C[-1]:.2f}, RSI {RSI[-1]:.0f}, MFI {MFI[-1]:.0f}, cloud {reg}")

def wcsv(path,rows):
    keys=list(rows[0].keys())
    with open(path,"w") as f:
        f.write(",".join(keys)+"\n")
        for r in rows: f.write(",".join(str(r[k]) for k in keys)+"\n")
wcsv(f"{DATA}/snapshot.csv",snap); wcsv(f"{DATA}/event_study.csv",ev_rows); wcsv(f"{DATA}/ichimoku_trend.csv",ich_rows)

# pooled event stats
pooled={}
for key,d in pool.items():
    ev=np.concatenate(d["ev"]) if d["ev"] else np.array([])
    base=np.concatenate(d["base"]) if d["base"] else np.array([])
    pooled[key]=stat(ev,base); pooled[key]["dir"]=SIGDIR[key]
json.dump(dict(pooled_20d=pooled),open(f"{DATA}/summary.json","w"),indent=2)

print("\n===== SNAPSHOT (current) =====")
print("tk\tclose\tRSI\tMFI\tcloud\tTK\tTD")
for s in snap: print(f"{s['ticker']}\t{s['close']}\t{s['RSI']:.0f}\t{s['MFI']:.0f}\t{s['cloud']}\t{s['TK']}\t{s['TDsetup']}")

print("\n===== EVENT STUDY (20-day forward return vs baseline) =====")
print("tk\tsignal\tn\tmean%\tbase%\tedge%\thit%\tt")
for r in ev_rows:
    print(f"{r['ticker']}\t{r['signal']}\t{r['n']}\t{r['mean20']}\t{r['base20']}\t{r['edge20']}\t{r['hit20']}\t{r['t_edge20']}")

print("\n===== POOLED (all tickers, 20d) =====")
for k,v in pooled.items(): print(f"{k}\t{json.dumps(v)}")

print("\n===== ICHIMOKU TREND vs BUY&HOLD =====")
print("tk\tBH_CAGR/MaxDD/Sh\tICH_CAGR/MaxDD/Sh\t%inv")
for r in ich_rows:
    print(f"{r['ticker']}\t{r['BH_CAGR']}/{r['BH_MaxDD']}/{r['BH_Sharpe']}\t{r['ICH_CAGR']}/{r['ICH_MaxDD']}/{r['ICH_Sharpe']}\t{r['ICH_pct']}")
# aggregate ichimoku
import statistics as st
print("\nICH avg: BH CAGR %.1f MaxDD %.1f Sh %.2f | ICH CAGR %.1f MaxDD %.1f Sh %.2f | ICH beat BH Sharpe %d/N, lower DD %d/N"%(
    st.mean([r['BH_CAGR'] for r in ich_rows]),st.mean([r['BH_MaxDD'] for r in ich_rows]),st.mean([r['BH_Sharpe'] for r in ich_rows]),
    st.mean([r['ICH_CAGR'] for r in ich_rows]),st.mean([r['ICH_MaxDD'] for r in ich_rows]),st.mean([r['ICH_Sharpe'] for r in ich_rows]),
    sum(1 for r in ich_rows if r['ICH_Sharpe']>r['BH_Sharpe']), sum(1 for r in ich_rows if r['ICH_MaxDD']>r['BH_MaxDD'])))
print("\nDONE")
