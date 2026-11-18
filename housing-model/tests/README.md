# Tests

[← back to the top README](../README.md)

Run: `python -m pytest -q` (no network, about 5 seconds).

## Synthetic data

`synth.py` writes small raw files in the same formats as the real downloads:

| File | Format details it copies |
|---|---|
| Zillow ZHVI, ZORI | Wide CSV, month-end date columns, ZIP as an integer (leading zeros lost) |
| FRED | `observation_date` column, `.` for a missing value, weekly mortgage series |
| ACS | Census API JSON; per-state files for old vintages; a ZCTA split across two states; `-666666666` for no estimate |
| IRS | `agi_stub` rows per ZIP, total rows for ZIP 0 and 99999, upper-case columns in later years, one missing year |
| BPS | Two header lines and a blank line, then fixed column positions |
| QCEW | `own_code` and `agglvl_code` rows, a `xx999` unknown county |
| Crosswalk | Pipe-delimited, a ZCTA in two counties, a row with no ZCTA |

The values are random. Only the formats are real.

## What the tests check

| Area | Tests |
|---|---|
| End to end | All checks pass; baselines run; all sources join |
| Label and momentum | Values match ZHVI; label is demeaned per group; last 12 months have no label |
| Release dates | ACS vintage changes at its release month; county and national joins use release months |
| Parsers | Split ZCTA keeps the larger part; negative codes become null; IRS stubs sum; QCEW keeps county totals; BPS header check |
| The checks themselves | A planted future feature and a shifted label both make `check` fail |
| Folds | The 13-month purge |
| Fetch | Skips 404; does not download a file again; writes the manifest |

## When a real file does not parse

Change the writer in `synth.py` to match the real format first. Then fix the parser
until the tests pass. Do not loosen a check to make a test pass.
