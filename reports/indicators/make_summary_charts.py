#!/usr/bin/env python3
"""Summary charts for the indicator backtest (reads data/ CSVs written by indicator_backtest.py)."""
import csv, numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
BASE="/home/user/scratch/reports/indicators"; DATA=f"{BASE}/data"; CH=f"{BASE}/charts"
TKS=["GOOG","AAPL","NVDA","MSFT","TSM","ASML","MRVL","AMD","JPM","AXP","AVGO","MRNA","MA"]
SIGS=["RSI_oversold","RSI_overbought","MFI_bulldiv","MFI_beardiv","TD_buy9","TD_sell9"]
DIR={"RSI_oversold":1,"RSI_overbought":-1,"MFI_bulldiv":1,"MFI_beardiv":-1,"TD_buy9":1,"TD_sell9":-1}
LBL={"RSI_oversold":"RSI<30 (buy)","RSI_overbought":"RSI>70 (sell)","MFI_bulldiv":"MFI bull div",
     "MFI_beardiv":"MFI bear div","TD_buy9":"TD buy-9","TD_sell9":"TD sell-9"}
rows=list(csv.DictReader(open(f"{DATA}/event_study.csv")))
E={(r["ticker"],r["signal"]):float(r["edge20"]) for r in rows}
T={(r["ticker"],r["signal"]):float(r["t_edge20"]) for r in rows}
INK="#1a202c";MUTED="#6b7280";GRID="#e5e7eb"

M=np.array([[E[(t,s)]*DIR[s] for t in TKS] for s in SIGS])
fig,ax=plt.subplots(figsize=(13,4.8),dpi=150)
vmax=max(3.0,np.abs(M).max()); im=ax.imshow(M,cmap="RdYlGn",norm=TwoSlopeNorm(vmin=-vmax,vcenter=0,vmax=vmax),aspect="auto")
ax.set_xticks(range(len(TKS))); ax.set_xticklabels(TKS,fontsize=10)
ax.set_yticks(range(len(SIGS))); ax.set_yticklabels([LBL[s] for s in SIGS],fontsize=10)
for i,s in enumerate(SIGS):
    for j,t in enumerate(TKS):
        v=M[i,j]; star="*" if abs(T[(t,s)])>=2 else ""
        ax.text(j,i,f"{v:+.1f}{star}",ha="center",va="center",fontsize=8,
                color="black" if abs(v)<vmax*0.6 else "white",fontweight="bold" if star else "normal")
ax.set_title("Does each indicator help, per stock?  Directional 20-day edge vs baseline (%, green = worked in intended direction; * = |t|>=2)",
             loc="left",fontsize=10.5,fontweight="bold",color=INK,pad=10)
ax.set_xticks(np.arange(-.5,len(TKS),1),minor=True); ax.set_yticks(np.arange(-.5,len(SIGS),1),minor=True)
ax.grid(which="minor",color="white",lw=1.5); ax.tick_params(length=0)
fig.text(0.005,0.005,"Event study, ~20y daily, in-sample, no costs · Yahoo Finance · NOT investment advice",fontsize=7.5,color=MUTED)
fig.tight_layout(); fig.savefig(f"{CH}/summary_edge_heatmap.png",facecolor="white",bbox_inches="tight"); plt.close(fig)

fig,ax=plt.subplots(figsize=(9.8,4.3),dpi=150)
vals=[E[(t,"RSI_oversold")] for t in TKS]; ts=[T[(t,"RSI_oversold")] for t in TKS]
b=ax.bar(TKS,vals,color=["#059669" if v>0 else "#b91c1c" for v in vals],width=0.66)
for bar,v,tt in zip(b,vals,ts):
    ax.text(bar.get_x()+bar.get_width()/2, v+(0.2 if v>=0 else -0.2), f"{v:+.1f}\n(t{tt:+.1f})",
            ha="center",va="bottom" if v>=0 else "top",fontsize=7.5,color=INK)
ax.axhline(0,color=MUTED,lw=0.8)
ax.set_ylim(min(vals)-2.6, max(vals)+2.0)   # headroom so value labels do not collide with tick labels
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color(GRID)
ax.grid(axis="y",color=GRID,lw=0.6); ax.set_axisbelow(True); ax.tick_params(colors=MUTED,length=0)
ax.set_ylabel("20-day edge after RSI<30 (%)",color=MUTED)
ax.set_title("'Buy the RSI dip' 20-day edge — works on steady compounders, catastrophic on high-beta names",loc="left",fontsize=11,fontweight="bold",color=INK,pad=10)
fig.text(0.005,0.005,"Positive = oversold bounce beat baseline · negative = falling-knife · ~20y daily, in-sample · Yahoo Finance",fontsize=7.5,color=MUTED)
fig.tight_layout(); fig.savefig(f"{CH}/summary_rsi_oversold_edge.png",facecolor="white",bbox_inches="tight"); plt.close(fig)

ich=list(csv.DictReader(open(f"{DATA}/ichimoku_trend.csv")))
fig,ax=plt.subplots(figsize=(10,4.5),dpi=150)
x=np.arange(len(ich)); w=0.4
ax.bar(x-w/2,[float(r["BH_MaxDD"]) for r in ich],w,color="#2b6cb0",label="Buy&Hold")
ax.bar(x+w/2,[float(r["ICH_MaxDD"]) for r in ich],w,color="#059669",label="Ichimoku trend")
ax.set_xticks(x); ax.set_xticklabels([r["ticker"] for r in ich])
ax.axhline(0,color=MUTED,lw=0.8); ax.legend(frameon=False,fontsize=9,loc="lower right")
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color(GRID)
ax.grid(axis="y",color=GRID,lw=0.6); ax.set_axisbelow(True); ax.tick_params(colors=MUTED,length=0)
ax.set_ylabel("Max drawdown (%)",color=MUTED)
ax.set_title("Ichimoku cloud filter cuts drawdown (11/12) — but avg CAGR fell 21%->13% and Sharpe 0.67->0.53",loc="left",fontsize=10.5,fontweight="bold",color=INK,pad=10)
fig.text(0.005,0.005,"Long only above the cloud, else cash(0%) · ~20y daily, no costs · Yahoo Finance",fontsize=7.5,color=MUTED)
fig.tight_layout(); fig.savefig(f"{CH}/summary_ichimoku.png",facecolor="white",bbox_inches="tight"); plt.close(fig)
print("summary charts regenerated for", len(TKS), "tickers")
