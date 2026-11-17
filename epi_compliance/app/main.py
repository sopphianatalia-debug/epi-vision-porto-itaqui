from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="EPI Vision — Módulo 3: Verificação de Uso Correto",
        version="1.0.0",
    )
    app.include_router(router, prefix=settings.api_prefix)

    @app.get("/health", tags=["health"])
    def root_health():
        return {"status": "ok"}

    return app


app = create_app()
