from .ratelimit import TokenBucket

import aiohttp, asyncio, json, time

class LoadEngine:
    def __init__(self, endpoint, model, api_key, concurrency, duration, rpm=1000, tpm=500000):
        self.endpoint, self.model, self.api_key = endpoint, model, api_key
        self.concurrency, self.duration = concurrency, duration
        self.bucket = TokenBucket(rpm, tpm)
        self.samples, self._stop = [], False

    async def run(self) -> None:
        t0 = time.monotonic()
        async with aiohttp.ClientSession() as sess:
            async with asyncio.TaskGroup() as tg:
                for i in range(self.concurrency):
                    tg.create_task(self._worker(sess, t0))

    async def _worker(self, sess, t0) -> None:
        payload = {"model": self.model, "messages": [{"role": "user", "content": "ping" * 25}], "max_tokens": 64}
        while not self._stop and time.monotonic() - t0 < self.duration:
            await self.bucket.acquire(200)
            s = time.perf_counter()
            try:
                async with sess.post(self.endpoint, json=payload,
                                     headers={"Authorization": f"Bearer {self.api_key}"},
                                     timeout=aiohttp.ClientTimeout(total=30)) as r:
                    data = await r.json()
                    status = 0 if r.status == 200 else 1
                    self.samples.append({"ts": time.monotonic() - t0,
                                         "latency_ms": (time.perf_counter() - s) * 1000,
                                         "status": status, "status_code": r.status,
                                         "tokens_in": 100, "tokens_out": len(data.get("choices", [{}])[0].get("message", {}).get("content", "")) // 4})
            except Exception:
                self.samples.append({"ts": time.monotonic() - t0,
                                     "latency_ms": (time.perf_counter() - s) * 1000,
                                     "status": 1, "status_code": 0, "tokens_in": 0, "tokens_out": 0})

    def stop(self) -> None:
        self._stop = True
