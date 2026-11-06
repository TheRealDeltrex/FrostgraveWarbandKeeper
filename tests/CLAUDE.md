# tests/

- `conftest.py` points `FWK_DATA_DIR` at a fresh temp dir before importing `warband_store`,
  so tests never touch real data. `fresh_warband` is a valid Elementalist with a legal
  8-spell starting pick.
- CI (`.github/workflows/test.yml`, Windows, Python 3.14) runs the full suite on pushes and
  PRs to `devversion`. Playwright isn't installed there, so `test_create_warband_submit.py`
  skips: a green run has no browser coverage.
- When a change alters what a helper returns, grep the suite for that helper rather than
  trusting a green targeted run.
