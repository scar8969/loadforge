"""Coverage for the CLI subcommands, the app factory and the legacy layers.

The three surfaces exercised here are the ones an ordinary run never reaches:
the ``report``/``compare`` subcommands (useful only once a real load test has
been recorded), the second branch of the application factory, and the failure
and non-numeric branches of the older ``_app`` web layer.

Contexts, not global state: the legacy application is a module-level singleton
whose SQLite file is bound at import time, so each test below works against a
private copy of ``gpt_load`` rooted at a throwaway ``DATA_DIR``. The ``isolated``
fixture puts the previous module objects back when the test ends, so the rest of
the suite keeps seeing the one application it started with.

The load engine and the network are the only substituted pieces; every other
line below is the production code path.
"""
from __future__ import annotations

import importlib
import json
import sys
import time
from types import SimpleNamespace

import pytest


def _drop_package():
    """Forget every gpt_load module, returning what was there before."""
    saved = {name: module for name, module in sys.modules.items()
             if name == "gpt_load" or name.startswith("gpt_load.")}
    for name in list(saved):
        del sys.modules[name]
    return saved


def _restore_package(saved):
    """Put the original module objects back and drop the private copies."""
    for name in [m for m in list(sys.modules)
                 if m == "gpt_load" or m.startswith("gpt_load.")]:
        del sys.modules[name]
    sys.modules.update(saved)


