# Evidence

Every line below was produced by a command run against this exact checkout, on this machine, at the time recorded. Nothing here is copied from the README.

| | |
| --- | --- |
| Generated | 2026-10-19 09:38 |
| Python | 3.14.7 |
| Platform | Windows 11 |

## Test suite

```sh
python -m pytest -q
```

- exit code **0**
- 80 passed in 81.99s (0:01:21)

## Static gates

| Gate | Exit | Last line |
| --- | --- | --- |
| `ruff check` | 0 | All checks passed! |
| `ruff format --check` | 0 | 25 files already formatted |
| `mypy src` | 0 | Success: no issues found in 16 source files |
| `bandit -c pyproject.toml -r src` | 0 | — |

## Live route walk

The application was imported through `wsgi.py` and each GET path declared in `openapi/` was requested once through the Werkzeug test client.

| Status | Path | Bytes | Content-Type |
| --- | --- | --- | --- |
| 200 | `/api/health` | 38 | application/json |
| 200 | `/api/runs` | 10991 | application/json |
| 404 | `/api/runs/{id}/stream` | 51 | application/json |

3 paths walked, 0 of them raised or answered 5xx.

## CLI

```
usage: gpt-load [-h] {run,report,compare} ...

positional arguments:
  {run,report,compare}

options:
  -h, --help            show this help message and exit
```

## Screenshots

Captured from the running service with headless Chromium at 1440x900 and committed with the repository:

| File | Bytes |
| --- | --- |
| `docs/assets/screens/compare.png` | 21,934 |
| `docs/assets/screens/healthz.png` | 8,454 |
| `docs/assets/screens/history.png` | 21,789 |
| `docs/assets/screens/livez.png` | 7,468 |
| `docs/assets/screens/metrics.png` | 15,220 |
| `docs/assets/screens/readyz.png` | 7,880 |
| `docs/assets/screens/root.png` | 35,134 |
| `docs/assets/screens/version.png` | 26,863 |

## Charts

Generated from the same measurements the README quotes: `coverage-modules.svg`, `coverage.svg`, `files.svg`, `latency.svg`, `loc.svg`, `payload.svg`, `tests.svg`.

## What this file does not prove

- It is not a load test: every request is a single uncached call from one process.
- A green suite is not a coverage claim; `pytest --cov` reports the number the README quotes.
- The route walk exercises GET paths only; mutating routes are covered by the suite.
