from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, Request
from starlette import status


class InMemoryRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = monotonic()
        window_start = now - self.window_seconds
        timestamps = self.requests[key]

        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de requetes. Reessayez plus tard.",
            )

        timestamps.append(now)


auth_limiter = InMemoryRateLimiter(max_requests=10, window_seconds=60)
chat_limiter = InMemoryRateLimiter(max_requests=20, window_seconds=60)
upload_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)


def _client_key(request: Request) -> str:
    if request.client:
        return request.client.host

    return "unknown"


def auth_rate_limit(request: Request) -> None:
    auth_limiter.check(_client_key(request))


def chat_rate_limit(request: Request) -> None:
    chat_limiter.check(_client_key(request))


def upload_rate_limit(request: Request) -> None:
    upload_limiter.check(_client_key(request))
