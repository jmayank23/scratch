"""Checks on the built table, and a data card.

Hard checks (the command fails if one fails):
  1. Release dates: for every source, available_month <= decision_month on every row.
  2. Label: label_g12 equals log ZHVI(t+12) - log ZHVI(t), checked on a sample against
     the normalized Zillow table.
  3. Momentum: zhvi_g12 uses only months <= t, checked the same way.
  4. No label column is in the feature list.
  5. Keys: (zip, month) is unique.

Soft checks (written to the data card): row and ZIP counts, null share per column,
rows per year, file size.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from . import config as C


def run_checks(data_dir: Path, sample: int = 20000) -> list[str]:
    interim, out = Path(data_dir) / "interim", Path(data_dir) / "out"
    panel = out / "panel.parquet"
    spec = json.loads((out / "columns.json").read_text())
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{panel}')")
    fails: list[str] = []
    h = C.HORIZON_MONTHS

    # 1. release dates
    for c in [c for c in spec["meta"] if c.endswith("_available_month")]:
        bad = con.execute(f"SELECT count(*) FROM p WHERE {c} > decision_month").fetchone()[0]
        if bad:
            fails.append(f"leakage: {bad:,} rows have {c} after decision_month")

    # 2 and 3. label and momentum against the source table
    con.execute(f"""
    CREATE VIEW z AS SELECT zip, CAST(month AS DATE) AS month, zhvi
    FROM read_parquet('{interim / "zhvi.parquet"}')
    """)
    row = con.execute(f"""
    WITH s AS (SELECT zip, month, label_g12, zhvi_g12 FROM p USING SAMPLE {int(sample)} ROWS)
    SELECT
      max(abs(s.label_g12 - (ln(f.zhvi) - ln(c.zhvi)))) AS label_err,
      max(abs(s.zhvi_g12 - (ln(c.zhvi) - ln(b.zhvi)))) AS mom_err,
      count(*) FILTER (WHERE s.label_g12 IS NOT NULL AND f.zhvi IS NULL) AS label_wo_future
    FROM s
    JOIN z c ON c.zip = s.zip AND c.month = s.month
    LEFT JOIN z f ON f.zip = s.zip AND f.month = CAST(s.month + INTERVAL {h} MONTH AS DATE)
    LEFT JOIN z b ON b.zip = s.zip AND b.month = CAST(s.month - INTERVAL 12 MONTH AS DATE)
    """).fetchone()
    label_err, mom_err, label_wo_future = row
    if label_err is not None and label_err > 1e-9:
        fails.append(f"label: max error {label_err:.3g} against ZHVI(t+{h})")
    if label_wo_future:
        fails.append(f"label: {label_wo_future} rows have a label but no ZHVI at t+{h}")
    if mom_err is not None and mom_err > 1e-9:
        fails.append(f"momentum: max error {mom_err:.3g} against ZHVI(t-12)")

    # 4. label not in features
    leaked = [c for c in spec["features"] if c.startswith("label")]
    if leaked:
        fails.append(f"features include label columns: {leaked}")

    # 5. unique keys
    dup = con.execute("SELECT count(*) - count(DISTINCT (zip, month)) FROM p").fetchone()[0]
    if dup:
        fails.append(f"keys: {dup:,} duplicate (zip, month) rows")

    _data_card(con, spec, panel, out / "data_card.md", fails)
    con.close()
    return fails


def _data_card(con, spec, panel: Path, dest: Path, fails: list[str]):
    n, nz, m0, m1, nl = con.execute("""
        SELECT count(*), count(DISTINCT zip), min(month), max(month), count(label_g12)
        FROM p""").fetchone()
    by_year = con.execute("""
        SELECT year(month) y, count(*) n, count(DISTINCT zip) zips, count(label_g12) labeled
        FROM p GROUP BY 1 ORDER BY 1""").fetchall()
    cols = spec["features"] + spec["labels"]
    nulls = con.execute("SELECT " + ", ".join(
        f'avg(CASE WHEN "{c}" IS NULL THEN 1.0 ELSE 0 END)' for c in cols) + " FROM p").fetchone()
    lines = [
        "# Data card: ZIP-by-month training table", "",
        f"- File: `{panel.name}`, {panel.stat().st_size / 1e9:.2f} GB",
        f"- Zillow snapshot: {spec.get('zillow_snapshot')}",
        f"- Sources joined: {', '.join(spec['sources']) or 'Zillow only'}",
        f"- Rows: {n:,}; ZIPs: {nz:,}; months: {m0} to {m1}",
        f"- Rows with a label: {nl:,} (the last {spec['horizon_months']} months have none)",
        f"- Features: {len(spec['features'])}", "",
        "## Checks", "",
        *(["- All hard checks passed."] if not fails else [f"- FAIL: {f}" for f in fails]), "",
        "## Rows per year", "", "| year | rows | ZIPs | labeled |", "|---|---|---|---|",
        *[f"| {y} | {r:,} | {z:,} | {lab:,} |" for y, r, z, lab in by_year], "",
        "## Null share per column", "", "| column | null share |", "|---|---|",
        *[f"| {c} | {v:.1%} |" for c, v in sorted(zip(cols, nulls), key=lambda t: -t[1])], "",
        "## Known limits", "",
        "- Zillow revises history. This table uses one snapshot. Keep each monthly snapshot.",
        "- ZIP is treated as ZCTA. They are close but not the same.",
        "- Each ZIP gets one county: the county with the largest land part of the ZCTA.",
        "- Release lags for IRS, BPS and QCEW are estimates in config.py.",
    ]
    dest.write_text("\n".join(lines) + "\n")
    print(f"[check] data card: {dest}")
