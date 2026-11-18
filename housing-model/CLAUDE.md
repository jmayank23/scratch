# Rules for Claude Code in housing-model

## How to write (Mayank's preferences for technical work)

- Write replies and docs in ASD-STE100 Simplified Technical English.
- Use indentation when it makes a reply clearer.
- Use visuals (Mermaid or ASCII diagrams, tables) when you explain how something works.
- Keep docs in layers: the top `README.md` is high level and points to subdirectory
  READMEs, which have more detail. Each level links one level deeper and back up.
  When you add a folder, add its README and link it from the level above.

## Repo rules

- This folder is on branch `housing-model` of the `scratch` repo. Keep `main` empty.
- Do not commit `data/`.
- Run `python -m pytest -q` before each commit.

## Model rules (do not break)

- A feature joins only by its public release month (`available_month <= decision_month`).
  `python -m housing check` must pass.
- A model uses only `columns.json` → `features`. Never `label_*` or meta columns.
- Do not filter ZIPs by past or future growth.
- Train with the folds in `housing/splits.py` (13-month purge).
- When a real file does not parse: change `tests/synth.py` to match the real format,
  then fix the parser. Do not loosen a check.

## Where to read next

- Plan and phases: `docs/plan.md`
- Sources and assumptions: `docs/data-sources.md`
- Target, folds and metrics: `docs/backtest.md`
- Code map: `housing/README.md`
