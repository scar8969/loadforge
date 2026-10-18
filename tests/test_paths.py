"""The environment contract for the runtime directories.

A deployment may spell a directory either bare (``DATA_DIR``) or namespaced
(``GPT_LOAD_DATA_DIR``). The namespaced spelling only works when
``ENV_PREFIX`` ends in the separator, and it did not: ``_env_path`` builds the
name by concatenation, so the prefix used to produce the unreachable
``GPT_LOADDATA_DIR`` and the namespaced form was silently ignored. These tests
pin both spellings and their precedence.
"""

from __future__ import annotations

import pathlib

from gpt_load import paths


def test_the_prefix_ends_with_the_separator():
    assert paths.ENV_PREFIX == "GPT_LOAD_"


def test_a_namespaced_variable_is_honoured(monkeypatch, tmp_path):
    monkeypatch.setenv("GPT_LOAD_DATA_DIR", str(tmp_path / "namespaced"))
    assert paths._env_path("DATA_DIR", tmp_path / "fallback") == tmp_path / "namespaced"


def test_a_bare_variable_is_honoured(monkeypatch, tmp_path):
    monkeypatch.delenv("GPT_LOAD_DATA_DIR", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "bare"))
    assert paths._env_path("DATA_DIR", tmp_path / "fallback") == tmp_path / "bare"


def test_the_namespaced_variable_wins_over_the_bare_one(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "bare"))
    monkeypatch.setenv("GPT_LOAD_DATA_DIR", str(tmp_path / "namespaced"))
    assert paths._env_path("DATA_DIR", tmp_path / "fallback") == tmp_path / "namespaced"


def test_the_default_is_used_when_nothing_is_set(monkeypatch, tmp_path):
    monkeypatch.delenv("GPT_LOAD_DATA_DIR", raising=False)
    monkeypatch.delenv("DATA_DIR", raising=False)
    assert paths._env_path("DATA_DIR", tmp_path / "fallback") == tmp_path / "fallback"


def test_a_tilde_is_expanded(monkeypatch, tmp_path):
    monkeypatch.setenv("GPT_LOAD_LOG_DIR", "~/gpt-load-logs")
    assert paths._env_path("LOG_DIR", tmp_path) == pathlib.Path("~/gpt-load-logs").expanduser()
