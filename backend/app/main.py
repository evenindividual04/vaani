import logging
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.config import settings
from app.storage.database import init_db, engine
from app.storage.models import PromptVersion


def configure_logging() -> None:
    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.CallsiteParameterAdder(
            [structlog.processors.CallsiteParameter.FUNC_NAME]
        ),
    ]
    if settings.LOG_FORMAT == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


configure_logging()
log = structlog.get_logger()


async def seed_initial_prompt_version() -> None:
    from sqlalchemy import select
    from app.storage.database import AsyncSessionFactory

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(PromptVersion).where(PromptVersion.version_id == "v1")
        )
        if result.scalar_one_or_none() is not None:
            return

        v1 = PromptVersion(
            version_id="v1",
            description="Initial prompt version",
            templates={},
            created_at=datetime.utcnow(),
            is_active=True,
        )
        session.add(v1)
        await session.commit()
        log.info("seeded_prompt_version", version="v1")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed_initial_prompt_version()
    log.info("vaani_started", environment=settings.ENVIRONMENT)
    yield
    from app.channels.websocket_handler import live_manager
    await live_manager.close_all()
    await engine.dispose()
    log.info("vaani_shutdown")


app = FastAPI(title="Vaani FNOL API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# ── REST API routers ──────────────────────────────────────────────────────────
from app.api.router import setup_routers  # noqa: E402
setup_routers(app)

# ── WebSocket + Twilio channel handlers ───────────────────────────────────────
from app.channels.websocket_handler import router as ws_router  # noqa: E402
from app.channels.twilio_handler import router as twilio_router  # noqa: E402
from app.channels.whatsapp_handler import router as whatsapp_router  # noqa: E402
app.include_router(ws_router)
app.include_router(twilio_router)
app.include_router(whatsapp_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "environment": settings.ENVIRONMENT}
