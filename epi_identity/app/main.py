from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import biometrics, employees, recognition
from app.config import get_settings
from app.database import init_db
from app.observability.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # Em produção, migrações são feitas via Alembic; init_db é conveniência de dev.
    if get_settings().environment != "production":
        await init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="EPI Vision — Módulo 1: Identificação Biométrica",
        version="1.0.0",
        lifespan=lifespan,
    )

    prefix = settings.api_prefix
    app.include_router(employees.router, prefix=prefix)
    app.include_router(biometrics.router, prefix=prefix)
    app.include_router(recognition.router, prefix=prefix)

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok", "provider": settings.face_provider}

    return app


app = create_app()
