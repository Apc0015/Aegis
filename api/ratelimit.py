"""
Minimal in-process, per-user sliding-window rate limiter.

Applied to the query endpoints — each query fans out to multiple paid LLM calls,
so an unthrottled user (or a runaway client loop) directly translates into cost
and latency for everyone. In-memory state means the limit is per-process; when
running multiple workers, front with a shared limiter (e.g. Redis) instead.
"""
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

RATE_LIMIT_PER_MINUTE = int(os.getenv("AEGIS_RATE_LIMIT_PER_MINUTE", "30"))
_WINDOW_SECONDS = 60.0

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)


def check_rate_limit(user_id: str) -> None:
    """Raise 429 if user_id exceeded RATE_LIMIT_PER_MINUTE in the last minute."""
    if RATE_LIMIT_PER_MINUTE <= 0:  # 0 disables limiting
        return
    now = time.monotonic()
    with _lock:
        dq = _hits[user_id]
        cutoff = now - _WINDOW_SECONDS
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= RATE_LIMIT_PER_MINUTE:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({RATE_LIMIT_PER_MINUTE} queries/minute). Try again shortly.",
                headers={"Retry-After": "60"},
            )
        dq.append(now)
