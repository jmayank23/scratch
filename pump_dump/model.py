"""Episode model for the "pump-and-revert-to-trend" hypothesis.

For a price series p(t) we work with y(t) = log p(t) and fit

    y(t) = a + b*t + h*tent(t; t0, t1, t2) + d*settle(t; t1, t2) + noise

    tent   : 0 before t0, rises linearly to 1 at t1 (the peak), falls back
             linearly to 0 at t2, and is 0 afterwards.
    settle : 0 before t1, rises linearly from 0 at t1 to 1 at t2, stays 1.

So relative to one straight log-trend line (a + b*t):
    * before t0 the stock sits on the trend,
    * it is h above trend at the peak t1 (the pump),
    * it is d above trend from t2 onwards (where the dump settles).

The hypothesis "the stock falls back to roughly where the pre-pump trend
would have put it" is exactly d ~= 0, i.e. reversion ratio r = 1 - d/h ~= 1.
    r ~ 1  -> pump & revert to trend   (hypothesis)
    r ~ 0  -> pump & hold              (gains kept, not a dump)
    r > 1  -> pump & crash below trend
    r < 0  -> kept rising after the "peak"

The fit is LOCAL: it uses only [t0 - pre_window, t2 + post_window], so the
"trend" is the pre-pump trajectory, not a multi-year straight line.

Given breakpoints (t0, t1, t2) the model is linear in (a, b, h, d), so every
candidate is solved in closed form from prefix sums; the breakpoints are found
by an exhaustive coarse grid search followed by local refinement.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np


@dataclass
class FitConfig:
    recent_days: int = 504        # pump must start within this many trading days of the end (~2y)
    pre_window: int = 252         # trading days before pump start used to anchor the trend (~1y)
    post_window: int = 63         # trading days after settle included in the local fit (~3m)
    min_pre_days: int = 252       # need a full pre-window before the pump starts
    min_post_days: int = 10       # trading days observed after the dump settles
    pump_len: tuple[int, int] = (5, 126)   # t1 - t0, trading days ("rapid": <= ~6 months)
    dump_len: tuple[int, int] = (5, 252)   # t2 - t1, trading days
    step: int = 5                 # coarse grid step
    refine: int = 5               # +/- window of the step-1 refinement
    min_pump: float = 0.10        # min excess log-rise above trend at the peak (~10.5%)
    select: str = "f"             # episode selection: "f" (F-stat vs plain trend) or "r2" (variance share)
    settle_window: int = 10       # days after t2 used to measure the settle price
    revert_band: float = 0.4      # |r - 1| <= band counts as "reverted to trend"
    min_drop: float = 0.08        # fitted peak -> settle must fall >= 8%, else it is a plateau, not a dump


# ---------------------------------------------------------------- fitting --

class _Prefix:
    """Prefix sums over the series so any segment sum is O(1)."""

    def __init__(self, y: np.ndarray):
        n = len(y)
        t = np.arange(n) / (n - 1)
        z = np.zeros(1)
        self.n = n
        self.tau = t
        self.S0 = np.concatenate([z, np.cumsum(np.ones(n))])
        self.S1 = np.concatenate([z, np.cumsum(t)])
        self.S2 = np.concatenate([z, np.cumsum(t * t)])
        self.Sy = np.concatenate([z, np.cumsum(y)])
        self.Sty = np.concatenate([z, np.cumsum(t * y)])
        self.Syy = np.concatenate([z, np.cumsum(y * y)])

    def seg(self, s, e):
        """Sums over the half-open index range [s, e)."""
        return tuple(P[e] - P[s] for P in (self.S0, self.S1, self.S2, self.Sy, self.Sty))

    def window(self, cfg, t0, t2):
        return np.maximum(0, t0 - cfg.pre_window), np.minimum(self.n, t2 + cfg.post_window)

    def linear_sse(self, w0, w1):
        F0, F1, F2, Fy, Fty = self.seg(w0, w1)
        det = F0 * F2 - F1 * F1
        a = (F2 * Fy - F1 * Fty) / det
        b = (F0 * Fty - F1 * Fy) / det
        return self.Syy[w1] - self.Syy[w0] - (a * Fy + b * Fty)


def _solve(pf: _Prefix, t0, t1, t2, w0, w1):
    """Vectorised least squares on windows [w0, w1) for arrays of breakpoints.

    Returns (theta[N,4], sse[N])."""
    tau = pf.tau
    T0, T1, T2 = tau[t0], tau[t1], tau[t2]

    A0, A1, A2, Ay, Aty = pf.seg(t0, t1)                       # rise segment
    B0, B1, B2, By, Bty = pf.seg(t1, t2)                       # fall segment
    C0, C1, C2, Cy, Cty = pf.seg(t2, w1)                       # post segment
    F0, F1, F2, Fy, Fty = pf.seg(w0, w1)                       # whole window

    # tent = aA + bA*t on A, aB + bB*t on B;  settle = gB + dB*t on B, 1 on C
    bA = 1.0 / (T1 - T0); aA = -T0 * bA
    bB = -1.0 / (T2 - T1); aB = T2 / (T2 - T1)
    dB = 1.0 / (T2 - T1); gB = -T1 * dB

    g1 = aA * A0 + bA * A1 + aB * B0 + bB * B1
    gt = aA * A1 + bA * A2 + aB * B1 + bB * B2
    gg = aA**2 * A0 + 2 * aA * bA * A1 + bA**2 * A2 + aB**2 * B0 + 2 * aB * bB * B1 + bB**2 * B2
    f1 = gB * B0 + dB * B1 + C0
    ft = gB * B1 + dB * B2 + C1
    ff = gB**2 * B0 + 2 * gB * dB * B1 + dB**2 * B2 + C0
    gf = aB * gB * B0 + (aB * dB + bB * gB) * B1 + bB * dB * B2
    gy = aA * Ay + bA * Aty + aB * By + bB * Bty
    fy = gB * By + dB * Bty + Cy

    N = len(t0)
    M = np.empty((N, 4, 4))
    M[:, 0, 0] = F0; M[:, 0, 1] = F1; M[:, 0, 2] = g1; M[:, 0, 3] = f1
    M[:, 1, 1] = F2; M[:, 1, 2] = gt; M[:, 1, 3] = ft
    M[:, 2, 2] = gg; M[:, 2, 3] = gf
    M[:, 3, 3] = ff
    iu = np.triu_indices(4, 1)
    M[:, iu[1], iu[0]] = M[:, iu[0], iu[1]]
    v = np.stack([Fy, Fty, gy, fy], axis=1)
    theta = np.linalg.solve(M, v[..., None])[..., 0]
    sse = pf.Syy[w1] - pf.Syy[w0] - np.einsum("ij,ij->i", theta, v)
    return theta, sse


def _grid(n, cfg: FitConfig, step: int, around=None):
    if around is None:
        lo = max(cfg.min_pre_days, n - cfg.recent_days)
        t0s = np.arange(lo, n, step)
        L1s = np.arange(cfg.pump_len[0], cfg.pump_len[1] + 1, step)
        L2s = np.arange(cfg.dump_len[0], cfg.dump_len[1] + 1, step)
        t0, L1, L2 = (a.ravel() for a in np.meshgrid(t0s, L1s, L2s, indexing="ij"))
        t1, t2 = t0 + L1, t0 + L1 + L2
    else:
        r = np.arange(-cfg.refine, cfg.refine + 1)
        d0, d1, d2 = (a.ravel() for a in np.meshgrid(r, r, r, indexing="ij"))
        t0, t1, t2 = around[0] + d0, around[1] + d1, around[2] + d2
    L1, L2 = t1 - t0, t2 - t1
    ok = ((t0 >= max(cfg.min_pre_days, n - cfg.recent_days)) & (t2 <= n - cfg.min_post_days)
          & (L1 >= cfg.pump_len[0]) & (L1 <= cfg.pump_len[1])
          & (L2 >= cfg.dump_len[0]) & (L2 <= cfg.dump_len[1]))
    return t0[ok], t1[ok], t2[ok]


def _best(pf, cfg, t0, t1, t2):
    """Most prominent pump episode among candidate breakpoints.

    Windows differ per candidate, so candidates are ranked by a window-size-aware
    statistic: the F-statistic of the episode model against a plain local trend
    (or the share of local variance it explains, if cfg.select == "r2")."""
    if len(t0) == 0:
        return None
    w0, w1 = pf.window(cfg, t0, t2)
    theta, sse = _solve(pf, t0, t1, t2, w0, w1)
    sse0 = pf.linear_sse(w0, w1)
    m = w1 - w0
    if cfg.select == "r2":
        crit = 1 - sse / sse0
    else:
        crit = ((sse0 - sse) / 2) / (sse / (m - 4))
    valid = theta[:, 2] >= cfg.min_pump          # a real pump above trend at the peak
    if not valid.any():
        return None
    i = np.flatnonzero(valid)[np.argmax(crit[valid])]
    return (int(t0[i]), int(t1[i]), int(t2[i]), theta[i], float(sse[i]), float(sse0[i]),
            int(w0[i]), int(w1[i]), float(crit[i]))


def fit_episode(y: np.ndarray, cfg: FitConfig):
    """Best pump/dump episode for log-price series y (demeaned internally)."""
    y = np.asarray(y, float)
    mu = y.mean()
    yc = y - mu
    pf = _Prefix(yc)
    best = _best(pf, cfg, *_grid(len(y), cfg, cfg.step))
    if best is None:
        return None
    ref = _best(pf, cfg, *_grid(len(y), cfg, 1, around=best[:3]))
    if ref is not None and ref[8] >= best[8]:
        best = ref
    t0, t1, t2, theta, sse, sse0, w0, w1, crit = best
    a, b, h, d = theta
    return dict(t0=t0, t1=t1, t2=t2, w0=w0, w1=w1, a=a + mu, b=b, h=h, d=d,
                sse=sse, sse0=sse0, crit=crit, n=len(y))


# ---------------------------------------------------------------- scoring --

def model_curves(fit, n):
    """Fitted episode curve and its no-pump counterfactual trend (log space), NaN outside the window."""
    tau = np.arange(n) / (n - 1)
    t0, t1, t2 = fit["t0"], fit["t1"], fit["t2"]
    T0, T1, T2 = tau[t0], tau[t1], tau[t2]
    tent = np.zeros(n); settle = np.zeros(n)
    tent[t0:t1] = (tau[t0:t1] - T0) / (T1 - T0)
    tent[t1:t2] = (T2 - tau[t1:t2]) / (T2 - T1)
    settle[t1:t2] = (tau[t1:t2] - T1) / (T2 - T1)
    settle[t2:] = 1.0
    trend = fit["a"] + fit["b"] * tau
    model = trend + fit["h"] * tent + fit["d"] * settle
    outside = np.ones(n, bool)
    outside[fit["w0"]:fit["w1"]] = False
    model[outside] = np.nan
    trend[outside] = np.nan
    return model, trend


def score_series(y: np.ndarray, cfg: FitConfig, fit=None):
    """Fit + derive interpretable metrics and a 0-100 hypothesis-signal score."""
    y = np.asarray(y, float)
    n = len(y)
    if fit is None:
        fit = fit_episode(y, cfg)
    if fit is None:
        return dict(has_pump=False, score=0.0, r=np.nan)

    t0, t1, t2, h, d = fit["t0"], fit["t1"], fit["t2"], fit["h"], fit["d"]
    fit_gain = max(0.0, 1.0 - fit["sse"] / fit["sse0"])   # share of local off-trend variance explained
    r = 1.0 - d / h                                  # reversion ratio

    p = np.exp(y)
    _, trend = model_curves(fit, n)
    p_start = p[t0]
    p_peak = p[t0:t2 + 1].max()
    p_settle = float(np.median(p[t2:min(n, t2 + cfg.settle_window)]))
    trend_at_settle = float(np.exp(trend[t2]))

    # Out-of-sample check: trend fitted ONLY on pre-pump data, extrapolated to t2.
    tau = np.arange(n) / (n - 1)
    pre = slice(fit["w0"], t0)
    cb = np.polyfit(tau[pre], y[pre], 1)
    pre_trend_at_settle = float(np.exp(np.polyval(cb, tau[t2])))

    # Price change from the fitted peak to the fitted settle level. r ~ 1 can also arise
    # when the price merely goes sideways until the rising trend catches up (no dump).
    model_drop = float(np.exp(fit["b"] * (tau[t2] - tau[t1]) + d - h) - 1)

    shape = max(0.0, 1.0 - abs(r - 1.0) / 0.5)      # 1 at perfect reversion, 0 if |r-1| >= 0.5
    magnitude = min(1.0, h / 0.30)                   # saturates at a 30%+ (log) excess pump
    above_start = p_settle > p_start
    score = 100.0 * shape * np.sqrt(fit_gain * magnitude) * (1.0 if above_start else 0.5)

    return dict(
        has_pump=True, score=float(score), r=float(r), h=float(h), d=float(d),
        fit_gain=float(fit_gain), shape=float(shape), magnitude=float(magnitude),
        t0=t0, t1=t1, t2=t2,
        pump_days=t1 - t0, dump_days=t2 - t1,
        trend_cagr=float(np.exp(fit["b"] / (n - 1) * 252) - 1),
        p_start=float(p_start), p_peak=float(p_peak), p_settle=p_settle,
        pump_pct=float(p_peak / p_start - 1),
        pump_excess_pct=float(np.exp(h) - 1),
        peak_to_settle_pct=model_drop,
        settle_vs_start_pct=float(p_settle / p_start - 1),
        settle_vs_trend_pct=float(p_settle / trend_at_settle - 1),
        settle_vs_pretrend_pct=float(p_settle / pre_trend_at_settle - 1),
        above_start=bool(above_start),
        resid_sd=float(np.sqrt(fit["sse"] / max(1, fit["w1"] - fit["w0"] - 7))),
        _fit=fit,
    )


# ------------------------------------------------------------ significance --

def block_bootstrap_paths(y: np.ndarray, n_paths: int, mean_block: int, rng: np.random.Generator):
    """Stationary block bootstrap of daily log returns -> synthetic log-price paths.

    Keeps the stock's drift, volatility and short-range dependence but scrambles
    any longer-range shape, so it answers "how often would a random path with this
    stock's statistics look this much like a pump-and-revert?"
    """
    ret = np.diff(y)
    m = len(ret)
    paths = np.empty((n_paths, m + 1))
    p_new = 1.0 / mean_block
    for k in range(n_paths):
        idx = np.empty(m, dtype=int)
        i = rng.integers(m)
        for j in range(m):
            if j == 0 or rng.random() < p_new:
                i = rng.integers(m)
            else:
                i = (i + 1) % m
            idx[j] = i
        paths[k, 0] = y[0]
        paths[k, 1:] = y[0] + np.cumsum(ret[idx])
    return paths


def null_scores(y, cfg: FitConfig, n_paths=200, mean_block=20, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for path in block_bootstrap_paths(np.asarray(y, float), n_paths, mean_block, rng):
        s = score_series(path, cfg)
        out.append((s["score"], s["r"]))
    return np.array(out)


def classify(s: dict, p_value: float, cfg: FitConfig, alpha: float = 0.10):
    if not s["has_pump"]:
        return "no_pump", "No pump >= threshold above trend"
    r = s["r"]
    if r < 0:
        shape = "continued_rise"
    elif abs(r - 1) <= cfg.revert_band and s["peak_to_settle_pct"] > -cfg.min_drop:
        shape = "plateau_trend_catchup"
    elif abs(r - 1) <= cfg.revert_band and s["above_start"]:
        shape = "pump_revert"
    elif abs(r - 1) <= cfg.revert_band:
        shape = "pump_revert_below_start"
    elif r < 1 - cfg.revert_band:
        shape = "pump_hold" if r < 0.3 else "partial_revert"
    else:
        shape = "crash_below_trend"
    if shape == "pump_revert":
        verdict = "SUPPORTS" if p_value < alpha else "WEAK (not distinguishable from noise)"
    elif shape in ("plateau_trend_catchup", "pump_revert_below_start"):
        verdict = "PARTIAL"
    else:
        verdict = "CONTRADICTS"
    return shape, verdict


def config_dict(cfg: FitConfig):
    return asdict(cfg)