@pytest.fixture()
def isolated(tmp_path, monkeypatch):
    """A private, throwaway copy of the package; restored on teardown."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("INSTANCE_DIR", str(tmp_path / "instance"))
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "log"))
    saved = _drop_package()
    try:
        yield SimpleNamespace(
            config=importlib.import_module("gpt_load.config"),
            app=importlib.import_module("gpt_load.app"),
            web=importlib.import_module("gpt_load._app"),
            cli=importlib.import_module("gpt_load.cli"),
        )
    finally:
        _restore_package(saved)


#: Three runs with hand-written summaries, so the assertions below are about the
#: formatting code and not about whatever a load test happened to produce. The
#: third carries a metric that is not a number: the delta column must degrade.
RUNS = [
    {"scenario": "smoke", "endpoint": "http://127.0.0.1:9/v1", "model": "gpt-4o",
     "status": "done", "summary_json": json.dumps({"rps": 42.5, "p50": 12.0})},
    {"scenario": "burst", "endpoint": "http://127.0.0.1:9/v1", "model": "gpt-4o-mini",
     "status": "done", "summary_json": json.dumps({"rps": 31.25, "p50": 18.5})},
    {"scenario": "text-only", "endpoint": "", "model": "gpt-4o", "status": "stopped",
     "summary_json": json.dumps({"rps": 5.0, "note": "no numbers here"})},
]


def _seed(web, rows=None):
    """Insert the sample runs straight into the private database."""
    with web.app.app_context():
        for row in rows if rows is not None else RUNS:
            web.db.session.add(web.Run(**row))
        web.db.session.commit()


def _await_status(client, run_id, wanted=("done", "stopped", "failed"), tries=120):
    """Poll the run list until the background thread has finalised the run."""
    for _ in range(tries):
        for row in client.get("/api/runs").get_json()["runs"]:
            if row["id"] == run_id and row["status"] in wanted:
                return row
        time.sleep(0.05)
    raise AssertionError("run %s never left 'running'" % run_id)


def test_report_prints_stored_runs_newest_first(isolated, capsys):
    _seed(isolated.web)

    assert isolated.cli.cmd_report(SimpleNamespace(limit=20, json=False)) == 0
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert [line.split()[0] for line in lines] == ["#3", "#2", "#1"]
    assert lines[0].startswith("#3 text-only")
    assert "stopped" in lines[0]
    assert "no numbers here" in lines[0]

    # --limit is honoured by the query, not by slicing the output afterwards.
    assert isolated.cli.cmd_report(SimpleNamespace(limit=1, json=False)) == 0
    assert len(capsys.readouterr().out.splitlines()) == 1


def test_report_json_prints_the_decoded_summaries(isolated, capsys):
    _seed(isolated.web)

    assert isolated.cli.cmd_report(SimpleNamespace(limit=20, json=True)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [row["id"] for row in payload] == [3, 2, 1]
    assert payload[0] == {"id": 3, "scenario": "text-only", "model": "gpt-4o",
                          "status": "stopped",
                          "summary": {"rps": 5.0, "note": "no numbers here"}}


def test_compare_lines_up_two_runs_and_degrades_non_numeric_metrics(isolated, capsys):
    _seed(isolated.web)

    assert isolated.cli.cmd_compare(SimpleNamespace(run_a=1, run_b=2)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["metric", "#1", "#2", "delta"]
    assert [line.split()[0] for line in lines[1:]] == ["p50", "rps"]
    # 18.5 - 12.0 for p50, 31.25 - 42.5 for rps: two decimal places either way.
    assert lines[1].split()[-1] == "6.50"
    assert lines[2].split()[-1] == "-11.25"

    # A metric the left run never recorded counts as zero, so p50 moves by the
    # whole right-hand value; a metric that is not a number at all has no delta.
    assert isolated.cli.cmd_compare(SimpleNamespace(run_a=3, run_b=2)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines[1:]] == ["note", "p50", "rps"]
    assert lines[1].split()[-1] == "-"
    assert lines[2].split()[-1] == "18.50"
    assert lines[3].split()[-1] == "26.25"


def test_compare_refuses_a_run_id_that_does_not_exist(isolated, capsys):
    _seed(isolated.web)

    rc = isolated.cli.cmd_compare(SimpleNamespace(run_a=1, run_b=99))
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.err.strip() == "both run ids must exist"
    assert captured.out == ""


def test_main_dispatches_report_and_compare(isolated, monkeypatch, capsys):
    _seed(isolated.web)

    monkeypatch.setattr(sys, "argv", ["gpt-load", "report", "--limit", "1", "--json"])
    assert isolated.cli.main() == 0
    assert [row["id"] for row in json.loads(capsys.readouterr().out)] == [3]

    monkeypatch.setattr(sys, "argv", ["gpt-load", "compare", "1", "2"])
    assert isolated.cli.main() == 0
    assert capsys.readouterr().out.startswith("metric")

    monkeypatch.setattr(sys, "argv", ["gpt-load", "compare", "1", "404"])
    assert isolated.cli.main() == 2


def test_create_app_installs_the_cross_cutting_layers_exactly_once(isolated):
    explicit = isolated.web.paths.INSTANCE_DIR / "explicit.db"
    settings = isolated.config.Settings.from_env({
        "APP_ENV": "test",
        "SECRET_KEY": "unit-test-secret-key",
        "LOG_LEVEL": "INFO",
        "LOG_JSON": "1",
        # A supplied DATABASE_URL is the operator's explicit choice and has to
        # reach the legacy configuration instead of being dropped on the floor.
        "DATABASE_URL": "sqlite:///" + explicit.as_posix(),
        "MAX_CONTENT_LENGTH": "1048576",
    })

    app = isolated.app.create_app(settings)
    assert app.config["CROSS_CUTTING_INSTALLED"] is True
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///" + explicit.as_posix()
    assert app.config["MAX_CONTENT_LENGTH"] == 1048576

    with app.test_client() as client:
        for path in ("/healthz", "/livez", "/readyz", "/metrics", "/version"):
            assert client.get(path).status_code == 200, path
        # The operational endpoints are read-only.
        assert client.post("/metrics").status_code == 405

    # The legacy application object is a singleton, so a second factory call
    # must not try to install the cross-cutting layers again, and get_app()
    # has to hand back that very same WSGI object.
    assert isolated.app.create_app(settings) is app
    assert isolated.app.get_app() is app


def test_a_failing_engine_marks_the_run_failed(isolated, monkeypatch):
    web = isolated.web

    class _FailingEngine:
        """Stands in for a load engine whose endpoint cannot be reached."""

        def __init__(self, *args, **kwargs):
            self.samples = []

        async def run(self):
            raise RuntimeError("the endpoint refused the connection")

        def stop(self):
            return None

    monkeypatch.setattr(web, "LoadEngine", _FailingEngine)
    web.app.config.update(TESTING=True)
    with web.app.test_client() as client:
        created = client.post("/api/runs", json={
            "scenario": "unreachable", "endpoint": "http://stub.invalid/v1",
            "model": "gpt-4o", "concurrency": 1, "duration": 1,
        })
        assert created.status_code == 200
        row = _await_status(client, created.get_json()["run_id"], wanted=("failed",))
    assert row["status"] == "failed"
    assert row["finished_at"], "a failed run still records when it stopped"


def test_compare_page_tolerates_a_metric_that_is_not_a_number(isolated):
    web = isolated.web
    _seed(web, [
        {"scenario": "one", "endpoint": "", "model": "gpt-4o", "status": "done",
         "summary_json": json.dumps({"rps": 12.5, "p50": 30.0})},
        {"scenario": "two", "endpoint": "", "model": "gpt-4o", "status": "done",
         "summary_json": json.dumps({"rps": "not-a-number", "p50": 21.0})},
    ])

    web.app.config.update(TESTING=True)
    with web.app.test_client() as client:
        page = client.get("/compare?a=1&b=2")
        missing = client.get("/compare?a=404&b=2")
    body = page.get_data(as_text=True)
    assert page.status_code == 200
    # The stored value is shown verbatim; only the delta gives up.
    assert "not-a-number" in body
    assert "-9.0000" in body
    assert missing.status_code == 200
    assert "Choose a left and a right run" in missing.get_data(as_text=True)
