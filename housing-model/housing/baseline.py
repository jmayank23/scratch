"""Momentum baselines and the backtest metrics.

A real model must beat these. Each score ranks ZIPs within one month:
  - mom12: zhvi_g12_rel_grp (last 12-month growth, minus the group mean)
  - mom3:  zhvi_g3
  - random: a random number (the floor)

Metrics per test month, against label_g12_dm (12-month forward growth minus group mean):
  - spearman: rank correlation of score and label
  - top10_hit: share of the score's top 10% that is also in the label's top 10%
               (random = about 0.10)
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from . import config as C

SCORES = {"mom12": "zhvi_g12_rel_grp", "mom3": "zhvi_g3", "random": "random()"}


def backtest_sql(score_expr: str, panel: str) -> str:
    years = ", ".join(str(y) for y in C.TEST_YEARS)
    return f"""
    WITH d AS (
        SELECT month, label_g12_dm AS y, {score_expr} AS s
        FROM read_parquet('{panel}')
        WHERE label_g12_dm IS NOT NULL AND year(month) IN ({years})
    ), d2 AS (SELECT * FROM d WHERE s IS NOT NULL),
    r AS (
        SELECT month,
               rank() OVER (PARTITION BY month ORDER BY s) AS rs,
               rank() OVER (PARTITION BY month ORDER BY y) AS ry,
               ntile(10) OVER (PARTITION BY month ORDER BY s DESC) AS ds,
               ntile(10) OVER (PARTITION BY month ORDER BY y DESC) AS dy
        FROM d2
    ), m AS (
        SELECT month, corr(rs, ry) AS spearman,
               avg(CASE WHEN dy = 1 THEN 1.0 ELSE 0 END) FILTER (WHERE ds = 1) AS top10_hit,
               count(*) AS n
        FROM r GROUP BY month
    )
    SELECT year(month) AS year, avg(spearman) AS spearman, avg(top10_hit) AS top10_hit,
           avg(n) AS zips_per_month
    FROM m GROUP BY 1 ORDER BY 1
    """


def run_baselines(data_dir: Path) -> dict:
    out = Path(data_dir) / "out"
    panel = str(out / "panel.parquet")
    con = duckdb.connect()
    con.execute("SELECT setseed(0.42)")
    results = {name: con.execute(backtest_sql(expr, panel)).fetchall()
               for name, expr in SCORES.items()}
    con.close()

    lines = ["# Baseline backtest", "",
             "Target: 12-month forward log growth of ZHVI, minus the metro (or state) mean.",
             "Higher is better. A model must beat mom12 in most years.", ""]
    for name, rows in results.items():
        lines += [f"## {name}", "", "| year | spearman | top-10% hit | ZIPs per month |",
                  "|---|---|---|---|"]
        lines += [f"| {y} | {s:.3f} | {t:.3f} | {n:,.0f} |" for y, s, t, n in rows
                  if s is not None and t is not None]
        if rows:
            ss = [r[1] for r in rows if r[1] is not None]
            tt = [r[2] for r in rows if r[2] is not None]
            if ss and tt:
                lines += [f"| all | {sum(ss)/len(ss):.3f} | {sum(tt)/len(tt):.3f} | |"]
        lines.append("")
    (out / "baseline_report.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return results
