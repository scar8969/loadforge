<p align="center">
  <img src="docs/assets/screens/root.png" alt="loadforge running" width="900">
</p>

<h1 align="center">loadforge</h1>

<p align="center"><b>Load-test an OpenAI-compatible endpoint and get percentiles, not vibes.</b></p>

<p align="center">
  <a href="https://github.com/scar8969/loadforge/actions/workflows/ci.yml"><img src="https://github.com/scar8969/loadforge/actions/workflows/ci.yml/badge.svg" alt="ci"></a> <a href="#quality-gates"><img src="https://img.shields.io/badge/tests-80%20passed-2ea44f" alt="tests: 80 passed"></a> <a href="#quality-gates"><img src="https://img.shields.io/badge/coverage-97.8%-brightgreen" alt="coverage: 97.8%"></a> <a href="#api"><img src="https://img.shields.io/badge/routes-10%20live-0969da" alt="routes: 10 live"></a> <a href="#requirements"><img src="https://img.shields.io/badge/python-3.11%2B-3776ab" alt="python: 3.11+"></a> <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-2ea44f" alt="license: MIT"></a>
</p>

loadforge drives concurrent chat-completion traffic at any OpenAI-compatible API, records a sample per request, and reports p50/p95/p99 latency, throughput and token cost per run. Runs are stored in SQLite so you can compare two configurations after the fact instead of arguing about which one felt faster.

---

