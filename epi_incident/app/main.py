from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import get_evidence, get_service
from app.api.evidence_routes import router as evidence_router
from app.api.routes import router
from app.api.worker_routes import router as worker_router
from app.api.ws import router as ws_router
from app.config import get_settings
from app.observability import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(_app):
        task = None
        if settings.evidence_dir:
            async def _purge_loop():
                while True:
                    try:
                        get_evidence().purge_expired(get_service().get, get_service().now())
                    except Exception:  # a limpeza nunca derruba o serviço
                        pass
                    await asyncio.sleep(settings.evidence_purge_interval_seconds)
            task = asyncio.create_task(_purge_loop())
        yield
        if task:
            task.cancel()

    app = FastAPI(title="EPI Vision — Fase 3.4: Incident Service", version="1.0.0", lifespan=lifespan)
    app.include_router(router, prefix=settings.api_prefix)
    app.include_router(evidence_router, prefix=settings.api_prefix)
    app.include_router(worker_router, prefix=settings.api_prefix)
    app.include_router(ws_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    def root_health():
        return {"status": "ok"}

    return app


app = create_app()
