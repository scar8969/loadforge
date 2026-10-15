"""Coverage for the command line, the load engine, and the legacy web layer.

Three parts of this toolkit are easy to leave untested because they are awkward
to reach from a pytest run: the argparse front end, the asyncio worker loop
(which talks to a real HTTP endpoint), and the older _app web layer that binds
its SQLite file at import time. Each is covered here with a substitute for the
only thing that would make the test non-hermetic - the network - and with the
real code path everywhere else.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
import time

import pytest

import aiohttp

from gpt_load.cli import main as cli_main
from gpt_load.loadgen import ratelimit
from gpt_load.loadgen.engine import LoadEngine
from gpt_load.loadgen.scenarios import load_scenario, validate_scenario
from gpt_load.loadgen.ratelimit import TokenBucket

SCENARIO = """endpoint: http://127.0.0.1:9/v1/chat/completions
model: gpt-4o
concurrency: 2
duration: 0.05
api_key: sk-not-a-real-key
"""


class _StubResponse:
    """Minimal stand-in for an aiohttp response."""

    def __init__(self, status=200, body=None):
        self.status = status
        self._body = body if body is not None else {
            "choices": [{"message": {"content": "ping" * 25}}]
        }

    async def json(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _StubSession:
    """Records each POST and replays a stub response."""

    def __init__(self, response):
        self.response = response
        self.posts = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        return self.response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _patch_session(monkeypatch, status=200):
    """Point aiohttp.ClientSession at a stub, returning that stub session."""
    session = _StubSession(_StubResponse(status=status))
    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: session)
    return session


def _fresh_web_layer(tmp_path, monkeypatch):
    """Import the legacy web layer against a throwaway database."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("INSTANCE_DIR", str(tmp_path / "instance"))
    for name in [m for m in list(sys.modules)
                 if m == "gpt_load" or m.startswith("gpt_load.")]:
        del sys.modules[name]
    return importlib.import_module("gpt_load._app")


def _wait_for_status(client, run_id, wanted=("done", "stopped", "failed"),
                     tries=120):
    """Poll the run list until the background thread has finalised the run."""
    for _ in range(tries):
        for row in client.get("/api/runs").get_json()["runs"]:
            if row["id"] == run_id and row["status"] in wanted:
                return row
        time.sleep(0.05)
    raise AssertionError("run %s never left 'running'" % run_id)


def test_cli_without_a_subcommand_prints_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["gpt-load"])
    assert cli_main() == 1
    out = capsys.readouterr().out
    assert "run" in out and "report" in out and "compare" in out


def test_cli_run_prints_a_summary_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "scn.yaml").write_text(SCENARIO, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["gpt-load", "run", "scn.yaml"])
    cli_main()
    out = capsys.readouterr().out
    assert "[gpt-load] rps=" in out
    assert "err=" in out and "cost=$" in out


def test_scenario_loader_reads_and_validates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ok.yaml").write_text(SCENARIO, encoding="utf-8")
    loaded = load_scenario("ok.yaml")
    assert loaded["model"] == "gpt-4o"
    assert loaded["concurrency"] == 2

    with pytest.raises(ValueError, match="scenario missing"):
        validate_scenario({"endpoint": "http://example.invalid"})


def test_worker_records_a_successful_sample(monkeypatch):
    session = _patch_session(monkeypatch)
    engine = LoadEngine(endpoint="http://stub.invalid/v1/chat/completions",
                        model="gpt-4o", api_key="sk-test", concurrency=1,
                        duration=0.05)
    asyncio.run(engine.run())
    assert engine.samples, "the worker loop recorded nothing"
    assert all(sample["status"] == 0 for sample in engine.samples)
    assert all(sample["status_code"] == 200 for sample in engine.samples)
    assert all(sample["tokens_in"] == 100 for sample in engine.samples)
    assert session.posts and session.posts[0][1]["json"]["model"] == "gpt-4o"
    assert session.posts[0][1]["headers"]["Authorization"] == "Bearer sk-test"


def test_worker_records_a_transport_failure(monkeypatch):
    _patch_session(monkeypatch, status=503)
    engine = LoadEngine("http://stub.invalid/v1", "gpt-4o", "", concurrency=1,
                        duration=0.05)
    asyncio.run(engine.run())
    assert engine.samples
    assert all(sample["status"] == 1 for sample in engine.samples)
    assert all(sample["status_code"] == 503 for sample in engine.samples)


