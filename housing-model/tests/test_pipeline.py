"""End-to-end and unit tests on synthetic raw files (no network)."""
from __future__ import annotations

import json
import shutil

import duckdb
import numpy as np
import pandas as pd
import pytest

from housing import config as C
from housing.baseline import run_baselines
from housing.build import build
from housing.checks import run_checks
from housing.fetch import Fetcher
from housing.normalize import normalize_all, parse_bps
from housing.splits import rolling_folds, split_frame

from . import synth


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    synth.write_all(d)
    normalize_all(d)
    build(d)
    return d


def _panel(d):
    return pd.read_parquet(d / "out" / "panel.parquet")


def _zhvi(d):
    return pd.read_parquet(d / "interim" / "zhvi.parquet")


# ---------------------------------------------------------------- end to end

def test_checks_pass(built):
    assert run_checks(built) == []
    assert (built / "out" / "data_card.md").exists()


def test_baseline_runs(built):
    res = run_baselines(built)
    assert set(res) == {"mom12", "mom3", "random"}
    assert res["mom12"], "baseline produced no test years"
    assert (built / "out" / "baseline_report.md").exists()


def test_all_sources_joined(built):
    spec = json.loads((built / "out" / "columns.json").read_text())
    assert set(spec["sources"]) == {"zori", "crosswalk", "acs", "irs", "bps", "qcew", "fred"}
    assert spec["zillow_snapshot"] == synth.SNAPSHOT
    assert not [c for c in spec["features"] if c.startswith("label")]
    assert "zhvi" not in spec["features"]  # raw level kept as meta; log level is a feature


# ---------------------------------------------------------------- label and momentum

def test_label_and_momentum_values(built):
    p, z = _panel(built), _zhvi(built)
    zip_, month = "78705", pd.Timestamp("2018-06-01")
    zz = z[z.zip == zip_].set_index("month")["zhvi"]
    row = p[(p.zip == zip_) & (p.month == month)].iloc[0]
    assert row.label_g12 == pytest.approx(np.log(zz[pd.Timestamp("2019-06-01")] / zz[month]))
    assert row.zhvi_g12 == pytest.approx(np.log(zz[month] / zz[pd.Timestamp("2017-06-01")]))
    assert row.decision_month == pd.Timestamp("2018-07-01")


def test_label_is_group_demeaned(built):
    p = _panel(built)
    g = p.dropna(subset=["label_g12_dm"]).groupby(["grp", "month"])["label_g12_dm"].mean()
    assert g.abs().max() < 1e-9


def test_last_months_have_no_label(built):
    p = _panel(built)
    last = p.month.max()
    assert p.loc[p.month > last - pd.DateOffset(months=12), "label_g12"].isna().all()
    assert p.loc[p.month == last - pd.DateOffset(months=12), "label_g12"].notna().any()


def test_late_series_starts_late(built):
    p = _panel(built)
    late = p[p.zip == synth.LATE_ZIP]
    assert late.month.min() == pd.Timestamp("2016-01-01")
    first = late.sort_values("month").iloc[0]
    assert pd.isna(first.zhvi_g12)  # no history before the series starts


def test_rural_zip_uses_state_group(built):
    p = _panel(built)
    assert set(p.loc[p.zip == "01001", "grp"]) == {"state:MA"}


# ---------------------------------------------------------------- release dates (as-of joins)

def test_acs_vintage_respects_release(built):
    p = _panel(built).set_index(["zip", "month"])
    # 2020 vintage is released 2022-03. Decision month 2022-02 (row month 2022-01) must
    # still use the 2019 vintage; decision month 2022-03 uses 2020.
    assert p.loc[("60605", pd.Timestamp("2022-01-01")), "acs_vintage"] == 2019
    assert p.loc[("60605", pd.Timestamp("2022-02-01")), "acs_vintage"] == 2020


def test_irs_skips_missing_year(built):
    p = _panel(built)
    years = set(p["irs_tax_year"].dropna().astype(int))
    assert 2015 not in years and 2014 in years and 2016 in years


def test_county_and_national_features(built):
    p = _panel(built).set_index(["zip", "month"])
    r = p.loc[("60601", pd.Timestamp("2020-06-01"))]
    assert r.county_fips == "17031"               # largest land part wins
    # decision month 2020-07: BPS 2019 is public (2020-05), QCEW 2019 is not (2020-09)
    assert r.bps_year == 2019
    assert r.qcew_year == 2018
    assert r.fred_mortgage30us_available_month <= r.decision_month


def test_county_peer_mean_excludes_self(built):
    p = _panel(built)
    m = p[p.month == pd.Timestamp("2019-01-01")]
    c = m[m.county_fips == "17043"]
    z0 = c.iloc[0]
    others = c[c.zip != z0.zip]["zhvi_g12"]
    assert z0.county_g12_ex_self == pytest.approx(others.mean())