**Contents** &nbsp;·&nbsp; [Why](#why-this-exists) &nbsp;·&nbsp; [What it does](#what-it-does) &nbsp;·&nbsp; [Quickstart](#quickstart) &nbsp;·&nbsp; [Screenshots](#screenshots) &nbsp;·&nbsp; [API](#api) &nbsp;·&nbsp; [CLI](#cli) &nbsp;·&nbsp; [Configuration](#configuration) &nbsp;·&nbsp; [Measured](#measured-not-estimated) &nbsp;·&nbsp; [How a request flows](#how-a-request-flows) &nbsp;·&nbsp; [Architecture](#architecture) &nbsp;·&nbsp; [Quality gates](#quality-gates) &nbsp;·&nbsp; [Development](#development) &nbsp;·&nbsp; [Deploy](#deploy) &nbsp;·&nbsp; [Limits](#limits-stated-rather-than-hidden)

## Why this exists

Most load generators tell you requests per second and stop there. What you actually need before raising a rate limit or switching a model is the tail: how bad p99 gets, how many requests error, and what the run cost in tokens. loadforge records every sample and derives those numbers from the samples, so the summary can be re-derived from the rows.

## What it does

| Capability | How it works |
| --- | --- |
| **Scenario-driven traffic** | Declarative scenarios with prompt sets, concurrency, duration and ramp; the engine schedules them and streams samples back as they land. |
| **Percentiles from samples** | p50/p95/p99, throughput and error rate computed over stored samples, not estimated from a counter. |
| **Token accounting** | Prompt and completion tokens counted per request (tiktoken when available), rolled up into a per-run cost. |
| **Live progress over SSE** | GET /api/runs/<id>/stream is a server-sent event stream, so a browser or curl sees samples as they arrive. |
| **Run history and diff** | Every run persists; the CLI compares two runs field by field. |
| **HTML dashboard** | A server-rendered page starts a run and shows the live table without a JavaScript build step. |

## Quickstart

```sh
git clone https://github.com/scar8969/loadforge.git
cd loadforge
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python wsgi.py                                 # http://127.0.0.1:8000
```

It is up when this answers:

```sh
curl -s http://127.0.0.1:8000/api/health
```

## Screenshots

Captured from the running service with headless Chromium at 1440×900, one image per page, committed under [`docs/assets/screens/`](docs/assets/screens/).

<table>
<tr>
<td width="50%"><img src="docs/assets/screens/compare.png" alt="/compare" width="100%"><br><sub><code>/compare</code> &middot; 21.4 KB</sub></td>
<td width="50%"><img src="docs/assets/screens/history.png" alt="/history" width="100%"><br><sub><code>/history</code> &middot; 21.3 KB</sub></td>
</tr>
</table>

The other 5 captures — the health, liveness, readiness, metrics and version endpoints — are committed in the same folder rather than shown here.

## API

Every route below is declared in [`openapi/loadforge.yaml`](openapi/loadforge.yaml) and exercised by the live probe recorded in [`docs/EVIDENCE.md`](docs/EVIDENCE.md).

| Method | Path | What it does |
| --- | --- | --- |
| `GET` | `/api/health` | liveness probe |
| `GET` | `/api/runs` | list runs, newest first |
| `POST` | `/api/runs` | create a run and start it in the background |
| `GET` | `/api/runs/{id}/stream` | server-sent event stream of samples for one run |
| `POST` | `/api/runs/{id}/stop` | stop a running load test |
| `POST` | `/run` | start a run from the HTML form |
| `POST` | `/runs/{id}/stop` | stop a run from the HTML form |
| `POST` | `/runs/{id}/delete` | delete a stored run and its samples |

## CLI

The same operations without an HTTP client. Installed as `loadforge`, and runnable from a checkout with no install:

```sh
python -m gpt_load.cli --help
```

```text
usage: gpt-load [-h] {run,report,compare} ...

positional arguments:
  {run,report,compare}

options:
  -h, --help            show this help message and exit
```

## Configuration

Environment only — there is no config file. Copy `.env.example` to `.env` and edit; `APP_ENV=production` refuses to start without `SECRET_KEY`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_ENV` | `development` | development \| staging \| production; production enforces the secret. |
| `SECRET_KEY` | `change-me-in-production` | Session/CSRF signing key. Required when APP_ENV=production. |
| `HOST` | `0.0.0.0` | Interface the dev server binds. |
| `PORT` | `8000` | Port the dev server and the container listen on. |
| `DEBUG` | `false` | Flask debug mode. Never true in production. |
| `MAX_CONTENT_LENGTH` | `8388608` | Largest accepted request body, in bytes. |
| `DATA_DIR` | `(empty)` | Where uploaded and generated files live. |
| `INSTANCE_DIR` | `(empty)` | Where the SQLite file and instance state live. |
| `LOG_DIR` | `(empty)` | Where rotated log files are written, if file logging is on. |
| `LOG_LEVEL` | `INFO` | DEBUG \| INFO \| WARNING \| ERROR. |
| `LOG_JSON` | `true` | true emits one JSON object per line; false is human-readable. |
| `REQUEST_ID_HEADER` | `X-Request-ID` | Header echoed on every response and stamped on every log line. |

## Measured, not estimated

Produced on this checkout by `pytest --cov` and by booting `wsgi.py` and issuing one real GET per documented path. The commands are recorded in [`docs/EVIDENCE.md`](docs/EVIDENCE.md).

| Signal | Value |
| --- | --- |
| Tests | **80 / 80 passed** (31.4 s, exit 0) |
| Line coverage | **97.8%** — 733 of 737 statements |
| Source | 16 files / 1,656 lines |
| Test code | 9 files / 1,425 lines |
| Documented paths | 7 in the spec, 3 GET |
| Live probe | 11 GET requests to the booted app, **10 answered 200** |
| Median latency | **22.7 ms** (single uncached request, dev server) |
| Slowest / fastest | 167.8 ms `/` / 6.3 ms `/readyz` |
| Bytes served | 17.5 KB across 11 responses |
| Screenshots | 8 captured |

## How a request flows

```text
client
  │  HTTP
  ▼
wsgi.py ──▶ gpt_load/app.py:get_app()
                │  reads config once (gpt_load/config.py)
                │  registers the blueprints
                ▼
           route handler
             ├──▶ gpt_load/models.py        tables, via Flask-SQLAlchemy
             ├──▶ gpt_load/errors.py        raises typed errors → one JSON envelope
             └──▶ gpt_load/observability.py JSON log line + X-Request-ID
```

Every response carries `X-Request-ID`, and the matching log line is written once at the end of the request with the status and duration, so a report of "it failed" is one `grep` away from the traceback.

## Architecture

```
loadforge/
├── src/gpt_load/
│   ├── http.py                         381  HTTP plumbing for gpt_load: correlation ids, access 
│   ├── _app.py                         256  The project's own Flask application: models, routes 
│   ├── config.py                       171  Environment-driven configuration for gpt_load
│   ├── observability.py                169  Structured logging and request correlation for gpt_l
│   ├── cli.py                          146  
│   ├── app.py                          119  Application factory for gpt_load
│   ├── errors.py                       108  Typed application errors and their HTTP mapping for 
│   ├── loadgen/engine.py                80  
│   ├── models.py                        64  
│   ├── paths.py                         55  Filesystem layout for gpt_load
│   ├── loadgen/metrics.py               42  
│   ├── loadgen/ratelimit.py             39  
├── openapi/loadforge.yaml                 the contract of record
├── schema/loadforge.sql                   the DDL
├── tests/                       the suite that has to stay green
├── docs/EVIDENCE.md             the recorded live route walk
├── Dockerfile                   multi-stage build
└── wsgi.py                      entry point
```

The package keeps one shape across the service: `config.py` reads the environment once, `observability.py` emits structured JSON logs carrying a request id, `errors.py` turns exceptions into a single JSON envelope, `models.py` holds the tables, and the blueprints under `src/` hold the routes.

## Quality gates

| Gate | Command | Threshold |
| --- | --- | --- |
| Suite | `pytest -q` | all green |
| Coverage | `pytest --cov` | floor in `pyproject.toml`, set below the measured value |
| Lint | `ruff check src tests` | zero findings |
| Format | `ruff format --check src tests` | zero reformats |
| Types | `mypy src` | zero errors |
| Security | `bandit -c pyproject.toml -r src` | reviewed skip list, no unreviewed finding |
| Live routes | boot `wsgi.py`, one GET per documented path | no 5xx, no undocumented guard |

CI runs the first six on Python 3.11, 3.12 and 3.13 on every push to `main`, plus a container build — [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Development

```sh
pip install -e ".[dev]"
python -m pytest -q                      # the suite
python -m pytest --cov                   # with the coverage floor
python -m ruff check src tests           # lint
python -m ruff format --check src tests  # formatting
python -m mypy src                       # types
python -m bandit -c pyproject.toml -r src  # security
pre-commit install                       # the same checks on commit
```

Dependabot opens grouped PRs for the dev tooling weekly and for actions and the base image monthly.

## Deploy

```sh
docker build -t loadforge .
docker run --rm -p 8000:8000 --env-file .env.example loadforge
```

A `docker-compose.yml` is included for a local run with a volume for the SQLite file. The image runs as a non-root user and serves through gunicorn.

## Limits, stated rather than hidden

- The engine targets one endpoint per run; multi-target fan-out is a scenario field, not a scheduler feature.
- Token counts are exact only when tiktoken is installed for the model family you test; otherwise they are estimated from text length and the run says so.

## License

MIT — see [LICENSE](LICENSE).
