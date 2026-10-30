"""Recovery test: plant known shapes in random walks and measure how often the detector gets them right.

    python -m pump_dump.validate_synthetic [--trials 30] [--select f|r2]

Each trial = drifting random walk (15%/yr) with daily vol sigma, plus (optionally) a
pump of +h log over 50 days that then settles over 100 days to:
    revert : back on the original trend   (true r = 1)
    hold   : stays ~95% elevated          (true r = 0.05)
    crash  : 0.3 log below trend          (true r ~ 1.86)
    none   : no pump at all
"""

from __future__ import annotations

import argparse
from multiprocessing import Pool

import numpy as np
import pandas as pd

from .model import FitConfig, classify, null_scores, score_series

SHAPES = {"revert": 0.0, "hold": 0.95, "crash": -0.85, "none": None}   # settle level as a fraction of h
EXPECTED = {"revert": {"pump_revert", "pump_revert_below_start"}, "hold": {"pump_hold", "partial_revert", "continued_rise"},
            "crash": {"crash_below_trend"}, "none": {"no_pump"}}


def make_path(shape, sigma, h, rng, n=756):
    tau = np.arange(n)
    y = np.log(100) + 0.15 / 252 * tau + np.cumsum(rng.normal(0, sigma, n))
    if SHAPES[shape] is not None:
        t0 = int(rng.integers(300, 520)); t1, t2 = t0 + 50, t0 + 150
        d = SHAPES[shape] * h
        y[t0:t1] += h * (tau[t0:t1] - t0) / (t1 - t0)
        y[t1:t2] += h + (d - h) * (tau[t1:t2] - t1) / (t2 - t1)
        y[t2:] += d
    return y


def trial(args):
    shape, sigma, h, seed, select, pre, post, n_null = args
    rng = np.random.default_rng(seed)
    cfg = FitConfig(select=select, pre_window=pre, min_pre_days=pre, post_window=post)
    y = make_path(shape, sigma, h, rng)
    s = score_series(y, cfg)
    p = 1.0
    if n_null and s["has_pump"]:
        null = null_scores(y, cfg, n_paths=n_null, seed=seed)
        p = float((1 + np.sum(null[:, 0] >= s["score"])) / (1 + n_null))
    got, verdict = classify(s, p, cfg)
    return dict(shape=shape, sigma=sigma, h=h, got=got, r=s["r"], correct=got in EXPECTED[shape],
                p=p, supports=verdict == "SUPPORTS")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=30)
    ap.add_argument("--select", default="f", choices=["f", "r2"])
    ap.add_argument("--h", type=float, nargs="*", default=[0.35, 0.6])
    ap.add_argument("--sigmas", type=float, nargs="*", default=[0.006, 0.01, 0.015, 0.02])
    ap.add_argument("--pre", type=int, default=FitConfig.pre_window)
    ap.add_argument("--post", type=int, default=FitConfig.post_window)
    ap.add_argument("--n-null", type=int, default=0,
                    help="also run the bootstrap test (slow) and report SUPPORTS rate per cell")
    a = ap.parse_args(argv)
    jobs = [(sh, sg, h, 10_000 * i + k, a.select, a.pre, a.post, a.n_null) for i, (sh, sg, h) in enumerate(
        (sh, sg, h) for sh in SHAPES for sg in a.sigmas for h in a.h) for k in range(a.trials)]
    with Pool() as pool:
        df = pd.DataFrame(pool.map(trial, jobs))
    acc = df.pivot_table(index=["h", "sigma"], columns="shape", values="correct", aggfunc="mean")
    print(f"Classification accuracy (select={a.select}, pre={a.pre}, post={a.post}, {a.trials} trials/cell):")
    print(acc.round(2).to_string())
    rev = df[(df["shape"] == "revert") & df["r"].notna()]
    print("\nMedian |r - 1| on planted reverts:")
    print(rev.assign(err=(rev["r"] - 1).abs()).groupby(["h", "sigma"])["err"].median().round(2).to_string())
    if a.n_null:
        print(f"\nSUPPORTS rate (revert shape AND bootstrap p < 0.10, {a.n_null} nulls):")
        print(df.pivot_table(index=["h", "sigma"], columns="shape", values="supports",
                             aggfunc="mean").round(2).to_string())
    return df


if __name__ == "__main__":
    main()
