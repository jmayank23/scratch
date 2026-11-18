# Backtest rules

[← docs index](README.md)

## Target

```
label_g12    = log ZHVI(t+12) - log ZHVI(t)
label_g12_dm = label_g12 - mean(label_g12) over the same group and month
group        = metro, or "state:XX" for a ZIP with no metro
```

Score the model as a ranking inside each month, not as a price forecast.

## The release-date rule

```
row month t ──► decision_month = t + 1   (ZHVI for t is published mid t+1)
                     │
                     ├─ ZHVI history up to t          (momentum features)
                     ├─ ACS vintage released <= t+1   (for example 2020 vintage: 2022-03)
                     ├─ IRS tax year released <= t+1
                     ├─ permits and jobs for years released <= t+1
                     └─ FRED month m, after its lag
```

The build uses an ASOF join: for each row, the latest release with
`available_month <= decision_month`. `python -m housing check` fails if a row breaks
this rule.

## Folds

```
             train rows                 purge (13 months)     test year
|──────────────────────────────────|─────────────────────|────────────────|
                          train_end = T - 13          T = Jan of test year
```

A training row at month t has a label that is public only at t + 13 (12-month horizon
+ 1-month release lag). So the last training row for a test year that starts at T is
T − 13. `housing/splits.py` makes one fold per test year, 2016 to 2025.

## Metrics

Per test month, then averaged per test year:

| Metric | Meaning | Random |
|---|---|---|
| Spearman | Rank correlation of score and `label_g12_dm` | about 0 |
| Top-10% hit | Share of the score's top 10% that is also in the label's top 10% | about 0.10 |

Compare years one by one. 2020 to 2022 behaved differently from other years.

## Baselines a model must beat

| Name | Score |
|---|---|
| mom12 | `zhvi_g12_rel_grp`: last 12-month growth minus the group mean |
| mom3 | `zhvi_g3`: last 3-month growth |
| random | a random number |
