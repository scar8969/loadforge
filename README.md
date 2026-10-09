# a1-gpt-load

[![python: 3.11 %7C 3.12 %7C 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab)](#requirements) [![tests: 73 passed](https://img.shields.io/badge/tests-73%20passed-2ea44f)](#quality-gates) [![coverage: 97.8%25](https://img.shields.io/badge/coverage-97.8%25-brightgreen)](#quality-gates) [![version: 0.1.0](https://img.shields.io/badge/version-0.1.0-0969da)](CHANGELOG.md) [![license: MIT](https://img.shields.io/badge/license-MIT-2ea44f)](LICENSE)

**a1-gpt-load** is a Flask service packaged the way a production service is packaged: a real package under `src/`, an environment-only configuration contract, structured JSON logs with request correlation, the five operational endpoints an orchestrator expects, a multi-stage container image, and CI gates that keep all of it honest.

This README is a measured document. Every number in it was produced on this exact checkout by the commands recorded in [docs/EVIDENCE.md](docs/EVIDENCE.md): **73 tests** run under pytest, **733 statements** traced by coverage, and **11 HTTP requests** issued over a real socket to the running server.

<table>
<tr>
<td align="center"><b>73 / 73</b><br><sub>tests passed</sub></td>
<td align="center"><b>97.8%</b><br><sub>line coverage</sub></td>
<td align="center"><b>1,472</b><br><sub>source lines</sub></td>
<td align="center"><b>11</b><br><sub>routes probed</sub></td>
<td align="center"><b>8</b><br><sub>screenshots</sub></td>
</tr>
</table>

---

## At a glance

| Signal | Measured value | How it was measured |
| --- | --- | --- |
| Tests passed | **73 / 73** | `python -m pytest -q` (exit code 0) |
| Test wall clock | 21.88 s | junit-xml suite time |
| Line coverage | **97.8%** | 729 of 733 statements executed, 4 missed |
| Source size | 1,472 lines / 16 modules | counted under `src/` |
| Test size | 1,239 lines / 8 files | counted under `tests/` |
| Documentation | 552 lines / 5 files | counted under `docs/` |
| Routes probed | 11 GET routes, 10 answered 200 | real HTTP against `127.0.0.1:<port>` |
| Total bytes served | 17.5 KB | 11 responses summed |
| Median response | 22.7 ms | median of 11 measured round trips |
| Screenshots | 8 captured | headless Chromium at 1440x900 |

The slowest measured route was **167.8 ms** (`/`) and the fastest **6.3 ms** (`/readyz`). Every figure is a single uncached first request against the development server, so the spread reflects cold template rendering and lazy imports rather than steady-state latency.

## Screenshots

Rendered from the running service with headless Chromium:

```sh
chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --user-data-dir=<dir> --virtual-time-budget=4000 \
  --window-size=1440,900 --screenshot=<png> <url>
```

The files are committed under `docs/assets/screens/`.

<table>
<tr>
<td width="50%"><img src="docs/assets/screens/root.png" alt="/" width="100%"><br><sub><code>/</code> &middot; 34.3 KB</sub></td>
<td width="50%"><img src="docs/assets/screens/compare.png" alt="/compare" width="100%"><br><sub><code>/compare</code> &middot; 21.4 KB</sub></td>
</tr>
</table>

<table>
<tr>
<td width="50%"><img src="docs/assets/screens/history.png" alt="/history" width="100%"><br><sub><code>/history</code> &middot; 21.3 KB</sub></td>
<td width="50%"><img src="docs/assets/screens/healthz.png" alt="/healthz" width="100%"><br><sub><code>/healthz</code> &middot; 8.3 KB</sub></td>
</tr>
</table>

<table>
<tr>
<td width="50%"><img src="docs/assets/screens/livez.png" alt="/livez" width="100%"><br><sub><code>/livez</code> &middot; 7.3 KB</sub></td>
<td width="50%"><img src="docs/assets/screens/metrics.png" alt="/metrics" width="100%"><br><sub><code>/metrics</code> &middot; 14.9 KB</sub></td>
</tr>
</table>

<table>
<tr>
<td width="50%"><img src="docs/assets/screens/readyz.png" alt="/readyz" width="100%"><br><sub><code>/readyz</code> &middot; 7.7 KB</sub></td>
<td width="50%"><img src="docs/assets/screens/version.png" alt="/version" width="100%"><br><sub><code>/version</code> &middot; 26.2 KB</sub></td>
</tr>
</table>

## Charts

Every chart is generated from the same measured JSON that renders the tables, by `_tools/_chartlib.py` - hand-written SVG with no plotting dependency - and committed so GitHub renders it without a build step.

![Line coverage](docs/assets/coverage.svg)

![Coverage by module](docs/assets/coverage-modules.svg)

![Test outcome](docs/assets/tests.svg)

![Response time per route](docs/assets/latency.svg)

![Response size per route](docs/assets/payload.svg)

![Repository size](docs/assets/loc.svg)

![File counts](docs/assets/files.svg)

## HTTP surface

Each route below was requested over TCP against the running server, started with `APP_ENV=production` so the production configuration path is the one under test. Static file routes are excluded: they are served by the WSGI container, not the application.

| # | Route | Status | Time | Bytes | Content type |
| --- | --- | --- | --- | --- | --- |
| 1 | `/` | **200** | 167.8 ms | 6,456 | text/html; charset=utf-8 |
| 2 | `/api/health` | **200** | 16.3 ms | 37 | application/json |
| 3 | `/api/runs` | **200** | 15.7 ms | 12 | application/json |
| 4 | `/api/runs/demo/stream` | **404** | 13.7 ms | 51 | application/json |
| 5 | `/compare` | **200** | 31.0 ms | 5,098 | text/html; charset=utf-8 |
| 6 | `/healthz` | **200** | 15.1 ms | 55 | application/json |
| 7 | `/history` | **200** | 41.3 ms | 4,926 | text/html; charset=utf-8 |
| 8 | `/livez` | **200** | 22.7 ms | 19 | application/json |
| 9 | `/metrics` | **200** | 29.9 ms | 304 | text/plain; version=0.0.4; charset=utf-8; charset=utf-8 |
| 10 | `/readyz` | **200** | 6.3 ms | 31 | application/json |
| 11 | `/version` | **200** | 24.1 ms | 904 | application/json |

Status distribution: **200** x10, **404** x1. No response was a 5xx.

### Declared API contract

`openapi/a1_gpt_load.yaml` declares **7 paths** carrying **8 operations** (3 GET, 5 POST):

| Method | Path |
| --- | --- |
| `GET` | `/api/health` |
| `GET` | `/api/runs` |
| `POST` | `/api/runs` |
| `GET` | `/api/runs/{id}/stream` |
| `POST` | `/api/runs/{id}/stop` |
| `POST` | `/run` |
| `POST` | `/runs/{id}/stop` |
| `POST` | `/runs/{id}/delete` |

### Headers on every response

| Header | Observed value |
| --- | --- |
| `X-Request-ID` | `b30f2746dba545a9be292c628d5d48bc` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Cross-Origin-Opener-Policy` | `same-origin` |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` |
| `Content-Type` | `application/json` |

## Architecture

LLM API load tester. `gpt-load` drives concurrent chat-completion traffic at an OpenAI-compatible endpoint from an asyncio worker pool, throttles it with a token bucket, and reports latency percentiles, error rate, and token cost.

```text
.dockerignore
.editorconfig
.env.example
.gitignore
.pre-commit-config.yaml
CHANGELOG.md
CODE_OF_CONDUCT.md
CONTRIBUTING.md
Dockerfile
LICENSE
Makefile
NOTES.md
README.md
SECURITY.md
conftest.py
docker-compose.yml
docker-entrypoint.sh
mypy.ini
pyproject.toml
requirements-dev.txt
requirements.txt
wsgi.py
.github/
  workflows/
    ci.yml
.tmp/
  .mypy/
    .gitignore
    CACHEDIR.TAG
    missing_stubs
docs/
  ARCHITECTURE.md
  EVIDENCE.md
  OPERATIONS.md
  adr/
    0001-src-layout-and-runtime-state.md
    0002-hand-rolled-metric-exposition.md
  assets/
    coverage-modules.svg
    coverage.svg
    files.svg
    latency.svg
    loc.svg
    payload.svg
    tests.svg
openapi/
  a1_gpt_load.yaml
schema/
  a1_gpt_load.sql
src/
  gpt_load/
    __init__.py
    _app.py
    app.py
    cli.py
    config.py
    errors.py
    http.py
    models.py
    observability.py
    paths.py
    py.typed
tests/
  conftest.py
  ...
```

Deeper material: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the module map and request lifecycle, [docs/OPERATIONS.md](docs/OPERATIONS.md) for running and configuring it, [docs/EVIDENCE.md](docs/EVIDENCE.md) for the raw recorded output this README quotes.

### Architecture decision records

| Record | Decision | Status |
| --- | --- | --- |
| [0001-src-layout-and-runtime-state.md](docs/adr/0001-src-layout-and-runtime-state.md) | 1. Adopt a src/ layout with an explicit runtime state directory | accepted |
| [0002-hand-rolled-metric-exposition.md](docs/adr/0002-hand-rolled-metric-exposition.md) | 2. Hand-roll metric exposition instead of depending on prometheus_client | accepted |

## Requirements

Configuration is environment-only, in the twelve-factor sense: nothing is read from a committed file, and `.env.example` is the complete list of what the process understands.

| Variable | Example value |
| --- | --- |
| `APP_ENV` | `development` |
| `SECRET_KEY` | `change-me-in-production` |
| `HOST` | `0.0.0.0` |
| `PORT` | `8000` |
| `DEBUG` | `false` |
| `MAX_CONTENT_LENGTH` | `8388608` |
| `DATA_DIR` | `(empty)` |
| `INSTANCE_DIR` | `(empty)` |
| `LOG_DIR` | `(empty)` |
| `LOG_LEVEL` | `INFO` |
| `LOG_JSON` | `true` |
| `REQUEST_ID_HEADER` | `X-Request-ID` |

## Quality gates

| Gate | Command | Result in this checkout |
| --- | --- | --- |
| Tests | `python -m pytest -q` | **73 passed, 0 failed, 0 errors** in 21.88 s |
| Coverage | `python -m pytest --cov=src/gpt_load` | **97.8%** of 733 statements (4 missed) |
| Lint | `python -m pyflakes src tests conftest.py wsgi.py` | **0 findings** in this checkout (pyflakes is the static checker available here; ruff cannot run on this host) |
| Types | `python -m mypy --config-file mypy.ini src` | **no issues found in 16 source files** in this checkout |
| Container | `docker build .` | Dockerfile reviewed, **not executed** - no container runtime on this host |

`make lint` and `make type` run the pinned `ruff` and `mypy` from the project virtualenv that `make install` creates; CI runs the same two tools. This host has no network access, so the `ruff` pinned in `requirements-dev.txt` could not be installed; the Lint row reports `pyflakes`, the checker that actually ran here, rather than a tool that never executed. Both static checks were run over the checkout and their raw output is stored in `docs/EVIDENCE.md`.

Coverage clears the **85%** floor declared in `pyproject.toml` (`fail_under`), so the same command that produced the number above also passes the gate.

### Test inventory

| File | def test_* | class Test* |
| --- | --- | --- |
| `tests/conftest.py` | 0 | 0 |
| `tests/test_a1_gpt_load.py` | 6 | 0 |
| `tests/test_cli_and_engine.py` | 10 | 0 |
| `tests/test_cli_cross_process.py` | 6 | 0 |
| `tests/test_config.py` | 9 | 0 |
| `tests/test_coverage_contracts.py` | 21 | 0 |
| `tests/test_line_coverage.py` | 8 | 0 |
| `tests/test_ops.py` | 11 | 0 |

### Make targets

| Target | What it does |
| --- | --- |
| `make help` | Show this help |
| `make install` | Create the virtualenv and install dev dependencies |
| `make fmt` | Auto-format (ruff is required; see requirements-dev.txt) |
| `make lint` | Lint without modifying anything |
| `make type` | Static type check |
| `make test` | Run the test suite |
| `make cov` | Run the test suite with coverage and enforce the floor |
| `make check` | The gate CI runs |
| `make run` | Start the development server |
| `make clean` | Remove caches and build artefacts |
| `make docker-build` | Build the container image |
| `make docker-run` | Run the container on port 8000 |

## Container image

| Property | Value |
| --- | --- |
| Build stages | 2 |
| Base images | `python:3.12-slim`, `python:3.12-slim` |
| COPY instructions | 4 |
| HEALTHCHECK | yes |
| Runs as non-root | yes |

`docker build` and `docker run` were **never executed** while this repository was produced: no container runtime is reachable from the generating host. The Dockerfile is a reviewed artefact, not a verified one.

## Continuous integration

| Workflow | Jobs | Steps | Commands |
| --- | --- | --- | --- |
| `ci.yml` | push, pull_request, workflow_dispatch, lint, test, security, container | 11 | | ; ruff check src tests ; ruff format --check src tests |

## Documentation index

| File | Contents |
| --- | --- |
| [README.md](README.md) | this file - the measured overview |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | module responsibilities, dependency direction, request lifecycle |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | how to run, configure, and operate the service |
| [docs/EVIDENCE.md](docs/EVIDENCE.md) | recorded command output - the raw source of every number here |
| [CONTRIBUTING.md](CONTRIBUTING.md) | setup and submission workflow |
| [SECURITY.md](SECURITY.md) | how to report a vulnerability |
| [CHANGELOG.md](CHANGELOG.md) | release history, Keep a Changelog form |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | community expectations |

## What this repository does not claim

- **No container run.** `docker build` was never executed.
- **No CI run.** The workflow files are real, but no GitHub runner has executed them from this checkout.
- **Static checks ran on this host, not the pinned toolchain.** `python -m pyflakes` and `python -m mypy` were executed here; `ruff` from the development requirements could not be installed on the generating host, so the lint gate named in `Makefile` is not the one that produced the numbers above.
- **No published artifact.** The package installs from this tree with `pip install -e .`; nothing was uploaded to an index.
- **Localhost only.** Every HTTP number was measured against `127.0.0.1` on the generating host, single-threaded, with no concurrency; treat them as smoke-test timings, not benchmarks.
- **No browser verification of content.** Screenshots were captured headlessly and checked structurally (valid PNG, expected dimensions, non-empty DOM); nobody has looked at them by eye in this session.

## License

MIT. See [LICENSE](LICENSE).
