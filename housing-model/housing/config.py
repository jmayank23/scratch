"""Settings for the ZIP-by-month training table.

Every source has:
  - a URL (or URL template),
  - the years to fetch,
  - a release lag, so that a feature is used only after its public release date.

Change values here, not in the code.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------- paths
DATA_DIR = Path(os.environ.get("HOUSING_DATA_DIR", "data")).resolve()
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
OUT_DIR = DATA_DIR / "out"

# Generic client name. Some hosts (irs.gov, bls.gov) refuse requests with no User-Agent.
USER_AGENT = "housing-model-build/0.1 (research script)"

# ---------------------------------------------------------------- panel
PANEL_START = "2012-01-01"  # first month kept in the output table
HORIZON_MONTHS = 12         # label = 12-month forward log growth of ZHVI

# ---------------------------------------------------------------- Zillow (target)
# Zillow publishes only the latest revision. We keep a dated snapshot of each download.
ZILLOW = {
    "zhvi": "https://files.zillowstatic.com/research/public_csvs/zhvi/"
            "Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv",
    "zori": "https://files.zillowstatic.com/research/public_csvs/zori/"
            "Zip_zori_uc_sfrcondomfr_sm_month.csv",
}
# ZHVI for month t is published in the middle of month t+1.
# So the row for month t is "decided" at month t+1, and every feature must be
# public on or before that decision month.
ZILLOW_RELEASE_LAG_MONTHS = 1

# ---------------------------------------------------------------- FRED (national macro)
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
# series -> months after the end of the data month until the value is public
FRED_SERIES = {
    "MORTGAGE30US": 1,  # weekly; monthly mean is complete at month end
    "UNRATE": 1,        # released first Friday of the next month
    "CPIAUCSL": 2,      # released mid next month; 2 is conservative
}

# ---------------------------------------------------------------- Census ACS 5-year (ZCTA)
ACS_URL = "https://api.census.gov/data/{year}/acs/acs5"
ACS_YEARS = list(range(2012, 2025))  # vintage = last year of the 5-year window
ACS_VARS = {
    "B01003_001E": "pop",
    "B19013_001E": "med_hh_income",
    "B25077_001E": "med_home_value",
    "B25064_001E": "med_gross_rent",
    "B25003_001E": "occ_units",
    "B25003_002E": "owner_occ_units",
    "B25003_003E": "renter_occ_units",
    "B25001_001E": "housing_units",
    "B01002_001E": "med_age",
    "B15003_001E": "pop_25plus",
    "B15003_022E": "edu_bachelors",
    "B15003_023E": "edu_masters",
    "B15003_024E": "edu_professional",
    "B15003_025E": "edu_doctorate",
}
# Release month of each ACS 5-year vintage (first of the month, YYYY-MM).
# The 2020 vintage was late because of the pandemic.
ACS_RELEASE = {
    2011: "2012-12", 2012: "2013-12", 2013: "2014-12", 2014: "2015-12",
    2015: "2016-12", 2016: "2017-12", 2017: "2018-12", 2018: "2019-12",
    2019: "2020-12", 2020: "2022-03", 2021: "2022-12", 2022: "2023-12",
    2023: "2024-12", 2024: "2026-01",
}
# Two-digit state FIPS codes (50 states + DC + PR). Used if the national ZCTA query fails.
STATE_FIPS = [
    "01", "02", "04", "05", "06", "08", "09", "10", "11", "12", "13", "15", "16", "17",
    "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31",
    "32", "33", "34", "35", "36", "37", "38", "39", "40", "41", "42", "44", "45", "46",
    "47", "48", "49", "50", "51", "53", "54", "55", "56", "72",
]

# ---------------------------------------------------------------- IRS SOI ZIP income
IRS_URL = "https://www.irs.gov/pub/irs-soi/{yy}zpallagi.csv"
IRS_YEARS = list(range(2011, 2024))  # tax years
# ASSUMPTION: ZIP data for tax year Y is public about 30 months after Dec of Y.
# Check the release dates on the IRS SOI page and change this if needed.
IRS_LAG_MONTHS = 30

# ---------------------------------------------------------------- Census Building Permits (county, annual)
BPS_URL = "https://www2.census.gov/econ/bps/County/co{year}a.txt"
BPS_YEARS = list(range(2010, 2026))
BPS_RELEASE_MONTH = 5  # annual county file for year Y is public about May of Y+1

# ---------------------------------------------------------------- BLS QCEW (county, annual)
QCEW_URL = "https://data.bls.gov/cew/data/api/{year}/a/industry/10.csv"
QCEW_YEARS = list(range(2013, 2026))
QCEW_RELEASE_MONTH = 9  # annual averages for year Y are public about September of Y+1

# ---------------------------------------------------------------- crosswalk
# Census 2020 ZCTA-to-county relationship file (pipe-delimited).
ZCTA_COUNTY_URL = ("https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/"
                   "tab20_zcta520_county20_natl.txt")

# ---------------------------------------------------------------- backtest
TEST_YEARS = list(range(2016, 2026))
PURGE_MONTHS = HORIZON_MONTHS
