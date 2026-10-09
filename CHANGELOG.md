# Changelog

All notable changes to a1-gpt-load are documented here.

The format follows Keep a Changelog (https://keepachangelog.com/en/1.1.0/), and
this project adheres to Semantic Versioning
(https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Recorded quality-gate evidence, quoted verbatim in
  [docs/EVIDENCE.md](docs/EVIDENCE.md) and in the README: 73 tests passed
  with 0 failures and 0 errors in 143.82 s, and 97.8% statement coverage
  over 733 statements, alongside the exact commands that produced both.
- Dependency-free SVG charts of test, coverage, latency, payload, LOC and
  file-count data, generated from the recorded metrics document and
  committed so they render on the repository page.
- Headless screenshots of all eight read-only routes under
  `docs/assets/screens/`.

### Changed

- The coverage floor is now verified rather than assumed: 97.80% measured
  against the 85% `fail_under` gate configured in `pyproject.toml`.
- The README quality-gate table and the architecture tree are generated
  from measurements instead of described by hand.

## [0.1.0] - 2026-10-08

First release under the current packaging. This is the industry-baseline
release: the domain behaviour is the original skeleton's, and everything around
it is new.

### Added

- `src/` layout with an installable distribution and a typed, importable
  package (`pip install -e .`).
- `create_app()` application factory plus a compatibility `wsgi.py` shim.
- Environment-driven configuration parsed into a frozen `Settings` object and
  validated at startup with actionable errors.
- Structured JSON logging with per-request correlation ids.
- Operational endpoints: `/healthz`, `/livez`, `/readyz`, `/metrics`
  and `/version`.
- Security headers and a uniform JSON error envelope on every response.
- Hand-rolled Prometheus text exposition, with no `prometheus_client`
  dependency.
- Multi-stage Dockerfile running as an unprivileged user, with a healthcheck, a
  read-only root filesystem and dropped capabilities.
- `Makefile`, pre-commit configuration, ruff and mypy configuration, pytest
  with a coverage floor, and a GitHub Actions pipeline covering lint, type, test,
  security and container build.
- Documentation set: README, architecture, operations runbook, ADRs, security
  policy, contributing guide and this changelog.

### Changed

- Every historical flat import was rewritten to a package-relative import, so the
  modules can no longer be shadowed.
- Runtime state moved to `var/` (database, logs), outside the importable tree.

### Known limitations

- ruff, bandit and pip-audit are configured but were never executed: the
  generating sandbox had no network access. `pyflakes` and `mypy` served as
  the static checks that could run on this host.
- The coverage floor is configured here; it was measured in the following
  pass at 97.8%, above the 85% gate.
- No container image has been built.

[Unreleased]: https://example.invalid/gpt_load/compare/v0.1.0...HEAD
[0.1.0]: https://example.invalid/gpt_load/releases/tag/v0.1.0
