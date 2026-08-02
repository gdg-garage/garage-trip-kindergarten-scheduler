<!--
Fill the sections below. Remove guidance comments (HTML comments) before finalizing if you like.
-->

# Title
Short, descriptive title for this change

## Summary
One-sentence summary of what changed and why.

## 1) Configuration / Conditions adjusted
- Files or settings changed:
  - e.g. path/to/config.yml: key = value
- Reason for the adjustment:
  - Brief explanation of why the config/conditions were changed

## 2) CSV generation & commit
- Command(s) used to generate the CSV:
```
# example
python scripts/generate_metrics.py --start 2026-07-01 --end 2026-07-31 --out data/metrics-2026-07.csv
```
- CSV file(s) committed (path(s) and commit hash/PR link if available):
  - e.g. data/metrics-2026-07.csv — commit: <commit-sha>

## 3) Script output / Metrics
Paste the full script output or the relevant metrics below (include logs, summary table, and any error/warning lines):

```
# Paste script output here
...
```

## How to review / Test
Step-by-step instructions for reviewers to validate the change:
1. Check config changes in <file(s)>.
2. Re-run the generation command: `...`
3. Confirm the CSV at `data/...csv` matches expected rows/columns and commit.
4. Verify metrics values in the pasted output.

## Risks / Rollback
- Known risks:
- Rollback plan (how to revert config or CSV if needed)

## Checklist
- [ ] I updated the configuration/conditions as described above
- [ ] I generated the CSV and committed it to the repo (path listed above)
- [ ] I pasted the script output / metrics in this PR
- [ ] Tests added or updated (if applicable)
- [ ] Documentation updated (if applicable)
