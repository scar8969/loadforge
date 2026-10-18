"""A1 gpt-load — tests. Run: pytest test_loadforge.py"""

import json
import threading

# --- mock OpenAI server ---
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class MockOpenAI(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        body = json.dumps(
            {
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def mock_server():
    srv = HTTPServer(("127.0.0.1", 0), MockOpenAI)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1/chat/completions"
    srv.shutdown()


def test_tokenizer():
    from gpt_load.loadgen.tokenizer import estimate_tokens

    assert estimate_tokens("hello world") > 0


def test_engine_runs_and_collects(mock_server):
    from gpt_load.loadgen.engine import LoadEngine

    eng = LoadEngine(mock_server, "gpt-4o", "test-key", concurrency=4, duration=2)
    import asyncio

    asyncio.run(eng.run())
    assert len(eng.samples) > 0


def test_summarize_metrics():
    from gpt_load.loadgen.metrics import summarize

    samples = [
        {
            "ts": i,
            "latency_ms": 100 + i,
            "status": 0,
            "status_code": 200,
            "tokens_in": 10,
            "tokens_out": 5,
        }
        for i in range(100)
    ]
    s = summarize(samples)
    assert s["rps"] > 0 and s["p50"] > 0 and s["err_rate"] == 0


def test_summarize_empty():
    from gpt_load.loadgen.metrics import summarize

    assert summarize([])["rps"] == 0


def test_scenario_validation(tmp_path):
    from gpt_load.loadgen.scenarios import validate_scenario

    with pytest.raises(ValueError):
        validate_scenario({"model": "gpt-4o"})


def test_ratelimit_bucket():
    from gpt_load.loadgen.ratelimit import TokenBucket

    b = TokenBucket(rpm=5, tpm=100000)
    import asyncio

    async def go():
        for _ in range(3):
            await b.acquire(10)

    asyncio.run(go())
