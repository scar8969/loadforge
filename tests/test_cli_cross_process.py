"""The repository front end is a real process, not an imported function.

The other suites import ``gpt_load.cli`` and call ``main()`` in-process. That
proves the argument parser works, but it cannot prove that the console entry
point reads a scenario file off disk, runs a real asyncio loop, and prints the
summary, because the same interpreter keeps its already-imported modules and
its already-adjusted ``sys.path``. This suite therefore starts a child process
for each case, exactly as ``gpt-load`` would be started by a shell, and reads
what that process wrote. ``report`` and ``compare`` are exercised the same way
against a throwaway SQLite database, which is the only way to prove that
``DATA_DIR`` is honoured at import time.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from gpt_load import paths

REPO_ROOT = paths.PROJECT_ROOT

SCENARIO = """endpoint: http://127.0.0.1:9/v1/chat/completions
model: gpt-4o
concurrency: 1
duration: 0
api_key: sk-cross-process
"""


def _child_env(tmp_path):
    """Environment for a child process that owns its own data directory."""
    env = os.environ.copy()
    # The package is imported from the source tree, and the interpreter path the
    # suite already runs with is kept: that is where the repository harness
    # exposes its vendored runtime dependencies.
    existing = [part for part in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if part]
    env["PYTHONPATH"] = os.pathsep.join(
        existing + [str(REPO_ROOT / "src"), str(REPO_ROOT)])
    env["DATA_DIR"] = str(tmp_path / "data")
    env["INSTANCE_DIR"] = str(tmp_path / "instance")
    env["TMP"] = env["TEMP"] = str(tmp_path / "tmp")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["SECRET_KEY"] = "cross-process-secret"
    env["APP_ENV"] = "test"
    for key in ("PYTEST_CURRENT_TEST", "COVERAGE_FILE"):
        env.pop(key, None)
    return env


def _child(tmp_path, *argv):
    """Run ``python -m gpt_load.cli`` in a fresh process and capture result."""
    for name in ("data", "instance", "tmp"):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, "-m", "gpt_load.cli", *argv],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, env=_child_env(tmp_path), cwd=str(tmp_path))


def test_module_entry_point_with_no_arguments_prints_help(tmp_path):
    done = _child(tmp_path)
    assert done.returncode == 1
    assert done.stdout.startswith("usage: gpt-load")
    for subcommand in ("run", "report", "compare"):
        assert subcommand in done.stdout


def test_run_subcommand_executes_a_scenario_in_a_child_process(tmp_path):
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text(SCENARIO, encoding="utf-8")
    done = _child(tmp_path, "run", str(scenario))
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.startswith("[gpt-load] rps=")
    assert "cost=$" in done.stdout


def test_run_subcommand_rejects_a_scenario_that_does_not_exist(tmp_path):
    done = _child(tmp_path, "run", str(tmp_path / "missing.yaml"))
    assert done.returncode != 0
    assert "missing.yaml" in done.stderr or "No such file" in done.stderr


def test_report_and_compare_round_trip_through_the_database(tmp_path):
    scenario = tmp_path / "scenario.yaml"
    scenario.write_text(SCENARIO, encoding="utf-8")
    first = _child(tmp_path, "run", str(scenario))
    second = _child(tmp_path, "run", str(scenario))
    assert first.returncode == 0 and second.returncode == 0

    reported = _child(tmp_path, "report", "--json", "--limit", "5")
    assert reported.returncode == 0, reported.stderr[-2000:]
    rows = json.loads(reported.stdout)
    assert [row["id"] for row in rows] == [2, 1]
    assert rows[0]["model"] == "gpt-4o"

    text_report = _child(tmp_path, "report", "--limit", "1")
    assert text_report.returncode == 0
    assert "#2" in text_report.stdout

    compared = _child(tmp_path, "compare", "1", "2")
    assert compared.returncode == 0, compared.stderr[-2000:]
    assert "metric" in compared.stdout and "delta" in compared.stdout


def test_compare_with_an_unknown_run_id_exits_with_code_two(tmp_path):
    done = _child(tmp_path, "compare", "1", "2")
    assert done.returncode == 2
    assert "must exist" in done.stderr


@pytest.mark.parametrize("name", ["config", "paths", "errors"])
def test_support_modules_import_cleanly_in_a_child_process(tmp_path, name):
    done = subprocess.run(
        [sys.executable, "-c", "import gpt_load.%s as m; print(m.__name__)" % name],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, env=_child_env(tmp_path), cwd=str(tmp_path))
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.strip() == "gpt_load." + name