# ---------------------------------------------------------------- parsers

def test_acs_split_zcta_keeps_largest_part(built):
    a = pd.read_parquet(built / "interim" / "acs.parquet")
    s = a[(a.zip == synth.SPLIT_ZIP) & (a.vintage == 2015)]
    assert len(s) == 1 and s.iloc[0]["pop"] > 500  # the small IN part had pop about 10


def test_acs_negative_codes_become_null(built):
    a = pd.read_parquet(built / "interim" / "acs.parquet")
    assert (a["med_hh_income"].dropna() >= 0).all()
    assert a["med_hh_income"].isna().any()


def test_irs_drops_total_rows_and_sums_stubs(built):
    irs = pd.read_parquet(built / "interim" / "irs.parquet")
    assert not irs.zip.isin(["00000", "99999"]).any()
    one = irs[(irs.zip == "01001") & (irs.tax_year == 2012)].iloc[0]
    assert one.irs_returns == sum(100 + s for s in range(1, 7))


def test_qcew_keeps_county_totals_only(built):
    q = pd.read_parquet(built / "interim" / "qcew.parquet")
    assert not q.county_fips.str.endswith("999").any()
    assert q.groupby(["county_fips", "year"]).size().max() == 1


def test_bps_header_check():
    with pytest.raises(ValueError):
        parse_bps("a,b,c\n1,2,3\n", 2020)
    good = parse_bps((
        "Survey,FIPS,FIPS,Region,Division,County,,1-unit,,,2-units,,,3-4 units,,,5+ units,,\n"
        "Date,State,County,Code,Code,Name,Bldgs,Units,Value,Bldgs,Units,Value,Bldgs,Units,"
        "Value,Bldgs,Units,Value\n\n"
        "2020,17,031,2,3,Cook County,10,10,1,2,4,1,1,3,1,5,90,1\n"), 2020)
    assert good.iloc[0].county_fips == "17031"
    assert good.iloc[0].bps_units_total == 10 + 4 + 3 + 90
    assert good.iloc[0].bps_units_5plus == 90


# ---------------------------------------------------------------- the checks catch errors

def test_leakage_check_fails_on_future_feature(built, tmp_path):
    d = tmp_path / "data"
    shutil.copytree(built, d)
    con = duckdb.connect()
    f = d / "out" / "panel.parquet"
    con.execute(f"""COPY (SELECT * REPLACE (CAST(acs_available_month + INTERVAL 24 MONTH AS DATE)
                        AS acs_available_month) FROM read_parquet('{f}'))
                    TO '{d}/out/tmp.parquet' (FORMAT parquet)""")
    (d / "out" / "tmp.parquet").replace(f)
    fails = run_checks(d)
    assert any("leakage" in x and "acs_available_month" in x for x in fails)


def test_label_check_fails_on_shifted_label(built, tmp_path):
    d = tmp_path / "data"
    shutil.copytree(built, d)
    f = d / "out" / "panel.parquet"
    p = pd.read_parquet(f)
    p["label_g12"] = p.groupby("zip")["label_g12"].shift(-1)  # a 13-month label by mistake
    p.to_parquet(f, index=False)
    assert any(x.startswith("label") for x in run_checks(d))


# ---------------------------------------------------------------- folds

def test_rolling_folds_purge():
    f = rolling_folds([2020])[0]
    assert f["train_end"] == pd.Timestamp("2018-12-01")  # 2020-01 minus 13 months
    df = pd.DataFrame({"month": pd.date_range("2017-01-01", "2021-01-01", freq="MS")})
    df["label_g12_dm"] = 0.0
    tr, te = split_frame(df, f)
    assert tr.month.max() == pd.Timestamp("2018-12-01")
    assert te.month.min() == pd.Timestamp("2020-01-01") and te.month.max() == pd.Timestamp("2020-12-01")


# ---------------------------------------------------------------- fetch

class _Resp:
    def __init__(self, code, body=b"x"):
        self.status_code, self.body = code, body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, n):
        yield self.body


def test_fetch_skips_404_and_keeps_existing(tmp_path, monkeypatch):
    f = Fetcher(tmp_path)
    monkeypatch.setattr(f.session, "get", lambda *a, **k: _Resp(404))
    assert f.get("https://example.invalid/a", tmp_path / "raw" / "a.csv") is None
    monkeypatch.setattr(f.session, "get", lambda *a, **k: _Resp(200, b"hello"))
    p = f.get("https://example.invalid/b", tmp_path / "raw" / "b.csv")
    assert p.read_bytes() == b"hello"
    monkeypatch.setattr(f.session, "get", lambda *a, **k: _Resp(200, b"changed"))
    assert f.get("https://example.invalid/b", p).read_bytes() == b"hello"  # not downloaded again
    lines = (tmp_path / "raw" / "manifest.jsonl").read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[1])["sha256"]