def test_stop_ends_the_worker_loop(monkeypatch):
    _patch_session(monkeypatch)
    engine = LoadEngine("http://stub.invalid/v1", "gpt-4o", "", concurrency=1,
                        duration=30)
    engine.stop()
    assert engine._stop is True
    asyncio.run(engine.run())
    assert engine.samples == []


def test_token_bucket_spends_and_replenishes():
    bucket = TokenBucket(rpm=1000, tpm=10 ** 9)
    asyncio.run(bucket.acquire(10 ** 9))
    assert bucket._tokens == 0
    assert len(bucket._req_ts) == 1
    asyncio.run(bucket.acquire(1))
    assert len(bucket._req_ts) == 2
    before = bucket._tokens
    bucket._refill()
    assert bucket._tokens >= before


def test_token_bucket_suspends_when_the_request_budget_is_spent(monkeypatch):
    class _Suspended(Exception):
        pass

    calls = []

    async def fake_sleep(_seconds):
        calls.append(_seconds)
        if len(calls) >= 2:
            raise _Suspended

    monkeypatch.setattr(ratelimit.asyncio, "sleep", fake_sleep)
    bucket = TokenBucket(rpm=1, tpm=10 ** 9)
    asyncio.run(bucket.acquire(1))
    with pytest.raises(_Suspended):
        asyncio.run(bucket.acquire(1))
    assert calls and calls[0] == pytest.approx(0.05)


def test_legacy_run_api_lifecycle(tmp_path, monkeypatch):
    module = _fresh_web_layer(tmp_path, monkeypatch)
    app = module.build_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        created = client.post("/api/runs", json={
            "scenario": "basic", "endpoint": "http://127.0.0.1:9/v1",
            "model": "gpt-4o", "concurrency": 1, "duration": 0,
        })
        assert created.status_code == 200
        run_id = created.get_json()["run_id"]
        row = _wait_for_status(client, run_id)
        assert row["status"] == "done"
        assert "rps" in row["summary"]

        health = client.get("/api/health").get_json()
        assert health["runs"] >= 1

        streamed = client.get("/api/runs/%d/stream" % run_id, buffered=True)
        assert streamed.mimetype == "text/event-stream"
        assert "data: " in streamed.get_data(as_text=True)


        assert client.post("/api/runs/%d/stop" % run_id).get_json() == {
            "status": "stopped"}

        listing = client.get("/api/runs").get_json()["runs"]
        assert any(item["id"] == run_id for item in listing)

        removed = client.post("/runs/%d/delete" % run_id)
        assert removed.status_code == 302
        assert not any(item["id"] == run_id
                       for item in client.get("/api/runs").get_json()["runs"])


def test_legacy_html_pages_and_form_flow(tmp_path, monkeypatch):
    module = _fresh_web_layer(tmp_path, monkeypatch)
    app = module.build_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        index = client.get("/")
        assert index.status_code == 200
        assert b"gpt-load" in index.data

        for _ in range(2):
            started = client.post("/run", data={
                "scenario": "basic", "endpoint": "http://127.0.0.1:9/v1",
                "model": "gpt-4o", "concurrency": "1", "duration": "0",
                "rpm": "1000", "tpm": "500000",
            })
            assert started.status_code == 302
        # A non-numeric concurrency must fall back to the default, not raise.
        assert client.post("/run", data={
            "scenario": "basic", "endpoint": "http://127.0.0.1:9/v1",
            "model": "gpt-4o", "concurrency": "not-an-int", "duration": "0",
        }).status_code == 302

        ids = [item["id"]
               for item in client.get("/api/runs").get_json()["runs"]][:2]
        assert len(ids) == 2
        for run_id in ids:
            _wait_for_status(client, run_id)

        history = client.get("/history")
        assert history.status_code == 200

        compared = client.get("/compare?a=%d&b=%d" % (ids[0], ids[1]))
        assert compared.status_code == 200
        # A non-numeric id is ignored rather than fatal.
        assert client.get("/compare?a=x&b=y").status_code == 200

        assert client.post("/runs/%d/stop" % ids[0]).status_code == 302
        assert client.post("/runs/%d/delete" % ids[1]).status_code == 302
        assert client.get("/api/health").status_code == 200


def test_a_stream_for_a_missing_run_ends_instead_of_raising(client):
    """A row deleted while the stream was open must end it, not raise on None."""
    streamed = client.get("/api/runs/999999999/stream", buffered=True)

    assert streamed.mimetype == "text/event-stream"
    assert '"status": "missing"' in streamed.get_data(as_text=True)
