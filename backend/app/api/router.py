"""API router — wires all sub-routers and registers rate limiting."""
from __future__ import annotations

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.auth import router as auth_router
from app.api.calls import router as calls_router
from app.api.diagnostics import router as diagnostics_router
from app.api.eval import router as eval_router
from app.api.prompts import router as prompts_router

limiter = Limiter(key_func=get_remote_address)


def setup_routers(app: FastAPI) -> None:
    """Register all API routers and rate limiting on the FastAPI app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(auth_router)
    app.include_router(calls_router)
    app.include_router(prompts_router)
    app.include_router(diagnostics_router)
    app.include_router(eval_router)
