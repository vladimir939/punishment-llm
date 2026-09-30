# data/

Empty until collection runs.

- `raw.csv` — written by the harness (`python -m harness --sync|--batch`).
  Append-only, flushed per row. Column meanings are in the root README.
- `humans.csv` — produced by `survey/import_forms.py` from the two Google Forms
  exports. Long format: one row per respondent per condition.

Do not hand-edit either file. The harness uses `raw.csv` as its resume index —
an edited row can cause a cell to be silently skipped or re-run.

Raw Google Forms exports (`survey/responses_v1.csv`, `responses_v2.csv`) carry
submission timestamps and must not be committed; `.gitignore` covers them.
