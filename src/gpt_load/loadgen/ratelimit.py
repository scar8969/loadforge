import asyncio
import time


class TokenBucket:
    """Sliding-window limiter for requests per minute and tokens per minute."""

    def __init__(self, rpm: int, tpm: int) -> None:
        self.rpm, self.tpm = rpm, tpm
        self._req_ts: list[float] = []
        self._tok_ts: list[float] = []
        self._tokens = float(tpm)

    async def acquire(self, n_tokens: int) -> None:
        while True:
            now = time.monotonic()
            self._req_ts = [t for t in self._req_ts if now - t < 60]
            self._tok_ts = [t for t in self._tok_ts if now - t < 60]
            if len(self._req_ts) >= self.rpm:
                await asyncio.sleep(0.05)
                continue
            if self._tokens < n_tokens:
                self._tokens = min(
                    self.tpm, self._tokens + self.tpm * (now - getattr(self, "_last", now)) / 60
                )
                if self._tokens < n_tokens:
                    await asyncio.sleep(0.05)
                    continue
            self._tokens -= n_tokens
            self._req_ts.append(now)
            self._last = now
            return

    def _refill(self) -> None:
        now = time.monotonic()
        last = getattr(self, "_last", now)
        self._tokens = min(float(self.tpm), self._tokens + self.tpm * (now - last) / 60.0)
        self._last = now
