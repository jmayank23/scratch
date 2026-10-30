"""Static matplotlib charts for the report."""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .model import model_curves  # noqa: E402

INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1", "#fcfcfb"
PRICE, FIT, TREND = "#2a78d6", "#eb6834", "#52514e"
VERDICT_COLOR = {"SUPPORTS": "#1baf7a", "WEAK": "#eda100", "CONTRADICTS": "#e34948", "NONE": "#8a8984"}


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def stock_chart(ticker, dates, y, s, path, ylabel="Price (log scale)"):
    fig, ax = plt.subplots(figsize=(9, 4.2), facecolor=SURFACE)
    _style(ax)
    p = np.exp(y)
    ax.plot(dates, p, color=PRICE, lw=1.4, label="Price")
    title = ticker
    if s.get("has_pump"):
        fit = s["_fit"]
        model, trend = model_curves(fit, len(y))
        ax.plot(dates, np.exp(trend), color=TREND, lw=1.4, ls="--", label="No-pump trend (counterfactual)")
        ax.plot(dates, np.exp(model), color=FIT, lw=2, label="Fitted pump/dump episode")
        t0, t1, t2 = s["t0"], s["t1"], s["t2"]
        ax.axvspan(dates[t0], dates[t2], color=FIT, alpha=0.07, lw=0)
        for t, lab in ((t0, "start"), (t1, "peak"), (t2, "settle")):
            ax.scatter([dates[t]], [p[t]], s=36, color=FIT, edgecolor=SURFACE, linewidth=2, zorder=5)
            ax.annotate(lab, (dates[t], p[t]), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=8, color=INK2)
        title += (f"   r = {s['r']:.2f}   score = {s['score']:.0f}   p = {s.get('p_value', np.nan):.3f}"
                  f"   [{s.get('verdict', '')}]")
    ax.set_yscale("log")
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def summary_chart(df, path, band):
    """Reversion ratio per stock: the hypothesis predicts r ~ 1."""
    d = df[df["has_pump"]].sort_values("r")
    if d.empty:
        return
    fig, ax = plt.subplots(figsize=(9, max(3.5, 0.24 * len(d) + 1.2)), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", visible=False)
    ax.axvspan(1 - band, 1 + band, color=VERDICT_COLOR["SUPPORTS"], alpha=0.10, lw=0)
    ax.axvline(1, color=MUTED, lw=1, ls="--")
    ax.axvline(0, color=MUTED, lw=1, ls=":")
    ypos = np.arange(len(d))
    keys = d["verdict"].str.split().str[0].fillna("NONE")
    colors = [VERDICT_COLOR.get(k, VERDICT_COLOR["NONE"]) for k in keys]
    r = d["r"].clip(-1.5, 3)
    ax.hlines(ypos, 1, r, color=GRID, lw=2)
    ax.scatter(r, ypos, s=20 + 1.6 * d["score"], c=colors, edgecolor=SURFACE, linewidth=2, zorder=3)
    ax.set_yticks(ypos, d["ticker"], fontsize=8, color=INK2)
    ax.set_xlabel("Reversion ratio r = 1 - (settle excess / peak excess)   "
                  "0 = pump & hold, 1 = back to trend, >1 = below trend", color=INK2, fontsize=9)
    ax.set_title("Where each stock's biggest recent pump settled (dot size = signal score)",
                 loc="left", fontsize=11, color=INK)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], marker="o", ls="", color=VERDICT_COLOR[k], label=lab, markersize=7)
               for k, lab in (("SUPPORTS", "Supports (p < alpha)"), ("WEAK", "Revert shape, not significant"),
                              ("CONTRADICTS", "Contradicts"))]
    ax.legend(handles=handles, frameon=False, fontsize=8, labelcolor=INK2, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)
    return p
