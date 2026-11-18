"""Turn raw files into tidy Parquet tables in data/interim/.

Each table has a key (zip or county_fips), a time column, and `available_month`:
the first month in which the values were public. The build joins on that column.

A source with no raw files is skipped, and the build leaves its columns out.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C


def _month(s) -> pd.Series:
    """Any date-like value -> first day of its month (datetime64)."""
    return pd.to_datetime(s).dt.to_period("M").dt.to_timestamp()


def _add_months(ts: pd.Series, n: int) -> pd.Series:
    return (ts.dt.to_period("M") + n).dt.to_timestamp()


def _write(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"  wrote {path.name}: {len(df):,} rows, {df.shape[1]} cols")


# ---------------------------------------------------------------- Zillow

def latest_zillow_snapshot(raw: Path) -> Path | None:
    snaps = sorted(p for p in (raw / "zillow").glob("*") if p.is_dir())
    return snaps[-1] if snaps else None


ZILLOW_ID_COLS = ["RegionID", "SizeRank", "RegionName", "RegionType", "StateName",
                  "State", "City", "Metro", "CountyName"]


def zillow_long(path: Path, value_name: str) -> pd.DataFrame:
    w = pd.read_csv(path, dtype={"RegionName": str})
    date_cols = [c for c in w.columns if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c)]
    ids = [c for c in ZILLOW_ID_COLS if c in w.columns]
    long = w.melt(id_vars=ids, value_vars=date_cols, var_name="date", value_name=value_name)
    long["zip"] = long["RegionName"].str.strip().str.zfill(5)
    long["month"] = _month(long["date"])
    long = long.rename(columns={"Metro": "metro", "State": "state", "City": "city",
                                "CountyName": "county_name"})
    keep = ["zip", "month", value_name] + [c for c in ["state", "metro", "city", "county_name"]
                                           if c in long.columns]
    long = long[keep].sort_values(["zip", "month"])
    # Keep the full monthly grid from the first non-null value onward. Gaps stay as nulls,
    # so that a lag of k rows is always a lag of k months.
    first = long.dropna(subset=[value_name]).groupby("zip")["month"].min().rename("first")
    long = long.merge(first, on="zip")
    long = long[long["month"] >= long["first"]].drop(columns="first")
    return long.reset_index(drop=True)


def norm_zillow(raw: Path, out: Path):
    snap = latest_zillow_snapshot(raw)
    if snap is None:
        raise FileNotFoundError("no Zillow snapshot: run `python -m housing fetch --only zillow`")
    print(f"  Zillow snapshot: {snap.name}")
    zhvi = zillow_long(snap / "zhvi.csv", "zhvi")
    _write(zhvi, out / "zhvi.parquet")
    (out / "zillow_snapshot.txt").write_text(snap.name)
    if (snap / "zori.csv").exists():
        zori = zillow_long(snap / "zori.csv", "zori")[["zip", "month", "zori"]]
        _write(zori, out / "zori.parquet")


# ---------------------------------------------------------------- FRED

def norm_fred(raw: Path, out: Path):
    rows = []
    for s, lag in C.FRED_SERIES.items():
        p = raw / "fred" / f"{s}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        date_col = "observation_date" if "observation_date" in df.columns else df.columns[0]
        df = df.rename(columns={date_col: "date", df.columns[1]: "value"})
        df["value"] = pd.to_numeric(df["value"], errors="coerce")  # FRED uses "." for missing
        df["month"] = _month(df["date"])
        m = df.groupby("month", as_index=False)["value"].mean().sort_values("month")
        m["chg12"] = m["value"] - m["value"].shift(12)
        m["series"] = s
        m["available_month"] = _add_months(m["month"], lag)
        rows.append(m)
    if rows:
        _write(pd.concat(rows, ignore_index=True), out / "fred.parquet")


# ---------------------------------------------------------------- ACS

def _acs_frame(path: Path) -> pd.DataFrame:
    data = json.loads(path.read_text())
    df = pd.DataFrame(data[1:], columns=data[0])
    zcol = [c for c in df.columns if c.startswith("zip code tabulation area")][0]
    df["zip"] = df[zcol].str.zfill(5)
    for v in C.ACS_VARS:
        if v in df.columns:
            x = pd.to_numeric(df[v], errors="coerce")
            df[v] = x.where(x >= 0)  # Census uses large negative codes for "no estimate"
    return df[["zip"] + [v for v in C.ACS_VARS if v in df.columns]]


def norm_acs(raw: Path, out: Path):
    frames = []
    for y in C.ACS_YEARS:
        nat = raw / "acs" / f"acs5_{y}_national.json"
        parts = [nat] if nat.exists() else sorted((raw / "acs").glob(f"acs5_{y}_st*.json"))
        if not parts:
            continue
        df = pd.concat([_acs_frame(p) for p in parts], ignore_index=True)
        # A ZCTA that crosses a state line comes back once per state. Keep the part with
        # the largest population.
        df = (df.sort_values("B01003_001E", ascending=False, na_position="last")
                .drop_duplicates("zip"))
        df["vintage"] = y
        frames.append(df)
    if not frames:
        return
    a = pd.concat(frames, ignore_index=True).rename(columns=C.ACS_VARS)
    a["owner_share"] = a["owner_occ_units"] / a["occ_units"]
    a["vacancy_rate"] = 1 - a["occ_units"] / a["housing_units"]
    edu = ["edu_bachelors", "edu_masters", "edu_professional", "edu_doctorate"]
    a["bach_plus_share"] = a[edu].sum(axis=1, min_count=1) / a["pop_25plus"]
    a = a.drop(columns=edu + ["pop_25plus", "owner_occ_units", "renter_occ_units"])
    a = a.sort_values(["zip", "vintage"])
    for c in ["pop", "med_hh_income", "med_home_value", "med_gross_rent", "housing_units"]:
        a[f"{c}_chg_1v"] = a.groupby("zip")[c].pct_change(fill_method=None)
    a["available_month"] = pd.to_datetime(a["vintage"].map(C.ACS_RELEASE) + "-01")
    a = a.dropna(subset=["available_month"])
    a = a.replace([np.inf, -np.inf], np.nan)
    _write(a.reset_index(drop=True), out / "acs.parquet")


# ---------------------------------------------------------------- IRS SOI

def norm_irs(raw: Path, out: Path):
    frames = []
    for y in C.IRS_YEARS:
        p = raw / "irs" / f"{y}zpallagi.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype=str, encoding="latin-1")
        df.columns = [c.strip().lower() for c in df.columns]
        need = {"zipcode", "n1", "a00100"}
        if not need <= set(df.columns):
            print(f"  WARN IRS {y}: missing columns {need - set(df.columns)}; skipped")
            continue
        df["zipcode"] = df["zipcode"].str.strip().str.zfill(5)
        df = df[~df["zipcode"].isin(["00000", "99999"])]
        for c in ["n1", "a00100"]:
            df[c] = pd.to_numeric(df[c].str.replace(",", ""), errors="coerce")
        g = df.groupby("zipcode", as_index=False)[["n1", "a00100"]].sum()
        g["tax_year"] = y
        frames.append(g)
    if not frames:
        return
    irs = pd.concat(frames, ignore_index=True).rename(
        columns={"zipcode": "zip", "n1": "irs_returns", "a00100": "irs_agi_k"})
    irs["irs_agi_per_return"] = irs["irs_agi_k"] * 1000 / irs["irs_returns"]
    irs = irs.sort_values(["zip", "tax_year"])
    for c in ["irs_returns", "irs_agi_per_return"]:
        irs[f"{c}_yoy"] = irs.groupby("zip")[c].pct_change(fill_method=None)
    dec = pd.to_datetime(irs["tax_year"].astype(str) + "-12-01")
    irs["available_month"] = _add_months(dec, C.IRS_LAG_MONTHS)
    irs = irs.replace([np.inf, -np.inf], np.nan)
    _write(irs.reset_index(drop=True), out / "irs.parquet")


# ---------------------------------------------------------------- Building permits

def parse_bps(text: str, year: int) -> pd.DataFrame:
    """Parse a Census BPS county annual file (coYYYYa.txt).

    ASSUMED layout (two header lines, then data rows):
      0 date, 1 state FIPS, 2 county FIPS, 3 region, 4 division, 5 name,
      6-8 1-unit (bldgs, units, value), 9-11 2-units, 12-14 3-4 units, 15-17 5+ units,
      then the same groups for "reported" counts.
    The header check below stops the build if the layout is different.
    """
    rows = list(csv.reader(io.StringIO(text)))
    header = " ".join(",".join(r) for r in rows[:2]).lower()
    if "units" not in header or "county" not in header:
        raise ValueError(f"BPS {year}: header does not look like the expected layout")
    recs = []
    for r in rows:
        if len(r) < 18 or not re.fullmatch(r"\d{4,6}", r[0].strip()):
            continue
        try:
            u = [float(r[i] or 0) for i in (7, 10, 13, 16)]
        except ValueError:
            continue
        recs.append({"county_fips": r[1].strip().zfill(2) + r[2].strip().zfill(3),
                     "year": year, "bps_units_total": sum(u), "bps_units_5plus": u[3],
                     "bps_units_1unit": u[0]})
    return pd.DataFrame(recs)


def norm_bps(raw: Path, out: Path):
    frames = []
    for y in C.BPS_YEARS:
        p = raw / "bps" / f"co{y}a.txt"
        if p.exists():
            frames.append(parse_bps(p.read_text(encoding="latin-1"), y))
    if not frames:
        return
    b = pd.concat(frames, ignore_index=True).sort_values(["county_fips", "year"])
    b["bps_units_yoy"] = b.groupby("county_fips")["bps_units_total"].pct_change(fill_method=None)
    b["bps_share_5plus"] = b["bps_units_5plus"] / b["bps_units_total"]
    b["available_month"] = pd.to_datetime((b["year"] + 1).astype(str)
                                          + f"-{C.BPS_RELEASE_MONTH:02d}-01")
    b = b.replace([np.inf, -np.inf], np.nan)
    _write(b.reset_index(drop=True), out / "bps.parquet")


# ---------------------------------------------------------------- QCEW

def norm_qcew(raw: Path, out: Path):
    frames = []
    for y in C.QCEW_YEARS:
        p = raw / "qcew" / f"{y}_county_total.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, dtype={"area_fips": str, "own_code": str, "agglvl_code": str})
        df = df[(df["own_code"].str.strip() == "0") & (df["agglvl_code"].str.strip() == "70")]
        df = df[~df["area_fips"].str.endswith("999")]
        frames.append(pd.DataFrame({
            "county_fips": df["area_fips"].str.zfill(5), "year": y,
            "qcew_emp": pd.to_numeric(df["annual_avg_emplvl"], errors="coerce"),
            "qcew_avg_pay": pd.to_numeric(df["avg_annual_pay"], errors="coerce"),
        }))
    if not frames:
        return
    q = pd.concat(frames, ignore_index=True).sort_values(["county_fips", "year"])
    for c in ["qcew_emp", "qcew_avg_pay"]:
        q[f"{c}_yoy"] = q.groupby("county_fips")[c].pct_change(fill_method=None)
    q["available_month"] = pd.to_datetime((q["year"] + 1).astype(str)
                                          + f"-{C.QCEW_RELEASE_MONTH:02d}-01")
    q = q.replace([np.inf, -np.inf], np.nan)
    _write(q.reset_index(drop=True), out / "qcew.parquet")


# ---------------------------------------------------------------- crosswalk

def norm_crosswalk(raw: Path, out: Path):
    """ZIP (as ZCTA) -> one county: the county with the largest land area of the ZCTA."""
    p = raw / "crosswalk" / "zcta_county_2020.txt"
    if not p.exists():
        return
    df = pd.read_csv(p, sep="|", dtype=str)
    df = df[df["GEOID_ZCTA5_20"].notna() & (df["GEOID_ZCTA5_20"].str.strip() != "")]
    df["part"] = pd.to_numeric(df["AREALAND_PART"], errors="coerce").fillna(0)
    df = df.sort_values("part", ascending=False).drop_duplicates("GEOID_ZCTA5_20")
    xw = pd.DataFrame({"zip": df["GEOID_ZCTA5_20"].str.zfill(5),
                       "county_fips": df["GEOID_COUNTY_20"].str.zfill(5)})
    _write(xw.reset_index(drop=True), out / "zip_county.parquet")


STEPS = {
    "zillow": norm_zillow, "fred": norm_fred, "acs": norm_acs, "irs": norm_irs,
    "bps": norm_bps, "qcew": norm_qcew, "crosswalk": norm_crosswalk,
}


def normalize_all(data_dir: Path):
    raw, out = Path(data_dir) / "raw", Path(data_dir) / "interim"
    for name, fn in STEPS.items():
        print(f"[normalize] {name}")
        fn(raw, out)
