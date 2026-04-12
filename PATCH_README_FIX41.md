# PATCH_README_FIX41

## Fixed

- Fixed `/api/v1/trades` crash caused by inconsistent variable names in trade journal builders:
  - closed-position entries now read `strategy` from `pos`
  - open-fill entries now read `strategy` from `trade`
- Added defensive skipping in `/api/v1/trades` item assembly so one malformed row does not crash the whole trades page.

## Verification

- `python3 -m compileall -q backend` passed.
