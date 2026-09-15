#!/usr/bin/env python3
"""
Valuation charts for the S&P 500 top-10 fundamental study.

Figures are built from `valuations.json` in this directory, which holds the
per-ticker numbers gathered for the 2026-09-15 run (see README.md for where each
figure came from and how firm it is). No market-data API is reachable from this
environment, so nothing here refetches prices - the JSON is the record.

Palette: dataviz reference instance, categorical slots 1-2
(blue #2a78d6, orange #eb6834), validated for both modes.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

BASE = os.path.dirname(os.path.abspath(__file__))
CHARTS = os.path.join(BASE, "charts")

# dataviz reference palette
BLUE, ORANGE, RED = "#2a78d6", "#eb6834", "#e34948"
SURFACE = "#fcfcfb"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASELINE = "#e1e0d9", "#c3c2b7"

SPX_FWD_PE = 19.1  # FactSet forward 12-month P/E for the S&P 500, early Sept 2026


def load():
    with open(os.path.join(BASE, "valuations.json")) as f:
        return json.load(f)


def style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(BASELINE)
        ax.spines[side].set_linewidth(1)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.set_axisbelow(True)


def titled(fig, title, subtitle, footnote):
    """Title block and footnote, both anchored to the figure's left edge."""
    fig.text(0.012, 0.965, title, fontsize=13.5, color=INK, fontweight="bold", va="top")
    fig.text(0.012, 0.902, subtitle, fontsize=9.5, color=INK2, va="top")
    fig.text(0.012, 0.018, footnote, fontsize=7.5, color=MUTED, va="bottom")


def chart_forward_pe(rows):
    """What you pay for a dollar of next year's earnings, vs the index."""
    rows = sorted(rows, key=lambda r: r["fwd_pe"])
    names = [f'{r["ticker"]}  {r["company"]}' for r in rows]
    vals = [r["fwd_pe"] for r in rows]
    y = range(len(rows))

    fig, ax = plt.subplots(figsize=(9.5, 5.6), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    ax.xaxis.grid(True, color=GRID, linewidth=1)
    ax.yaxis.grid(False)

    cap = 40.0  # Tesla runs far off the scale; its bar is clipped and labelled
    label_x = cap + 4.0  # fixed value column, so no label can collide with the reference line
    drawn = [min(v, cap) for v in vals]
    ax.barh(list(y), drawn, height=0.6, color=BLUE, zorder=3)

    for i, (v, d) in enumerate(zip(vals, drawn)):
        if v > cap:
            ax.plot([cap + 0.6], [i], marker=">", color=BLUE, markersize=7, zorder=4)
        ax.text(label_x, i, f"{v:.0f}", va="center", ha="right", fontsize=9.5,
                color=INK2, zorder=4)

    ax.axvline(SPX_FWD_PE, color=ORANGE, linewidth=2, linestyle=(0, (5, 3)), zorder=5)
    ax.annotate(f"S&P 500 average  {SPX_FWD_PE}",
                xy=(SPX_FWD_PE, len(rows) - 0.4), xytext=(SPX_FWD_PE + 0.6, len(rows) - 0.25),
                color=ORANGE, fontsize=9, fontweight="bold", va="center", ha="left")

    ax.set_yticks(list(y))
    ax.set_yticklabels(names, fontsize=9.5, color=INK)
    ax.set_xlim(0, label_x + 0.5)
    ax.set_xticks([0, 10, 20, 30, 40])
    ax.set_xlabel("Forward price-to-earnings ratio  (price ÷ next 12 months' expected earnings)",
                  fontsize=9.5, color=INK2, labelpad=9)
    titled(fig,
           "What you pay for a dollar of next year's profit",
           "Lower = cheaper. Bars left of the dashed line cost less than the average S&P 500 company.",
           "As of 2026-09-15. Forward P/E consensus estimates; see README.md for sources and confidence. "
           "Tesla's bar is clipped — its true value is 158. Not investment advice.")
    fig.tight_layout(rect=(0, 0.045, 1, 0.88))
    out = os.path.join(CHARTS, "forward-pe.png")
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return out


def chart_implied_growth(rows):
    """Trailing P/E vs forward P/E, expressed as the earnings change it implies.

    Plotting the two P/Es side by side fails here: Tesla's trailing 301 flattens
    every other bar. The ratio between them carries the same information on a
    scale that fits, and states the question directly - is profit expected to
    rise or fall?
    """
    for r in rows:
        r["_implied"] = (r["trailing_pe"] / r["fwd_pe"] - 1.0) * 100.0
    rows = sorted(rows, key=lambda r: r["_implied"])
    names = [r["ticker"] for r in rows]
    vals = [r["_implied"] for r in rows]
    y = range(len(rows))

    fig, ax = plt.subplots(figsize=(9.5, 5.2), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    ax.xaxis.grid(True, color=GRID, linewidth=1)
    ax.yaxis.grid(False)

    # Diverging pair from the reference palette: blue (rise) <-> red (fall).
    colors = [BLUE if v >= 0 else RED for v in vals]
    ax.barh(list(y), vals, height=0.6, color=colors, zorder=3)
    ax.axvline(0, color=BASELINE, linewidth=1.5, zorder=4)

    for i, v in enumerate(vals):
        ax.text(v + (3 if v >= 0 else -3), i, f"{v:+.0f}%", va="center",
                ha="left" if v >= 0 else "right", fontsize=9.5, color=INK2, zorder=4)

    # The two bars that are accounting artifacts rather than business forecasts.
    # Both notes sit in open space to the right of the bar end, clear of the
    # y-tick labels on the left and of the axis edge on the right.
    flags = {
        "AVGO": (26, "accounting, not growth:\nGAAP vs adjusted earnings"),
        "GOOGL": (40, "accounting, not decline:\none-off $98bn equity gain"),
    }
    for i, r in enumerate(rows):
        if r["ticker"] in flags:
            dx, text = flags[r["ticker"]]
            ax.text(vals[i] + dx, i, text, va="center", ha="left",
                    fontsize=8, color=MUTED, style="italic", zorder=4)

    ax.set_yticks(list(y))
    ax.set_yticklabels(names, fontsize=9.5, color=INK)
    ax.set_xlim(-60, 285)
    ax.set_xticks([-50, 0, 50, 100, 150, 200, 250])
    ax.set_xticklabels([f"{t:+d}%" if t else "0%" for t in [-50, 0, 50, 100, 150, 200, 250]])
    ax.set_xlabel("Implied change in earnings, trailing → forward", fontsize=9.5,
                  color=INK2, labelpad=9)
    ax.legend(handles=[Patch(facecolor=BLUE, label="Profit expected to rise"),
                       Patch(facecolor=RED, label="Profit expected to fall")],
              loc="lower right", frameon=False, fontsize=9, labelcolor=INK2)
    titled(fig,
           "Where the market expects profits to go next",
           "How far this year's P/E sits above next year's — the market's own forecast, in one number.",
           "As of 2026-09-15. Derived as trailing P/E ÷ forward P/E − 1. Not investment advice.")
    fig.tight_layout(rect=(0, 0.045, 1, 0.88))
    out = os.path.join(CHARTS, "implied-earnings-change.png")
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    return out


def main():
    os.makedirs(CHARTS, exist_ok=True)
    rows = load()["stocks"]
    for path in (chart_forward_pe(rows), chart_implied_growth(rows)):
        print("wrote", path)


if __name__ == "__main__":
    main()
