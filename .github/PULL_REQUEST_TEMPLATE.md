<!--
This repository uses OR-Tools CP-SAT to generate kindergarten shift schedules.
Template fields and commands below follow the project's README to avoid confusion for contributors.
-->

# Title
Short, descriptive title for this change (e.g. "Adjust config and regenerate schedule CSV for July").

## Summary
One-sentence summary of what changed and why. Mention the affected config.yaml keys (if any) and the generated CSV filename.

## 1) Configuration / Conditions adjusted
- Files or settings changed (include exact paths and keys):
  - `config.yaml`: list any parent availability, partner, shift_blocks, parents_per_shift, or constraints you changed.
  - Example: `config.yaml: parents[2].available_days = ["Sun","Mon","Tue"]`
- Reason for the adjustment:
  - Brief explanation (availability update, fairness weight tweak, locked slots, etc.).

Notes (from this project README):
- The scheduler reads configuration from `config.yaml`. Hard constraints enforced by the solver include parent availability, parents_per_shift = 2, max_shifts_per_day, no consecutive shifts, and the couple early-week separation policy.
- If you change partner availability or couple_policy, describe the expected effect on solved schedules (e.g., more/fewer feasible pairings, fairness variance changes).

## 2) CSV generation & commit
Follow the exact commands in the README to reproduce your run locally.

- Create virtualenv and install dependencies:
```
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

- Generate the initial schedule CSV (matches README):
```
./venv/bin/python3 run.py --export-csv schedule.csv
```

- Partial regeneration (lock existing filled slots, solve only empty slots):
1. Edit `schedule.csv` and delete names only for the slots you want the solver to re-generate (leave fixed/locked slots intact).
2. Run:
```
./venv/bin/python3 run.py --input-csv schedule.csv --export-csv schedule.csv
```

- Syncing with Google Sheets (if used):
  - Place your Google Service Account key as `credentials.json` in the repo root.
  - Share the target Google Sheet with the service account email.
  - Run:
```
./venv/bin/python3 run.py --sync-gsheet
```

- CSV file(s) committed (path and commit/PR reference):
  - `schedule.csv` — commit: <commit-sha>

Project-specific CSV notes:
- The solver works on 2-hour shift blocks but the exported CSV/Google Sheet uses 30-minute rows (each 2-hour block expands into 4 rows between 09:00–18:00). Reviewers should expect repeated names for the same 2-hour block.
- Double-check you are editing the CSV in the 30-minute format when preparing partial regenerations.

## 3) Script output / Metrics
Paste the scheduler's full metrics output (or a representative excerpt) below. The README includes a sample metrics report — include at least the Parent Shift Distribution table and Fairness Variance.

```
=== SCHEDULING METRICS & FAIRNESS REPORT ===

Parent Shift Distribution:
Parent      Shifts  Hours       Avail Days    Shifts/Avail Day
--------  --------  --------  ------------  ------------------
Vit              6  12.0 hrs             6                1
... (paste full output here)

Fairness Variance (lower is better): 0.0139
Parent Pairing Counts:
Parent Pair      Times Scheduled Together
-------------  --------------------------
Eva & Klara                             2
...
```

## How to review / Test (explicit steps from README)
1. Verify the `config.yaml` changes listed in section 1.
2. Recreate the virtualenv and install requirements exactly as shown above.
3. Run `./venv/bin/python3 run.py --export-csv schedule.csv` and inspect `schedule.csv`.
4. For partial-regeneration PRs, confirm only intended slots were emptied before re-running and that previously filled slots remain unchanged after solve.
5. If the PR syncs to Google Sheets, verify `credentials.json` and sheet sharing are correct and inspect the Sheet after `--sync-gsheet`.
6. Compare pasted metrics to expected distribution and fairness variance.

## Risks / Rollback
- Known risks: accidentally overwriting `schedule.csv` or the Google Sheet when running `--export-csv` or `--sync-gsheet`. Always backup the current CSV/Sheet or make changes on a copy before syncing.
- Rollback: revert the config change commit and restore the previous `schedule.csv` from git history. For Google Sheets, restore from Google Sheets version history if necessary.

## Checklist
- [ ] I updated `config.yaml` and listed the exact changes above
- [ ] I generated `schedule.csv` using `./venv/bin/python3 run.py --export-csv schedule.csv` and committed it to the repo
- [ ] I pasted the scheduler's metrics output (see README sample format)
- [ ] For partial-regeneration: I confirmed locked slots remained unchanged and only empty slots were solved
- [ ] I verified Google Sheets sync steps and credentials (if applicable)
- [ ] Tests updated or added (if applicable)
- [ ] Documentation updated (README or other docs) if behavior changed
