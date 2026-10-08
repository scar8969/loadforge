import statistics

MODEL_COSTS = {"gpt-4o": (2.50, 10.00), "gpt-4o-mini": (0.15, 0.60)}  # $/1M in/out

def summarize(samples: list) -> dict:
    if not samples:
        return {"rps": 0, "p50": 0, "p95": 0, "p99": 0, "err_rate": 0, "cost": 0, "tokens_in": 0, "tokens_out": 0}
    lats = sorted(s["latency_ms"] for s in samples)
    n = len(lats)
    errs = sum(1 for s in samples if s["status"] != 0)
    tin = sum(s["tokens_in"] for s in samples)
    tout = sum(s["tokens_out"] for s in samples)
    span = max(s["ts"] for s in samples) or 1
    cost = 0.0
    for s in samples:
        if s["status_code"] == 200:
            cost += (s["tokens_in"] / 1e6 * MODEL_COSTS.get("gpt-4o", (2.5, 10.0))[0]
                     + s["tokens_out"] / 1e6 * MODEL_COSTS.get("gpt-4o", (2.5, 10.0))[1])
    return {"rps": round(n / span, 1), "p50": round(statistics.median(lats), 1),
            "p95": round(lats[int(n * .95) - 1], 1), "p99": round(lats[int(n * .99) - 1], 1),
            "err_rate": round(errs / n * 100, 2), "cost": round(cost, 2),
            "tokens_in": tin, "tokens_out": tout}
