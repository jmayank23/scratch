"""Build the ZIP-by-month training table with DuckDB.

One row = one ZIP in one month t.
  - decision_month = t + 1 (ZHVI for month t is public in month t+1).
  - label_g12      = log ZHVI(t+12) - log ZHVI(t).
  - label_g12_dm   = label_g12 minus the mean of its group (metro, or state if no metro)
                     in the same month. This is the ranking target.
  - Every non-Zillow feature comes from an ASOF join: the latest release with
    available_month <= decision_month. So no feature uses data that was not public yet.

Output: data/out/panel.parquet and data/out/columns.json (which columns are features).
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb

from . import config as C


def _has(p: Path) -> bool:
    return p.exists()


def _view(con, name: str, path: Path, renames: dict[str, str], prefix: str,
          keys: tuple[str, ...], date_cols: tuple[str, ...] = ("available_month",)):
    """Create a view with prefixed column names and DATE-typed time columns."""
    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()]
    sel = []
    for c in cols:
        new = renames.get(c, c if c in keys else f"{prefix}{c}")
        expr = f'CAST("{c}" AS DATE)' if c in date_cols else f'"{c}"'
        sel.append(f'{expr} AS "{new}"')
    con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT {', '.join(sel)} "
                f"FROM read_parquet('{path}')")


def build(data_dir: Path, threads: int | None = None) -> Path:
    interim, out = Path(data_dir) / "interim", Path(data_dir) / "out"
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    if threads:
        con.execute(f"SET threads = {int(threads)}")
    h, lag = C.HORIZON_MONTHS, C.ZILLOW_RELEASE_LAG_MONTHS
    sources = []

    # ------------------------------------------------------------ 1. price panel and label
    zhvi = interim / "zhvi.parquet"
    if not _has(zhvi):
        raise FileNotFoundError("data/interim/zhvi.parquet is missing: run normalize first")
    print("[build] price panel and label")
    con.execute(f"""
    CREATE TABLE p AS
    WITH z AS (
        SELECT zip, CAST(month AS DATE) AS month, zhvi,
               ln(CASE WHEN zhvi > 0 THEN zhvi END) AS lz,
               state, metro, city, county_name
        FROM read_parquet('{zhvi}')
    ), w AS (
        SELECT *,
            lz - lag(lz, 1)  OVER w AS zhvi_g1,
            lz - lag(lz, 3)  OVER w AS zhvi_g3,
            lz - lag(lz, 6)  OVER w AS zhvi_g6,
            lz - lag(lz, 12) OVER w AS zhvi_g12,
            lag(lz, 12) OVER w - lag(lz, 24) OVER w AS zhvi_g12_prev,
            lz - lag(lz, 60) OVER w AS zhvi_g60,
            lz - max(lz) OVER (PARTITION BY zip ORDER BY month
                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS zhvi_drawdown,
            lead(lz, {h}) OVER w - lz AS label_g12
        FROM z
        WINDOW w AS (PARTITION BY zip ORDER BY month)
    )
    SELECT * EXCLUDE (lz), lz AS zhvi_log,
           CAST(month + INTERVAL {lag} MONTH AS DATE) AS decision_month,
           coalesce(metro, 'state:' || state) AS grp
    FROM w
    WHERE zhvi IS NOT NULL
    """)

    # ------------------------------------------------------------ 2. rent (same release as ZHVI)
    zori = interim / "zori.parquet"
    if _has(zori):
        print("[build] rent")
        sources.append("zori")
        con.execute(f"""
        CREATE TABLE r AS
        SELECT zip, CAST(month AS DATE) AS month, zori,
               ln(zori) - lag(ln(zori), 12) OVER (PARTITION BY zip ORDER BY month) AS zori_g12
        FROM read_parquet('{zori}') WHERE zori > 0
        """)
        con.execute("""
        CREATE OR REPLACE TABLE p AS
        SELECT p.*, r.zori, r.zori_g12, p.zhvi / (r.zori * 12) AS price_to_rent
        FROM p LEFT JOIN r USING (zip, month)
        """)

    # ------------------------------------------------------------ 3. county key
    xw = interim / "zip_county.parquet"
    if _has(xw):
        sources.append("crosswalk")
        con.execute(f"""
        CREATE OR REPLACE TABLE p AS
        SELECT p.*, x.county_fips FROM p
        LEFT JOIN read_parquet('{xw}') x USING (zip)
        """)
    else:
        con.execute("ALTER TABLE p ADD COLUMN county_fips VARCHAR")

    # ------------------------------------------------------------ 4. peer context (same month)
    print("[build] peer context")
    con.execute("""
    CREATE OR REPLACE TABLE p AS
    SELECT *,
        zhvi_g12 - avg(zhvi_g12) OVER g AS zhvi_g12_rel_grp,
        count(zhvi_g12) OVER g AS grp_n_zips,
        (sum(zhvi_g12) OVER c - coalesce(zhvi_g12, 0))
            / nullif(count(zhvi_g12) OVER c - CAST(zhvi_g12 IS NOT NULL AS INT), 0)
            AS county_g12_ex_self,
        label_g12 - avg(label_g12) OVER g AS label_g12_dm
    FROM p
    WINDOW g AS (PARTITION BY grp, month),
           c AS (PARTITION BY county_fips, month)
    """)

    # ------------------------------------------------------------ 5. ASOF joins, ZIP level
    def asof(view: str, key: str | None, src: str):
        on = f"p.{key} = s.{key} AND " if key else ""
        excl = f"EXCLUDE ({key})" if key else ""
        con.execute(f"""
        CREATE OR REPLACE TABLE p AS
        SELECT p.*, s.* {excl}
        FROM p ASOF LEFT JOIN {view} s
          ON {on}p.decision_month >= s.{src}_available_month
        """)

    acs = interim / "acs.parquet"
    if _has(acs):
        print("[build] ACS (ZIP, as-of release)")
        sources.append("acs")
        _view(con, "acs_v", acs, {"available_month": "acs_available_month"}, "acs_", ("zip",))
        asof("acs_v", "zip", "acs")

    irs = interim / "irs.parquet"
    if _has(irs):
        print("[build] IRS (ZIP, as-of release)")
        sources.append("irs")
        _view(con, "irs_v", irs, {"available_month": "irs_available_month",
                                  "tax_year": "irs_tax_year"}, "", ("zip",))
        asof("irs_v", "zip", "irs")

    # ------------------------------------------------------------ 6. ASOF joins, county level
    for name, prefix in (("bps", "bps_"), ("qcew", "qcew_")):
        f = interim / f"{name}.parquet"
        if _has(f):
            print(f"[build] {name} (county, as-of release)")
            sources.append(name)
            _view(con, f"{name}_v", f, {"available_month": f"{name}_available_month",
                                        "year": f"{name}_year"}, "", ("county_fips",))
            asof(f"{name}_v", "county_fips", name)

    # ------------------------------------------------------------ 7. ASOF joins, national
    fred = interim / "fred.parquet"
    if _has(fred):
        print("[build] FRED (national, as-of release)")
        sources.append("fred")
        series = [r[0] for r in con.execute(
            f"SELECT DISTINCT series FROM read_parquet('{fred}') ORDER BY 1").fetchall()]
        for s in series:
            k = s.lower()
            con.execute(f"""
            CREATE OR REPLACE VIEW fred_{k} AS
            SELECT CAST(available_month AS DATE) AS fred_{k}_available_month,
                   value AS fred_{k}, chg12 AS fred_{k}_chg12
            FROM read_parquet('{fred}') WHERE series = '{s}'
            """)
            asof(f"fred_{k}", None, f"fred_{k}")

    # ------------------------------------------------------------ 8. write
    print("[build] write")
    # DATE columns are written as TIMESTAMP, so pandas reads them as datetime64.
    date_cols = [r[0] for r in con.execute("DESCRIBE p").fetchall() if r[1] == "DATE"]
    repl = ", ".join(f'CAST("{c}" AS TIMESTAMP) AS "{c}"' for c in date_cols)
    con.execute(f"""
    CREATE OR REPLACE TABLE p AS
    SELECT * REPLACE ({repl}) FROM p WHERE month >= DATE '{C.PANEL_START}' ORDER BY month, zip
    """)
    cols = [r[0] for r in con.execute("DESCRIBE p").fetchall()]
    ids = ["zip", "month", "decision_month", "state", "metro", "city", "county_name",
           "county_fips", "grp"]
    labels = [c for c in cols if c.startswith("label_")]
    meta = [c for c in cols if c.endswith("_available_month") or c in
            ("acs_vintage", "irs_tax_year", "bps_year", "qcew_year", "zhvi")]
    feats = [c for c in cols if c not in set(ids) | set(labels) | set(meta)]
    snap = (interim / "zillow_snapshot.txt")
    spec = {"ids": [c for c in ids if c in cols], "labels": labels, "meta": meta,
            "features": feats, "sources": sources,
            "zillow_snapshot": snap.read_text().strip() if snap.exists() else None,
            "horizon_months": h, "release_lag_months": lag}
    (out / "columns.json").write_text(json.dumps(spec, indent=2))
    dest = out / "panel.parquet"
    con.execute(f"COPY p TO '{dest}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 200000)")
    n = con.execute("SELECT count(*) FROM p").fetchone()[0]
    print(f"[build] {dest}: {n:,} rows, {len(cols)} columns, {len(feats)} features")
    con.close()
    return dest
