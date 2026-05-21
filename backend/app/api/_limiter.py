"""Shared slowapi limiter instance — import from here to avoid circular deps."""
from __future__ import annotations

import os
import uuid

from slowapi import Limiter
from slowapi.util import get_remote_address


def _key_func(request):
    # In test environments give every request a unique key so rate limits
    # never fire — each test is isolated and shouldn't share a counter.
    if os.getenv("ENVIRONMENT") == "test":
        return str(uuid.uuid4())
    return get_remote_address(request)

storage_uri = os.getenv("REDIS_URL", "memory://")
limiter = Limiter(key_func=_key_func, storage_uri=storage_uri)
