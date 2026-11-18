"""Write small synthetic raw files in the same formats as the real downloads.

The values are random. The formats (column names, header lines, codes for missing values,
wide Zillow layout, per-state ACS files) copy the real sources, so the parsers are tested.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from housing import config as C

SNAPSHOT = "2026-11-01"
# zip -> (state, metro, county_fips). Metro "" = rural ZIP with no metro.
ZIPS = {}
_rng = np.random.default_rng(7)
for i in range(24):
    county = "17031" if i < 16 else "17043"
    ZIPS[f"{60600 + i:05d}"] = ("IL", "Chicago-Naperville-Elgin, IL-IN-WI", county)
for i in range(18):
    ZIPS[f"{78700 + i:05d}"] = ("TX", "Austin-Round Rock-Georgetown, TX", "48453")
for i in range(6):
    ZIPS[f"{1001 + i:05d}"] = ("MA", "", "25013")  # leading zero ZIPs, rural
STATE_FIPS = {"IL": "17", "TX": "48", "MA": "25"}
LATE_ZIP = "78717"      # series starts in 2016
SPLIT_ZIP = "60601"     # ZCTA in two states (ACS) and two counties (crosswalk)


def _month_ends(start="2005-01", end="2026-10"):
    return pd.period_range(start, end, freq="M").to_timestamp(how="end").normalize()


def write_zillow(raw: Path):
    d = raw / "zillow" / SNAPSHOT
    d.mkdir(parents=True, exist_ok=True)
    dates = _month_ends()
    rows_v, rows_r = [], []
    for k, (zip_, (st, metro, _)) in enumerate(ZIPS.items()):
        drift = 0.002 + 0.004 * _rng.random()
        lv = np.log(200_000 * (1 + _rng.random())) + np.cumsum(
            drift + 0.006 * _rng.standard_normal(len(dates)))
        v = np.exp(lv)
        if zip_ == LATE_ZIP:
            v[dates < pd.Timestamp("2016-01-01")] = np.nan
        base = {"RegionID": 90000 + k, "SizeRank": k, "RegionName": int(zip_),
                "RegionType": "zip", "StateName": st, "State": st, "City": "Town",
                "Metro": metro or np.nan, "CountyName": "Some County"}
        rows_v.append({**base, **{d_.strftime("%Y-%m-%d"): x for d_, x in zip(dates, v)}})
        r = v / 160 * (1 + 0.01 * _rng.standard_normal(len(dates)))
        r[dates < pd.Timestamp("2015-01-01")] = np.nan
        rows_r.append({**base, **{d_.strftime("%Y-%m-%d"): x for d_, x in zip(dates, r)}})
    pd.DataFrame(rows_v).to_csv(d / "zhvi.csv", index=False)
    pd.DataFrame(rows_r).to_csv(d / "zori.csv", index=False)


def write_fred(raw: Path):
    d = raw / "fred"
    d.mkdir(parents=True, exist_ok=True)
    wk = pd.date_range("2004-01-01", "2026-11-12", freq="W-THU")
    m = pd.DataFrame({"observation_date": wk.strftime("%Y-%m-%d"),
                      "MORTGAGE30US": np.round(4 + np.sin(np.arange(len(wk)) / 80), 2).astype(object)})
    m.loc[5, "MORTGAGE30US"] = "."  # FRED code for missing
    m.to_csv(d / "MORTGAGE30US.csv", index=False)
    mo = pd.date_range("2004-01-01", "2026-10-01", freq="MS")
    for s, base in (("UNRATE", 5.0), ("CPIAUCSL", 250.0)):
        pd.DataFrame({"observation_date": mo.strftime("%Y-%m-%d"),
                      s: base + np.arange(len(mo)) * 0.01}).to_csv(d / f"{s}.csv", index=False)


def _acs_rows(year: int, zips: list[str], pop_scale=1.0):
    header = ["NAME"] + list(C.ACS_VARS) + ["zip code tabulation area"]
    rows = [header]
    for z in zips:
        vals = []
        for v in C.ACS_VARS:
            x = int(1000 * pop_scale * (1 + _rng.random()) + (year - 2010) * 10)
            vals.append(str(x))
        rows.append([f"ZCTA5 {z}"] + vals + [z])
    return rows


def write_acs(raw: Path):
    d = raw / "acs"
    d.mkdir(parents=True, exist_ok=True)
    for y in C.ACS_YEARS:
        if y < 2020:  # older vintages: per-state files (national query refused)
            for st, fips in STATE_FIPS.items():
                zs = [z for z, v in ZIPS.items() if v[0] == st]
                rows = _acs_rows(y, zs)
                if st == "IL":
                    rows[1][list(C.ACS_VARS).index("B19013_001E") + 1] = "-666666666"
                (d / f"acs5_{y}_st{fips}.json").write_text(json.dumps(rows))
            # the split ZCTA also shows up in IN with a small population part
            small = _acs_rows(y, [SPLIT_ZIP], pop_scale=0.01)
            (d / f"acs5_{y}_st18.json").write_text(json.dumps(small))
        else:
            (d / f"acs5_{y}_national.json").write_text(json.dumps(_acs_rows(y, list(ZIPS))))


def write_irs(raw: Path):
    d = raw / "irs"
    d.mkdir(parents=True, exist_ok=True)
    for y in C.IRS_YEARS:
        if y == 2015:
            continue  # a missing year must be skipped
        recs = []
        for z, (st, _, _) in ZIPS.items():
            for stub in range(1, 7):
                recs.append({"STATEFIPS": STATE_FIPS[st], "STATE": st, "zipcode": int(z),
                             "agi_stub": stub, "N1": 100 + stub, "A00100": 5000 * stub})
        for special in (0, 99999):
            recs.append({"STATEFIPS": "17", "STATE": "IL", "zipcode": special, "agi_stub": 1,
                         "N1": 10**6, "A00100": 10**9})
        df = pd.DataFrame(recs)
        if y >= 2018:
            df.columns = [c.upper() for c in df.columns]  # case changes between years
        df.to_csv(d / f"{y}zpallagi.csv", index=False)


def write_bps(raw: Path):
    d = raw / "bps"
    d.mkdir(parents=True, exist_ok=True)
    counties = sorted({v[2] for v in ZIPS.values()})
    h1 = ("Survey,FIPS,FIPS,Region,Division,County,,1-unit,,,2-units,,,3-4 units,,,"
          "5+ units,,,1-unit rep,,,2-units rep,,,3-4 units rep,,,5+ units rep,,")
    h2 = ("Date,State,County,Code,Code,Name,Bldgs,Units,Value,Bldgs,Units,Value,Bldgs,Units,"
          "Value,Bldgs,Units,Value,Bldgs,Units,Value,Bldgs,Units,Value,Bldgs,Units,Value,"
          "Bldgs,Units,Value")
    for y in C.BPS_YEARS:
        lines = [h1, h2, ""]
        for c in counties:
            u1, u2, u3, u5 = 100 + y % 7, 4, 6, 50 + y % 5
            vals = [u1, u1, u1 * 300, 2, u2, 900, 2, u3, 1200, 3, u5, 9000] + [0] * 12
            lines.append(",".join([str(y), c[:2], c[2:], "2", "3", f"County {c}"]
                                  + [str(v) for v in vals]))
        (d / f"co{y}a.txt").write_text("\n".join(lines) + "\n")


def write_qcew(raw: Path):
    d = raw / "qcew"
    d.mkdir(parents=True, exist_ok=True)
    counties = sorted({v[2] for v in ZIPS.values()})
    for y in C.QCEW_YEARS:
        recs = []
        for c in counties + ["17999"]:
            for own, agg in (("0", "70"), ("5", "71")):
                recs.append({"area_fips": c, "own_code": own, "industry_code": "10",
                             "agglvl_code": agg, "size_code": 0, "year": y, "qtr": "A",
                             "disclosure_code": "", "annual_avg_estabs": 10,
                             "annual_avg_emplvl": 1000 + y, "total_annual_wages": 1,
                             "avg_annual_pay": 50000 + 100 * (y - 2013)})
        pd.DataFrame(recs).to_csv(d / f"{y}_county_total.csv", index=False)


def write_crosswalk(raw: Path):
    d = raw / "crosswalk"
    d.mkdir(parents=True, exist_ok=True)
    cols = ["OID_ZCTA5_20", "GEOID_ZCTA5_20", "NAMELSAD_ZCTA5_20", "AREALAND_ZCTA5_20",
            "AREAWATER_ZCTA5_20", "MTFCC_ZCTA5_20", "CLASSFP_ZCTA5_20", "FUNCSTAT_ZCTA5_20",
            "OID_COUNTY_20", "GEOID_COUNTY_20", "NAMELSAD_COUNTY_20", "AREALAND_COUNTY_20",
            "AREAWATER_COUNTY_20", "MTFCC_COUNTY_20", "CLASSFP_COUNTY_20", "FUNCSTAT_COUNTY_20",
            "AREALAND_PART", "AREAWATER_PART"]
    lines = ["|".join(cols)]

    def row(z, county, part):
        return "|".join(["1", z, f"ZCTA5 {z}", "100", "0", "G6350", "B5", "S", "2", county,
                         "X County", "1000", "0", "G4020", "H1", "A", str(part), "0"])
    for z, (_, _, county) in ZIPS.items():
        lines.append(row(z, county, 900))
    lines.append(row(SPLIT_ZIP, "17097", 100))       # smaller part in another county
    lines.append(row("", "17099", 50))               # county part with no ZCTA
    (d / "zcta_county_2020.txt").write_text("\n".join(lines) + "\n")


def write_all(data_dir: Path):
    raw = Path(data_dir) / "raw"
    for fn in (write_zillow, write_fred, write_acs, write_irs, write_bps, write_qcew,
               write_crosswalk):
        fn(raw)
