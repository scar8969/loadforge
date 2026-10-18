"""Behaviour contracts for the pieces of gpt_load that ship but were unproven.

Each test here exists because a line of shipping code was reachable and
uncovered: the shared error envelope, the metric exposition branches, the
compatibility layer that lets this project keep its own operational endpoints,
the two log formatters, and the two fallbacks in the load generator. They assert
what a caller or an operator observes, not that a line ran.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import types

import pytest
from flask import Flask

from gpt_load import http, observability
from gpt_load.config import Settings
from gpt_load.errors import (
    AppError,
    BadRequest,
    Conflict,
    Forbidden,
    NotFound,
    PayloadTooLarge,
    RateLimited,
    ServiceUnavailable,
    Unauthorized,
    error_payload,
)
from gpt_load.http import Counter, render_metrics


def _settings(**overrides):
    base = {"APP_ENV": "test", "SECRET_KEY": "contract-test-secret"}
    base.update(overrides)
    return Settings.from_env(base)


# --------------------------------------------------------------------------- #
# errors.py -- the envelope every caller sees
# --------------------------------------------------------------------------- #


def test_app_error_defaults_the_message_to_the_class_docstring():
    generic = AppError()
    assert generic.message == "Base class for errors that are safe to show to a caller."
    assert generic.status_code == 500
    assert generic.code == "internal_error"
    assert str(generic) == generic.message


def test_app_error_to_dict_carries_details_only_when_they_were_supplied():
    bare = NotFound("no such run")
    assert bare.to_dict() == {"error": "not_found", "message": "no such run"}
    assert "details" not in bare.to_dict()

    detailed = Conflict("run already finished", run_id=7, state="done")
    assert detailed.to_dict() == {
        "error": "conflict",
        "message": "run already finished",
        "details": {"run_id": 7, "state": "done"},
    }


def test_every_error_subclass_keeps_its_status_code_and_machine_code():
    observed = [
        (cls.status_code, cls.code)
        for cls in (
            BadRequest,
            Unauthorized,
            Forbidden,
            NotFound,
            Conflict,
            PayloadTooLarge,
            RateLimited,
            ServiceUnavailable,
        )
    ]
    assert observed == [
        (400, "bad_request"),
        (401, "unauthorized"),
        (403, "forbidden"),
        (404, "not_found"),
        (409, "conflict"),
        (413, "payload_too_large"),
        (429, "rate_limited"),
        (503, "service_unavailable"),
    ]


def test_error_payload_helper_builds_the_same_envelope():
    assert error_payload("bad_request", "no") == {"error": "bad_request", "message": "no"}
    assert error_payload("not_found", "gone", run_id=3)["details"] == {"run_id": 3}


# --------------------------------------------------------------------------- #
# http.py -- counters and the Prometheus text format
# --------------------------------------------------------------------------- #


def test_counter_accumulates_snapshots_and_resets():
    counter = Counter()
    assert counter.snapshot() == []
    counter.inc("runs_total")
    counter.inc("runs_total", 2.0)
    counter.inc("latency_seconds_sum", 0.25, model="gpt-4o")
    snapshot = {
        (name, tuple(sorted(labels.items()))): value for name, labels, value in counter.snapshot()
    }
    assert snapshot[("runs_total", ())] == 3.0
    assert snapshot[("latency_seconds_sum", (("model", "gpt-4o"),))] == 0.25
    counter.reset()
    assert counter.snapshot() == []


def test_render_metrics_covers_labelled_and_unlabelled_counters():
    http.METRICS.inc("selftest_requests_total", method="GET", status="200")
    http.METRICS.inc("selftest_up")
    text = render_metrics()
    lines = text.splitlines()
    assert "# TYPE selftest_requests_total counter" in lines
    assert 'selftest_requests_total{method="GET",status="200"} 1' in lines
    assert "# TYPE selftest_up counter" in lines
    assert "selftest_up 1" in lines
    assert "# TYPE process_uptime_seconds gauge" in lines
    assert text.endswith(os.linesep if False else chr(10))


def test_settings_production_flag():
    assert _settings(APP_ENV="production").is_production is True
    assert _settings(APP_ENV="development").is_production is False


# --------------------------------------------------------------------------- #
# http.py -- the compatibility layer over paths this project already answers
# --------------------------------------------------------------------------- #


def _probe_app():
    probe = Flask("probe-" + str(id(object())))

    @probe.get("/version")
    def version():
        return {"legacy": True, "list": [1, 2]}

    @probe.get("/healthz")
    def healthz():
        return {"legacy_health": True}, 200

    @probe.get("/readyz")
    def readyz():
        return "the project own readiness page"

    return probe


def test_adopt_ops_paths_merges_into_the_views_the_project_already_owns():
    probe = _probe_app()
    settings = _settings()
    claimed = http.adopt_ops_paths(probe, settings, ())
    # Paths this project never answered are left for the blueprint to add.
    assert claimed == ["/healthz", "/readyz", "/version"]

    with probe.test_client() as probe_client:
        merged = probe_client.get("/version").get_json()
        assert merged["legacy"] is True and merged["list"] == [1, 2]
        assert merged["service"] == "gpt_load" and merged["version"]
        assert merged["config"]["secret_key_configured"] is True

        tuple_case = probe_client.get("/healthz").get_json()
        assert tuple_case["legacy_health"] is True and tuple_case["status"] == "ok"

        # A rendered page keeps the historical response verbatim.
        page = probe_client.get("/readyz")
        assert page.get_data(as_text=True) == "the project own readiness page"


def test_guard_ops_methods_refuses_writes_only_where_nothing_publishes_them():
    probe = Flask("guard-probe")

    @probe.route("/metrics", methods=["GET", "POST"])
    def metrics():
        return "metrics"

    added = http.guard_ops_methods(probe, ("/metrics", "/livez", "/already"))
    # /metrics already publishes POST, so only its remaining write verbs are
    # guarded; the other two paths have nothing published at all.
    assert added == ["/metrics", "/livez", "/already"]
    assert http.guard_ops_methods(probe, ("/livez",)) == []
    with probe.test_client() as probe_client:
        assert probe_client.post("/metrics").status_code == 200
        assert probe_client.put("/metrics").status_code == 405
        assert probe_client.put("/livez").status_code == 405
        assert probe_client.delete("/already").status_code == 405


def test_guard_ops_methods_skips_a_path_that_publishes_every_write_method():
    probe = Flask("guard-probe-all")

    @probe.route("/metrics", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def metrics():
        return "ok"

    assert http.guard_ops_methods(probe, ("/metrics",)) == []


def test_reject_ops_method_raises_a_read_only_method_not_allowed():
    from werkzeug.exceptions import MethodNotAllowed

    with pytest.raises(MethodNotAllowed) as caught:
        http._reject_ops_method()
    assert caught.value.valid_methods == ["GET"]


def test_install_observability_adds_hsts_only_in_production():
    probe = Flask("hsts-probe")
    http.install_observability(probe, _settings(APP_ENV="production"))
    with probe.test_client() as probe_client:
        response = probe_client.get("/nothing-here")
        assert response.headers["Strict-Transport-Security"].startswith("max-age=")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Request-ID"]


def test_teardown_logs_the_exception_that_escaped_a_view(capsys):
    probe = Flask("teardown-probe")
    http.install_observability(probe, _settings())
    probe.config["PROPAGATE_EXCEPTIONS"] = False

    @probe.get("/explodes")
    def explodes():
        raise RuntimeError("view blew up")

    with probe.test_client() as probe_client:
        assert probe_client.get("/explodes").status_code == 500
    assert "unhandled exception while serving" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# observability.py -- the two formatters and the lazy root handler
# --------------------------------------------------------------------------- #


def test_json_formatter_records_the_exception(capsys):
    observability.configure_logging("INFO", json_output=True)
    try:
        raise ValueError("structured failure")
    except ValueError:
        logging.getLogger("gpt_load.selftest").exception("boom")
    records = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]
    assert records[-1]["exception"].endswith("ValueError: structured failure")
    assert records[-1]["service"] == "gpt_load"
    assert records[-1]["request_id"]


def test_text_formatter_renders_the_exception(capsys):
    observability.configure_logging("INFO", json_output=False)
    try:
        raise RuntimeError("text failure")
    except RuntimeError:
        logging.getLogger("gpt_load.selftest").exception("kaboom")
    out = capsys.readouterr().out
    assert "level=error logger=gpt_load.selftest" in out
    assert "RuntimeError: text failure" in out


def test_configure_logging_reads_log_json_from_the_environment(capsys):
    os.environ["LOG_JSON"] = "0"
    try:
        observability.configure_logging("DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert isinstance(root.handlers[-1].formatter, observability._TextFormatter)

        os.environ["LOG_JSON"] = "yes"
        observability.configure_logging("not-a-level")
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert isinstance(root.handlers[-1].formatter, observability._JsonFormatter)
    finally:
        os.environ.pop("LOG_JSON", None)
        observability.configure_logging("INFO", json_output=True)
    capsys.readouterr()


def test_get_logger_configures_logging_on_first_use(monkeypatch):
    calls = []
    monkeypatch.setattr(observability, "_CONFIGURED", False)
    monkeypatch.setattr(observability, "configure_logging", lambda *a, **k: calls.append((a, k)))
    assert observability.get_logger("gpt_load.lazy").name == "gpt_load.lazy"
    assert calls == [((), {})]


# --------------------------------------------------------------------------- #
# the two load-generator fallbacks
# --------------------------------------------------------------------------- #


def test_tokenizer_falls_back_when_the_encoding_cannot_be_resolved(monkeypatch):
    from gpt_load.loadgen import tokenizer

    def explode(name):
        raise LookupError("no encoding for " + str(name))

    monkeypatch.setitem(sys.modules, "tiktoken", types.SimpleNamespace(encoding_for_model=explode))
    assert tokenizer.estimate_tokens("abcdefgh") == 2
    assert tokenizer.estimate_tokens("") == 1


def _bounded_sleep(slept, limit=3):
    """A sleep that records the pause and then ends the (otherwise endless) loop."""

    async def sleeper(seconds):
        slept.append(seconds)
        if len(slept) >= limit:
            raise RuntimeError("the bucket never became ready")

    return sleeper


def _frozen_bucket(monkeypatch, slept, limit=3):
    """A bucket whose clock never advances, so waiting never becomes waitingless."""
    from gpt_load.loadgen import ratelimit

    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: 1000.0)
    monkeypatch.setattr(asyncio, "sleep", _bounded_sleep(slept, limit))
    return ratelimit


def test_token_bucket_waits_when_the_per_minute_quota_is_spent(monkeypatch):
    slept = []
    ratelimit = _frozen_bucket(monkeypatch, slept)
    bucket = ratelimit.TokenBucket(rpm=1, tpm=1000)
    asyncio.run(bucket.acquire(5))
    assert slept == [], "the first request fits inside the quota"
    with pytest.raises(RuntimeError):
        asyncio.run(bucket.acquire(5))
    # Monotonic time is frozen, so the spent request never leaves the window.
    assert slept == [0.05, 0.05, 0.05]


def test_token_bucket_waits_when_the_token_budget_is_short(monkeypatch):
    slept = []
    ratelimit = _frozen_bucket(monkeypatch, slept)
    bucket = ratelimit.TokenBucket(rpm=100, tpm=10)
    with pytest.raises(RuntimeError):
        asyncio.run(bucket.acquire(50))
    assert slept == [0.05, 0.05, 0.05]


def test_token_bucket_refills_on_demand(monkeypatch):
    from gpt_load.loadgen import ratelimit

    bucket = ratelimit.TokenBucket(rpm=100, tpm=10)
    asyncio.run(bucket.acquire(4))
    bucket._tokens = 0.0
    bucket._last = 0.0
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: 3600.0)
    asyncio.run(bucket.acquire(10))
    assert bucket._tokens == 0.0
