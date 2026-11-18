# Data sources

[← docs index](README.md)

All URLs, years and lags are in [`housing/config.py`](../housing/config.py).

## Sources in the build

| Source | Level | Frequency | Years | Public after | Columns |
|---|---|---|---|---|---|
| Zillow ZHVI | ZIP | monthly | 2000+ | month t: mid t+1 | label, zhvi_* momentum, peer context |
| Zillow ZORI | ZIP | monthly | 2015+ | month t: mid t+1 | zori, zori_g12, price_to_rent |
| Census ACS 5-year | ZCTA | yearly | vintages 2012-2024 | per vintage, see `ACS_RELEASE` | acs_* |
| IRS SOI ZIP income | ZIP | yearly | tax years 2011-2023 | about 30 months after the tax year (assumed) | irs_* |
| Census Building Permits | county | yearly | 2010+ | May of next year (assumed) | bps_* |
| BLS QCEW | county | yearly | 2013+ | September of next year (assumed) | qcew_* |
| FRED | national | monthly | 2004+ | 1 or 2 months, per series | fred_* |
| Census ZCTA-county file | ZCTA → county | static (2020) | | | county_fips |

## Assumptions to confirm on real files

| Item | Assumption | Where |
|---|---|---|
| BPS file layout | Two header lines; units columns at positions 7, 10, 13, 16 | `parse_bps` in `housing/normalize.py` |
| IRS release lag | 30 months after December of the tax year | `IRS_LAG_MONTHS` |
| BPS release month | May of the next year | `BPS_RELEASE_MONTH` |
| QCEW release month | September of the next year | `QCEW_RELEASE_MONTH` |
| ACS ZCTA query | National query works for newer vintages; older ones need one query per state | `fetch_acs` |

## Known limits

- **Zillow revisions:** Zillow changes past values and publishes only the latest
  version. The build uses one snapshot. Keep each monthly snapshot
  (`data/raw/zillow/YYYY-MM-DD/`) to measure the effect.
- **ZIP and ZCTA:** close but not the same. PO-box ZIPs have no ACS values.
- **One county per ZIP:** the county with the largest land part of the ZCTA, not the
  largest population part.
- **Static files:** the crosswalk is from 2020. Do not add static risk maps (flood,
  wildfire) as if they were known in earlier years.

## Do not filter ZIPs by past growth

Do not keep only ZIPs that grew over the last 10 years. That uses the future to pick
training rows, so the backtest looks better than it is. Keep all ZIPs.

## Sources to add

In about this order (Phase 2 in [plan.md](plan.md)):

1. **FHFA ZIP5 HPI** (yearly, repeat sales): a second price signal.
2. **HMDA** (yearly, tract): loan counts, amounts, buyer income.
3. **Census ZCTA shapes**: adjacency graph for neighbor features.
4. **NOAA climate normals and FEMA NRI**: only with dated versions.
5. **Policy and zoning events**: hand-coded, with a public date for each event.
