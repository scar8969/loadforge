# Evidence

Every claim below comes from a command that was actually run against this
exact checkout. Nothing here is inferred from the source alone.

## Commands

```sh
# from the project directory, with _tools and _tools/_vendor on PYTHONPATH
python -m pytest -q -p hosttmp_proj tests/
python -m compileall -q src
```

## Recorded results

| check | result |
| --- | --- |
| compileall | exit 0 |
| mypy | Success: no issues found in 16 source files |
| pyflakes | 0 findings |
| pytest | 80 passed in 29.47s |
| pytest_exit_code | 0 |
| recorded_at | 2026-10-15 |
| routes_ok | 11 |
| routes_probed | 11 |

## HTTP surface

One real GET per rule in the assembled URL map, through Flask's test
client. `ok` includes 404 on a templated path: an empty database has
no such resource, and 404 is the honest answer for that.

| method | path | rule | status | bytes | note |
| --- | --- | --- | --- | --- | --- |
| GET | `/` | `/` | 200 | 8733 | ok |
| GET | `/api/health` | `/api/health` | 200 | 38 | ok |
| GET | `/api/runs` | `/api/runs` | 200 | 4664 | ok |
| GET | `/api/runs/demo/stream` | `/api/runs/<int:rid>/stream` | 404 | 51 | ok |
| GET | `/compare` | `/compare` | 200 | 6663 | ok |
| GET | `/healthz` | `/healthz` | 200 | 55 | ok |
| GET | `/history` | `/history` | 200 | 13174 | ok |
| GET | `/livez` | `/livez` | 200 | 19 | ok |
| GET | `/metrics` | `/metrics` | 200 | 305 | ok |
| GET | `/readyz` | `/readyz` | 200 | 31 | ok |
| GET | `/version` | `/version` | 200 | 881 | ok |

## Operational endpoints

`/healthz` answered **200**:

```
{"service":"gpt_load","status":"ok","version":"0.1.0"}
```

`/livez` answered **200**:

```
{"status":"alive"}
```

`/readyz` answered **200**:

```
{"checks":[],"status":"ready"}
```

`/metrics` answered **200**:

```
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200"} 5
# TYPE http_request_duration_seconds_sum counter
http_request_duration_seconds_sum{method="GET"} 0.0508526
http_requests_total{method="GET",status="404"} 1
# TYPE process_uptime_seconds gauge
process_uptime_seconds 0.952
```

`/version` answered **200**:

```
{"config":{"app_name":"gpt_load","data_dir":".\\var","database_configured":false,"debug":false,"env":"development","host":"0.0.0.0","legacy_env_present":[],"log_json":true,"log_level":"INFO","port":8000,"secret_key_configured":false},"paths":{"data_dir":".\\var","inst
```

## Headers observed on /healthz

| header | value |
| --- | --- |
| X-Request-ID | 28b45a70f030423fb0b029b3ca9e4402 |
| X-Content-Type-Options | nosniff |
| X-Frame-Options | DENY |
| Referrer-Policy | no-referrer |
| Cross-Origin-Opener-Policy | same-origin |
| Permissions-Policy | geolocation=(), microphone=(), camera=() |
| Content-Type | application/json |

## Static analysis

`python -m pyflakes src tests conftest.py wsgi.py` reported **0 finding(s)**:

```
(no output)
```

`python -m mypy --config-file mypy.ini src` said:

```
Success: no issues found in 16 source files
```

`ruff`, `bandit` and `pip-audit` are configured in this project but are absent from this host and cannot be installed without network access, so no result for them is recorded either way.

## What this file does not claim

- No screenshot in this file: the HTTP surface above is evidenced with recorded status codes and bodies instead.
  Headless screenshots of the same routes are committed under `docs/assets/screens/`, captured by the README pipeline rather than by this recorder.
- No network access: the suite is hermetic and contacts no remote host.
- No container run: the Dockerfile is reviewed, not executed, because no
  container runtime is reachable from this host.
